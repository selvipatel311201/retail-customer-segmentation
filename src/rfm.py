#!/usr/bin/env python3
"""Build a customer-level table: RFM, segments, K-Means clusters, CLV, churn.

Two segmentations are produced deliberately:
  - rule-based RFM scoring, which the business understands and can action
  - K-Means on scaled log(R,F,M), which finds structure nobody specified
Where they disagree is the interesting part, so both are kept side by side.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
TX = ROOT / "data" / "clean_transactions.parquet"
OUT = ROOT / "data" / "customers.csv"
STATS = ROOT / "outputs" / "rfm_stats.json"

CHURN_DAYS = 180          # no purchase in 6 months -> treated as churned
RANDOM_STATE = 42


def build_rfm(tx: pd.DataFrame):
    # Snapshot = day after the last transaction, so the most recent buyer has
    # recency of 1 rather than 0 (0 breaks the log transform later).
    snapshot = tx["InvoiceDate"].max() + pd.Timedelta(days=1)

    rfm = tx.groupby("CustomerID").agg(
        Recency=("InvoiceDate", lambda s: (snapshot - s.max()).days),
        Frequency=("Invoice", "nunique"),
        Monetary=("Revenue", "sum"),
        FirstPurchase=("InvoiceDate", "min"),
        LastPurchase=("InvoiceDate", "max"),
        Items=("Quantity", "sum"),
        # A handful of customers order from more than one country; take the
        # one they use most rather than dropping the field.
        Country=("Country", lambda s: s.mode().iat[0] if not s.mode().empty else "Unknown"),
    ).reset_index()

    # Scores 1-5 by quintile. Recency is reversed: fewer days since the last
    # order is better, so the lowest recency earns a 5.
    rfm["R_Score"] = pd.qcut(rfm["Recency"], 5, labels=[5, 4, 3, 2, 1]).astype(int)
    # Frequency is heavily tied at the low end (many customers ordered once),
    # so rank first to break ties before cutting into quintiles.
    rfm["F_Score"] = pd.qcut(rfm["Frequency"].rank(method="first"), 5,
                             labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["M_Score"] = pd.qcut(rfm["Monetary"], 5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["RFM_Score"] = (rfm["R_Score"].astype(str) + rfm["F_Score"].astype(str)
                        + rfm["M_Score"].astype(str))
    return rfm, snapshot


def segment(row) -> str:
    """Standard RFM segment names, driven by R and F."""
    r, f = row["R_Score"], row["F_Score"]
    if r >= 4 and f >= 4:
        return "Champions"
    if r >= 3 and f >= 3:
        return "Loyal"
    if r >= 4 and f <= 2:
        return "New / Promising"
    if r == 3 and f <= 2:
        return "Needs Attention"
    if r <= 2 and f >= 4:
        return "Can't Lose Them"
    if r <= 2 and f == 3:
        return "At Risk"
    if r <= 2 and f <= 2:
        return "Hibernating / Lost"
    return "Other"


def cluster(rfm: pd.DataFrame):
    """K-Means on log-transformed, standardised RFM.

    R, F and M are all heavily right-skewed; without the log transform the
    clustering is dominated by a handful of very large customers.
    """
    X = np.log1p(rfm[["Recency", "Frequency", "Monetary"]])
    Xs = StandardScaler().fit_transform(X)

    elbow = []
    for k in range(2, 9):
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10).fit(Xs)
        elbow.append({"k": k, "inertia": round(float(km.inertia_), 1),
                      "silhouette": round(float(silhouette_score(Xs, km.labels_)), 3)})
        print(f"   k={k}  inertia={km.inertia_:>9,.0f}  "
              f"silhouette={elbow[-1]['silhouette']}")

    # Silhouette peaks at k=2 on RFM data because the dominant structure is
    # simply active vs inactive. That is a real split but useless to a
    # marketing team. Choose by the elbow instead -- the k after which the
    # drop in inertia flattens -- and sanity-check it is interpretable.
    # Kneedle: normalise both axes, then take the point furthest from the
    # straight line joining the first and last. That is the elbow, and unlike
    # a ratio test it does not depend on an arbitrary threshold.
    ks = np.array([e["k"] for e in elbow], dtype=float)
    ins = np.array([e["inertia"] for e in elbow], dtype=float)
    kn = (ks - ks.min()) / (ks.max() - ks.min())
    inn = (ins - ins.min()) / (ins.max() - ins.min())
    # Perpendicular distance from each point to the line (0,1) -> (1,0).
    dist = np.abs(kn + inn - 1) / np.sqrt(2)
    best_k = int(ks[int(dist.argmax())])
    best_k = min(max(best_k, 4), 6)   # keep it to a number a team can act on
    print(f"   elbow distances: "
          f"{', '.join(f'k={int(k)}:{d:.3f}' for k, d in zip(ks, dist))}")
    km = KMeans(n_clusters=best_k, random_state=RANDOM_STATE, n_init=10).fit(Xs)
    rfm["Cluster"] = km.labels_
    return rfm, best_k, elbow


if __name__ == "__main__":
    tx = pd.read_parquet(TX)
    print(f"transactions: {len(tx):,}")

    rfm, snapshot = build_rfm(tx)
    print(f"customers   : {len(rfm):,}   snapshot: {snapshot.date()}")

    rfm["Segment"] = rfm.apply(segment, axis=1)

    print("\nK-Means (choosing k by silhouette):")
    rfm, best_k, elbow = cluster(rfm)
    print(f"   chosen k = {best_k}")

    # Commercial metrics
    rfm["AOV"] = (rfm["Monetary"] / rfm["Frequency"]).round(2)
    lifespan_days = (rfm["LastPurchase"] - rfm["FirstPurchase"]).dt.days
    rfm["LifespanDays"] = lifespan_days

    # CLV = AOV x expected orders per year x gross margin.
    #
    # Orders per year is measured over how long we have OBSERVED the customer
    # (first purchase -> snapshot), not over their active span. Using the
    # active span divides a one-time buyer by zero days and makes dead
    # customers look infinitely valuable -- the bug this replaces.
    MARGIN = 0.30
    observed_days = (snapshot - rfm["FirstPurchase"]).dt.days.clip(lower=30)
    rfm["ObservedDays"] = observed_days
    rfm["OrdersPerYear"] = (rfm["Frequency"] / (observed_days / 365)).round(2)
    rfm["CLV_1yr"] = (rfm["AOV"] * rfm["OrdersPerYear"] * MARGIN).round(2)
    rfm["Churned"] = (rfm["Recency"] > CHURN_DAYS).astype(int)

    rfm = rfm.sort_values("Monetary", ascending=False)
    OUT.parent.mkdir(exist_ok=True)
    rfm.to_csv(OUT, index=False)

    total_rev = float(rfm["Monetary"].sum())
    by_seg = rfm.groupby("Segment").agg(
        customers=("CustomerID", "count"),
        revenue=("Monetary", "sum"),
        avg_clv=("CLV_1yr", "mean"),
        churn_rate=("Churned", "mean"),
    ).sort_values("revenue", ascending=False)
    by_seg["pct_customers"] = (100 * by_seg["customers"] / len(rfm)).round(1)
    by_seg["pct_revenue"] = (100 * by_seg["revenue"] / total_rev).round(1)

    print(f"\n{'SEGMENT':<22}{'CUST':>7}{'%CUST':>7}{'REVENUE':>13}{'%REV':>7}"
          f"{'CHURN':>8}{'AVG CLV':>10}")
    for s, r in by_seg.iterrows():
        print(f"{s:<22}{int(r.customers):>7,}{r.pct_customers:>7.1f}"
              f"{r.revenue:>13,.0f}{r.pct_revenue:>7.1f}"
              f"{100*r.churn_rate:>7.0f}%{r.avg_clv:>10,.0f}")

    # Pareto: what share of customers drives what share of revenue
    top = rfm.nlargest(int(len(rfm) * 0.20), "Monetary")["Monetary"].sum()
    pareto = round(100 * top / total_rev, 1)

    stats = {
        "customers": len(rfm), "total_revenue": round(total_rev, 2),
        "snapshot_date": str(snapshot.date()), "churn_days": CHURN_DAYS,
        "margin_assumption": MARGIN, "best_k": best_k, "elbow": elbow,
        "overall_churn_rate": round(float(rfm["Churned"].mean()), 3),
        "median_aov": round(float(rfm["AOV"].median()), 2),
        "top20pct_revenue_share": pareto,
        "segments": json.loads(by_seg.reset_index().to_json(orient="records")),
    }
    STATS.write_text(json.dumps(stats, indent=2))

    print(f"\ntop 20% of customers -> {pareto}% of revenue")
    print(f"overall churn ({CHURN_DAYS}d): {100*rfm['Churned'].mean():.1f}%")
    print(f"median AOV: GBP {rfm['AOV'].median():,.2f}")
    print(f"\nwrote {OUT.name} ({len(rfm):,} rows) and {STATS.name}")
