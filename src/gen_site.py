#!/usr/bin/env python3
"""Generate the static report page published at retail.selvipatel.com.

Streamlit needs a running server, so it cannot go on GitHub Pages. This bakes
the real findings into a self-contained page that loads instantly with no cold
start -- which for a recruiter clicking a link from a resume matters more than
interactivity. The Streamlit app stays linked for anyone who wants to explore.

Every number is read from the pipeline outputs, never hardcoded.
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs"

# The published Tableau Public viz. Kept here rather than inline because
# republishing under a new name changes the URL, and this is the one place
# that has to be edited when it does.
TABLEAU = ("https://public.tableau.com/app/profile/selvi.patel/viz/"
           "retail_17897602838350/RetailCustomerSegmentationLifetimeValue")
GITHUB = "https://github.com/selvipatel311201/retail-customer-segmentation"

stats = json.loads((ROOT / "outputs" / "rfm_stats.json").read_text())
findings = json.loads((ROOT / "outputs" / "findings.json").read_text())
clean = json.loads((ROOT / "outputs" / "cleaning_log.json").read_text())

segments = stats["segments"]

# The two segments the Tableau contact list is filtered to: high historical
# value, no recent order. Counted rather than hardcoded so the prose on the
# page cannot drift away from the dashboard it describes.
LAPSED = ("At Risk", "Can't Lose Them")
lapsed_customers = sum(s["customers"] for s in segments if s["Segment"] in LAPSED)

retention_rows = list(csv.reader((ROOT / "outputs" / "cohort_retention.csv").open()))
head, *body = retention_rows

# Cluster medians for the scatter summary
import statistics as st
clusters = {}
with (ROOT / "data" / "customers.csv").open() as fh:
    for r in csv.DictReader(fh):
        c = clusters.setdefault(int(r["Cluster"]), {"R": [], "F": [], "M": [], "n": 0, "rev": 0.0})
        c["R"].append(float(r["Recency"])); c["F"].append(float(r["Frequency"]))
        c["M"].append(float(r["Monetary"])); c["n"] += 1; c["rev"] += float(r["Monetary"])
total_rev = sum(c["rev"] for c in clusters.values())
cluster_rows = sorted(
    ({"id": k, "n": v["n"], "R": st.median(v["R"]), "F": st.median(v["F"]),
      "M": st.median(v["M"]), "share": 100 * v["rev"] / total_rev}
     for k, v in clusters.items()),
    key=lambda x: -x["share"])

CLUSTER_NAMES = {0: "VIPs", 1: "Lapsing regulars", 2: "Active light buyers",
                 3: "One-and-done"}


def seg_bars():
    mx = max(s["revenue"] for s in segments)
    out = []
    for s in segments:
        w = 100 * s["revenue"] / mx
        out.append(f"""
        <tr>
          <td class="seg">{s['Segment']}</td>
          <td class="num">{s['customers']:,}</td>
          <td class="num">{s['pct_customers']:.1f}%</td>
          <td class="bar-cell"><div class="bar" style="width:{w:.1f}%"></div>
              <span>£{s['revenue']:,.0f}</span></td>
          <td class="num strong">{s['pct_revenue']:.1f}%</td>
          <td class="num">{100*s['churn_rate']:.0f}%</td>
        </tr>""")
    return "".join(out)


def retention_table():
    cols = head[1:13]
    rows = []
    for r in body:
        cells = []
        for v in r[1:13]:
            try:
                x = float(v)
                shade = min(x / 45, 1.0)
                cells.append(f'<td class="heat" style="--a:{shade:.2f}">{x:.0f}</td>')
            except ValueError:
                cells.append('<td class="heat empty"></td>')
        rows.append(f"<tr><th>{r[0]}</th>{''.join(cells)}</tr>")
    header = "".join(f"<th>{c}</th>" for c in cols)
    return f"<tr><th>Cohort</th>{header}</tr>" + "".join(rows)


def recs():
    out = []
    for i, r in enumerate(findings["recommendations"], 1):
        out.append(f"""
        <div class="rec">
          <div class="rec-n">{i}</div>
          <div>
            <h3>{r['title']}</h3>
            <p>{r['finding']}</p>
            <p class="action"><strong>Action.</strong> {r['action']}</p>
            <p class="val">£{r['value_gbp']:,.0f} <span>gross margin — {r['assumption']}</span></p>
          </div>
        </div>""")
    return "".join(out)


def clusters_html():
    out = []
    for c in cluster_rows:
        out.append(f"""
        <tr>
          <td class="seg">{CLUSTER_NAMES.get(c['id'], f"Cluster {c['id']}")}</td>
          <td class="num">{c['n']:,}</td>
          <td class="num">{c['R']:.0f} days</td>
          <td class="num">{c['F']:.0f}</td>
          <td class="num">£{c['M']:,.0f}</td>
          <td class="num strong">{c['share']:.1f}%</td>
        </tr>""")
    return "".join(out)


HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Retail Customer Segmentation &amp; Lifetime Value — Selvi Patel</title>
<meta name="description" content="Segmentation, churn and lifetime value analysis over 1.07M retail transactions. RFM scoring, K-Means clustering and costed retention recommendations.">
<style>
  :root {{
    --ink:#15171a; --muted:#6b7280; --line:#e5e7eb; --bg:#ffffff;
    --accent:#1d4ed8; --accent-soft:#dbeafe; --good:#047857;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --ink:#e8eaed; --muted:#9aa0a6; --line:#2c3034; --bg:#121416;
             --accent:#7aa2f7; --accent-soft:#1b2740; --good:#4ade80; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:960px; margin:0 auto; padding:56px 24px 80px; }}
  header {{ border-bottom:1px solid var(--line); padding-bottom:28px; margin-bottom:40px; }}
  h1 {{ font-size:clamp(28px,4.5vw,40px); line-height:1.15; margin:0 0 10px;
        letter-spacing:-.02em; }}
  .sub {{ color:var(--muted); margin:0 0 18px; font-size:17px; }}
  .links a {{ display:inline-block; margin-right:14px; color:var(--accent);
    text-decoration:none; font-weight:500; border-bottom:1px solid transparent; }}
  .links a:hover {{ border-bottom-color:var(--accent); }}
  h2 {{ font-size:13px; text-transform:uppercase; letter-spacing:.09em;
        color:var(--muted); margin:46px 0 16px; font-weight:600; }}
  .kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
    gap:14px; }}
  .kpi {{ border:1px solid var(--line); border-radius:10px; padding:18px 16px; }}
  .kpi b {{ display:block; font-size:27px; letter-spacing:-.02em; margin-bottom:3px; }}
  .kpi span {{ color:var(--muted); font-size:13px; }}
  .lead {{ font-size:19px; line-height:1.6; border-left:3px solid var(--accent);
    padding-left:18px; margin:30px 0; }}
  table {{ width:100%; border-collapse:collapse; font-size:14.5px; }}
  th {{ text-align:left; font-weight:600; color:var(--muted); font-size:12px;
    text-transform:uppercase; letter-spacing:.05em; padding:0 10px 9px;
    border-bottom:1px solid var(--line); }}
  td {{ padding:11px 10px; border-bottom:1px solid var(--line); }}
  .num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
  .strong {{ font-weight:650; }}
  .seg {{ font-weight:550; }}
  .bar-cell {{ position:relative; min-width:190px; }}
  .bar {{ position:absolute; left:10px; top:50%; transform:translateY(-50%);
    height:19px; background:var(--accent-soft); border-radius:3px; z-index:0; }}
  .bar-cell span {{ position:relative; z-index:1; font-variant-numeric:tabular-nums; }}
  .scroll {{ overflow-x:auto; }}
  .heat {{ text-align:center; padding:7px 4px; font-size:12.5px;
    font-variant-numeric:tabular-nums;
    background:color-mix(in srgb, var(--accent) calc(var(--a)*55%), transparent); }}
  .heat.empty {{ background:none; }}
  .rec {{ display:flex; gap:18px; padding:22px 0; border-bottom:1px solid var(--line); }}
  .rec-n {{ flex:0 0 30px; height:30px; border-radius:50%; background:var(--accent-soft);
    color:var(--accent); display:grid; place-items:center; font-weight:650; font-size:14px; }}
  .rec h3 {{ margin:2px 0 8px; font-size:17px; }}
  .rec p {{ margin:0 0 8px; }}
  .action {{ color:var(--muted); }}
  .val {{ color:var(--good); font-weight:650; font-size:17px; }}
  .val span {{ color:var(--muted); font-weight:400; font-size:13px; }}
  .note {{ background:color-mix(in srgb, var(--accent) 6%, transparent);
    border-radius:10px; padding:18px 20px; font-size:14.5px; }}
  .note p {{ margin:0 0 10px; }} .note p:last-child {{ margin:0; }}
  footer {{ margin-top:56px; padding-top:22px; border-top:1px solid var(--line);
    color:var(--muted); font-size:14px; }}
</style>
</head>
<body>
<div class="wrap">

<header>
  <h1>Retail Customer Segmentation &amp; Lifetime Value</h1>
  <p class="sub">{clean['clean_rows']:,} cleaned transactions · {stats['customers']:,} customers ·
     {clean['date_min']} to {clean['date_max']}</p>
  <div class="links">
    <a href="{TABLEAU}">Tableau dashboard →</a>
    <a href="{GITHUB}">Source code →</a>
    <a href="https://selvipatel.com">Selvi Patel →</a>
  </div>
</header>

<div class="kpis">
  <div class="kpi"><b>{stats['customers']:,}</b><span>Customers</span></div>
  <div class="kpi"><b>£{stats['total_revenue']/1e6:.1f}M</b><span>Revenue analysed</span></div>
  <div class="kpi"><b>{stats['top20pct_revenue_share']:.0f}%</b><span>Revenue from top 20%</span></div>
  <div class="kpi"><b>{100*stats['overall_churn_rate']:.0f}%</b><span>Churned (180 days)</span></div>
</div>

<p class="lead">Twenty percent of customers generate {stats['top20pct_revenue_share']:.1f}% of revenue,
and of everyone who buys once, only {findings['retention']['month_12']:.1f}% are still buying a year
later. The business is carried by a small group it cannot afford to lose.</p>

<h2>Interactive dashboard</h2>
<p>The same analysis published to Tableau Public: revenue and customer counts by segment, the
cluster scatter, and a ranked contact list of the {lapsed_customers:,} high-value
customers who have stopped buying.
<a href="{TABLEAU}" style="color:var(--accent)">Open it full size →</a></p>
<div class="scroll" style="border:1px solid var(--line); border-radius:8px">
  <iframe src="{TABLEAU}?:showVizHome=no&amp;:embed=y&amp;:toolbar=no"
    title="Retail customer segmentation dashboard on Tableau Public"
    width="1360" height="1000" loading="lazy"
    style="border:0; display:block"></iframe>
</div>

<h2>Segments</h2>
<div class="scroll"><table>
  <tr><th>Segment</th><th class="num">Customers</th><th class="num">% of base</th>
      <th>Revenue</th><th class="num">% of revenue</th><th class="num">Churned</th></tr>
  {seg_bars()}
</table></div>

<h2>K-Means clusters</h2>
<p>Run independently of the rule-based segments above, on log-scaled recency, frequency
and monetary value. <em>k</em> was chosen by the elbow method — silhouette scoring peaked at
k=2, which splits customers into active and inactive: true, but nothing a team can act on.</p>
<div class="scroll"><table>
  <tr><th>Cluster</th><th class="num">Customers</th><th class="num">Median recency</th>
      <th class="num">Median orders</th><th class="num">Median spend</th>
      <th class="num">% of revenue</th></tr>
  {clusters_html()}
</table></div>

<h2>Cohort retention</h2>
<p>Each row is a month's new customers; each column is months since their first purchase.
Retention falls from {findings['retention']['month_1']:.1f}% at month one to
{findings['retention']['month_12']:.1f}% at month twelve.</p>
<div class="scroll"><table>{retention_table()}</table></div>

<h2>Recommendations</h2>
{recs()}
<p class="val" style="margin-top:22px;font-size:19px">
  £{findings['total_opportunity_gbp']:,.0f} <span>total identified gross margin</span></p>

<h2>Method &amp; limitations</h2>
<div class="note">
  <p><strong>Cleaning.</strong> {clean['raw_rows']:,} raw rows reduced to
  {clean['clean_rows']:,} ({clean['pct_dropped']}% dropped): cancelled invoices, non-product
  lines such as postage and bank charges, exact duplicates, and
  {clean['steps'][0]['rows_dropped']:,} rows with no customer ID.</p>
  <p><strong>Known bias.</strong> Those missing-ID rows are guest checkouts — real sales that
  cannot be attributed to a person. They skew toward one-time buyers, so every segment here
  over-represents repeat customers. Stated rather than hidden.</p>
  <p><strong>Lifetime value.</strong> AOV × orders per year × 30% assumed gross margin, where
  orders per year is measured over how long each customer has been observed, not over their
  active span — dividing by active span sends one-time buyers to infinity.</p>
  <p><strong>Churn.</strong> Defined as no purchase within 180 days of the snapshot date.</p>
</div>

<footer>
  Built by <a href="https://selvipatel.com" style="color:var(--accent)">Selvi Patel</a> ·
  Python, Pandas, Scikit-Learn, SQL, Tableau ·
  Data: <a href="https://archive.ics.uci.edu/dataset/502/online+retail+ii"
  style="color:var(--accent)">Online Retail II</a>, UCI Machine Learning Repository
</footer>

</div>
</body>
</html>
"""

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(HTML)
    (OUT / "CNAME").write_text("retail.selvipatel.com\n")
    (OUT / ".nojekyll").write_text("")
    print(f"wrote {OUT/'index.html'}  ({len(HTML):,} bytes)")
    print(f"wrote {OUT/'CNAME'} -> retail.selvipatel.com")
