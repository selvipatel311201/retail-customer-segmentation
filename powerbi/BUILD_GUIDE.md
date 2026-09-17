# Power BI dashboard — build guide

Four pages over `data/customers.csv` (5,853 rows) and
`outputs/cohort_retention.csv`. Written for **Power BI Service**
(`app.powerbi.com`) because Power BI Desktop is Windows-only.

The order matters: **form → layout → colour, last**. Most bad dashboards pick
colours first.

---

## 0. Setup

1. `app.powerbi.com` → **My workspace** → **New** → **Semantic model** → upload
   `data/customers.csv`
2. Repeat for `outputs/cohort_retention.csv` (separate model — no relationship
   needed, it's a standalone matrix)
3. **New report** on the customers model
4. **View → Themes → Browse for themes** → upload `powerbi/theme.json`

The theme sets a colour-blind-validated categorical palette, recessive
gridlines, no visual headers, and 8px rounded borders. Everything below assumes
it is loaded — do not override colours per visual.

---

## 1. Measures

Create these on the `customers` table (**Modeling → New measure**). Format each
as noted; Power BI will not do it for you.

```dax
Total Revenue = SUM(customers[Monetary])
```
*Format: currency, £, 0 decimals*

```dax
Customer Count = DISTINCTCOUNT(customers[CustomerID])
```

```dax
Total Orders = SUM(customers[Frequency])
```

```dax
Avg Order Value = DIVIDE([Total Revenue], [Total Orders])
```
*Format: currency, £, 0 decimals*

```dax
Churn Rate =
DIVIDE(
    CALCULATE([Customer Count], customers[Churned] = 1),
    [Customer Count]
)
```
*Format: percentage, 0 decimals*

```dax
Revenue Share % =
DIVIDE([Total Revenue], CALCULATE([Total Revenue], ALL(customers)))
```
*Format: percentage, 1 decimal*

```dax
Customer Share % =
DIVIDE([Customer Count], CALCULATE([Customer Count], ALL(customers)))
```
*Format: percentage, 1 decimal*

```dax
Avg CLV = AVERAGE(customers[CLV_1yr])
```
*Format: currency, £, 0 decimals*

```dax
Median Recency = MEDIAN(customers[Recency])
```

### The one that shows you can actually write DAX

Everything above is a one-liner. This one computes the Pareto concentration —
what share of revenue comes from the top 20% of customers by spend — and it is
worth including precisely because it needs variables, a virtual table and
`RANKX`:

```dax
Top 20% Revenue Share =
VAR AllCustomers = ALL( customers )
VAR CutoffRank   = ROUNDUP( COUNTROWS( AllCustomers ) * 0.2, 0 )
VAR Ranked =
    ADDCOLUMNS(
        AllCustomers,
        "@Rank", RANKX( AllCustomers, customers[Monetary], , DESC, Dense )
    )
VAR TopRevenue  = SUMX( FILTER( Ranked, [@Rank] <= CutoffRank ), customers[Monetary] )
VAR AllRevenue  = SUMX( AllCustomers, customers[Monetary] )
RETURN
    DIVIDE( TopRevenue, AllRevenue )
```
*Format: percentage, 1 decimal. Should return **77.2%** — if it doesn't, the
measure is wrong.*

---

## 2. Page 1 — Overview

**The job of this page: state the problem in five seconds.**

**Top row — four Card visuals**, equal width across the canvas:

| Card | Field | Reads |
|---|---|---|
| 1 | `Customer Count` | 5,853 |
| 2 | `Total Revenue` | £17.1M |
| 3 | `Top 20% Revenue Share` | 77.2% |
| 4 | `Churn Rate` | 41% |

Rename each card's label to something a human says out loud — "Revenue from top
20% of customers", not "Top 20% Revenue Share".

**Left, large — Bar chart (not column):**
- Y axis: `Segment`  ·  X axis: `Total Revenue`
- Sort descending by Total Revenue
- Turn **data labels on** — three palette slots sit below 3:1 contrast on white,
  so labels are required, not optional
- Horizontal bars because segment names are long; vertical columns would force
  the labels to rotate

**Right — Donut chart:**
- Legend: `Segment` · Values: `Customer Count`
- This is the only place a donut earns its place: the point is that Champions
  are a *quarter of customers* but two-thirds of revenue, and the contrast with
  the bar chart beside it makes that land

**Bottom — one text box**, one sentence, large:

> 20% of customers generate 77.2% of revenue. Month-12 retention is 9.5%.

**Slicer** (top-right, horizontal): `Segment`.

---

## 3. Page 2 — Segments

**The job: let someone interrogate the segments.**

**Matrix visual** (not a table — matrix supports the row hierarchy):
- Rows: `Segment`
- Values: `Customer Count`, `Customer Share %`, `Total Revenue`,
  `Revenue Share %`, `Avg Order Value`, `Avg CLV`, `Churn Rate`
- **Conditional formatting → Data bars** on `Total Revenue` only. One column
  with bars, not five — bars everywhere is noise.
- **Background colour** scale on `Churn Rate` using the theme's minimum/maximum.

**Scatter chart:**
- X: `Recency` · Y: `Monetary` · Legend: `Cluster` · Size: `Frequency`
- Details: `CustomerID`
- Set **both axes to logarithmic** (Format → X axis → Scale type → Log). Without
  this a handful of very large customers flatten everything into the corner.
- Cap the series at **four** — `Cluster` has exactly four values, which is the
  limit for all-pairs colour separation in a scatter. Do not put `Segment`
  (seven values) on a scatter legend.

**Slicers:** `Segment`, `Country`, and a `Churned` toggle.

---

## 4. Page 3 — Retention

Switch to the `cohort_retention` model.

**Matrix visual:**
- Rows: `Cohort` · Columns: months 0–12 · Values: the retention percentage
- **Conditional formatting → Background colour**, sequential blue
  (`#dbeafe` → `#1d4ed8`), lowest to highest
- **One hue, light to dark.** Never a red-yellow-green scale here — this is
  magnitude, not polarity, and a rainbow implies thresholds that don't exist.

**Text box beneath it:**

> Of every 100 first-time buyers, about 20 return within a month and 10 are
> still buying a year later.

---

## 5. Page 4 — Who to act on

**The job: give someone a list they can work from tomorrow.**

**Table visual:**
- Columns: `CustomerID`, `Segment`, `Recency`, `Frequency`, `Monetary`, `AOV`,
  `CLV_1yr`, `Country`
- Filter: `Segment` is **Can't Lose Them** or **At Risk**
- Sort: `Monetary` descending
- Top N filter: 50

**Three Card visuals** above it — one per recommendation, showing the value:
£37,240 · £177,391 · £5,560. Add a text box under each with the one-line
finding from `outputs/findings.json`.

---

## 6. The rules that separate good from generic

**One axis, always.** Never put two measures of different scale on one chart
with a secondary y-axis. Power BI makes this easy and it is the single most
common chart mistake. Two measures → two charts.

**Colour follows the entity, not the rank.** Because the theme fixes the
palette order, "Champions" keeps the same colour when a slicer changes the
visible set. Never set colours per-visual by hand.

**Sequential means one hue.** The retention matrix goes light→dark in a single
blue. Diverging (two hues + grey midpoint) is only for data with a real centre,
like variance against target. You have none here.

**Recessive gridlines.** The theme sets them to `#eceef0`. Don't darken them.
Delete axis titles when the label already says it — "Total Revenue" above a
bar chart does not also need an axis called "Total Revenue".

**Labels, not legends, where you can.** Seven segments in a legend forces the
eye back and forth. Data labels on the bars remove the lookup entirely.

**Round numbers.** £17,081,129 is noise. Format to £17.1M on cards, £ with 0
decimals in tables.

## 7. What to avoid

| Don't | Why |
|---|---|
| Dual-axis combo charts | Two scales, no honest comparison |
| Pie charts with 7 slices | Nobody can rank angles; use the bar chart |
| 3D or gradient fills | Distorts area, adds nothing |
| A KPI card for every measure | Four cards maximum; the rest belong in the matrix |
| Red/amber/green on retention | That's a polarity scale on magnitude data |
| Default Power BI colours | Not validated for colour blindness; the theme is |
| Screenshots of tables as images | Kills interactivity, the one thing Power BI has |

---

## 8. Publishing

**File → Publish to web (public)** gives you a link you can put on a resume.
Note it is genuinely public — that's fine here, the data is an open UCI
dataset with no personal information beyond anonymous customer IDs.

Then send me the URL and I'll add it to your resume next to
`retail.selvipatel.com`.
