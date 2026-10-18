# SAIL2025 crowd monitor – dashboard

Interactive dashboard for crowd managers (during the event) and the SAIL Amsterdam Foundation
(evaluation afterwards), built on the cleaned LVMA pedestrian counts of SAIL2025 (20–24 August 2025).
Python + Dash/Plotly, open source, no licence costs.

## Run it (GitHub Codespaces or your own laptop)

The `Dashboard` folder sits next to the `Data` folder in the root of the repository:

```
SAILproject/
├── Data/
│   ├── SAIL2025_LVMA_cleaned.csv      ← output of SAIL2025_cleaned.ipynb
│   └── sensor-location.xlsx
└── Dashboard/
    ├── app.py  config.py  sail_data.py  sail_analysis.py  figures.py  check_data.py
    ├── assets/  (style.css, dashboard.js – loaded by Dash automatically)
    └── requirements.txt
```

In the terminal:

```bash
pip install -r Dashboard/requirements.txt
cd Dashboard
python app.py
```

Open http://127.0.0.1:8050. In Codespaces a pop-up "Open in Browser" appears; otherwise open the
**Ports** tab and click the globe icon next to port 8050. Stop the dashboard with `Ctrl+C`.

Options: `python app.py --live` (live mode, see below), `--port 8051`, `--debug` (auto-reload while you
edit the code). `python check_data.py` prints a summary of the data and analysis without a browser.

## What is on the screen

**Monitoring** (crowd manager, US1) – six elements:
1. *Measurement time banner* – time of the values shown, replay/live mode, number of locations per level.
2. *Map* – every sensor coloured by pressure level; grey = no valid data; soft grey halo = sudden change in the last 15 min. Click a marker to select it. In the **Heat map** view (default) every sensor gets a glow in its level colour that grows and becomes stronger with the flow per metre, so the busy places stand out at a glance; quiet places fade out. Switch to **Markers** for the plain markers. **Walking directions** (on by default) draws an arrow from every sensor in each walking direction; a longer, thicker arrow means more pedestrians per minute in that direction. Hover over the tip of an arrow for the numbers.
3. *Highest pressure now* – top 5 locations by flow per metre, with the attention and threshold lines.
4. *Sudden changes* – alerts flagged in the last hour, newest first. Click one to select that location.
5. *Location card* – count, flow per metre, deviation from the typical pattern, walking-direction split, peak today, data validity.
6. *Flow at the selected location* – count per 3 min against the typical pattern of the other event days (continued 1 h ahead), level lines, sudden-change markers, gaps for missing data; or both walking directions.

Controls: day, time slider and **Play** (replays the event as if it were live; ×180, ×60 or real time).

**Evaluation** (SAIL Amsterdam Foundation, US2): choose event days, hours and locations, then see the peak
table (peak count, peak flow per metre, time, level, number of sudden changes, valid data %), the minutes
per location above the normal level, an hour-by-location heat map, the daily pattern of one location on every
event day, and a timeline of all sudden changes. Peaks and sudden changes can be downloaded as CSV.

**Alerts** (crowd manager): she chooses when she gets a pop-up. A rule = locations (empty = all) + a pressure
level (attention / threshold exceeded / crisis "or higher") and/or events (sudden increase, sudden decrease,
sensor without valid data). The pop-up appears at the top right on every tab when a location *newly* reaches
the level (or rises to a higher one), so not again every 3 minutes. "Show" opens that location on the Monitoring
tab; by default the replay pauses when a pop-up appears. Rules are remembered in the browser; all pop-ups of the
session are listed in the alert history. Code: `alerts_tab.py` + `assets/alerts.css`.

## Code structure (architecture from report section 4.5)

| File | Component | Main functions |
|---|---|---|
| `sail_data.py` | Data component | MF1 load counts + locations, link to effective width, step-4 indicators · MF6 data quality |
| `sail_analysis.py` | Analysis component | MF2 levels, peaks, ranking · MF4 sudden changes · MF5 typical pattern, hourly averages |
| `figures.py`, `app.py` | Presentation component | MF3 all charts (`figures.py`), layout and interaction (`app.py`) |
| `alerts_tab.py` | Presentation component | SF4.4 alert rules and pop-ups (Alerts tab) |
| `config.py` | – | every threshold, colour and parameter (NFO4) |

Each component only uses the output of the previous one. The formulas for N, Q, q, directional share and ΔN
are identical to `SAIL2025_indicators_step4.ipynb` (checked: zero difference on all valid rows; run
`check_data.py` after the notebook to repeat the check).

## Methods and settings (all in `config.py`)

- **Pressure levels** – flow per metre q (ped/min/m) with Fruin's walkway levels of service converted to
  metric (A ≤ 23, B 23–33, C 33–49, D 49–66, E 66–82, F > 82), grouped into the four colours of NFC2:
  normal (A–B, q < 33), attention (C, q ≥ 33), threshold exceeded (D–E, q ≥ 49), crisis (F, q ≥ 82).
  **The grouping is an assumption the group should confirm** with the background research.
  In the SAIL data this gives 310 intervals "attention", 20 "threshold exceeded" (two ferry landings) and none "crisis".
- **Sudden changes** (design alternative D2) – reference = mean and SD of the previous 5 intervals (15 min).
  An interval exceeds when |N − mean| > 2 SD and the flow (now or reference) ≥ 50 ped/3 min. A change is
  flagged when 2 consecutive intervals exceed in the same direction. Result: 459 flags over 5 days
  (319 increases, 140 decreases).
- **Data quality** – a missing value is "no valid data". A sensor that counts 0 in both directions for ≥ 60 min
  while it normally counts ≥ 20 ped/3 min at that time of day is marked suspect. Unavailable data is never shown
  as 0 and is left out of rankings, peaks and change detection.
- **Typical pattern** – median of the 15-minute average on the *other* event days at the same time of day.
- **Colours** – the five level colours were checked with a colour-blindness simulation (protanopia/deuteranopia,
  all pairs distinguishable); level names are always shown next to the colour.

## Requirements → where they are implemented

Codes follow the chapter-2 draft; check them against your final report.

| Requirement | Implemented in |
|---|---|
| FC1 count per 3 min per location | location card, time series, map hover |
| FC2 flow per metre of effective width | `sail_data.add_indicators`; map colour, ranking, card |
| FC3 2D map of all sensors | Monitoring map (heat-map view or markers) |
| FC4 measurement time of every value | banner, card ("measured hh:mm"), all hovers |
| FC5 peak flow and time of peak | Evaluation peak table; card "peak today so far" |
| FC6 flag sudden increases/decreases | `sail_analysis.detect_sudden_changes`; alerts list, pop-ups, map halo, ▲▼ markers, timeline |
| FC7 select location, day, time window | Monitoring: day, time, location; Evaluation: days, hours, locations |
| FC8 missing/defective data as unavailable | `sail_data.check_quality`; grey markers, warning in card, grey bands in chart |
| NFC1 anonymous aggregated data | only 3-minute counts are used |
| NFC2 one colour scheme (green/orange/red/black) | `config.LEVELS`, used by every view |
| NFC3 colour-blind safe | checked palette + labels next to every colour |
| NFC4 no programming knowledge | browser interface, all choices by clicking |
| NFC5 Python with course data | Python, Dash, pandas |
| FO1 top-5 ranking by flow per metre | "Highest pressure now" |
| FO2 comparison with typical pattern | grey typical line, "vs typical" tile, daily pattern |
| FO3 directional and total flow | arrows on the map, "By direction" view, direction split in card |
| FO4 limit false alarms | persistence + minimum level (`config.CHANGE_*`) |
| FO5 line charts per location | time series, daily pattern |
| FO6 live data | `python app.py --live`; replace `load_counts()` by an API request |
| NFO1 busiest location found in ≤ 30 s | ranking at the top right + level counts in the banner (test with users) |
| NFO2 response ≤ 2 s | measured on the SAIL data: overview 0.07 s, detail 0.04 s, evaluation 0.26 s (server side) |
| NFO3 ≤ 6 visual elements per screen | Monitoring: 6 elements |
| NFO4 transferable | all event-specific settings in `config.py` |
| NFO5 completeness | "valid data" in card and peak table |
| NFO6 thresholds based on comfort/safety levels | Fruin levels in `config.LEVELS` |
| NFO7 low cost | open-source packages only |

## Live mode

`python app.py --live` re-reads the data source every 3 minutes and always shows the latest interval; the time
controls are then disabled and the banner shows how old the latest measurement is (with a warning when it is
older than 6 minutes). With the historical file it therefore warns that the data is outdated – that is
intended. For real live use only `load_counts()` in `sail_data.py` has to return the newest counts in the same
table format (for example from an LVMA API).

## Known limitations (useful for the evaluation chapter)

- Ferry-landing sensors (GVCV) count in bursts when a ferry arrives, so they produce many of the sudden-change
  flags. Consider separate parameters for these sensors when testing FO4.
- The zero-count rule cannot tell a sensor failure from a real closure or a time without ferries (e.g. early
  weekend mornings at some landings, Brug Oostertoegang on 23 Aug 10:48–13:24). The card therefore says
  "sensor failure or closure?".
- The typical pattern uses all other event days, including later days. That is fine for evaluation; in live use
  only earlier days (or a previous edition) would be available.
- The comparison with neighbouring sensors from alternative D2 is not implemented.
- The heat-map view is a glow per sensor, not a smoothed density surface: the counts are only measured at the
  sensors, so colours are not interpolated between them, and nearby sensors do not add up to a higher level.
  Where many sensors are close together (e.g. the Wallen area) the glows overlap and that area looks a bit
  more intense. Glow size and strength can be tuned with `HEAT_SIZE` and `HEAT_LAYERS` in `config.py`.
- The arrows on the map are drawn in metres, so they grow when you zoom in. Where sensors are close together
  (Wallen, CS) the arrows overlap at the default zoom; zoom in to separate them. Arrow size: `FLOW_*` in `config.py`.
- The map uses free CARTO base maps and needs an internet connection in the browser. Without it, start with
  `SAIL_MAP_STYLE=white-bg python app.py` to show the markers on a blank background.
