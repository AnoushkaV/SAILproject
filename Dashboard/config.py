"""
config.py - every setting of the SAIL2025 crowd-monitoring dashboard in one place.

Thresholds, colours, detection parameters and file paths are only defined here.
The other files read them from this module, so the dashboard can be tuned or moved to
another event / sensor network by editing this file only (NFO4).
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Files (MF1)
# ---------------------------------------------------------------------------
DASHBOARD_DIR = Path(__file__).resolve().parent
DATA_DIR = DASHBOARD_DIR.parent / "Data"
COUNTS_FILE = DATA_DIR / "SAIL2025_LVMA_cleaned.csv"      # output of SAIL2025_cleaned.ipynb
LOCATIONS_FILE = DATA_DIR / "sensor-location.xlsx"

INTERVAL_MIN = 3                       # one LVMA measurement = 3 minutes
EVENT_START = "2025-08-20 00:00"       # data outside the event period is ignored
EVENT_END = "2025-08-25 00:00"
LOCAL_TZ = "Europe/Amsterdam"

# Fixes to the location file (same as sensor-location_cleaned.ipynb)
SENSOR_RENAMES = {"GASA-06": "GASA-06-B"}   # GASA-06-B replaced GASA-06 (Azartplein B)
SENSORS_REMOVED = ["GVCV-09"]              # defect, not in the cleaned counts

# Readable location names (the location file uses names like "IJBoulevardA1").
# Sensors that are not listed keep the name from the location file.
LOCATION_NAMES = {
    "GASA-01-A1": "IJ-boulevard A1",
    "GASA-01-A2": "IJ-boulevard A2",
    "GASA-01-B": "IJ-boulevard B",
    "GASA-01-C": "IJ-boulevard C",
    "GASA-02-01": "Brug Oostertoegang 1",
    "GASA-02-02": "Brug Oostertoegang 2",
    "GASA-04": "CS ri. Oosterdokskade",
    "GASA-05-O": "Noorderpark Oost",
    "GASA-05-W": "Noorderpark West",
}

# Optional names for the two walking directions of a sensor: {sensor: (name A, name B)}.
# Direction A is the smallest bearing in the column names (e.g. GASA-03_105), B the opposite.
# Sensors that are not listed get compass labels such as "towards E (105°)".
DIRECTION_NAMES = {}

# ---------------------------------------------------------------------------
# Pressure levels (MF2, NFC2, NFO6)
# ---------------------------------------------------------------------------
# Based on flow per metre of effective walking width q (ped/min/m).
# Fruin (1971) walkway levels of service, converted from ped/min/ft to ped/min/m:
#     A <= 23 | B 23-33 | C 33-49 | D 49-66 | E 66-82 | F > 82
# grouped into the four colour levels of NFC2. A level starts at its lower bound (q >= bound).
# TO CHECK by the group (background research): the grouping of the Fruin levels.
LEVELS = [
    # key          label                 q from  colour     Fruin LOS
    ("normal",    "Normal",                0,   "#0f9d74", "A–B"),
    ("attention", "Attention",            33,   "#f0a500", "C"),
    ("threshold", "Threshold exceeded",   49,   "#a61e1e", "D–E"),
    ("crisis",    "Crisis",               82,   "#0b0b0b", "F"),
]
UNAVAILABLE = ("unavailable", "No valid data", "#b5b4ad")
# These five colours were checked with a colour-blindness simulation (protanopia and
# deuteranopia, NFC3): every pair stays distinguishable. Labels are always shown next to them.

LEVEL_KEYS = [lv[0] for lv in LEVELS]
LEVEL_LABEL = {lv[0]: lv[1] for lv in LEVELS} | {UNAVAILABLE[0]: UNAVAILABLE[1]}
LEVEL_COLOR = {lv[0]: lv[3] for lv in LEVELS} | {UNAVAILABLE[0]: UNAVAILABLE[2]}
LEVEL_LOS = {lv[0]: lv[4] for lv in LEVELS}
LEVEL_FROM = {lv[0]: lv[2] for lv in LEVELS}

# ---------------------------------------------------------------------------
# Sudden changes (MF4) - method of design alternative D2 (report 4.4/4.5)
# ---------------------------------------------------------------------------
# Reference = mean and standard deviation of the previous CHANGE_WINDOW intervals.
# An interval EXCEEDS when |N - mean| > CHANGE_K x std and the flow (now or reference)
# is at least CHANGE_MIN_LEVEL. A change is FLAGGED when CHANGE_PERSISTENCE consecutive
# intervals exceed in the same direction (limits false alarms).
CHANGE_WINDOW = 5          # 5 x 3 min = 15 min
CHANGE_K = 2.0
CHANGE_PERSISTENCE = 2
CHANGE_MIN_LEVEL = 50      # ped / 3 min

# ---------------------------------------------------------------------------
# Data quality (MF6, FC8)
# ---------------------------------------------------------------------------
# Missing values (NaN) are always "unavailable". A sensor that counts 0 in both directions
# for at least ZERO_RUN_MIN minutes, while it normally counts at least ZERO_RUN_REFERENCE
# pedestrians per 3 min at that time of day, is marked as suspect = unavailable.
ZERO_RUN_MIN = 60
ZERO_RUN_REFERENCE = 20    # ped / 3 min (median of all event days at the same time of day)

# ---------------------------------------------------------------------------
# Typical pattern (MF5, FO2)
# ---------------------------------------------------------------------------
# Typical = median of the OTHER event days at the same time of day, on 15-minute averages.
SMOOTH_INTERVALS = 5       # 5 x 3 min = 15-minute average
DEVIATION_MIN_TYPICAL = 10 # no % deviation when the typical count is below this (ped / 3 min)

# ---------------------------------------------------------------------------
# Presentation (MF3)
# ---------------------------------------------------------------------------
RANKING_TOP_N = 5          # FO1
ALERT_LOOKBACK_MIN = 60    # alerts list: sudden changes flagged in the last hour
ALERT_ACTIVE_MIN = 15      # map halo: sudden changes flagged in the last 15 minutes
TYPICAL_AHEAD_MIN = 60     # time series: typical pattern shown up to 1 h after "now"
CHART_WINDOWS = {"2h": ("Last 2 h", 120), "6h": ("Last 6 h", 360), "day": ("Since 00:00", None)}
REPLAY_SPEEDS = {          # label: milliseconds per 3-minute step
    "×180 (1 s = 3 min)": 1000,
    "×60 (3 s = 3 min)": 3000,
    "Real time (3 min)": 180_000,
}
LIVE_REFRESH_S = 180       # live mode: re-read the data source every 3 minutes (FO6)
DATA_MAX_AGE_MIN = 6       # live mode: warn when the latest measurement is older than this

MAP_VIEW_DEFAULT = "heat"  # "heat" = glow per sensor (heat-map view), "markers" = markers only
# Heat-map view: glow diameter in px = min + per_q * q, capped at max (q in ped/min/m) ...
HEAT_SIZE = (22, 1.4, 90)
# ... drawn as rings of (relative size, opacity), from outside to inside, for a soft edge
HEAT_LAYERS = [(1.0, 0.10), (0.82, 0.11), (0.64, 0.13), (0.46, 0.16), (0.3, 0.22)]

MAP_CENTER = {"lat": 52.3835, "lon": 4.9075}
MAP_ZOOM = 12.3
MAP_STYLE = {"light": "carto-positron", "dark": "carto-darkmatter"}

# Chart chrome per theme. Series colours are a colour-blind-checked categorical order;
# the sequential ramp (one hue, light -> dark) is used for the heat map.
THEMES = {
    "light": {
        "surface": "#fcfcfb", "page": "#f4f3f0", "ink": "#0b0b0b", "ink2": "#52514e",
        "muted": "#898781", "grid": "#e1e0d9", "axis": "#c3c2b7",
        "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"],
        "sequential": ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
    },
    "dark": {
        "surface": "#1a1a19", "page": "#0d0d0d", "ink": "#f0efec", "ink2": "#c3c2b7",
        "muted": "#898781", "grid": "#2c2c2a", "axis": "#383835",
        "series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"],
        "sequential": ["#0d366b", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"],
    },
}
