"""
check_data.py - quick check of the data and analysis behind the dashboard (no browser needed).

    python check_data.py

Prints what the dashboard will show (sensors, data quality, levels, sudden changes, peaks) and,
if ../Data/indicators/step4_base_indicators.csv exists (output of SAIL2025_indicators_step4.ipynb),
checks that the dashboard calculates exactly the same indicators as the notebook.
"""
import numpy as np
import pandas as pd

import config as cfg
import sail_analysis as sa

data = sa.load()
b = data.base
print(f"Period: {b['timestamp'].min():%d %b %H:%M} – {b['timestamp'].max():%d %b %H:%M}, "
      f"{b['sensor'].nunique()} sensors, {len(b):,} sensor x 3-min rows")
print("\nData status (MF6):", b["status"].value_counts().to_dict())
bad = b[b["status"] != "ok"].groupby(["sensor", "status"]).size()
print(bad.to_string() if len(bad) else "  all valid")
print("\nIntervals per level (MF2):", b["level"].value_counts().reindex(sa.LEVEL_ORDER).to_dict())
print(f"\nSudden changes (MF4): {len(data.events)} "
      f"({(data.events['type'] == 'increase').sum()} increases, {(data.events['type'] == 'decrease').sum()} decreases)")
print("\nTop 5 peaks (FC5):")
peaks = sa.peak_table(b, data.events)
print(peaks.head(5)[["label", "peak_N", "peak_q", "peak_time", "peak_level"]]
      .round({"peak_q": 1}).to_string(index=False))

nb_file = cfg.DATA_DIR / "indicators" / "step4_base_indicators.csv"
if nb_file.exists():
    nb = pd.read_csv(nb_file)
    nb["timestamp"] = pd.to_datetime(nb["timestamp"].astype(str).str[:19])
    m = b.merge(nb, on=["sensor", "timestamp"], suffixes=("", "_nb"))
    ok = m["status"] == "ok"
    print(f"\nComparison with {nb_file.name} ({ok.sum():,} valid rows):")
    for col in ["N_total", "Q_total", "q_specific", "share_A_pct", "dN_total"]:
        diff = (m.loc[ok, col] - m.loc[ok, col + "_nb"]).abs().max()
        print(f"  {col:12s} max difference = {0 if pd.isna(diff) else diff:.6f}")
    print(f"  rows the dashboard marks as suspect (notebook keeps the 0 counts): {(m['status'] == 'suspect').sum()}")
else:
    print(f"\n(run SAIL2025_indicators_step4.ipynb first to compare with {nb_file.name})")
