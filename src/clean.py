#!/usr/bin/env python3
"""Load and clean the Online Retail II transactions.

Every row dropped is counted and reported. The drop log is not bookkeeping --
it is the part of this project an interviewer will actually probe, because the
decisions here (especially dropping guest checkouts) bias everything downstream.
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "online_retail_II.xlsx"
OUT = ROOT / "data" / "clean_transactions.parquet"
LOG = ROOT / "outputs" / "cleaning_log.json"


def load() -> pd.DataFrame:
    # The workbook holds two sheets, one per year. Both are needed: two years
    # gives enough history for cohort retention to mean anything.
    sheets = pd.read_excel(RAW, sheet_name=None, engine="openpyxl")
    print(f"sheets found: {list(sheets)}")
    df = pd.concat(sheets.values(), ignore_index=True)
    df.columns = [c.strip().replace(" ", "") for c in df.columns]
    return df


def clean(df: pd.DataFrame):
    steps = []
    n0 = len(df)

    def drop(mask, reason):
        nonlocal df
        n = int(mask.sum())
        if n:
            df = df.loc[~mask].copy()
        steps.append({"reason": reason, "rows_dropped": n,
                      "rows_remaining": len(df)})
        print(f"  -{n:>7,}  {reason:<52} -> {len(df):,}")

    print(f"\nraw rows: {n0:,}\n")

    # Guest checkouts. These are real sales but cannot be attributed to a
    # customer, so they are unusable for segmentation. This is the single
    # biggest drop and the one worth being able to defend.
    drop(df["CustomerID"].isna(), "no CustomerID (guest checkout, unattributable)")

    # Cancellations: invoice numbers prefixed with C, mirrored by negative
    # quantities. Keeping them would understate frequency and monetary value.
    inv = df["Invoice"].astype(str)
    drop(inv.str.startswith("C"), "cancelled invoice (Invoice starts with 'C')")

    drop(df["Quantity"] <= 0, "non-positive quantity (returns/adjustments)")
    drop(df["Price"] <= 0, "non-positive price (free items/adjustments)")

    # Non-product stock codes: postage, bank charges, samples, manual entries.
    admin = df["StockCode"].astype(str).str.upper().isin(
        {"POST", "D", "DOT", "M", "S", "AMAZONFEE", "BANK CHARGES", "B", "CRUK",
         "PADS", "ADJUST", "ADJUST2", "TEST001", "TEST002", "GIFT"})
    drop(admin, "non-product line (postage, fees, manual adjustments)")

    drop(df.duplicated(), "exact duplicate row")

    df["CustomerID"] = df["CustomerID"].astype(int)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["Revenue"] = df["Quantity"] * df["Price"]
    # StockCode and Invoice mix ints with codes like '79323P' / 'C536379'.
    # Force to string so the column has one type end to end.
    for col in ("Invoice", "StockCode", "Description", "Country"):
        df[col] = df[col].astype(str)

    summary = {
        "raw_rows": n0,
        "clean_rows": len(df),
        "rows_dropped": n0 - len(df),
        "pct_dropped": round(100 * (n0 - len(df)) / n0, 1),
        "customers": int(df["CustomerID"].nunique()),
        "orders": int(df["Invoice"].nunique()),
        "products": int(df["StockCode"].nunique()),
        "countries": int(df["Country"].nunique()),
        "revenue_total": round(float(df["Revenue"].sum()), 2),
        "date_min": str(df["InvoiceDate"].min().date()),
        "date_max": str(df["InvoiceDate"].max().date()),
        "steps": steps,
    }
    return df, summary


if __name__ == "__main__":
    df, summary = clean(load())
    OUT.parent.mkdir(exist_ok=True)
    LOG.parent.mkdir(exist_ok=True)
    df.to_parquet(OUT, index=False)
    LOG.write_text(json.dumps(summary, indent=2))

    print(f"\n{'='*64}")
    print(f"raw            : {summary['raw_rows']:>12,}")
    print(f"clean          : {summary['clean_rows']:>12,}  "
          f"({summary['pct_dropped']}% dropped)")
    print(f"customers      : {summary['customers']:>12,}")
    print(f"orders         : {summary['orders']:>12,}")
    print(f"products       : {summary['products']:>12,}")
    print(f"revenue        : {summary['revenue_total']:>12,.0f} GBP")
    print(f"date range     : {summary['date_min']} to {summary['date_max']}")
    print(f"\nwrote {OUT.name} and {LOG.name}")
