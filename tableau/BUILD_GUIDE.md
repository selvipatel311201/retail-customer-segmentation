# Tableau Public — build guide

Five worksheets combined into one dashboard, over
`data/customers.csv` (5,853 rows). Tableau Public is free and runs natively on
macOS.

Build the worksheets first, the dashboard last. Trying to build the dashboard
first is the usual way people get stuck.

---

## 0. Connect

1. Open **Tableau Public**
2. **Connect → To a File → Text file**
3. In the file dialog press **⌘ + Shift + G**, paste `~/retail-analytics/data`
4. Choose `customers.csv`
5. Tableau shows a preview grid. Check `Monetary`, `Recency`, `CLV_1yr` are
   green (**measures**, i.e. numbers) and `Segment`, `Country` are blue
   (**dimensions**, i.e. categories).
6. **`Cluster` will import as a measure — fix it.** Right-click it →
   **Convert to Dimension**. It's a category label, not a quantity.
7. Click **Sheet 1** at the bottom.

## 1. Calculated fields

**Analysis → Create Calculated Field** for each. Name them exactly as shown.

```
Total Revenue
SUM([Monetary])
```

```
Customer Count
COUNTD([CustomerID])
```

```
Total Orders
SUM([Frequency])
```

```
Avg Order Value
SUM([Monetary]) / SUM([Frequency])
```

```
Churn Rate
SUM([Churned]) / COUNTD([CustomerID])
```
*`Churned` is already 1/0, so summing it counts churned customers.*

```
Avg CLV
AVG([CLV_1yr])
```

```
Revenue Share
SUM([Monetary]) / TOTAL(SUM([Monetary]))
```
*This is a **table calculation** — it only works inside a view, not on a card
by itself. Format as percentage.*

Format each: right-click the field → **Default Properties → Number Format** →
Currency (£, 0 decimals) for money, Percentage (1 decimal) for rates.

## 2. Set the colour palette — once

Tableau ships a colour-blind-safe palette. Use it and don't hand-pick colours.

When a colour legend first appears: click the legend's dropdown arrow →
**Edit Colors** → in the palette dropdown choose **Color Blind** → **Assign
Palette** → OK.

Do this the first time and Tableau reuses it.

---

## 3. Sheet 1 — "Revenue by segment"

The headline chart.

1. Drag **`Segment`** → **Rows**
2. Drag **`Total Revenue`** → **Columns**
3. Sort descending: hover the Total Revenue axis → click the descending-sort icon
4. On the **Marks** card, drag **`Total Revenue`** onto **Label** (turns numbers on)
5. Drag **`Segment`** onto **Color**
6. Rename the sheet (bottom tab): **Revenue by segment**

Horizontal bars, not vertical — the segment names are long and would rotate.

## 4. Sheet 2 — "Customers by segment"

1. New worksheet
2. Drag **`Segment`** → **Rows**, **`Customer Count`** → **Columns**
3. Sort descending
4. **`Segment`** → **Color**, **`Customer Count`** → **Label**
5. Rename: **Customers by segment**

Placed beside Sheet 1 this is the whole story: Champions are a *quarter* of
customers but *two-thirds* of revenue.

## 5. Sheet 3 — "Clusters"

1. New worksheet
2. **`Recency`** → **Columns**, **`Monetary`** → **Rows**
3. Both default to SUM — change each to **AVG**: click the pill → Measure → Average
4. Drag **`CustomerID`** → **Detail** on the Marks card (this makes one dot per
   customer rather than one aggregate blob)
5. **`Cluster`** → **Color**
6. **`Frequency`** → **Size**
7. Marks type → **Circle**
8. **Log-scale both axes**: right-click each axis → **Edit Axis** → tick
   **Logarithmic**. Without this a few huge customers squash everything into a corner.
9. Rename: **Clusters**

## 6. Sheet 4 — "Segment detail"

A text table.

1. New worksheet
2. **`Segment`** → **Rows**
3. Drag onto **Text** on the Marks card, in this order:
   `Customer Count`, `Total Revenue`, `Avg Order Value`, `Avg CLV`, `Churn Rate`
4. Marks type → **Text**
5. Sort by Total Revenue descending
6. Rename: **Segment detail**

## 7. Sheet 5 — "Who to contact"

The actionable list.

1. New worksheet
2. **Rows**: `CustomerID`, `Segment`, `Country`
3. **Text**: `Recency`, `Frequency`, `Monetary`, `CLV_1yr`
4. Filter: drag **`Segment`** → Filters → tick only **Can't Lose Them** and
   **At Risk**
5. Sort by `Monetary` descending
6. Filter to top 50: drag `CustomerID` → Filters → **Top** tab → By field →
   Top 50 by `Monetary` (Sum)
7. Rename: **Who to contact**

---

## 8. The dashboard

1. Bottom bar → **New Dashboard** (the middle icon)
2. Left panel → **Size** → **Automatic** (so it works on any screen)
3. Drag sheets onto the canvas in this order:

```
┌──────────────────────────────────────────┐
│  Title text:  Retail Customer            │
│  Segmentation & Lifetime Value           │
├────────────────────┬─────────────────────┤
│  Revenue by        │  Customers by       │
│  segment           │  segment            │
├────────────────────┴─────────────────────┤
│  Segment detail                          │
├──────────────────────────────────────────┤
│  Clusters          │  Who to contact     │
└────────────────────┴─────────────────────┘
```

4. Drag a **Text** object to the top for the title
5. Add a filter: click the *Revenue by segment* sheet → its dropdown arrow →
   **Filters → Segment**. Then on that filter's dropdown → **Apply to Worksheets
   → All Using This Data Source**, so one click filters the whole dashboard.

## 9. Publish

1. **File → Save to Tableau Public As…**
2. Sign in
3. Name it: **Retail Customer Segmentation & Lifetime Value**
4. Save

It opens in your browser at a URL like
`public.tableau.com/app/profile/selvi.patel/viz/...`

**Then send me that URL** and I'll put it on your resume.

---

## Things that go wrong

| Symptom | Cause |
|---|---|
| Scatter shows one dot | `CustomerID` not on **Detail** |
| Everything in the corner | Axes not logarithmic |
| Cluster shows as a number | Not converted to Dimension |
| Bars all one colour | `Segment` not on **Color** |
| Filter only affects one chart | Not applied to all worksheets |
| Revenue Share errors on a card | It's a table calculation — only works inside a view |

## Rules worth keeping

**Never two measures on one axis.** Tableau makes dual-axis easy; it's still
the most misleading chart there is. Two measures → two sheets.

**Use the Color Blind palette**, not hand-picked colours. Around 8% of men have
some colour-vision deficiency, and a hiring manager may be one of them.

**Label the bars.** A bar chart where you have to look back at a legend is
slower to read than one with the number on it.

**Round the numbers.** £17,081,129 is noise. £17.1M is a fact.
