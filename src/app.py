"""Streamlit explorer for the customer segmentation.

Deploy: push to GitHub, then connect the repo at share.streamlit.io.
Run locally: streamlit run src/app.py
"""

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(page_title="Retail Customer Segmentation",
                   page_icon="📊", layout="wide")


@st.cache_data
def load():
    cust = pd.read_csv(ROOT / "data" / "customers.csv")
    ret = pd.read_csv(ROOT / "outputs" / "cohort_retention.csv", index_col=0)
    return cust, ret


cust, retention = load()

st.title("Retail Customer Segmentation & Lifetime Value")
st.caption("Online Retail II — 776,827 cleaned transactions, 5,853 customers, "
           "Dec 2009 – Dec 2011. Built by Selvi Patel · selvipatel.com")

# ---- headline numbers -------------------------------------------------
total_rev = cust["Monetary"].sum()
top20 = cust.nlargest(int(len(cust) * 0.2), "Monetary")["Monetary"].sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Customers", f"{len(cust):,}")
c2.metric("Revenue", f"£{total_rev/1e6:.1f}M")
c3.metric("Top 20% drive", f"{100*top20/total_rev:.0f}% of revenue")
c4.metric("Churn rate (180d)", f"{100*cust['Churned'].mean():.0f}%")

st.divider()

# ---- filters ----------------------------------------------------------
segments = sorted(cust["Segment"].unique())
picked = st.multiselect("Filter by segment", segments, default=segments)
view = cust[cust["Segment"].isin(picked)]

# ---- segment economics ------------------------------------------------
st.subheader("Segment economics")
seg = view.groupby("Segment").agg(
    Customers=("CustomerID", "count"),
    Revenue=("Monetary", "sum"),
    Median_AOV=("AOV", "median"),
    Median_CLV=("CLV_1yr", "median"),
    Churn=("Churned", "mean"),
).sort_values("Revenue", ascending=False)
seg["% of revenue"] = (100 * seg["Revenue"] / total_rev).round(1)
seg["Churn"] = (100 * seg["Churn"]).round(0)

left, right = st.columns([3, 2])
with left:
    st.dataframe(
        seg.style.format({"Customers": "{:,}", "Revenue": "£{:,.0f}",
                          "Median_AOV": "£{:,.0f}", "Median_CLV": "£{:,.0f}",
                          "Churn": "{:.0f}%", "% of revenue": "{:.1f}%"}),
        use_container_width=True)
with right:
    st.bar_chart(seg["Revenue"], height=300)

st.divider()

# ---- RFM scatter ------------------------------------------------------
st.subheader("Recency vs Monetary, by K-Means cluster")
st.caption("Log scale. Clusters were found on scaled log(R, F, M) with k chosen "
           "by the elbow method — not by silhouette, which collapses to k=2 here.")
plot = view[["Recency", "Monetary", "Frequency", "Cluster"]].copy()
plot = plot[plot["Monetary"] > 0]
st.scatter_chart(plot, x="Recency", y="Monetary", color="Cluster",
                 size="Frequency", height=420)

st.divider()

# ---- retention --------------------------------------------------------
st.subheader("Cohort retention (% of each month's new customers still active)")
st.dataframe(retention.style.format("{:.0f}").background_gradient(cmap="Blues"),
             use_container_width=True)

st.divider()

# ---- at-risk table ----------------------------------------------------
st.subheader("Highest-value customers at risk")
st.caption("Bought often, spent heavily, and have gone quiet. This is the "
           "win-back list.")
at_risk = (view[view["Segment"].isin(["Can't Lose Them", "At Risk"])]
           .nlargest(25, "Monetary")
           [["CustomerID", "Segment", "Recency", "Frequency", "Monetary",
             "AOV", "CLV_1yr", "Country"]])
st.dataframe(
    at_risk.style.format({"Monetary": "£{:,.0f}", "AOV": "£{:,.0f}",
                          "CLV_1yr": "£{:,.0f}"}),
    use_container_width=True, hide_index=True)
