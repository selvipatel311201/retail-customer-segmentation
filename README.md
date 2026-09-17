# Retail Customer Segmentation & Lifetime Value

Segmentation, churn and CLV analysis over **776,827 cleaned retail transactions**
from 5,853 customers (Online Retail II, Dec 2009 – Dec 2011).

**Selvi Patel** · [selvipatel.com](https://selvipatel.com)

---

## Headline findings

| | |
|---|---|
| **20% of customers generate 77.2% of revenue** | Severe concentration risk |
| 1,476 Champions (25.2% of base) | **69.2% of all revenue** |
| Overall churn (no order in 180 days) | **40.7%** |
| Month-12 cohort retention | **9.5%** (from 20.1% at month 1) |
| Median average order value | **£277.94** |
| Identified margin opportunity | **£220,191** |

---

## Pipeline

```
online_retail_II.xlsx          1,067,371 raw rows
        │
        ▼  src/clean.py        every drop counted and justified
clean_transactions.parquet       776,827 rows  (27.2% dropped)
        │
        ▼  src/rfm.py          RFM scoring + K-Means + CLV + churn
customers.csv                      5,853 rows  ← load this into Power BI
        │
        ▼  src/findings.py     cohort retention + costed recommendations
cohort_retention.csv, findings.json
        │
        ▼  src/app.py          Streamlit explorer
```

## What was cleaned, and why it matters

| Dropped | Rows | Reason |
|---|---|---|
| No CustomerID | 243,007 | Guest checkouts — real sales, but unattributable to a customer |
| Cancelled invoices | 18,744 | Invoice prefixed `C` |
| Non-positive price | 71 | Free items and adjustments |
| Non-product lines | 2,662 | Postage, bank charges, manual entries |
| Exact duplicates | 26,060 | Byte-identical rows |

**This introduces a known bias.** Guest checkouts skew toward one-time buyers,
so dropping them over-represents repeat customers in every segment below. That
is a limitation of the analysis, not a detail — it is stated rather than hidden.

## Method notes

**RFM scoring.** Recency, Frequency and Monetary per customer, each scored 1–5
by quintile. Recency is reversed (fewer days since last order = better).
Frequency is rank-transformed before cutting, because the low end is heavily
tied — 1,619 customers ordered exactly once.

**K-Means.** Run on `log1p(R, F, M)` then standardised, because all three are
strongly right-skewed and raw values let a handful of very large customers
dominate the clustering.

**Choosing k.** Silhouette peaks at k=2 (score 0.438), but that split is just
active vs inactive — true, and useless to a marketing team. k was chosen by the
elbow instead, using perpendicular distance from the line joining the endpoints,
giving **k=4**.

**CLV.** `AOV × orders-per-year × 30% gross margin`, where orders-per-year is
measured over how long the customer has been *observed* (first purchase →
snapshot), not over their active span. Using the active span divides one-time
buyers by zero days and makes lapsed customers appear infinitely valuable.

## K-Means clusters

| Cluster | Customers | Median recency | Median orders | Median spend | Churn | Share of revenue |
|---|---|---|---|---|---|---|
| 0 — VIPs | 1,179 | 16 days | 13 | £4,910 | 0% | **73.3%** |
| 1 — Lapsing regulars | 1,456 | 183 days | 5 | £1,460 | 50% | 16.9% |
| 2 — Active light buyers | 1,246 | 24 days | 3 | £720 | 0% | 6.1% |
| 3 — One-and-done | 1,972 | 401 days | 1 | £278 | 80% | 3.7% |

## Recommendations

**1 — Win back "Can't Lose Them" · £37,240**
358 customers have ordered 6 times on average but have been silent for 338 days,
carrying £1,034,451 of historical revenue. Sequenced win-back offer.
*Assumes 12% response, 30% margin.*

**2 — Protect Champions · £177,391**
1,476 customers produce £11.8M — 69.2% of revenue. Losing 5% of them costs
£591,302. Named account care for the top 200, plus an alert when a Champion's
inter-order gap exceeds twice their own norm.
*Assumes protecting 5% of Champion revenue at 30% margin.*

**3 — Convert one-time buyers · £5,560**
1,619 customers (27.7%) ordered exactly once at a median of £229, producing just
3.3% of revenue. Post-purchase sequence with a second-order incentive at day 30.
*Assumes 5% conversion at median AOV.*

---

## Running it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python src/clean.py       # ~2 min (reads a 44MB workbook)
.venv/bin/python src/rfm.py
.venv/bin/python src/findings.py
.venv/bin/streamlit run src/app.py
```

Data: [Online Retail II, UCI ML Repository](https://archive.ics.uci.edu/dataset/502/online+retail+ii)

---

## Building the Power BI dashboard

Load `data/customers.csv`. Add these measures (Power BI Service works — Desktop
is Windows-only):

```dax
Total Revenue    = SUM(customers[Monetary])
Customer Count   = DISTINCTCOUNT(customers[CustomerID])
Avg Order Value  = DIVIDE([Total Revenue], SUM(customers[Frequency]))
Churn Rate       = DIVIDE(CALCULATE([Customer Count], customers[Churned] = 1), [Customer Count])
Revenue Share %  = DIVIDE([Total Revenue], CALCULATE([Total Revenue], ALL(customers)))
Avg CLV          = AVERAGE(customers[CLV_1yr])
Revenue per Cust = DIVIDE([Total Revenue], [Customer Count])
```

Suggested pages:

1. **Overview** — KPI cards (revenue, customers, AOV, churn), revenue by segment
   bar, customer count by segment donut
2. **Segments** — matrix of segment × (customers, revenue, %revenue, churn, CLV),
   scatter of Recency vs Monetary coloured by Cluster
3. **Retention** — `cohort_retention.csv` as a matrix with conditional formatting
4. **At risk** — table filtered to `Can't Lose Them` and `At Risk`, sorted by
   Monetary, as the actionable win-back list
