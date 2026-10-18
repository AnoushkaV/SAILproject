"""
sail_analysis.py - ANALYSIS COMPONENT of the dashboard.

    MF2  assess pedestrian pressure per location   -> levels, peaks, ranking, time per level
    MF4  detect and signal sudden changes          -> rolling z-score with persistence
    MF5  analyse flow patterns over time and days  -> typical pattern, deviation, hourly averages

Input: the base table of sail_data.build_base(). No Dash or Plotly in this file.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import config as cfg
import sail_data

STEP = pd.Timedelta(minutes=cfg.INTERVAL_MIN)
LEVEL_ORDER = cfg.LEVEL_KEYS + [cfg.UNAVAILABLE[0]]


# ---------------------------------------------------------------------------
# MF2 - pressure level per interval
# ---------------------------------------------------------------------------
def assign_level(q: pd.Series) -> pd.Series:
    """Colour level from flow per metre q (ped/min/m); no valid q -> 'unavailable'."""
    bounds = [lv[2] for lv in cfg.LEVELS] + [np.inf]
    level = pd.cut(q, bins=bounds, labels=cfg.LEVEL_KEYS, right=False, include_lowest=True)
    level = level.astype(object).where(q.notna(), cfg.UNAVAILABLE[0])
    return pd.Categorical(level, categories=LEVEL_ORDER, ordered=True)


# ---------------------------------------------------------------------------
# MF5 - typical pattern of the other event days
# ---------------------------------------------------------------------------
def add_typical(df: pd.DataFrame) -> pd.DataFrame:
    """
    N15        15-minute average of the count (previous 5 intervals, as in live use)
    typical15  median of N15 on the OTHER event days at the same time of day (FO2)
    dev_pct    deviation of N15 from typical15 in %
    """
    df["N15"] = df.groupby("sensor", sort=False)["N_total"].transform(
        lambda s: s.rolling(cfg.SMOOTH_INTERVALS, min_periods=cfg.SMOOTH_INTERVALS).mean())

    wide = df.pivot_table(index=["sensor", "slot"], columns="date", values="N15", aggfunc="first",
                          dropna=False)
    typical = pd.DataFrame({day: wide.drop(columns=day).median(axis=1, skipna=True)
                            for day in wide.columns})
    typical = (typical.reset_index()
                      .melt(id_vars=["sensor", "slot"], var_name="date", value_name="typical15"))
    typical["date"] = pd.to_datetime(typical["date"])
    df = df.merge(typical, on=["sensor", "slot", "date"], how="left")

    ok_typ = df["typical15"].where(df["typical15"] >= cfg.DEVIATION_MIN_TYPICAL)
    df["dev_pct"] = (df["N15"] - ok_typ) / ok_typ * 100
    return df


# ---------------------------------------------------------------------------
# MF4 - sudden changes
# ---------------------------------------------------------------------------
def detect_sudden_changes(df: pd.DataFrame, window=cfg.CHANGE_WINDOW, k=cfg.CHANGE_K,
                          persistence=cfg.CHANGE_PERSISTENCE, min_level=cfg.CHANGE_MIN_LEVEL):
    """
    Rolling z-score with persistence (design alternative D2):
      reference   mean and standard deviation of the previous `window` intervals
      exceeds     |N - mean| > k * std  and  max(N, mean) >= min_level
                  (max(): a drop from a busy level to almost nobody is still relevant)
      flagged     `persistence` consecutive intervals exceed in the same direction
    The alert is raised at the interval where the persistence is first reached. Intervals
    without a complete valid reference (start of the data, after an outage) are not tested.

    Adds columns ref_mean, ref_std, change_sign, change_flag to df and returns (df, events).
    """
    g = df.groupby("sensor", sort=False)["N_total"]
    df["ref_mean"] = g.transform(lambda s: s.shift(1).rolling(window, min_periods=window).mean())
    df["ref_std"] = g.transform(lambda s: s.shift(1).rolling(window, min_periods=window).std())

    dev = df["N_total"] - df["ref_mean"]
    exceeds = (dev.abs() > k * df["ref_std"]) & (np.fmax(df["N_total"], df["ref_mean"]) >= min_level)
    sign = np.sign(dev).where(exceeds, 0).fillna(0).astype(int)
    df["change_sign"] = sign

    # position within a run of equal signs (per sensor)
    new_run = sign.ne(sign.groupby(df["sensor"]).shift()) | df["sensor"].ne(df["sensor"].shift())
    run_id = new_run.cumsum()
    run_pos = sign.groupby(run_id).cumcount() + 1
    flagged = (sign != 0) & (run_pos >= persistence)
    df["change_flag"] = np.where(flagged, np.where(sign > 0, "increase", "decrease"), "")

    raised = flagged & (run_pos == persistence)
    first = df.groupby(run_id)[["timestamp", "ref_mean"]].transform("first")
    last_ts = df.groupby(run_id)["timestamp"].transform("last")

    ev = df.loc[raised, ["sensor", "location_name", "label", "timestamp", "N_total",
                         "q_specific", "level"]].copy()
    ev = ev.rename(columns={"timestamp": "flagged_at", "N_total": "N_at_flag", "q_specific": "q_at_flag",
                            "level": "level_at_flag"})
    ev.insert(3, "type", np.where(sign[raised] > 0, "increase", "decrease"))
    ev["start"] = first.loc[raised, "timestamp"]
    ev["end"] = last_ts[raised]
    ev["N_before"] = first.loc[raised, "ref_mean"]
    ev["change"] = ev["N_at_flag"] - ev["N_before"]
    ev["change_pct"] = ev["change"] / ev["N_before"].where(ev["N_before"] > 0) * 100
    events = ev.sort_values("flagged_at").reset_index(drop=True)
    return df, events


# ---------------------------------------------------------------------------
# Everything the dashboard needs, computed once at start-up
# ---------------------------------------------------------------------------
@dataclass
class DashboardData:
    base: pd.DataFrame                  # sensor x interval, sorted by sensor, timestamp
    events: pd.DataFrame                # one row per sudden change
    loc: pd.DataFrame                   # sensor locations
    sensors: pd.DataFrame               # one row per sensor: name, width, lat/lon, directions
    by_time: pd.DataFrame = field(repr=False, default=None)   # base indexed by timestamp
    by_sensor: dict = field(repr=False, default_factory=dict)  # sensor -> rows of that sensor

    @property
    def timestamps(self) -> pd.DatetimeIndex:
        return self.by_time.index.unique()

    @property
    def days(self) -> list:
        return sorted(self.base["date"].unique())

    def snapshot(self, t) -> pd.DataFrame:
        """All sensors at one measurement time."""
        if t not in self.by_time.index:
            return self.by_time.iloc[0:0].reset_index()
        return self.by_time.loc[[t]].reset_index()


def prepare(base: pd.DataFrame, loc: pd.DataFrame) -> DashboardData:
    base = base.copy()
    base["level"] = assign_level(base["q_specific"])
    base = add_typical(base)
    base = base.sort_values(["sensor", "timestamp"]).reset_index(drop=True)
    base, events = detect_sudden_changes(base)

    sensors = (base.groupby("sensor", sort=True)
                   .agg(location_name=("location_name", "first"), label=("label", "first"),
                        eff_width_m=("eff_width_m", "first"), lat=("lat", "first"), lon=("lon", "first"),
                        dir_A_deg=("dir_A_deg", "first"), dir_B_deg=("dir_B_deg", "first"))
                   .reset_index())
    sensors["dir_A_name"] = [direction_name(s, a, 0) for s, a in zip(sensors.sensor, sensors.dir_A_deg)]
    sensors["dir_B_name"] = [direction_name(s, b, 1) for s, b in zip(sensors.sensor, sensors.dir_B_deg)]

    data = DashboardData(base=base, events=events, loc=loc, sensors=sensors)
    data.by_time = base.set_index("timestamp").sort_index()
    data.by_sensor = {s: d.reset_index(drop=True) for s, d in base.groupby("sensor", sort=False)}
    return data


def load() -> DashboardData:
    base, loc = sail_data.load_base()
    return prepare(base, loc)


# ---------------------------------------------------------------------------
# Helpers used by the dashboard views
# ---------------------------------------------------------------------------
COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def direction_name(sensor: str, deg, i: int) -> str:
    if sensor in cfg.DIRECTION_NAMES:
        return cfg.DIRECTION_NAMES[sensor][i]
    if pd.isna(deg):
        return "—"
    return f"towards {COMPASS[int(((deg % 360) + 22.5) // 45) % 8]} ({int(deg)}°)"


def ranking(snap: pd.DataFrame, n=cfg.RANKING_TOP_N) -> pd.DataFrame:
    """FO1: locations with the highest flow per metre at this moment (valid data only)."""
    return snap.dropna(subset=["q_specific"]).nlargest(n, "q_specific")


def recent_events(events: pd.DataFrame, t, minutes: int) -> pd.DataFrame:
    """Sudden changes flagged in (t - minutes, t], newest first."""
    sel = (events["flagged_at"] > t - pd.Timedelta(minutes=minutes)) & (events["flagged_at"] <= t)
    return events[sel].sort_values("flagged_at", ascending=False)


def select_period(base: pd.DataFrame, days=None, hours=(0, 24), sensors=None) -> pd.DataFrame:
    """Rows of the selected event days, hours [h0, h1) and sensors (FC7)."""
    sel = base["hour"].between(hours[0], hours[1] - 1)
    if days:
        sel &= base["date"].isin(pd.to_datetime(list(days)))
    if sensors:
        sel &= base["sensor"].isin(sensors)
    return base[sel]


def peak_table(sel: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """FC5: peak count and peak flow per metre per sensor, with time of the peak.
    Also the time spent per level (SF2.5), number of sudden changes and valid data share (NFO5)."""
    if sel.empty:
        return pd.DataFrame()
    valid = sel.dropna(subset=["q_specific"])
    rows = sel.groupby("sensor").agg(location_name=("location_name", "first"), label=("label", "first"),
                                     eff_width_m=("eff_width_m", "first"),
                                     valid_pct=("status", lambda s: (s == "ok").mean() * 100))
    for col in ("peak_N", "peak_q", "peak_time", "peak_level"):
        rows[col] = None
    if not valid.empty:
        idx = valid.groupby("sensor")["q_specific"].idxmax()
        peak = valid.loc[idx].set_index("sensor")
        rows["peak_N"] = peak["N_total"]
        rows["peak_q"] = peak["q_specific"]
        rows["peak_time"] = peak["timestamp"]
        rows["peak_level"] = peak["level"].astype(str)
    minutes = (sel.groupby(["sensor", "level"], observed=False).size().unstack(fill_value=0)
               * cfg.INTERVAL_MIN)
    for key in cfg.LEVEL_KEYS:
        rows[f"min_{key}"] = minutes[key] if key in minutes else 0
    rows["n_changes"] = (events_in(events, sel).groupby("sensor").size()
                         .reindex(rows.index, fill_value=0))
    rows = rows.reset_index()
    rows["peak_q"] = pd.to_numeric(rows["peak_q"])
    return rows.sort_values("peak_q", ascending=False, na_position="last").reset_index(drop=True)


def events_in(events: pd.DataFrame, sel: pd.DataFrame) -> pd.DataFrame:
    """Sudden changes that were flagged inside the selected days, hours and sensors."""
    if sel.empty:
        return events.iloc[0:0]
    ev = events[events["sensor"].isin(sel["sensor"].unique())]
    ev = ev[ev["flagged_at"].dt.normalize().isin(sel["date"].unique())
            & ev["flagged_at"].dt.hour.between(sel["hour"].min(), sel["hour"].max())]
    return ev


def hourly_flow(sel: pd.DataFrame) -> pd.DataFrame:
    """MF5: average flow per metre per sensor and clock hour (valid intervals only)."""
    h = sel.assign(hour_ts=sel["timestamp"].dt.floor("h"))
    return (h.groupby(["sensor", "label", "hour_ts"], observed=True)
             .agg(q_avg=("q_specific", "mean"), N_avg=("N_total", "mean"), n=("q_specific", "count"))
             .reset_index())
