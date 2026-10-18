"""
sail_data.py - DATA COMPONENT of the dashboard.

    MF1  capture and prepare the flow data
         load the counts and the sensor locations, link every count to its location and
         effective walking width, calculate the step-4 indicators
    MF6  safeguard data reliability
         mark missing and suspect data as unavailable instead of showing it as 0 (FC8)

The formulas are the same as in SAIL2025_indicators_step4.ipynb. The analysis component
(sail_analysis.py) only uses the table returned by `build_base()`, so for live use only
`load_counts()` has to be replaced by a request to the LVMA data service (FO6).

No Dash or Plotly in this file: it can also be imported in a notebook.
"""
import numpy as np
import pandas as pd

import config as cfg

TIME_COLS = ["hour", "minute", "day", "month", "weekday", "is_weekend"]
STEP = pd.Timedelta(minutes=cfg.INTERVAL_MIN)


# ---------------------------------------------------------------------------
# MF1 - loading
# ---------------------------------------------------------------------------
def load_locations(path=cfg.LOCATIONS_FILE) -> pd.DataFrame:
    """Sensor id, location name, effective width (m) and lat/lon, one row per sensor."""
    loc = pd.read_excel(path)
    # \xa0 and double spaces in the column names -> one normal space
    loc.columns = loc.columns.str.replace(r"\s+", " ", regex=True).str.strip()
    loc = loc.rename(columns={"Objectummer": "sensor", "Locatienaam": "location_name",
                              "Effectieve breedte": "eff_width_m", "Lat/Long": "latlon"})
    loc["sensor"] = loc["sensor"].astype(str).str.strip().replace(cfg.SENSOR_RENAMES)
    loc = loc[~loc["sensor"].isin(cfg.SENSORS_REMOVED)].copy()

    loc["location_name"] = loc["sensor"].map(cfg.LOCATION_NAMES).fillna(loc["location_name"].str.strip())
    # decimal comma -> number
    loc["eff_width_m"] = pd.to_numeric(loc["eff_width_m"].astype(str).str.replace(",", ".", regex=False),
                                       errors="coerce")
    # "52.380686, 4.899041" (sometimes without a space) -> lat, lon
    latlon = loc["latlon"].astype(str).str.split(",", n=1, expand=True)
    loc["lat"] = pd.to_numeric(latlon[0].str.strip(), errors="coerce")
    loc["lon"] = pd.to_numeric(latlon[1].str.strip(), errors="coerce")
    return loc[["sensor", "location_name", "eff_width_m", "lat", "lon"]].reset_index(drop=True)


def load_counts(path=cfg.COUNTS_FILE) -> pd.DataFrame:
    """
    Wide count table: one row per 3-minute timestamp, one column per SENSOR_DIRECTION.

    Live use (FO6): replace the read_csv by a request to the LVMA data service that returns
    the same columns. Everything after this function stays the same.
    """
    counts = pd.read_csv(path)
    raw = counts["timestamp"].astype(str)
    if raw.str.contains(r"[+-]\d{2}:?\d{2}$").all():
        # timestamps with a UTC offset (e.g. +02:00) -> local wall-clock time without time zone
        ts = pd.to_datetime(raw, utc=True).dt.tz_convert(cfg.LOCAL_TZ).dt.tz_localize(None)
    else:
        ts = pd.to_datetime(raw)
    counts["timestamp"] = ts
    counts = counts[(ts >= pd.Timestamp(cfg.EVENT_START)) & (ts < pd.Timestamp(cfg.EVENT_END))]
    counts = counts.drop(columns=[c for c in TIME_COLS if c in counts.columns])

    # complete 3-minute grid: an interval that is missing in the source becomes NaN (MF6)
    counts = counts.drop_duplicates("timestamp").set_index("timestamp").sort_index()
    grid = pd.date_range(counts.index.min(), counts.index.max(), freq=STEP)
    return counts.reindex(grid).rename_axis("timestamp").reset_index()


# ---------------------------------------------------------------------------
# MF1 - link counts to locations, step-4 indicators
# ---------------------------------------------------------------------------
def to_long(counts: pd.DataFrame, loc: pd.DataFrame) -> pd.DataFrame:
    """One row per sensor x timestamp with the two walking directions next to each other."""
    sensor_cols = [c for c in counts.columns if c != "timestamp"]
    directions: dict[str, list[int]] = {}
    for col in sensor_cols:
        sensor, deg = col.rsplit("_", 1)
        directions.setdefault(sensor, []).append(int(deg))

    parts = []
    for sensor, degs in directions.items():
        degs = sorted(degs)
        a = degs[0]
        b = degs[1] if len(degs) > 1 else None
        parts.append(pd.DataFrame({
            "timestamp": counts["timestamp"],
            "sensor": sensor,
            "dir_A_deg": a,
            "dir_B_deg": b if b is not None else np.nan,
            "N_A": counts[f"{sensor}_{a}"].astype(float),
            "N_B": counts[f"{sensor}_{b}"].astype(float) if b is not None else np.nan,
            "n_dirs": len(degs),
        }))
    df = pd.concat(parts, ignore_index=True)

    unknown = sorted(set(df["sensor"]) - set(loc["sensor"]))
    if unknown:
        print(f"[sail_data] sensors without location / width (shown as unavailable): {unknown}")
    df = df.merge(loc, on="sensor", how="left")
    df["location_name"] = df["location_name"].fillna(df["sensor"])
    return df.sort_values(["sensor", "timestamp"]).reset_index(drop=True)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Step 4: N_total, Q, q, directional share and change between consecutive intervals."""
    # 1. count per 3 minutes - only if every direction of the sensor is available
    n_valid = df[["N_A", "N_B"]].notna().sum(axis=1)
    df["N_total"] = df[["N_A", "N_B"]].sum(axis=1).where(n_valid == df["n_dirs"])

    # 2. flow (ped/min) and flow per metre of effective width (ped/min/m)
    df["Q_total"] = df["N_total"] / cfg.INTERVAL_MIN
    df["Q_A"] = df["N_A"] / cfg.INTERVAL_MIN
    df["Q_B"] = df["N_B"] / cfg.INTERVAL_MIN
    df["q_specific"] = df["N_total"] / (cfg.INTERVAL_MIN * df["eff_width_m"])

    # 3. directional share (undefined when nobody passed)
    valid_total = df["N_total"].where(df["N_total"] > 0)
    df["share_A_pct"] = df["N_A"] / valid_total * 100
    df["share_B_pct"] = df["N_B"] / valid_total * 100

    # 4. change between two valid measurements of the same sensor, exactly 3 min apart
    g = df.groupby("sensor", sort=False)
    exactly_3min = g["timestamp"].diff() == STEP
    df["N_prev"] = g["N_total"].shift()
    df["dN_total"] = g["N_total"].diff().where(exactly_3min)
    df["dN_total_pct"] = df["dN_total"] / df["N_prev"].where(df["N_prev"] > 0) * 100
    return df


# ---------------------------------------------------------------------------
# MF6 - data reliability
# ---------------------------------------------------------------------------
def check_quality(df: pd.DataFrame) -> pd.DataFrame:
    """
    Status per sensor x interval:
        ok       valid measurement
        missing  no value (NaN), e.g. CMSA-GAWW-20 after its failure on 23 August
        suspect  0 in both directions for >= ZERO_RUN_MIN minutes while the sensor normally
                 counts >= ZERO_RUN_REFERENCE pedestrians at that time of day
    Only information up to the current interval is used, as it would be in live use.
    Missing and suspect counts are set to NaN, so they are never shown as 0 flow (FC8)
    and are left out of rankings, peaks and change detection (SF6.4).
    """
    df["slot"] = (df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute) // cfg.INTERVAL_MIN
    df["N_total_raw"] = df[["N_A", "N_B"]].sum(axis=1, min_count=1)
    reference = df.groupby(["sensor", "slot"])["N_total_raw"].transform("median")

    zero = df["N_total_raw"].eq(0)
    new_run = zero.ne(zero.groupby(df["sensor"]).shift()) | df["sensor"].ne(df["sensor"].shift())
    run_id = new_run.cumsum()
    zero_minutes = zero.astype(int).groupby(run_id).cumsum() * cfg.INTERVAL_MIN
    suspect_now = zero & (zero_minutes >= cfg.ZERO_RUN_MIN) & (reference >= cfg.ZERO_RUN_REFERENCE)
    # once suspect, the sensor stays suspect until it counts again (end of the zero run)
    suspect = suspect_now.astype(int).groupby(run_id).cummax().astype(bool)

    missing = df[["N_A", "N_B"]].isna().sum(axis=1) > (2 - df["n_dirs"])
    df["status"] = np.select([missing, suspect], ["missing", "suspect"], default="ok")
    df.loc[df["status"] != "ok", ["N_A", "N_B"]] = np.nan

    # time of the last valid measurement (SF6.3); for a suspect zero run: the last count before it
    ok = df["status"] == "ok"
    last_ok = df["timestamp"].where(ok).groupby(df["sensor"]).ffill()
    last_counting = df["timestamp"].where(ok & df["N_total_raw"].gt(0)).groupby(df["sensor"]).ffill()
    df["last_valid_ts"] = last_ok.where(df["status"] != "suspect", last_counting)
    return df


def build_base(counts: pd.DataFrame, loc: pd.DataFrame) -> pd.DataFrame:
    """Base table for the dashboard: one row = sensor x 3-minute interval."""
    df = to_long(counts, loc)
    df = check_quality(df)
    df = add_indicators(df)
    df["date"] = df["timestamp"].dt.normalize()
    df["hour"] = df["timestamp"].dt.hour
    df["label"] = df["location_name"] + " · " + df["sensor"]
    return df


def load_base() -> tuple[pd.DataFrame, pd.DataFrame]:
    loc = load_locations()
    return build_base(load_counts(), loc), loc
