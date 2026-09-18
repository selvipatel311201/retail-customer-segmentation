#!/usr/bin/env python3
"""Generate the static report page published at retail.selvipatel.com.

A recruiter clicking a link from a resume gets one chance to be interested, so
the page is a single self-contained file that paints instantly: no framework,
no cold start, no request to anything but a font. The Tableau workbook is
embedded for anyone who wants to poke at it.

Every number on the page is read from the pipeline outputs. Nothing is typed in
by hand, so re-running the analysis re-writes the prose along with the charts.
"""

import csv
import json
import statistics as st
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

clusters, spend = {}, []
with (ROOT / "data" / "customers.csv").open() as fh:
    for r in csv.DictReader(fh):
        c = clusters.setdefault(int(r["Cluster"]),
                                {"R": [], "F": [], "M": [], "n": 0, "rev": 0.0})
        c["R"].append(float(r["Recency"])); c["F"].append(float(r["Frequency"]))
        c["M"].append(float(r["Monetary"])); c["n"] += 1; c["rev"] += float(r["Monetary"])
        spend.append(float(r["Monetary"]))

total_rev = sum(c["rev"] for c in clusters.values())
cluster_rows = sorted(
    ({"id": k, "n": v["n"], "R": st.median(v["R"]), "F": st.median(v["F"]),
      "M": st.median(v["M"]), "share": 100 * v["rev"] / total_rev}
     for k, v in clusters.items()),
    key=lambda x: -x["share"])

CLUSTER_NAMES = {0: "VIPs", 1: "Lapsing regulars", 2: "Active light buyers",
                 3: "One-and-done"}


# --------------------------------------------------------------------------
# Charts, drawn as inline SVG.  A charting library would be 60kB and one more
# thing to fail; these are two polylines.
# --------------------------------------------------------------------------

CW, CH = 720, 300          # viewBox
PL, PR, PT, PB = 52, 18, 18, 46   # plot padding


def _x(frac):
    return PL + frac * (CW - PL - PR)


def _y(frac):
    return CH - PB - frac * (CH - PT - PB)


def _grid(ticks, fmt):
    """Horizontal gridlines with left-hand labels, 0-100 scale."""
    out = []
    for t in ticks:
        y = _y(t / 100)
        out.append(f'<line class="g" x1="{PL}" y1="{y:.1f}" x2="{CW-PR}" y2="{y:.1f}"/>')
        out.append(f'<text class="ax" x="{PL-10}" y="{y+4:.1f}" text-anchor="end">'
                   f'{fmt.format(t)}</text>')
    return "".join(out)


def pareto_svg():
    """Cumulative share of revenue against cumulative share of customers."""
    ranked = sorted(spend, reverse=True)
    n, total = len(ranked), sum(ranked)
    running, pts = 0.0, []
    step = max(1, n // 240)
    for i, v in enumerate(ranked, 1):
        running += v
        if i % step == 0 or i == n:
            pts.append((_x(i / n), _y(running / total)))
    path = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
    area = f"{_x(0):.1f},{_y(0):.1f} " + path + f" {_x(1):.1f},{_y(0):.1f}"

    share = stats["top20pct_revenue_share"]
    mx, my = _x(0.2), _y(share / 100)
    xlabels = "".join(
        f'<text class="ax" x="{_x(p/100):.1f}" y="{CH-PB+20}" text-anchor="middle">{p}%</text>'
        for p in (0, 20, 40, 60, 80, 100))

    return f"""<svg viewBox="0 0 {CW} {CH}" role="img" preserveAspectRatio="xMidYMid meet"
     aria-label="Cumulative revenue share: the top 20 percent of customers account for {share:.1f} percent of revenue">
  {_grid([0, 25, 50, 75, 100], "{}%")}
  <polygon class="area" points="{area}"/>
  <polyline class="line" points="{path}"/>
  <line class="marker" x1="{mx:.1f}" y1="{_y(0):.1f}" x2="{mx:.1f}" y2="{my:.1f}"/>
  <line class="marker" x1="{PL}" y1="{my:.1f}" x2="{mx:.1f}" y2="{my:.1f}"/>
  <circle class="dot" cx="{mx:.1f}" cy="{my:.1f}" r="5"/>
  <text class="call" x="{mx+12:.1f}" y="{my-10:.1f}">top 20% of customers → {share:.1f}% of revenue</text>
  {xlabels}
  <text class="ax" x="{_x(0.5):.1f}" y="{CH-6}" text-anchor="middle">customers, ranked by spend</text>
</svg>"""


def retention_curve():
    """Mean retention across every monthly cohort, months 0-12."""
    out = []
    for m in range(13):
        vals = [float(r[m + 1]) for r in body
                if len(r) > m + 1 and r[m + 1] not in ("", "nan")]
        out.append(sum(vals) / len(vals) if vals else 0.0)
    return out


def retention_svg():
    curve = retention_curve()
    pts = [(_x(m / 12), _y(v / 100)) for m, v in enumerate(curve)]
    path = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
    area = f"{pts[0][0]:.1f},{_y(0):.1f} " + path + f" {pts[-1][0]:.1f},{_y(0):.1f}"
    ex, ey = pts[-1]
    xlabels = "".join(
        f'<text class="ax" x="{_x(m/12):.1f}" y="{CH-PB+20}" text-anchor="middle">{m}</text>'
        for m in (0, 3, 6, 9, 12))

    return f"""<svg viewBox="0 0 {CW} {CH}" role="img" preserveAspectRatio="xMidYMid meet"
     aria-label="Cohort retention falls from 100 percent at month zero to {curve[12]:.1f} percent at month twelve">
  {_grid([0, 25, 50, 75, 100], "{}%")}
  <polygon class="area" points="{area}"/>
  <polyline class="line" points="{path}"/>
  <circle class="dot" cx="{ex:.1f}" cy="{ey:.1f}" r="5"/>
  <text class="call" x="{ex-8:.1f}" y="{ey-14:.1f}" text-anchor="end">{curve[12]:.1f}% at month 12</text>
  {xlabels}
  <text class="ax" x="{_x(0.5):.1f}" y="{CH-6}" text-anchor="middle">months since first purchase</text>
</svg>"""


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------

def seg_bars():
    mx = max(s["revenue"] for s in segments)
    out = []
    for s in segments:
        w = 100 * s["revenue"] / mx
        hot = ' data-lead="true"' if s["Segment"] == "Champions" else ""
        out.append(f"""
        <tr{hot}>
          <td class="seg">{s['Segment']}</td>
          <td class="num">{s['customers']:,}</td>
          <td class="num dim">{s['pct_customers']:.1f}%</td>
          <td class="bar-cell"><div class="bar" style="width:{w:.1f}%"></div>
              <span>£{s['revenue']:,.0f}</span></td>
          <td class="num strong">{s['pct_revenue']:.1f}%</td>
          <td class="num dim">{100*s['churn_rate']:.0f}%</td>
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
                cells.append(f'<td class="heat" style="--a:{min(x/45,1.0):.2f}">{x:.0f}</td>')
            except ValueError:
                cells.append('<td class="heat empty"></td>')
        rows.append(f"<tr><th>{r[0]}</th>{''.join(cells)}</tr>")
    header = "".join(f"<th>{c}</th>" for c in cols)
    return f"<tr><th>Cohort</th>{header}</tr>" + "".join(rows)


def clusters_html():
    out = []
    for c in cluster_rows:
        out.append(f"""
        <tr>
          <td class="seg">{CLUSTER_NAMES.get(c['id'], f"Cluster {c['id']}")}</td>
          <td class="num">{c['n']:,}</td>
          <td class="num dim">{c['R']:.0f} days</td>
          <td class="num dim">{c['F']:.0f}</td>
          <td class="num">£{c['M']:,.0f}</td>
          <td class="num strong">{c['share']:.1f}%</td>
        </tr>""")
    return "".join(out)


def recs():
    out = []
    for i, r in enumerate(findings["recommendations"], 1):
        out.append(f"""
        <article class="rec">
          <div class="rec-head"><span class="rec-n">{i}</span>
            <h3>{r['title']}</h3></div>
          <p>{r['finding']}</p>
          <p class="action"><span>Action</span>{r['action']}</p>
          <p class="val">£{r['value_gbp']:,.0f}<span>gross margin · {r['assumption']}</span></p>
        </article>""")
    return "".join(out)


HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Retail Customer Segmentation &amp; Lifetime Value — Selvi Patel</title>
<meta name="description" content="Segmentation, churn and lifetime value analysis over 1.07M retail transactions. RFM scoring, K-Means clustering and costed retention recommendations.">
<meta name="theme-color" content="#f5f5f7" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)">
<meta property="og:title" content="Retail Customer Segmentation &amp; Lifetime Value">
<meta property="og:description" content="20% of customers generate {stats['top20pct_revenue_share']:.1f}% of revenue. RFM scoring, K-Means clustering and CLV modelling over 1.07M transactions.">
<meta property="og:type" content="website">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><rect width='24' height='24' rx='6' fill='%231d1d1f'/><g fill='%23ffffff'><rect x='5' y='13' width='3' height='6' rx='1'/><rect x='10.5' y='9' width='3' height='10' rx='1'/><rect x='16' y='5' width='3' height='14' rx='1'/></g></svg>">
<style>
  :root {{
    --bg:#f5f5f7; --surface:#ffffff; --ink:#1d1d1f; --muted:#6e6e73;
    --line:#e3e3e6; --line-strong:#d2d2d7; --accent:#0066cc; --accent-soft:#e8f0fb;
    --good:#1d7a4f; --shadow:0 1px 2px rgba(0,0,0,.04), 0 8px 24px rgba(0,0,0,.05);
    --radius:16px;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg:#000000; --surface:#151517; --ink:#f5f5f7; --muted:#98989d;
      --line:#2a2a2d; --line-strong:#39393d; --accent:#4a9eff; --accent-soft:#132339;
      --good:#42d392; --shadow:0 1px 2px rgba(0,0,0,.5), 0 8px 24px rgba(0,0,0,.35);
    }}
  }}
  * {{ box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; scroll-padding-top:76px; }}
  @media (prefers-reduced-motion:reduce) {{ html {{ scroll-behavior:auto; }} }}
  body {{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    font-size:17px; line-height:1.6; -webkit-font-smoothing:antialiased;
    font-feature-settings:"cv05","ss01";
  }}
  a {{ color:var(--accent); }}

  /* ---- nav ---- */
  nav {{
    position:sticky; top:0; z-index:20; backdrop-filter:saturate(180%) blur(20px);
    -webkit-backdrop-filter:saturate(180%) blur(20px);
    background:color-mix(in srgb, var(--bg) 82%, transparent);
    border-bottom:1px solid var(--line);
  }}
  .nav-in {{
    max-width:1040px; margin:0 auto; padding:0 24px; height:52px;
    display:flex; align-items:center; gap:26px; font-size:13.5px;
  }}
  .nav-in .mark {{ font-weight:600; letter-spacing:-.01em; margin-right:auto; }}
  .nav-in a {{ color:var(--muted); text-decoration:none; white-space:nowrap; }}
  .nav-in a:hover {{ color:var(--ink); }}
  @media (max-width:820px) {{ .nav-in .hide-sm {{ display:none; }} }}

  .wrap {{ max-width:1040px; margin:0 auto; padding:0 24px 96px; }}

  /* ---- hero ---- */
  header {{ padding:76px 0 8px; }}
  .eyebrow {{
    font-size:12px; font-weight:600; letter-spacing:.12em; text-transform:uppercase;
    color:var(--accent); margin:0 0 14px;
  }}
  h1 {{
    font-size:clamp(34px,5.4vw,56px); line-height:1.06; letter-spacing:-.028em;
    font-weight:700; margin:0 0 18px; max-width:17ch;
  }}
  .sub {{ color:var(--muted); font-size:19px; margin:0 0 30px; max-width:60ch; }}
  .cta {{ display:flex; flex-wrap:wrap; gap:10px; }}
  .btn {{
    display:inline-flex; align-items:center; gap:7px; text-decoration:none;
    font-size:14.5px; font-weight:550; padding:10px 18px; border-radius:980px;
    border:1px solid var(--line-strong); color:var(--ink); background:var(--surface);
    transition:transform .15s ease, border-color .15s ease;
  }}
  .btn:hover {{ transform:translateY(-1px); border-color:var(--ink); }}
  .btn.primary {{ background:var(--accent); border-color:var(--accent); color:#fff; }}
  .btn.primary:hover {{ opacity:.9; }}

  /* ---- kpis ---- */
  .kpis {{
    display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
    gap:12px; margin:44px 0 0;
  }}
  .kpi {{
    background:var(--surface); border:1px solid var(--line); border-radius:var(--radius);
    padding:22px 20px; box-shadow:var(--shadow);
  }}
  .kpi b {{
    display:block; font-size:34px; font-weight:650; letter-spacing:-.03em;
    line-height:1.1; margin-bottom:6px; font-variant-numeric:tabular-nums;
  }}
  .kpi span {{ color:var(--muted); font-size:13.5px; }}

  .lead {{
    font-size:23px; line-height:1.5; letter-spacing:-.015em; font-weight:500;
    margin:56px 0 0; max-width:34ch;
  }}
  .lead em {{ font-style:normal; color:var(--muted); }}

  /* ---- sections ---- */
  section {{ margin-top:80px; }}
  h2 {{
    font-size:28px; letter-spacing:-.022em; font-weight:650; margin:0 0 8px;
  }}
  .say {{ color:var(--muted); font-size:16.5px; margin:0 0 24px; max-width:68ch; }}
  .card {{
    background:var(--surface); border:1px solid var(--line); border-radius:var(--radius);
    box-shadow:var(--shadow); overflow:hidden;
  }}
  .card .pad {{ padding:22px 24px; }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  @media (max-width:860px) {{ .grid2 {{ grid-template-columns:1fr; }} }}

  /* ---- svg charts ---- */
  figure {{ margin:0; }}
  figure svg {{ display:block; width:100%; height:auto; }}
  figcaption {{
    padding:0 24px 20px; color:var(--muted); font-size:13.5px;
  }}
  .chart-title {{
    padding:20px 24px 4px; font-size:15px; font-weight:600;
  }}
  svg .g {{ stroke:var(--line); stroke-width:1; }}
  svg .ax {{ fill:var(--muted); font-size:12px;
             font-family:Inter,-apple-system,sans-serif; }}
  svg .line {{ fill:none; stroke:var(--accent); stroke-width:2.5;
               stroke-linejoin:round; stroke-linecap:round; }}
  svg .area {{ fill:var(--accent); opacity:.09; }}
  svg .marker {{ stroke:var(--muted); stroke-width:1.5; stroke-dasharray:3 3; }}
  svg .dot {{ fill:var(--accent); }}
  svg .call {{ fill:var(--ink); font-size:13px; font-weight:600;
               font-family:Inter,-apple-system,sans-serif; }}

  /* ---- tables ---- */
  .scroll {{ overflow-x:auto; }}
  table {{ width:100%; border-collapse:collapse; font-size:14.5px; }}
  th {{
    text-align:left; font-weight:600; color:var(--muted); font-size:11.5px;
    text-transform:uppercase; letter-spacing:.06em; padding:16px 14px 11px;
    border-bottom:1px solid var(--line); white-space:nowrap;
  }}
  td {{ padding:13px 14px; border-bottom:1px solid var(--line); }}
  tr:last-child td {{ border-bottom:0; }}
  tr[data-lead] td {{ background:color-mix(in srgb, var(--accent) 5%, transparent); }}
  .num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
  .dim {{ color:var(--muted); }}
  .strong {{ font-weight:650; }}
  .seg {{ font-weight:550; }}
  .bar-cell {{ position:relative; min-width:200px; }}
  .bar {{
    position:absolute; left:14px; top:50%; transform:translateY(-50%);
    height:22px; background:var(--accent-soft); border-radius:5px; z-index:0;
  }}
  .bar-cell span {{ position:relative; z-index:1; font-variant-numeric:tabular-nums; }}
  .heat {{
    text-align:center; padding:8px 5px; font-size:12.5px; border-bottom:0;
    font-variant-numeric:tabular-nums;
    background:color-mix(in srgb, var(--accent) calc(var(--a)*58%), transparent);
  }}
  .heat.empty {{ background:none; }}
  .scroll th[scope], .scroll tbody th {{ font-size:12px; }}

  /* ---- embed ---- */
  .embed {{ position:relative; }}
  .embed iframe {{ display:block; border:0; width:1360px; height:1000px; }}

  /* ---- recommendations ---- */
  .recs {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:16px; }}
  .rec {{
    background:var(--surface); border:1px solid var(--line); border-radius:var(--radius);
    box-shadow:var(--shadow); padding:24px; display:flex; flex-direction:column;
  }}
  .rec-head {{ display:flex; gap:12px; align-items:flex-start; margin-bottom:12px; }}
  .rec-n {{
    flex:0 0 26px; height:26px; border-radius:50%; background:var(--accent-soft);
    color:var(--accent); display:grid; place-items:center; font-weight:650; font-size:13px;
  }}
  .rec h3 {{ margin:1px 0; font-size:17px; letter-spacing:-.012em; line-height:1.35; }}
  .rec p {{ margin:0 0 12px; font-size:15px; color:var(--muted); }}
  .action span {{
    display:block; font-size:11.5px; letter-spacing:.07em; text-transform:uppercase;
    color:var(--ink); font-weight:600; margin-bottom:3px;
  }}
  .val {{
    margin:auto 0 0 !important; padding-top:14px; border-top:1px solid var(--line);
    color:var(--good) !important; font-weight:650; font-size:22px;
    letter-spacing:-.02em; font-variant-numeric:tabular-nums;
  }}
  .val span {{ display:block; color:var(--muted); font-weight:400; font-size:12.5px;
               letter-spacing:0; margin-top:2px; }}
  .total {{
    margin-top:18px; padding:20px 24px; border-radius:var(--radius);
    background:var(--surface); border:1px solid var(--line); box-shadow:var(--shadow);
    display:flex; align-items:baseline; gap:12px; flex-wrap:wrap;
  }}
  .total b {{ font-size:28px; font-weight:650; letter-spacing:-.025em; color:var(--good);
              font-variant-numeric:tabular-nums; }}
  .total span {{ color:var(--muted); font-size:14.5px; }}

  /* ---- method ---- */
  .method {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:16px; }}
  .method div {{
    background:var(--surface); border:1px solid var(--line); border-radius:var(--radius);
    padding:22px; font-size:14.5px; color:var(--muted); box-shadow:var(--shadow);
  }}
  .method strong {{ display:block; color:var(--ink); font-size:13px; letter-spacing:.05em;
                    text-transform:uppercase; margin-bottom:8px; }}

  footer {{
    margin-top:84px; padding-top:26px; border-top:1px solid var(--line);
    color:var(--muted); font-size:14px;
  }}
</style>
</head>
<body>

<nav>
  <div class="nav-in">
    <span class="mark">Retail Segmentation</span>
    <a href="#dashboard" class="hide-sm">Dashboard</a>
    <a href="#segments" class="hide-sm">Segments</a>
    <a href="#retention" class="hide-sm">Retention</a>
    <a href="#actions" class="hide-sm">Actions</a>
    <a href="#method" class="hide-sm">Method</a>
    <a href="{GITHUB}">GitHub ↗</a>
  </div>
</nav>

<div class="wrap">

<header>
  <p class="eyebrow">Retail analytics</p>
  <h1>Customer Segmentation &amp; Lifetime Value</h1>
  <p class="sub">{clean['raw_rows']:,} transactions from {clean['date_min']} to
  {clean['date_max']}, cleaned to {clean['clean_rows']:,} line items across
  {stats['customers']:,} identified customers — then segmented, clustered and costed.</p>
  <div class="cta">
    <a class="btn primary" href="{TABLEAU}">Open the dashboard</a>
    <a class="btn" href="{GITHUB}">Source code</a>
    <a class="btn" href="https://selvipatel.com">Selvi Patel</a>
  </div>
</header>

<div class="kpis">
  <div class="kpi"><b>{stats['customers']:,}</b><span>Customers analysed</span></div>
  <div class="kpi"><b>£{stats['total_revenue']/1e6:.1f}M</b><span>Revenue</span></div>
  <div class="kpi"><b>{stats['top20pct_revenue_share']:.1f}%</b><span>Revenue from the top 20%</span></div>
  <div class="kpi"><b>{findings['retention']['month_12']:.1f}%</b><span>Still buying at month 12</span></div>
</div>

<p class="lead">The business is carried by a small group it cannot afford to lose —
<em>and most of the people it acquires never come back.</em></p>

<section id="concentration">
  <h2>Revenue is concentrated</h2>
  <p class="say">Ranking all {stats['customers']:,} customers by spend and accumulating their
  revenue gives the curve below. It bends hard and early: the first fifth of customers carry
  {stats['top20pct_revenue_share']:.1f}% of everything.</p>
  <div class="grid2">
    <div class="card">
      <p class="chart-title">Cumulative revenue share</p>
      <figure>{pareto_svg()}
        <figcaption>Every customer, ranked highest spend first.</figcaption>
      </figure>
    </div>
    <div class="card">
      <p class="chart-title">Cohort retention</p>
      <figure>{retention_svg()}
        <figcaption>Mean across every monthly acquisition cohort.</figcaption>
      </figure>
    </div>
  </div>
</section>

<section id="dashboard">
  <h2>Interactive dashboard</h2>
  <p class="say">The same analysis published to Tableau Public: revenue and customer counts by
  segment, the cluster scatter, and a ranked contact list of the {lapsed_customers:,} high-value
  customers who have stopped buying. <a href="{TABLEAU}">Open it full size ↗</a></p>
  <div class="card scroll embed">
    <iframe src="{TABLEAU}?:showVizHome=no&amp;:embed=y&amp;:toolbar=no&amp;:tabs=no"
      title="Retail customer segmentation dashboard on Tableau Public"
      loading="lazy"></iframe>
  </div>
</section>

<section id="segments">
  <h2>Segments</h2>
  <p class="say">Seven groups from RFM quintile scoring — recency, frequency and monetary value,
  each scored 1 to 5, then mapped to named segments a team can actually act on.</p>
  <div class="card scroll"><table>
    <tr><th>Segment</th><th class="num">Customers</th><th class="num">% of base</th>
        <th>Revenue</th><th class="num">% of revenue</th><th class="num">Churned</th></tr>
    {seg_bars()}
  </table></div>
</section>

<section id="clusters">
  <h2>K-Means clusters</h2>
  <p class="say">Run independently of the rule-based segments above, on log-scaled recency,
  frequency and monetary value. <em>k</em> came from the elbow method rather than the silhouette:
  silhouette peaked at k=2, which splits customers into active and inactive — true, but nothing
  a team can do anything with.</p>
  <div class="card scroll"><table>
    <tr><th>Cluster</th><th class="num">Customers</th><th class="num">Median recency</th>
        <th class="num">Median orders</th><th class="num">Median spend</th>
        <th class="num">% of revenue</th></tr>
    {clusters_html()}
  </table></div>
</section>

<section id="retention">
  <h2>Cohort retention</h2>
  <p class="say">Each row is one month's new customers; each column is months since their first
  purchase. Retention falls from {findings['retention']['month_1']:.1f}% at month one to
  {findings['retention']['month_12']:.1f}% at month twelve.</p>
  <div class="card scroll"><table>{retention_table()}</table></div>
</section>

<section id="actions">
  <h2>What to do about it</h2>
  <p class="say">Three costed actions. Each states the assumption it rests on, because a number
  without its assumption is a guess wearing a suit.</p>
  <div class="recs">{recs()}</div>
  <div class="total">
    <b>£{findings['total_opportunity_gbp']:,.0f}</b>
    <span>total identified gross margin, on the assumptions stated above</span>
  </div>
</section>

<section id="method">
  <h2>Method &amp; limitations</h2>
  <div class="method">
    <div><strong>Cleaning</strong>{clean['raw_rows']:,} raw rows reduced to
      {clean['clean_rows']:,} ({clean['pct_dropped']}% dropped): cancelled invoices, non-product
      lines such as postage and bank charges, exact duplicates, and
      {clean['steps'][0]['rows_dropped']:,} rows with no customer ID.</div>
    <div><strong>Known bias</strong>Those missing-ID rows are guest checkouts — real sales that
      cannot be attributed to a person. They skew toward one-time buyers, so every segment here
      over-represents repeat customers. Stated rather than hidden.</div>
    <div><strong>Lifetime value</strong>AOV × orders per year × 30% assumed gross margin, where
      orders per year is measured over how long each customer has been <em>observed</em>, not over
      their active span — dividing by active span sends one-time buyers to infinity.</div>
    <div><strong>Churn</strong>No purchase within {stats['churn_days']} days of the
      {stats['snapshot_date']} snapshot. Four segments show 0% or 100% by construction, because
      the segments are themselves defined on recency.</div>
  </div>
</section>

<footer>
  Built by <a href="https://selvipatel.com">Selvi Patel</a> ·
  Python, Pandas, Scikit-Learn, SQL, Tableau ·
  Data: <a href="https://archive.ics.uci.edu/dataset/502/online+retail+ii">Online Retail II</a>,
  UCI Machine Learning Repository
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
