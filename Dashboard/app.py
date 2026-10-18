"""
app.py - PRESENTATION COMPONENT of the SAIL2025 crowd-monitoring dashboard (MF3).

Run from the Dashboard folder:
    python app.py              historical data, with replay ("play") of the event
    python app.py --live       live mode: re-reads the data source every 3 minutes (FO6)
and open http://127.0.0.1:8050 (in Codespaces: the forwarded port 8050).

Two tabs:
    Monitoring  - for the crowd manager during the event (user story US1)
    Evaluation  - for the SAIL Amsterdam Foundation after the event (user story US2)
"""
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update

import config as cfg
import figures as figs
import sail_analysis as sa

STEP = pd.Timedelta(minutes=cfg.INTERVAL_MIN)
SLOTS_PER_DAY = 24 * 60 // cfg.INTERVAL_MIN
GRAPH_CONFIG = {"displaylogo": False, "displayModeBar": False}

DATA = sa.load()   # replaced on every refresh in live mode


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def ts_of(day: str, slot: int) -> pd.Timestamp:
    return pd.Timestamp(day) + int(slot or 0) * STEP


def day_slot(t: pd.Timestamp):
    return t.strftime("%Y-%m-%d"), int((t - t.normalize()) / STEP)


def fmt(x, digits=0, suffix=""):
    return "—" if x is None or pd.isna(x) else f"{x:,.{digits}f}{suffix}"


def fmt_age(delta: pd.Timedelta) -> str:
    minutes = delta.total_seconds() / 60
    if minutes < 60:
        return f"{minutes:.0f} min"
    if minutes < 48 * 60:
        return f"{minutes / 60:.1f} h"
    return f"{minutes / 1440:.0f} days"


def dot(level: str, large=False):
    return html.Span(className=f"dot {level}" + (" lg" if large else ""),
                     style={"background": cfg.LEVEL_COLOR[level]})


def field(label, child, cls=""):
    return html.Div([html.Span(label, className="field-label"), child], className=f"field {cls}")


def card(title, children, sub=None, cls="", head_extra=None, flush=False, card_id=None):
    head = html.Div([html.Div([html.H2(title)] + ([html.P(sub, className="card-sub")] if sub else [])),
                     head_extra if head_extra is not None else html.Span()], className="card-head")
    kwargs = {"id": card_id} if card_id else {}
    return html.Div([head] + children, className=f"card {'flush' if flush else ''} {cls}", **kwargs)


def level_key():
    items = [html.Span([dot(k), f"{cfg.LEVEL_LABEL[k]} "
                        + (f"q ≥ {cfg.LEVEL_FROM[k]}" if cfg.LEVEL_FROM[k] else f"q < {cfg.LEVEL_FROM['attention']}")],
                       className="item") for k in cfg.LEVEL_KEYS]
    items.append(html.Span([dot("unavailable"), cfg.LEVEL_LABEL["unavailable"]], className="item"))
    items.append(html.Span([html.Span(className="halo-key"), f"Sudden change (last {cfg.ALERT_ACTIVE_MIN} min)"],
                           className="item"))
    items.append(html.Span("Heat map: the glow grows with q = pedestrians per minute per metre of effective "
                           "width (Fruin levels)", className="item", style={"color": "var(--muted)"}))
    return html.Div(items, className="level-key")


def day_options(data):
    return [{"label": d.strftime("%a %d %b"), "value": d.strftime("%Y-%m-%d")} for d in data.days]


def location_options(data):
    s = data.sensors.sort_values("location_name")
    return [{"label": f"{n} · {sid}", "value": sid} for n, sid in zip(s["location_name"], s["sensor"])]


def busiest_moment(data):
    return data.base.groupby("timestamp")["N_total"].sum().idxmax()


# ---------------------------------------------------------------------------
# layout
# ---------------------------------------------------------------------------
def monitoring_tab(live: bool):
    t0 = DATA.timestamps.max() if live else busiest_moment(DATA)
    day0, slot0 = day_slot(t0)
    top_sensor = sa.ranking(DATA.snapshot(t0), 1)["sensor"]
    sensor0 = top_sensor.iloc[0] if len(top_sensor) else DATA.sensors["sensor"].iloc[0]
    marks = {i: f"{i * cfg.INTERVAL_MIN // 60:02d}:00" for i in range(0, SLOTS_PER_DAY, 60 // cfg.INTERVAL_MIN * 3)}

    filters = html.Div(className="filters", children=[
        field("Day", dcc.Dropdown(id="day", options=day_options(DATA), value=day0, clearable=False,
                                  searchable=False, disabled=live, style={"width": "150px"})),
        field("Time", dcc.Slider(id="slot", min=0, max=SLOTS_PER_DAY - 1, step=1, value=slot0, marks=marks,
                                 disabled=live, allow_direct_input=False, updatemode="mouseup",
                                 tooltip={"placement": "bottom", "transform": "slotToTime"}), cls="grow"),
        field("Replay", html.Div([
            html.Button("▶ Play", id="play", className="btn primary", disabled=live),
            dcc.Dropdown(id="speed", options=[{"label": k, "value": v} for k, v in cfg.REPLAY_SPEEDS.items()],
                         value=list(cfg.REPLAY_SPEEDS.values())[0], clearable=False, searchable=False,
                         disabled=live, style={"width": "190px"}),
        ], className="inline")),
        field("Location", dcc.Dropdown(id="location", options=location_options(DATA), value=sensor0,
                                       clearable=False), cls="wide"),
    ])

    view_toggle = html.Div(className="chart-options", children=[
        dcc.RadioItems(id="view", value="total", inline=True, className="radio-inline",
                       options=[{"label": "Total vs typical", "value": "total"},
                                {"label": "By direction", "value": "direction"}]),
        dcc.RadioItems(id="window", value="6h", inline=True, className="radio-inline",
                       options=[{"label": v[0], "value": k} for k, v in cfg.CHART_WINDOWS.items()]),
    ])
    return html.Div([
        filters,
        html.Div(id="banner", className="banner"),
        html.Div(className="grid", children=[
            card("Map of sensor locations", [
                dcc.Graph(id="map", config={**GRAPH_CONFIG, "scrollZoom": True}, style={"height": "470px"}),
                level_key()], sub="Colour = pressure level at the measurement time · click a marker to select it",
                head_extra=dcc.RadioItems(id="map-view", value=cfg.MAP_VIEW_DEFAULT, inline=True,
                                          className="radio-inline",
                                          options=[{"label": "Heat map", "value": "heat"},
                                                   {"label": "Markers", "value": "markers"}]),
                cls="span-7", flush=True),
            html.Div(className="span-5 stack", children=[
                card("Highest pressure now", [dcc.Graph(id="ranking", config=GRAPH_CONFIG)],
                     sub=f"Top {cfg.RANKING_TOP_N} locations by flow per metre · click a bar to select it"),
                card("Sudden changes", [html.Div(id="alerts", className="alerts")],
                     sub=(f"Flagged in the last {cfg.ALERT_LOOKBACK_MIN} min: {cfg.CHANGE_PERSISTENCE} intervals "
                          f"in a row more than {cfg.CHANGE_K:g} SD from the previous "
                          f"{cfg.CHANGE_WINDOW * cfg.INTERVAL_MIN} min")),
            ]),
        ]),
        html.Div(className="grid", children=[
            html.Div(id="loc-card", className="card span-4"),
            card("Flow at the selected location", [dcc.Graph(id="timeseries", config=GRAPH_CONFIG)],
                 sub="Count per 3 minutes · grey = typical for this time on the other event days",
                 head_extra=view_toggle, cls="span-8"),
        ]),
        dcc.Interval(id="ticker", interval=1000, disabled=True),
    ])


def evaluation_tab():
    days = day_options(DATA)
    busiest = sa.peak_table(DATA.base, DATA.events)["sensor"].iloc[0]
    marks = {h: f"{h:02d}:00" for h in range(0, 25, 3)}
    filters = html.Div(className="filters", children=[
        field("Event days", dcc.Checklist(id="ev-days", options=days, value=[d["value"] for d in days],
                                          inline=True, className="check-inline")),
        field("Hours", dcc.RangeSlider(id="ev-hours", min=0, max=24, step=1, value=[0, 24], marks=marks,
                                       allow_direct_input=False, pushable=1,
                                       tooltip={"placement": "bottom", "transform": "hourLabel"}), cls="grow"),
        field("Locations", dcc.Dropdown(id="ev-sensors", options=location_options(DATA), multi=True,
                                        placeholder="All locations"), cls="wide"),
        field("Download", html.Div([
            html.Button("Peaks (CSV)", id="dl-peaks-btn", className="btn"),
            html.Button("Sudden changes (CSV)", id="dl-events-btn", className="btn"),
            dcc.Download(id="dl-peaks"), dcc.Download(id="dl-events"),
        ], className="inline")),
    ])
    return html.Div([
        filters,
        html.Div(className="grid", children=[
            card("Peak flow per location", [html.Div(id="peak-table", className="table-wrap")],
                 sub="Highest 3-minute value in the selection · click a location for its daily pattern",
                 cls="span-8"),
            card("Time above the normal level", [dcc.Graph(id="level-minutes", config=GRAPH_CONFIG)],
                 sub="Minutes per location in each pressure level", cls="span-4"),
        ]),
        html.Div(className="grid", children=[
            card("Average flow per metre by hour", [dcc.Graph(id="heatmap", config=GRAPH_CONFIG)],
                 sub="Hourly average of q per location · blank = no valid data · click a row for its daily pattern",
                 cls="span-12"),
        ]),
        html.Div(className="grid", children=[
            card("Daily pattern", [dcc.Graph(id="daily", config=GRAPH_CONFIG)],
                 sub="The same location on each event day (15-minute averages)",
                 head_extra=dcc.Dropdown(id="focus", options=location_options(DATA), clearable=False,
                                         value=busiest, style={"width": "300px"}),
                 cls="span-6"),
            card("Sudden changes over the event", [dcc.Graph(id="timeline", config=GRAPH_CONFIG)],
                 sub="Where and when sudden increases and decreases were flagged", cls="span-6"),
        ]),
    ])


def build_layout(live: bool):
    return html.Div(className="app", children=[
        dcc.Store(id="theme", storage_type="local"),
        dcc.Store(id="data-version", data=0),
        dcc.Interval(id="live-refresh", interval=cfg.LIVE_REFRESH_S * 1000, disabled=not live),
        html.Header(className="topbar", children=[
            html.Div([html.H1("SAIL2025 crowd monitor"),
                      html.P("Pedestrian flows at the LVMA counting sensors · SAIL Amsterdam, 20–24 August 2025",
                             className="subtitle")]),
            html.Div([html.Button("Dark mode", id="theme-toggle", className="btn ghost")], className="topbar-right"),
        ]),
        dcc.Tabs(id="tabs", value="monitoring", className="tabs", mobile_breakpoint=0, children=[
            dcc.Tab(label="Monitoring", value="monitoring", className="tab", selected_className="tab--selected",
                    children=monitoring_tab(live)),
            dcc.Tab(label="Evaluation", value="evaluation", className="tab", selected_className="tab--selected",
                    children=evaluation_tab()),
        ]),
    ])


# ---------------------------------------------------------------------------
# monitoring views
# ---------------------------------------------------------------------------
def banner_children(t, snap, live):
    counts = snap["level"].astype(str).value_counts()
    chips = [html.Span([dot(k), html.B(int(counts.get(k, 0))), cfg.LEVEL_LABEL[k].lower()], className="level-chip")
             for k in cfg.LEVEL_KEYS + ["unavailable"]]
    if live:
        now = datetime.now(ZoneInfo(cfg.LOCAL_TZ)).replace(tzinfo=None)
        age = pd.Timestamp(now) - t
        stale = age > pd.Timedelta(minutes=cfg.DATA_MAX_AGE_MIN)
        mode = html.Span(f"Live · data {fmt_age(age)} old" + (" – outdated, check the data feed" if stale else ""),
                         className=f"mode-chip {'stale' if stale else 'live'}")
    else:
        mode = html.Span("Historical replay – not live data", className="mode-chip")
    return [
        html.Div([html.Span("Measurement time", className="label"),
                  html.Span(t.strftime("%a %d %b %Y · %H:%M"), className="value")], className="banner-time"),
        mode,
        html.Div(chips, className="level-chips", title="Number of sensor locations per pressure level"),
    ]


def alert_items(events):
    if events.empty:
        return [html.Div(f"No sudden changes in the last {cfg.ALERT_LOOKBACK_MIN} minutes.", className="empty")]
    items = []
    for _, e in events.head(12).iterrows():
        up = e["type"] == "increase"
        # a percentage from an almost empty reference (e.g. 1 -> 194) says little: then only the difference
        pct = (f" ({e['change']:+.0f}, {e['change_pct']:+.0f}%)" if e["N_before"] >= 20
               else f" ({e['change']:+.0f})")
        items.append(html.Button(
            id={"type": "alert", "index": f"{e['sensor']}|{e['flagged_at']:%Y%m%d%H%M}"},
            className="alert-item", n_clicks=0,
            children=[
                html.Span("▲" if up else "▼", className="arrow", **{"aria-label": e["type"]}),
                html.Span(e["flagged_at"].strftime("%H:%M"), className="time"),
                html.Span(e["label"], className="where"),
                html.Span(f"Sudden {e['type']}: {fmt(e['N_before'])} → {fmt(e['N_at_flag'])} ped / 3 min{pct}",
                          className="what"),
            ]))
    if len(events) > 12:
        items.append(html.Div(f"+ {len(events) - 12} earlier", className="empty"))
    return items


def location_card(info, rows, t):
    now = rows[rows["timestamp"] == t]
    if now.empty:
        return [html.P("No data for this moment.", className="empty")]
    r = now.iloc[0]
    level = str(r["level"])
    today = rows[(rows["date"] == t.normalize()) & (rows["timestamp"] <= t)]
    valid_today = (today["status"] == "ok").mean() * 100 if len(today) else float("nan")
    peak = today.dropna(subset=["q_specific"])
    peak = peak.loc[peak["q_specific"].idxmax()] if len(peak) else None

    children = [
        html.H3(info["location_name"], className="loc-title"),
        html.P(f"{info['sensor']} · effective width {fmt(info['eff_width_m'], 1)} m · measured {t:%H:%M}",
               className="loc-meta"),
        html.Div([dot(level, True), cfg.LEVEL_LABEL[level],
                  html.Span(f"Fruin LOS {cfg.LEVEL_LOS[level]}", className="los") if level in cfg.LEVEL_LOS else None],
                 className="badge"),
    ]
    if r["status"] != "ok":
        reason = ("no counts received" if r["status"] == "missing"
                  else f"0 counted for ≥ {cfg.ZERO_RUN_MIN} min while this location is normally busy "
                       "(sensor failure or closure?)")
        last = r["last_valid_ts"]
        children.append(html.Div(
            f"Data unavailable: {reason}. Last valid measurement: "
            f"{last:%a %d %b %H:%M}." if pd.notna(last) else f"Data unavailable: {reason}.", className="warn"))

    dev = r["dev_pct"]
    children.append(html.Div(className="tiles", children=[
        html.Div([html.Div("Last 3 minutes", className="t-label"), html.Div(fmt(r["N_total"]), className="t-value"),
                  html.Div("pedestrians, both directions", className="t-unit")], className="tile"),
        html.Div([html.Div("Flow per metre", className="t-label"), html.Div(fmt(r["q_specific"], 1), className="t-value"),
                  html.Div("ped/min/m", className="t-unit")], className="tile"),
        html.Div([html.Div("Vs typical", className="t-label"),
                  html.Div("—" if pd.isna(dev) else f"{dev:+.0f}%", className="t-value"),
                  html.Div("last 15 min vs other days", className="t-unit")], className="tile"),
    ]))

    share_a = r["share_A_pct"]
    if pd.notna(share_a):
        children += [
            html.Div("Walking direction (last 3 min)", className="t-label"),
            html.Div([html.Div(className="a", style={"width": f"{share_a:.0f}%"}),
                      html.Div(className="b", style={"width": f"{100 - share_a:.0f}%"})], className="split"),
            html.Div([html.Span([html.Span(className="key", style={"background": "var(--series-a)"}),
                                 f"{info['dir_A_name']}: {share_a:.0f}% ({fmt(r['N_A'])})"]),
                      html.Span([html.Span(className="key", style={"background": "var(--series-b)"}),
                                 f"{info['dir_B_name']}: {100 - share_a:.0f}% ({fmt(r['N_B'])})"])],
                     className="split-legend"),
        ]
    facts = [
        ("Peak today so far", "—" if peak is None else
         f"{peak['q_specific']:.1f} ped/min/m at {peak['timestamp']:%H:%M} ({fmt(peak['N_total'])} / 3 min)"),
        ("Typical now (other days)", f"{fmt(r['typical15'])} ped / 3 min"),
        ("Valid data today", fmt(valid_today, 0, "%")),
    ]
    children.append(html.Ul([html.Li([html.Span(k), html.Span(v)]) for k, v in facts], className="facts"))
    return children


# ---------------------------------------------------------------------------
# evaluation views
# ---------------------------------------------------------------------------
def peak_table_children(peaks):
    if peaks.empty:
        return html.P("No data in this selection.", className="empty")
    head = html.Tr([html.Th("Location"), html.Th("Width m", className="num"),
                    html.Th("Peak / 3 min", className="num", title="Highest count in 3 minutes, both directions"),
                    html.Th("Peak q", className="num", title="Highest flow per metre, ped/min/m"),
                    html.Th("Time of peak"), html.Th("Level at peak"),
                    html.Th("Changes", className="num", title="Number of sudden changes flagged"),
                    html.Th("Valid", className="num", title="Share of 3-minute intervals with valid data")])
    rows = []
    for _, p in peaks.iterrows():
        lvl = p["peak_level"] if isinstance(p["peak_level"], str) else "unavailable"
        rows.append(html.Tr([
            html.Td(html.Button(p["label"], className="row-link", title=p["label"],
                                id={"type": "peak-row", "index": p["sensor"]}, n_clicks=0)),
            html.Td(fmt(p["eff_width_m"], 1), className="num"),
            html.Td(fmt(p["peak_N"]), className="num"),
            html.Td(fmt(p["peak_q"], 1), className="num"),
            html.Td("—" if pd.isna(p["peak_time"]) else pd.Timestamp(p["peak_time"]).strftime("%a %d %b %H:%M")),
            html.Td(html.Span([dot(lvl), cfg.LEVEL_LABEL[lvl]], className="lv")),
            html.Td(int(p["n_changes"]), className="num"),
            html.Td(fmt(p["valid_pct"], 0, "%"), className="num"),
        ]))
    return html.Table([html.Thead(head), html.Tbody(rows)], className="peaks")


def label_order(peaks):
    """Locations sorted by peak flow per metre (busiest first) - same order in every chart."""
    return list(peaks["label"]) if not peaks.empty else []


# ---------------------------------------------------------------------------
# app + callbacks
# ---------------------------------------------------------------------------
def create_app(live=False) -> Dash:
    app = Dash(__name__, title="SAIL2025 crowd monitor", suppress_callback_exceptions=True)
    app.layout = build_layout(live)

    # theme: OS preference on first visit, then the toggle; remembered in the browser
    app.clientside_callback(
        """
        function(n, stored) {
            var theme = stored;
            if (!theme) {
                theme = (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
            } else if (n) {
                theme = stored === 'dark' ? 'light' : 'dark';
            }
            document.documentElement.setAttribute('data-theme', theme);
            return [theme, theme === 'dark' ? 'Light mode' : 'Dark mode'];
        }
        """,
        Output("theme", "data"), Output("theme-toggle", "children"),
        Input("theme-toggle", "n_clicks"), State("theme", "data"),
    )

    # ---- replay ------------------------------------------------------------
    @app.callback(Output("ticker", "disabled"), Output("play", "children"), Output("ticker", "interval"),
                  Input("play", "n_clicks"), Input("speed", "value"), State("ticker", "disabled"))
    def toggle_play(_, speed, disabled):
        if ctx.triggered_id == "play":
            disabled = not disabled
        return disabled, ("⏸ Pause" if not disabled else "▶ Play"), speed

    @app.callback(Output("slot", "value"), Output("day", "value"),
                  Input("ticker", "n_intervals"), State("slot", "value"), State("day", "value"),
                  prevent_initial_call=True)
    def tick(_, slot, day):
        t = ts_of(day, slot) + STEP
        if t > DATA.timestamps.max():
            return no_update, no_update
        new_day, new_slot = day_slot(t)
        return new_slot, (new_day if new_day != day else no_update)

    # ---- live mode: re-read the data source every LIVE_REFRESH_S seconds (FO6) ----
    if live:
        @app.callback(Output("data-version", "data"),
                      Output("day", "value", allow_duplicate=True), Output("slot", "value", allow_duplicate=True),
                      Input("live-refresh", "n_intervals"), prevent_initial_call="initial_duplicate")
        def refresh(n):
            global DATA
            if n:
                DATA = sa.load()
            d, s = day_slot(DATA.timestamps.max())
            return n or 0, d, s

    # ---- select a location: map, ranking or alert ----------------------------
    @app.callback(Output("location", "value"),
                  Input("map", "clickData"), Input("ranking", "clickData"),
                  Input({"type": "alert", "index": ALL}, "n_clicks"), prevent_initial_call=True)
    def pick_location(map_click, rank_click, _):
        trig = ctx.triggered_id
        if trig == "map" and map_click:
            return map_click["points"][0]["customdata"][0]
        if trig == "ranking" and rank_click:
            return rank_click["points"][0]["customdata"][0]
        if isinstance(trig, dict) and trig.get("type") == "alert" and any(t["value"] for t in ctx.triggered):
            return trig["index"].split("|")[0]
        return no_update

    # ---- overview: banner, map, ranking, alerts ------------------------------
    @app.callback(Output("banner", "children"), Output("map", "figure"), Output("ranking", "figure"),
                  Output("alerts", "children"),
                  Input("day", "value"), Input("slot", "value"), Input("location", "value"),
                  Input("map-view", "value"), Input("theme", "data"), Input("data-version", "data"))
    def update_overview(day, slot, sensor, map_view, theme, _):
        t = ts_of(day, slot)
        snap = DATA.snapshot(t)
        active = sa.recent_events(DATA.events, t, cfg.ALERT_ACTIVE_MIN)["sensor"].unique()
        recent = sa.recent_events(DATA.events, t, cfg.ALERT_LOOKBACK_MIN)
        return (banner_children(t, snap, live),
                figs.map_figure(snap, sensor, active, theme, map_view),
                figs.ranking_figure(sa.ranking(snap), theme),
                alert_items(recent))

    # ---- detail: selected location -----------------------------------------
    @app.callback(Output("loc-card", "children"), Output("timeseries", "figure"),
                  Input("day", "value"), Input("slot", "value"), Input("location", "value"),
                  Input("window", "value"), Input("view", "value"), Input("theme", "data"),
                  Input("data-version", "data"))
    def update_detail(day, slot, sensor, window, view, theme, _):
        t = ts_of(day, slot)
        rows = DATA.by_sensor.get(sensor)
        if rows is None:
            return [html.P("Select a location.", className="empty")], figs.empty_figure("Select a location", theme, 330)
        info = DATA.sensors.set_index("sensor").loc[sensor].to_dict() | {"sensor": sensor}
        fig = figs.timeseries_figure(rows, info, t, cfg.CHART_WINDOWS[window][1], view, DATA.events, theme)
        return location_card(info, rows, t), fig

    # ---- evaluation ----------------------------------------------------------
    def evaluation_selection(days, hours, sensors):
        return sa.select_period(DATA.base, days or ["1900-01-01"], tuple(hours or (0, 24)), sensors)

    @app.callback(Output("peak-table", "children"), Output("level-minutes", "figure"),
                  Output("heatmap", "figure"), Output("timeline", "figure"),
                  Input("ev-days", "value"), Input("ev-hours", "value"), Input("ev-sensors", "value"),
                  Input("theme", "data"), Input("data-version", "data"))
    def update_evaluation(days, hours, sensors, theme, _):
        sel = evaluation_selection(days, hours, sensors)
        peaks = sa.peak_table(sel, DATA.events)
        order = label_order(peaks)
        return (peak_table_children(peaks),
                figs.level_minutes_figure(peaks, theme),
                figs.heatmap_figure(sa.hourly_flow(sel), order, theme),
                figs.change_timeline_figure(sa.events_in(DATA.events, sel), order, theme))

    @app.callback(Output("focus", "value"),
                  Input("heatmap", "clickData"), Input({"type": "peak-row", "index": ALL}, "n_clicks"),
                  Input("timeline", "clickData"), prevent_initial_call=True)
    def pick_focus(heat_click, _, line_click):
        trig = ctx.triggered_id
        label_to_sensor = dict(zip(DATA.sensors["label"], DATA.sensors["sensor"]))
        if trig == "heatmap" and heat_click:
            return label_to_sensor.get(heat_click["points"][0]["y"], no_update)
        if trig == "timeline" and line_click:
            return label_to_sensor.get(line_click["points"][0]["customdata"][0], no_update)
        if isinstance(trig, dict) and any(t["value"] for t in ctx.triggered):
            return trig["index"]
        return no_update

    @app.callback(Output("daily", "figure"),
                  Input("focus", "value"), Input("ev-days", "value"), Input("ev-hours", "value"),
                  Input("theme", "data"), Input("data-version", "data"))
    def update_daily(sensor, days, hours, theme, _):
        rows = DATA.by_sensor.get(sensor, pd.DataFrame())
        info = DATA.sensors.set_index("sensor").loc[sensor].to_dict() if sensor in DATA.by_sensor else {}
        return figs.daily_pattern_figure(rows, DATA.days, days, tuple(hours or (0, 24)), info, theme)

    @app.callback(Output("dl-peaks", "data"), Input("dl-peaks-btn", "n_clicks"),
                  State("ev-days", "value"), State("ev-hours", "value"), State("ev-sensors", "value"),
                  prevent_initial_call=True)
    def download_peaks(_, days, hours, sensors):
        peaks = sa.peak_table(evaluation_selection(days, hours, sensors), DATA.events)
        peaks = peaks.round({"valid_pct": 1, "peak_q": 2})
        return dcc.send_data_frame(peaks.drop(columns=["label"], errors="ignore").to_csv,
                                   "sail2025_peaks.csv", index=False)

    @app.callback(Output("dl-events", "data"), Input("dl-events-btn", "n_clicks"),
                  State("ev-days", "value"), State("ev-hours", "value"), State("ev-sensors", "value"),
                  prevent_initial_call=True)
    def download_events(_, days, hours, sensors):
        ev = sa.events_in(DATA.events, evaluation_selection(days, hours, sensors))
        ev = ev.round({"N_before": 1, "change": 1, "change_pct": 1, "q_at_flag": 2})
        return dcc.send_data_frame(ev.drop(columns=["label"], errors="ignore").to_csv,
                                   "sail2025_sudden_changes.csv", index=False)

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SAIL2025 crowd-monitoring dashboard")
    parser.add_argument("--live", action="store_true", help="re-read the data source every 3 minutes")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    create_app(live=args.live).run(host=args.host, port=args.port, debug=args.debug)
