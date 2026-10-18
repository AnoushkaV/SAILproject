"""
alerts_tab.py - ALERTS tab: the crowd manager chooses when she gets a pop-up (SF4.4).

An alert rule = which locations (empty = all locations) + at which pressure level
(attention / threshold exceeded / crisis) and/or on which events (sudden increase,
sudden decrease, sensor without valid data).

Every time the measurement time changes (replay, time slider or a live update), the rules are
checked against the new 3-minute interval. A pop-up appears when a location NEWLY reaches the
chosen level or a higher one - not again every 3 minutes while it stays at that level. A rise
to a higher level (attention -> threshold exceeded) gives a new pop-up.

The rules are remembered in the browser. All pop-ups of this session are kept in the alert history.

How it is connected in app.py (three lines):
    import alerts_tab
    alerts_tab.layout(DATA)            -> children of the "Alerts" tab
    alerts_tab.popup()                 -> once in the main layout (the pop-up itself + its stores)
    alerts_tab.register_callbacks(app, lambda: DATA)   -> in create_app()
"""
import time

import pandas as pd
from dash import ALL, Input, Output, State, ctx, dcc, html, no_update

import config as cfg

STEP = pd.Timedelta(minutes=cfg.INTERVAL_MIN)
RANK = {"unavailable": -1, "normal": 0, "attention": 1, "threshold": 2, "crisis": 3}
ALERT_LEVELS = ["attention", "threshold", "crisis"]
EVENTS = {"increase": "Sudden increase", "decrease": "Sudden decrease",
          "unavailable": "Sensor without valid data"}
DEFAULT_RULES = [{"id": "default", "sensors": [], "level": "threshold", "events": []}]
MAX_POPUP = 8          # messages shown at once in the pop-up
MAX_HISTORY = 300      # messages kept in the alert history


# ---------------------------------------------------------------------------
# small layout helpers
# ---------------------------------------------------------------------------
def _dot(level):
    return html.Span(className=f"dot {level}", style={"background": cfg.LEVEL_COLOR.get(level, cfg.UNAVAILABLE[2])})


def _field(label, child):
    return html.Div([html.Span(label, className="field-label"), child], className="field")


def _card(title, sub, children, cls):
    return html.Div([html.Div([html.Div([html.H2(title), html.P(sub, className="card-sub")])], className="card-head")]
                    + children, className=f"card {cls}")


def _location_options(data):
    s = data.sensors.sort_values("location_name")
    return [{"label": f"{n} · {sid}", "value": sid} for n, sid in zip(s["location_name"], s["sensor"])]


# ---------------------------------------------------------------------------
# layout
# ---------------------------------------------------------------------------
def layout(data):
    """Children of the Alerts tab: new rule, active rules + settings, alert history."""
    level_options = ([{"label": f"{cfg.LEVEL_LABEL[k]} or higher (q ≥ {cfg.LEVEL_FROM[k]})", "value": k}
                      for k in ALERT_LEVELS] + [{"label": "No level alert", "value": "none"}])
    new_rule = _card("New alert rule", "Choose where and when you want a pop-up", [
        html.Div(className="rule-form", children=[
            _field("Locations", dcc.Dropdown(id="al-sensors", options=_location_options(data), multi=True,
                                             placeholder="All locations")),
            _field("Pop-up when the pressure level reaches",
                   dcc.RadioItems(id="al-level", options=level_options, value="threshold", className="radio-stack")),
            _field("And/or on these events",
                   dcc.Checklist(id="al-events", value=[], className="radio-stack",
                                 options=[{"label": v, "value": k} for k, v in EVENTS.items()])),
            html.Div([html.Button("Add rule", id="al-add", className="btn primary"),
                      html.Span(id="al-msg", className="footnote")], className="inline"),
        ]),
    ], "span-5")

    rules = _card("Active rules", "A pop-up appears when at least one rule is met", [
        dcc.Checklist(id="al-settings", value=["on", "pause"], className="radio-stack",
                      options=[{"label": "Pop-ups on", "value": "on"},
                               {"label": "Pause the replay when a pop-up appears", "value": "pause"}]),
        html.Div(id="al-rules", className="rules"),
    ], "span-7")

    history = _card("Alert history", "Every pop-up of this session, newest first", [
        html.Div(html.Button("Clear history", id="al-clear", className="btn"), className="inline"),
        html.Div(id="al-history", className="table-wrap"),
    ], "span-12")

    return html.Div([html.Div([new_rule, rules], className="grid"), html.Div([history], className="grid")])


def popup():
    """The pop-up (top right, on every tab) and the stores of the alerts. Put this once in the main layout."""
    return html.Div([
        dcc.Store(id="al-rules-store", data=DEFAULT_RULES, storage_type="local"),
        dcc.Store(id="al-history-store", data=[]),
        dcc.Store(id="al-popup-store", data=[]),
        html.Div(id="al-popup", className="popup", style={"display": "none"}, role="alertdialog", children=[
            html.Div([html.Strong(id="al-popup-title"),
                      html.Button("Dismiss", id="al-popup-close", className="btn ghost")], className="popup-head"),
            html.Div(id="al-popup-body", className="popup-body"),
        ]),
    ])


# ---------------------------------------------------------------------------
# checking the rules (no Dash in here, so it can be tested on its own)
# ---------------------------------------------------------------------------
def find_alerts(data, t, rules) -> list[dict]:
    """Messages for all rules that are met at measurement time t (compared with t - 3 min)."""
    now = data.snapshot(t)
    if now.empty:
        return []
    now = now.set_index("sensor")
    prev = data.snapshot(t - STEP).set_index("sensor")
    ev = data.events[data.events["flagged_at"] == t].drop_duplicates("sensor").set_index("sensor")
    stamp = t.strftime("%a %d %b %H:%M")
    found = {}

    def add(sensor, kind, level, text):
        found[(sensor, kind)] = {"id": f"{sensor}|{kind}|{t:%Y%m%d%H%M}", "time": stamp, "sensor": sensor,
                                 "label": now.loc[sensor, "label"], "kind": kind, "level": level, "text": text}

    for rule in rules or []:
        for s in (rule.get("sensors") or list(now.index)):
            if s not in now.index:
                continue
            r = now.loc[s]
            level = str(r["level"])
            level_prev = str(prev.loc[s, "level"]) if s in prev.index else "normal"
            wanted = rule.get("level")
            if wanted and RANK[level] >= RANK[wanted] and RANK[level] > RANK[level_prev]:
                add(s, "level", level, f"{cfg.LEVEL_LABEL[level]}: q = {r['q_specific']:.1f} ped/min/m "
                                       f"({r['N_total']:.0f} ped / 3 min)")
            for kind in rule.get("events") or []:
                if kind in ("increase", "decrease") and s in ev.index and ev.loc[s, "type"] == kind:
                    e = ev.loc[s]
                    add(s, kind, level, f"{EVENTS[kind]}: {e['N_before']:.0f} → {e['N_at_flag']:.0f} ped / 3 min")
                if kind == "unavailable" and r["status"] != "ok" and (s not in prev.index or prev.loc[s, "status"] == "ok"):
                    add(s, kind, "unavailable", "No valid data from this sensor (failure or closure?)")
    return sorted(found.values(), key=lambda m: -RANK.get(m["level"], 0))


def _rule_text(rule, names):
    where = ("All locations" if not rule.get("sensors")
             else ", ".join(names.get(s, s) for s in rule["sensors"]))
    what = []
    if rule.get("level"):
        what.append(f"{cfg.LEVEL_LABEL[rule['level']]} or higher")
    what += [EVENTS[k] for k in rule.get("events") or []]
    return where, " · ".join(what)


# ---------------------------------------------------------------------------
# callbacks
# ---------------------------------------------------------------------------
def register_callbacks(app, get_data):
    """get_data() returns the current DashboardData (it is replaced in live mode)."""

    @app.callback(Output("al-rules-store", "data"), Output("al-msg", "children"),
                  Input("al-add", "n_clicks"), Input({"type": "al-del", "index": ALL}, "n_clicks"),
                  State("al-sensors", "value"), State("al-level", "value"), State("al-events", "value"),
                  State("al-rules-store", "data"), prevent_initial_call=True)
    def edit_rules(_, __, sensors, level, events, rules):
        rules = list(rules or [])
        trig = ctx.triggered_id
        if trig == "al-add":
            if level == "none" and not events:
                return no_update, "Choose a level or at least one event."
            rules.append({"id": f"r{time.time_ns()}", "sensors": sensors or [],
                          "level": None if level == "none" else level, "events": events or []})
            return rules, "Rule added."
        if isinstance(trig, dict) and any(t["value"] for t in ctx.triggered):
            return [r for r in rules if r["id"] != trig["index"]], "Rule removed."
        return no_update, no_update

    @app.callback(Output("al-rules", "children"), Input("al-rules-store", "data"))
    def show_rules(rules):
        if not rules:
            return html.P("No rules: you will not get pop-ups.", className="empty")
        names = dict(zip(get_data().sensors["sensor"], get_data().sensors["location_name"]))
        items = []
        for rule in rules:
            where, what = _rule_text(rule, names)
            items.append(html.Div(className="rule", children=[
                _dot(rule["level"]) if rule.get("level") else html.Span(className="dot", style={"background": "var(--accent)"}),
                html.Div([html.Div(what, className="rule-what"), html.Div(where, className="rule-where")]),
                html.Button("Remove", id={"type": "al-del", "index": rule["id"]}, n_clicks=0, className="btn ghost"),
            ]))
        return items

    @app.callback(Output("al-popup-store", "data"), Output("al-history-store", "data"),
                  Output("ticker", "disabled", allow_duplicate=True), Output("play", "children", allow_duplicate=True),
                  Input("day", "value"), Input("slot", "value"),
                  State("al-rules-store", "data"), State("al-settings", "value"), State("al-popup-store", "data"),
                  State("al-history-store", "data"), State("ticker", "disabled"), prevent_initial_call=True)
    def check(day, slot, rules, settings, current, history, ticker_disabled):
        settings = settings or []
        if "on" not in settings or not rules:
            return no_update, no_update, no_update, no_update
        msgs = find_alerts(get_data(), pd.Timestamp(day) + int(slot or 0) * STEP, rules)
        if not msgs:
            return no_update, no_update, no_update, no_update
        pause = "pause" in settings and not ticker_disabled
        return ((msgs + (current or []))[:MAX_POPUP], (msgs + (history or []))[:MAX_HISTORY],
                True if pause else no_update, "▶ Play" if pause else no_update)

    @app.callback(Output("al-popup", "style"), Output("al-popup-title", "children"),
                  Output("al-popup-body", "children"), Input("al-popup-store", "data"))
    def show_popup(msgs):
        if not msgs:
            return {"display": "none"}, "", []
        top = max(msgs, key=lambda m: RANK.get(m["level"], 0))["level"]
        items = [html.Div(className="popup-item", children=[
            _dot(m["level"]),
            html.Div([html.Div([html.B(m["label"]), html.Span(m["time"], className="popup-time")]),
                      html.Div(m["text"], className="popup-text")]),
            html.Button("Show", id={"type": "al-go", "index": m["id"]}, n_clicks=0, className="btn"),
        ]) for m in msgs]
        title = "1 new alert" if len(msgs) == 1 else f"{len(msgs)} new alerts"
        return {"display": "block", "borderTopColor": cfg.LEVEL_COLOR.get(top, cfg.UNAVAILABLE[2])}, title, items

    @app.callback(Output("al-popup-store", "data", allow_duplicate=True),
                  Input("al-popup-close", "n_clicks"), prevent_initial_call=True)
    def dismiss(_):
        return []

    @app.callback(Output("tabs", "value"), Output("location", "value", allow_duplicate=True),
                  Output("al-popup-store", "data", allow_duplicate=True),
                  Input({"type": "al-go", "index": ALL}, "n_clicks"), State("al-popup-store", "data"),
                  prevent_initial_call=True)
    def go_to_location(_, msgs):
        trig = ctx.triggered_id
        if not isinstance(trig, dict) or not any(t["value"] for t in ctx.triggered):
            return no_update, no_update, no_update
        return "monitoring", trig["index"].split("|")[0], [m for m in msgs or [] if m["id"] != trig["index"]]

    @app.callback(Output("al-history", "children"), Input("al-history-store", "data"))
    def show_history(history):
        if not history:
            return html.P("No alerts yet. Start the replay on the Monitoring tab.", className="empty")
        rows = [html.Tr([html.Td(m["time"]), html.Td(m["label"]),
                         html.Td(html.Span([_dot(m["level"]), m["text"]], className="lv"))]) for m in history]
        return html.Table([html.Thead(html.Tr([html.Th("Measurement time"), html.Th("Location"), html.Th("Alert")])),
                           html.Tbody(rows)], className="peaks")

    @app.callback(Output("al-history-store", "data", allow_duplicate=True),
                  Input("al-clear", "n_clicks"), prevent_initial_call=True)
    def clear_history(_):
        return []
