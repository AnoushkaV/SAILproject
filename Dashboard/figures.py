"""
figures.py - the charts of the dashboard (part of the PRESENTATION COMPONENT, MF3).

Every function gets prepared data and a theme name ("light" / "dark") and returns a Plotly
figure. Team members can add or replace a visualisation here without touching the
callbacks in app.py.

Colour rules (NFC2, NFC3):
- pressure levels always use cfg.LEVEL_COLOR (green / orange / red / black, grey = no data)
  and are always shown with their label;
- series that are not a level (directions, days, increase/decrease) use the categorical
  colours of the theme, never the level colours.
"""
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go

import config as cfg

FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
DAY_FMT = "%a %d %b"
MAP_STYLE_OVERRIDE = os.environ.get("SAIL_MAP_STYLE")  # e.g. "white-bg" when there is no internet


def _t(theme):
    return cfg.THEMES.get(theme, cfg.THEMES["light"])


def base_layout(theme, **kwargs):
    t = _t(theme)
    axis = dict(gridcolor=t["grid"], linecolor=t["axis"], zeroline=False, showline=True,
                tickfont=dict(color=t["muted"], size=11), title_font=dict(color=t["ink2"], size=12),
                ticks="", automargin=True)
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=t["ink2"]),
        margin=dict(l=8, r=12, t=8, b=8),
        hoverlabel=dict(bgcolor=t["surface"], bordercolor=t["axis"],
                        font=dict(family=FONT, color=t["ink"], size=12)),
        xaxis=dict(axis), yaxis=dict(axis),
        showlegend=False,
        legend=dict(orientation="h", x=0, y=1.02, xanchor="left", yanchor="bottom",
                    font=dict(color=t["ink2"], size=12), bgcolor="rgba(0,0,0,0)", itemclick="toggle"),
    )
    layout.update(kwargs)
    return layout


def empty_figure(message, theme, height=None):
    t = _t(theme)
    fig = go.Figure()
    fig.update_layout(**base_layout(theme, height=height))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
                       font=dict(color=t["muted"], size=13))
    return fig


def _fmt(x, digits=0, unit=""):
    if x is None or pd.isna(x):
        return "—"
    return f"{x:,.{digits}f}{unit}"


# ---------------------------------------------------------------------------
# Monitoring view
# ---------------------------------------------------------------------------
def _heat_layers(snap):
    """Heat-map view: a soft glow around every sensor with valid data. The glow has the colour of
    the pressure level and grows with the flow per metre, so busy places stand out at a glance.
    The colours are not smeared out between sensors (nothing is measured there), and nearby
    sensors do not add up to a higher level."""
    v = snap.dropna(subset=["q_specific"]).sort_values("q_specific")   # busiest drawn on top
    if v.empty:
        return []
    q = v["q_specific"].to_numpy()
    size_min, per_q, size_max = cfg.HEAT_SIZE
    size = np.clip(size_min + per_q * q, size_min, size_max)
    # quiet places fade out, busy places glow: full strength from the attention level upwards
    strength = 0.3 + 0.7 * np.clip(q / cfg.LEVEL_FROM["attention"], 0, 1)
    color = v["level"].astype(str).map(cfg.LEVEL_COLOR)
    return [go.Scattermap(lat=v["lat"], lon=v["lon"], mode="markers", hoverinfo="skip",
                          marker=dict(size=size * scale, color=color, opacity=opacity * strength))
            for scale, opacity in cfg.HEAT_LAYERS]


def _offset(lat, lon, bearing_deg, forward_m, right_m=0.0):
    """Point at forward_m metres in the compass direction bearing_deg (and right_m to the right)."""
    th = np.radians(bearing_deg)
    east = np.sin(th) * forward_m + np.cos(th) * right_m
    north = np.cos(th) * forward_m - np.sin(th) * right_m
    return lat + north / 111_320, lon + east / (111_320 * np.cos(np.radians(lat)))


def _flow_layers(snap, sensors, theme):
    """FO3 on the map: an arrow from each sensor in each walking direction. The longer and thicker
    the arrow, the more pedestrians per minute walk in that direction."""
    t = _t(theme)
    info = sensors.set_index("sensor")
    base, per_q, max_len = cfg.FLOW_LENGTH
    bins = {w: ([], []) for _, w in cfg.FLOW_WIDTH}           # line width -> (lats, lons)
    tips = []
    for _, r in snap.dropna(subset=["lat", "lon"]).iterrows():
        for col, deg_col, name_col in (("Q_A", "dir_A_deg", "dir_A_name"), ("Q_B", "dir_B_deg", "dir_B_name")):
            q, deg = r[col], r[deg_col]
            if pd.isna(q) or pd.isna(deg) or q < cfg.FLOW_MIN:
                continue
            length = min(base + per_q * q, max_len)
            head = min(max(0.3 * length, 25), 80)
            lat0, lon0 = r["lat"], r["lon"]
            tip = _offset(lat0, lon0, deg, length)
            left = _offset(lat0, lon0, deg, length - head, -0.6 * head)
            right = _offset(lat0, lon0, deg, length - head, 0.6 * head)
            width = [w for start, w in cfg.FLOW_WIDTH if q >= start][-1]
            lats, lons = bins[width]
            lats += [lat0, tip[0], None, left[0], tip[0], right[0], None]
            lons += [lon0, tip[1], None, left[1], tip[1], right[1], None]
            tips.append((tip[0], tip[1], r["sensor"], r["location_name"], info.loc[r["sensor"], name_col],
                         q, q * cfg.INTERVAL_MIN))
    traces = [go.Scattermap(lat=lats, lon=lons, mode="lines", hoverinfo="skip",
                            line=dict(width=w, color=t["series"][0]), opacity=0.9)
              for w, (lats, lons) in bins.items() if lats]
    if tips:
        tp = pd.DataFrame(tips, columns=["lat", "lon", "sensor", "name", "dir", "Q", "N"])
        traces.append(go.Scattermap(
            lat=tp["lat"], lon=tp["lon"], mode="markers", marker=dict(size=16, color="rgba(0,0,0,0)"),
            customdata=np.column_stack([tp["sensor"], tp["name"], tp["dir"], tp["Q"].round(0), tp["N"].round(0)]),
            hovertemplate="<b>%{customdata[1]}</b> · %{customdata[0]}<br>Walking %{customdata[2]}<br>"
                          "<b>%{customdata[3]} ped/min</b> (%{customdata[4]} per 3 min)<extra></extra>"))
    return traces


def map_figure(snap, selected, alert_sensors, theme, view="heat", flows=False, sensors=None):
    """FC3 / SF3.2: 2D map, one marker per sensor coloured by pressure level (grey = no data).
    view="heat" adds a glow per sensor that grows with the flow per metre (heat-map view).
    A soft halo marks sensors with a sudden change in the last minutes (SF4.4)."""
    t = _t(theme)
    snap = snap.dropna(subset=["lat", "lon"])
    level = snap["level"].astype(str)
    heat = view == "heat"
    fig = go.Figure(_heat_layers(snap) if heat else [])
    flow_traces = _flow_layers(snap, sensors, theme) if flows and sensors is not None else []
    for tr in flow_traces[:-1] if flow_traces else []:      # arrows below the markers
        fig.add_trace(tr)

    halo = snap[snap["sensor"].isin(alert_sensors)]
    if len(halo):
        fig.add_trace(go.Scattermap(lat=halo["lat"], lon=halo["lon"], mode="markers", hoverinfo="skip",
                                    marker=dict(size=38, color=t["ink"], opacity=0.22)))
    sel = snap[snap["sensor"] == selected]
    if len(sel):
        fig.add_trace(go.Scattermap(lat=sel["lat"], lon=sel["lon"], mode="markers", hoverinfo="skip",
                                    marker=dict(size=23 if heat else 27, color=t["ink"])))
    # surface ring so overlapping markers stay readable; light ring for black (crisis) in dark mode
    ring = np.where((level == "crisis") & (theme == "dark"), t["ink2"], t["surface"])
    fig.add_trace(go.Scattermap(lat=snap["lat"], lon=snap["lon"], mode="markers", hoverinfo="skip",
                                marker=dict(size=16 if heat else 20, color=ring)))

    custom = np.column_stack([
        snap["sensor"], snap["location_name"], level.map(cfg.LEVEL_LABEL),
        [_fmt(v) for v in snap["N_total"]], [_fmt(v, 1) for v in snap["q_specific"]],
        snap["timestamp"].dt.strftime("%a %d %b %H:%M"),
        [("Last valid measurement " + v.strftime("%a %H:%M")) if (s != "ok" and pd.notna(v)) else ""
         for s, v in zip(snap["status"], snap["last_valid_ts"])],
    ])
    fig.add_trace(go.Scattermap(
        lat=snap["lat"], lon=snap["lon"], mode="markers",
        marker=dict(size=11 if heat else 15, color=level.map(cfg.LEVEL_COLOR)),
        customdata=custom,
        hovertemplate=("<b>%{customdata[1]}</b> · %{customdata[0]}<br>"
                       "<b>%{customdata[2]}</b><br>"
                       "%{customdata[3]} ped / 3 min · %{customdata[4]} ped/min/m<br>"
                       "Measured %{customdata[5]}<br>%{customdata[6]}<extra></extra>"),
    ))
    if flow_traces:                                          # hover targets at the arrow tips on top
        fig.add_trace(flow_traces[-1])
    style = MAP_STYLE_OVERRIDE or cfg.MAP_STYLE.get(theme, "carto-positron")
    fig.update_layout(
        map=dict(style=style, center=cfg.MAP_CENTER, zoom=cfg.MAP_ZOOM),
        margin=dict(l=0, r=0, t=0, b=0), showlegend=False, uirevision="map",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor=t["surface"], bordercolor=t["axis"], font=dict(family=FONT, color=t["ink"])),
    )
    return fig


def ranking_figure(top, theme):
    """FO1 / SF3.6: the locations with the highest flow per metre right now."""
    t = _t(theme)
    if top.empty:
        return empty_figure("No valid measurements at this moment", theme, height=250)
    top = top.reset_index(drop=True)
    pos = list(range(len(top), 0, -1))           # highest at the top
    names = [n if len(n) <= 34 else n[:32] + "…" for n in top["label"]]
    level = top["level"].astype(str)
    custom = np.column_stack([top["sensor"], top["location_name"], level.map(cfg.LEVEL_LABEL),
                              [_fmt(v) for v in top["N_total"]], top["eff_width_m"]])
    fig = go.Figure(go.Bar(
        x=top["q_specific"], y=pos, orientation="h", width=0.56,
        marker=dict(color=level.map(cfg.LEVEL_COLOR), cornerradius=4),
        text=[f"{q:.1f}" for q in top["q_specific"]], textposition="outside", cliponaxis=False,
        textfont=dict(color=t["ink"], size=12),
        customdata=custom,
        hovertemplate=("<b>%{customdata[1]}</b> · %{customdata[0]}<br><b>%{x:.1f} ped/min/m</b> · "
                       "%{customdata[2]}<br>%{customdata[3]} ped / 3 min on %{customdata[4]} m<extra></extra>"),
    ))
    xmax = max(top["q_specific"].max() * 1.2, cfg.LEVEL_FROM["threshold"] * 1.35)  # room for the labels
    fig.update_layout(**base_layout(theme, height=250, margin=dict(l=8, r=16, t=24, b=8)))
    fig.update_yaxes(tickvals=pos, ticktext=names, showline=False, showgrid=False,
                     tickfont=dict(color=t["ink2"], size=12), range=[0.4, len(top) + 0.6])
    fig.update_xaxes(range=[0, xmax], title_text="Flow per metre (ped/min/m)", showgrid=True)
    for key, anchor in (("attention", "right"), ("threshold", "left")):
        fig.add_vline(x=cfg.LEVEL_FROM[key], line=dict(color=cfg.LEVEL_COLOR[key], width=1.5, dash="dot"))
        fig.add_annotation(x=cfg.LEVEL_FROM[key], y=1, yref="paper", yanchor="bottom", xanchor=anchor,
                           showarrow=False, text=f" {cfg.LEVEL_LABEL[key].split()[0]} ≥ {cfg.LEVEL_FROM[key]} ",
                           font=dict(color=t["muted"], size=11))
    return fig


def _runs(mask: pd.Series, ts: pd.Series):
    """Start/end timestamps of consecutive True values."""
    out, start, prev = [], None, None
    for m, x in zip(mask, ts):
        if m and start is None:
            start = x
        if not m and start is not None:
            out.append((start, prev))
            start = None
        prev = x
    if start is not None:
        out.append((start, prev))
    return out


def timeseries_figure(rows, info, t_now, window_min, view, events, theme):
    """FO5 / FO2 / FO3 / FC6: count per 3 min at one location, with the typical pattern of
    the other event days, directional flows, sudden-change markers and level lines."""
    t = _t(theme)
    start = t_now.normalize() if window_min is None else t_now - pd.Timedelta(minutes=window_min)
    ahead_end = t_now + pd.Timedelta(minutes=cfg.TYPICAL_AHEAD_MIN)
    hist = rows[(rows["timestamp"] >= start) & (rows["timestamp"] <= t_now)]
    ahead = rows[(rows["timestamp"] >= start) & (rows["timestamp"] <= ahead_end)]
    if hist.empty:
        return empty_figure("No data for this period", theme, height=330)

    fig = go.Figure()
    hover_time = "%{x|%a %H:%M}"
    if view == "direction":
        for col, name, color in (("N_A", info["dir_A_name"], t["series"][1]),
                                 ("N_B", info["dir_B_name"], t["series"][2])):
            fig.add_trace(go.Scatter(x=hist["timestamp"], y=hist[col], mode="lines", name=name,
                                     line=dict(color=color, width=2), connectgaps=False,
                                     hovertemplate=f"%{{y:.0f}} ped / 3 min<extra>{name}</extra>"))
        ymax = np.nanmax(hist[["N_A", "N_B"]].to_numpy(dtype=float)) if hist[["N_A", "N_B"]].notna().any().any() else 1
    else:
        fig.add_trace(go.Scatter(x=ahead["timestamp"], y=ahead["typical15"], mode="lines",
                                 name="Typical (other event days, 15-min avg)",
                                 line=dict(color=t["muted"], width=2),
                                 hovertemplate="%{y:.0f} typical<extra></extra>"))
        fig.add_trace(go.Scatter(x=hist["timestamp"], y=hist["N_total"], mode="lines",
                                 name="Count per 3 min (both directions)",
                                 line=dict(color=t["series"][0], width=2), connectgaps=False,
                                 hovertemplate="<b>%{y:.0f} ped / 3 min</b><extra></extra>"))
        ev = events[(events["sensor"] == info["sensor"]) & (events["flagged_at"] >= start)
                    & (events["flagged_at"] <= t_now)]
        for typ, symbol, name in (("increase", "triangle-up", "Sudden increase"),
                                  ("decrease", "triangle-down", "Sudden decrease")):
            e = ev[ev["type"] == typ]
            if len(e):
                fig.add_trace(go.Scatter(
                    x=e["flagged_at"], y=e["N_at_flag"], mode="markers", name=name,
                    marker=dict(symbol=symbol, size=13, color=t["ink"], line=dict(color=t["surface"], width=2)),
                    customdata=np.column_stack([[_fmt(v) for v in e["N_before"]], [_fmt(v, 0, "%") for v in e["change_pct"]]]),
                    hovertemplate=f"{name}: %{{y:.0f}} (was %{{customdata[0]}}, %{{customdata[1]}})<extra></extra>"))
        vals = pd.concat([hist["N_total"], ahead["typical15"]]).to_numpy(dtype=float)
        ymax = np.nanmax(vals) if np.isfinite(vals).any() else 1
        # level lines converted to a count for this location: N = q * 3 min * width
        width = info["eff_width_m"]
        if pd.notna(width):
            for key in ("attention", "threshold", "crisis"):
                n_line = cfg.LEVEL_FROM[key] * cfg.INTERVAL_MIN * width
                if n_line <= ymax * 1.3:
                    ymax = max(ymax, n_line)
                    fig.add_hline(y=n_line, line=dict(color=cfg.LEVEL_COLOR[key], width=1.5, dash="dot"))
                    fig.add_annotation(x=1, xref="paper", y=n_line, xanchor="right", yanchor="bottom",
                                       showarrow=False, text=f"{cfg.LEVEL_LABEL[key]} (q ≥ {cfg.LEVEL_FROM[key]})",
                                       font=dict(color=t["muted"], size=11))

    # periods without valid data (FC8, SF6.6)
    for a, b in _runs(hist["status"].ne("ok"), hist["timestamp"]):
        fig.add_vrect(x0=a - pd.Timedelta(minutes=1.5), x1=b + pd.Timedelta(minutes=1.5),
                      fillcolor=t["muted"], opacity=0.16, line_width=0, layer="below")
        fig.add_annotation(x=a, y=1, yref="paper", xanchor="left", yanchor="top", showarrow=False,
                           text="no valid data", font=dict(color=t["muted"], size=11))

    fig.add_vline(x=t_now, line=dict(color=t["ink2"], width=1))
    fig.add_annotation(x=t_now, y=1, yref="paper", yanchor="bottom", showarrow=False,
                       text=f"now {t_now:%H:%M}", font=dict(color=t["ink"], size=11))
    fig.update_layout(**base_layout(theme, height=330, showlegend=True, hovermode="x unified",
                                    margin=dict(l=8, r=12, t=40, b=8)))
    fig.update_xaxes(range=[start, ahead_end], tickformat="%H:%M", showgrid=False,
                     hoverformat="%a %d %b %H:%M", showspikes=True, spikemode="across",
                     spikecolor=t["axis"], spikethickness=1, spikedash="solid")
    fig.update_yaxes(title_text="Pedestrians per 3 min", rangemode="tozero", range=[0, ymax * 1.12])
    return fig


# ---------------------------------------------------------------------------
# Evaluation view
# ---------------------------------------------------------------------------
def level_minutes_figure(peaks, theme):
    """SF2.5: minutes per location above the normal level (attention / threshold / crisis)."""
    t = _t(theme)
    keys = [k for k in cfg.LEVEL_KEYS if k != "normal"]
    if peaks.empty:
        return empty_figure("No data in this selection", theme, height=300)
    p = peaks.assign(total=peaks[[f"min_{k}" for k in keys]].sum(axis=1))
    p = p[p["total"] > 0].sort_values("total")
    if p.empty:
        return empty_figure("No location left the normal level in this selection", theme, height=300)
    names = [n if len(n) <= 34 else n[:32] + "…" for n in p["label"]]
    fig = go.Figure()
    for key in keys:
        fig.add_trace(go.Bar(
            y=list(range(len(p))), x=p[f"min_{key}"], orientation="h", name=cfg.LEVEL_LABEL[key],
            marker=dict(color=cfg.LEVEL_COLOR[key], line=dict(color=t["surface"], width=2)),
            customdata=np.column_stack([p["location_name"], p["sensor"]]),
            hovertemplate=f"<b>%{{x:.0f}} min</b> {cfg.LEVEL_LABEL[key].lower()}<br>"
                          "%{customdata[0]} · %{customdata[1]}<extra></extra>"))
    height = max(220, 70 + 26 * len(p))
    fig.update_layout(**base_layout(theme, height=height, barmode="stack", showlegend=True,
                                    barcornerradius=4, bargap=0.38, margin=dict(l=8, r=12, t=30, b=8)))
    fig.update_layout(legend_traceorder="normal")
    fig.update_yaxes(tickvals=list(range(len(p))), ticktext=names, showgrid=False, showline=False,
                     tickfont=dict(color=t["ink2"], size=12))
    fig.update_xaxes(title_text="Minutes", showgrid=True)
    return fig


def heatmap_figure(hourly, order, theme):
    """MF5: average flow per metre per location and hour - where and when was it busy?"""
    t = _t(theme)
    if hourly.empty:
        return empty_figure("No data in this selection", theme, height=300)
    piv = hourly.pivot_table(index="label", columns="hour_ts", values="q_avg", aggfunc="first")
    piv = piv.reindex([o for o in order if o in piv.index])
    n = hourly.pivot_table(index="label", columns="hour_ts", values="n", aggfunc="first").reindex(piv.index)
    steps = t["sequential"]
    scale = [[i / (len(steps) - 1), c] for i, c in enumerate(steps)]
    fig = go.Figure(go.Heatmap(
        z=piv.to_numpy(), x=piv.columns, y=piv.index, colorscale=scale, zmin=0,
        zmax=max(np.nanmax(piv.to_numpy()), 1), ygap=2, xgap=0, hoverongaps=False,
        customdata=n.to_numpy(),
        colorbar=dict(title=dict(text="ped/min/m", font=dict(color=t["ink2"], size=11)), thickness=10,
                      len=0.6, outlinewidth=0, tickfont=dict(color=t["muted"], size=11)),
        hovertemplate="<b>%{z:.1f} ped/min/m</b> (hour average)<br>%{y}<br>%{x|%a %d %b, %H:00}"
                      "<br>%{customdata} valid 3-min intervals<extra></extra>"))
    fig.update_layout(**base_layout(theme, height=max(320, 60 + 17 * len(piv)),
                                    margin=dict(l=8, r=8, t=8, b=8)))
    fig.update_yaxes(autorange="reversed", showgrid=False, showline=False, tickfont=dict(size=11, color=t["ink2"]))
    fig.update_xaxes(showgrid=False, tickformat="%a %d\n%H:%M", dtick=6 * 3600 * 1000)
    return fig


def daily_pattern_figure(rows, all_days, days_selected, hours, info, theme):
    """FO2 / SF5.3: the same location on every event day, on top of each other (15-min averages)."""
    t = _t(theme)
    if rows.empty:
        return empty_figure("Select a location", theme, height=320)
    fig = go.Figure()
    sel_days = set(pd.to_datetime(days_selected)) if days_selected else set(all_days)
    for i, day in enumerate(all_days):                   # colour follows the day, not its rank
        if day not in sel_days:
            continue
        d = rows[(rows["date"] == day) & rows["hour"].between(hours[0], hours[1] - 1)]
        x = pd.Timestamp("2025-01-01") + (d["timestamp"] - day)
        name = day.strftime(DAY_FMT)
        fig.add_trace(go.Scatter(x=x, y=d["N15"], mode="lines", name=name, connectgaps=False,
                                 line=dict(color=t["series"][i % len(t["series"])], width=2),
                                 hovertemplate=f"<b>%{{y:.0f}}</b> ped / 3 min<extra>{name}</extra>"))
    fig.update_layout(**base_layout(theme, height=320, showlegend=True, hovermode="x unified",
                                    margin=dict(l=8, r=12, t=30, b=8)))
    fig.update_xaxes(tickformat="%H:%M", hoverformat="%H:%M", showgrid=False)
    fig.update_yaxes(title_text="Pedestrians per 3 min (15-min avg)", rangemode="tozero")
    return fig


def change_timeline_figure(events, order, theme):
    """RQ3 / FC6: where and when sudden increases and decreases were flagged."""
    t = _t(theme)
    if events.empty:
        return empty_figure("No sudden changes in this selection", theme, height=320)
    labels = [o for o in order if o in set(events["label"])]
    ypos = {lab: i for i, lab in enumerate(labels)}
    fig = go.Figure()
    for typ, symbol, color, name in (("increase", "triangle-up", t["series"][0], "Sudden increase"),
                                     ("decrease", "triangle-down", t["series"][1], "Sudden decrease")):
        e = events[events["type"] == typ]
        if e.empty:
            continue
        fig.add_trace(go.Scatter(
            x=e["flagged_at"], y=e["label"].map(ypos), mode="markers", name=name,
            marker=dict(symbol=symbol, size=10, color=color, line=dict(color=t["surface"], width=1)),
            customdata=np.column_stack([e["label"], [_fmt(v) for v in e["N_before"]], [_fmt(v) for v in e["N_at_flag"]],
                                        [_fmt(v, 0, "%") for v in e["change_pct"]]]),
            hovertemplate=(f"<b>{name}</b> %{{x|%a %d %b %H:%M}}<br>%{{customdata[0]}}<br>"
                           "%{customdata[1]} → %{customdata[2]} ped / 3 min (%{customdata[3]})<extra></extra>")))
    names = [lab if len(lab) <= 34 else lab[:32] + "…" for lab in labels]
    fig.update_layout(**base_layout(theme, height=max(320, 70 + 18 * len(labels)), showlegend=True,
                                    margin=dict(l=8, r=12, t=30, b=8)))
    fig.update_yaxes(tickvals=list(range(len(labels))), ticktext=names, autorange="reversed",
                     showgrid=True, showline=False, tickfont=dict(size=11, color=t["ink2"]))
    pad = pd.Timedelta(hours=1)
    fig.update_xaxes(tickformat="%a %d\n%H:%M", showgrid=False,
                     range=[events["flagged_at"].min().normalize(), events["flagged_at"].max() + pad])
    return fig
