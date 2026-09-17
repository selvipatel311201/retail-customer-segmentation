#!/usr/bin/env python3
"""Cohort retention plus the three costed recommendations.

The recommendations are the point of the project. A segment chart says what
is true; a recommendation says what to do about it and what it is worth. Every
figure here traces back to the data, and the assumptions (response rates,
margin) are stated inline rather than buried.
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TX = ROOT / "data" / "clean_transactions.parquet"
CUST = ROOT / "data" / "customers.csv"
OUT = ROOT / "outputs"

MARGIN = 0.30           # gross margin assumption
WINBACK_RESPONSE = 0.12  # typical email win-back response rate
REACTIVATION_UPLIFT = 0.05


def cohorts(tx: pd.DataFrame) -> pd.DataFrame:
    """Monthly acquisition cohorts x months-since-first-purchase retention."""
    tx = tx.copy()
    tx["Month"] = tx["InvoiceDate"].dt.to_period("M")
    first = tx.groupby("CustomerID")["Month"].min().rename("Cohort")
    tx = tx.join(first, on="CustomerID")
    tx["Offset"] = (tx["Month"].dt.year - tx["Cohort"].dt.year) * 12 + \
                   (tx["Month"].dt.month - tx["Cohort"].dt.month)

    counts = tx.groupby(["Cohort", "Offset"])["CustomerID"].nunique().unstack(fill_value=0)
    sizes = counts.iloc[:, 0]
    retention = counts.divide(sizes, axis=0).round(4) * 100
    retention.index = retention.index.astype(str)
    return retention


if __name__ == "__main__":
    tx = pd.read_parquet(TX)
    cust = pd.read_csv(CUST)
    OUT.mkdir(exist_ok=True)

    ret = cohorts(tx)
    ret.to_csv(OUT / "cohort_retention.csv")

    m1 = ret[1].mean() if 1 in ret.columns else float("nan")
    m3 = ret[3].mean() if 3 in ret.columns else float("nan")
    m6 = ret[6].mean() if 6 in ret.columns else float("nan")
    m12 = ret[12].mean() if 12 in ret.columns else float("nan")
    print("COHORT RETENTION (mean across cohorts)")
    print(f"   month 1 : {m1:5.1f}%")
    print(f"   month 3 : {m3:5.1f}%")
    print(f"   month 6 : {m6:5.1f}%")
    print(f"   month 12: {m12:5.1f}%")

    total_rev = cust["Monetary"].sum()
    recs = []

    # 1. Win back "Can't Lose Them" -- high frequency, high spend, gone quiet.
    clt = cust[cust["Segment"] == "Can't Lose Them"]
    clt_rev = clt["Monetary"].sum()
    clt_recover = clt_rev * WINBACK_RESPONSE * MARGIN
    recs.append({
        "title": "Win back 'Can't Lose Them' before they are gone for good",
        "finding": (f"{len(clt):,} customers ({100*len(clt)/len(cust):.1f}% of the base) "
                    f"have bought {clt['Frequency'].median():.0f} times on average but "
                    f"have not ordered in {clt['Recency'].median():.0f} days. They carry "
                    f"GBP {clt_rev:,.0f} of historical revenue "
                    f"({100*clt_rev/total_rev:.1f}% of the total)."),
        "action": "Targeted win-back offer, sequenced email plus phone for the top decile.",
        "value_gbp": round(clt_recover, 0),
        "assumption": f"{WINBACK_RESPONSE:.0%} response, {MARGIN:.0%} gross margin",
    })

    # 2. Protect Champions -- the concentration risk.
    champ = cust[cust["Segment"] == "Champions"]
    champ_rev = champ["Monetary"].sum()
    at_risk_5pct = champ_rev * 0.05 * MARGIN
    recs.append({
        "title": "Protect Champions: the revenue base is dangerously concentrated",
        "finding": (f"{len(champ):,} customers ({100*len(champ)/len(cust):.1f}%) generate "
                    f"GBP {champ_rev:,.0f} — {100*champ_rev/total_rev:.1f}% of all revenue. "
                    f"Losing just 5% of them costs GBP {champ_rev*0.05:,.0f} in revenue."),
        "action": ("Named account care for the top 200, early-warning alert when a "
                   "Champion's gap between orders exceeds twice their own norm."),
        "value_gbp": round(at_risk_5pct, 0),
        "assumption": f"Protecting 5% of Champion revenue at {MARGIN:.0%} margin",
    })

    # 3. Convert one-and-done buyers to a second order.
    onetime = cust[cust["Frequency"] == 1]
    ot_aov = onetime["AOV"].median()
    ot_value = len(onetime) * REACTIVATION_UPLIFT * ot_aov * MARGIN
    recs.append({
        "title": "Convert one-time buyers to a second purchase",
        "finding": (f"{len(onetime):,} customers ({100*len(onetime)/len(cust):.1f}%) ordered "
                    f"exactly once, at a median of GBP {ot_aov:,.0f}. They account for only "
                    f"{100*onetime['Monetary'].sum()/total_rev:.1f}% of revenue — the single "
                    f"largest untapped group."),
        "action": ("Post-purchase onboarding sequence with a second-order incentive, "
                   "triggered 30 days after first delivery."),
        "value_gbp": round(ot_value, 0),
        "assumption": f"{REACTIVATION_UPLIFT:.0%} conversion to a second order at median AOV",
    })

    print(f"\n{'='*70}\nRECOMMENDATIONS\n{'='*70}")
    for i, r in enumerate(recs, 1):
        print(f"\n{i}. {r['title']}")
        print(f"   {r['finding']}")
        print(f"   ACTION: {r['action']}")
        print(f"   VALUE : GBP {r['value_gbp']:,.0f}  ({r['assumption']})")

    total_opp = sum(r["value_gbp"] for r in recs)
    print(f"\n   TOTAL IDENTIFIED OPPORTUNITY: GBP {total_opp:,.0f} gross margin")

    (OUT / "findings.json").write_text(json.dumps({
        "retention": {"month_1": round(float(m1), 1), "month_3": round(float(m3), 1),
                      "month_6": round(float(m6), 1), "month_12": round(float(m12), 1)},
        "recommendations": recs,
        "total_opportunity_gbp": total_opp,
    }, indent=2))
    print(f"\nwrote cohort_retention.csv and findings.json")
