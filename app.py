"""PeakWatch dashboard — streamlit run app.py (or run_dashboard.bat).
Map-first navigation: click a member town -> full town page with a
mini-MA locator. Reads only from the store.
"""
import json
import os
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Cloud secrets bridge: Streamlit Cloud provides st.secrets, local runs use
# .env — copy secrets into the environment BEFORE peakwatch.config loads.
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str) and _k not in os.environ:
            os.environ[_k] = _v
except Exception:
    pass

from peakwatch.analytics import (alert_budget_curve, climatology, risk_flags,
                                 survival_runway)
from peakwatch.isone import ISONEClient
from peakwatch.peaks import EASTERN
from peakwatch.store import DB_PATH
from peakwatch.townhourly import SEASON, _seasonal_alphas

st.set_page_config(page_title="PeakWatch — ISO-NE", page_icon="⚡", layout="wide")

RNS_RATE, FCA_RATE = 183.71, 3.58  # $/kW-yr (2026), $/kW-mo (FCA18)
ACCENT = "#ff6b35"


# ---------------- Login gate ----------------
def _check_login():
    import hashlib
    import os
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
    want_user = os.getenv("AUTH_USER", "admin")
    want_hash = os.getenv("AUTH_PASSWORD_SHA256", "")
    if st.session_state.get("authed"):
        return True
    _, mid, _ = st.columns([1, 1, 1])
    with mid:
        st.markdown("## ⚡ PeakWatch")
        st.caption("Sign in to continue")
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Sign in", use_container_width=True):
                if (u == want_user and want_hash
                        and hashlib.sha256(p.encode()).hexdigest() == want_hash):
                    st.session_state["authed"] = True
                    st.rerun()
                st.error("Wrong username or password.")
    return False


if not _check_login():
    st.stop()


@st.cache_resource
def _con():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


@st.cache_data(ttl=300)
def get_live():
    try:
        return ISONEClient().five_minute_system_load_current()
    except Exception:
        return {}


@st.cache_data(ttl=900)
def q(sql, params=()):
    return pd.read_sql(sql, _con(), params=params)


@st.cache_data(ttl=3600)
def get_peak_probs():
    try:
        from peakwatch.peakmodel import live_scores
        return live_scores()
    except Exception as e:
        return pd.DataFrame({"error": [str(e)[:120]]})


@st.cache_data(ttl=3600)
def get_alphas():
    _, alphas = _seasonal_alphas(_con())
    return alphas.reset_index()


@st.cache_data(ttl=3600)
def zone_hour_fracs():
    """Zone share of system load by (season, hour), past 365 days — the
    bridge from live 5-min system load down to zones."""
    zd = q("SELECT ts, zone, rt_load_mw FROM clean_zone_demand "
           "WHERE rt_load_mw IS NOT NULL AND ts >= date('now', '-365 days')")
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    local = zd["ts"].dt.tz_convert(EASTERN)
    zd["hour"] = local.dt.hour
    zd["season"] = local.dt.month.map(lambda m: SEASON.get(m, "sh"))
    sys_tot = zd.groupby("ts")["rt_load_mw"].transform("sum")
    zd["frac"] = zd["rt_load_mw"] / sys_tot
    return zd.groupby(["zone", "season", "hour"])["frac"].mean()


@st.cache_data(ttl=600)
def latest_actual_zone():
    try:
        return ISONEClient().realtime_hourly_demand_current()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=1800)
def danger_days():
    """Plain-language peak danger for the coming days: (level, message).
    level: 'alert' | 'watch' | 'clear'."""
    probs = get_peak_probs()
    wx = q("SELECT ts, AVG(temp_c) t FROM raw_weather_fcst GROUP BY ts")
    tmax = {}
    if len(wx):
        wx["ts"] = pd.to_datetime(wx["ts"], utc=True)
        wx["date"] = wx["ts"].dt.tz_convert(EASTERN).dt.date
        tmax = wx.groupby("date")["t"].max().to_dict()
    if "p_exceed" not in probs.columns or not len(probs):
        return "clear", "Quiet grid — no elevated peak conditions detected."
    worst = probs.loc[probs["p_exceed"].idxmax()]
    d = pd.Timestamp(worst["date"])
    day_name = f"{d.strftime('%A, %b')} {d.day}"
    t_f = tmax.get(worst["date"])
    heat = f" — forecast high {t_f * 9 / 5 + 32:.0f}°F" if t_f else ""
    if worst["p_exceed"] >= 0.5:
        return "alert", (f"🔥 PEAK ALERT {day_name}{heat}. The grid is likely "
                         "to hit this month's high between 5–7 PM. Batteries "
                         "and demand response should run. Every MW off the "
                         "grid in that window saves ~$15,000 this month.")
    if worst["p_exceed"] >= 0.2:
        return "watch", (f"⚠️ Peak watch {day_name}{heat}. Conditions could "
                         "challenge this month's high in the late afternoon. "
                         "Have batteries ready; a final call comes with the "
                         "morning forecast.")
    return "clear", ("😎 All clear for the coming days. This month's peak "
                     "(set July 2 during the heat wave) is very unlikely to "
                     "be beaten — no special action needed.")


@st.cache_data(ttl=86400)
def get_geojson():
    path = Path(__file__).parent / "reference" / "ma_towns.geojson"
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(ttl=86400)
def locator_fig(town):
    """Mini MA map with one town highlighted — the town-page header art."""
    gj = get_geojson()
    names = [f["properties"]["TOWN"] for f in gj["features"]]
    others = [n for n in names if n != town]
    fig = go.Figure()
    fig.add_choropleth(geojson=gj, featureidkey="properties.TOWN",
                       locations=others, z=[0] * len(others),
                       colorscale=[[0, "#262b36"], [1, "#262b36"]],
                       showscale=False, marker_line_color="#3a4150",
                       marker_line_width=0.3, hoverinfo="skip")
    fig.add_choropleth(geojson=gj, featureidkey="properties.TOWN",
                       locations=[town], z=[1],
                       colorscale=[[0, ACCENT], [1, ACCENT]],
                       showscale=False, marker_line_color="#ffffff",
                       marker_line_width=1.5, hoverinfo="text", text=[town])
    fig.update_geos(fitbounds="geojson", visible=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(height=170, margin=dict(l=0, r=0, t=0, b=0),
                      paper_bgcolor="rgba(0,0,0,0)", dragmode=False)
    return fig


def render_town_page(town):
    rnl = q("SELECT month, rnl_mw, zone FROM clean_town_rnl WHERE town=? "
            "ORDER BY month", (town,))
    zone = rnl["zone"].mode()[0] if len(rnl) else "?"

    head_l, head_r = st.columns([2, 1])
    with head_l:
        st.markdown(f"## {town}")
        st.caption(f"Load zone **{zone}** · MMWEC member · "
                   f"{len(rnl)} months of settlement history")
    with head_r:
        st.plotly_chart(locator_fig(town), use_container_width=True,
                        config={"staticPlot": True},
                        key=f"loc_{town}")

    if not len(rnl):
        st.warning("No settlement data for this town.")
        return

    # -- Now strip: live estimate chained from 5-min system load --
    live = get_live()
    alphas = get_alphas()
    amap = alphas[alphas["town"] == town].set_index("season")["alpha"]
    if live and len(amap):
        now_local = pd.Timestamp.now(tz=EASTERN)
        season_now = SEASON.get(now_local.month, "sh")
        fracs = zone_hour_fracs()
        zfrac = fracs.get((zone, season_now, now_local.hour), None)
        formula = ("Live 5-min system load × this zone's typical share of "
                   "system for this hour and season × this town's settlement "
                   "share of the zone.")
        n1, n2, n3 = st.columns(3)
        if zfrac:
            zone_now = live["load_mw"] * zfrac
            town_now = zone_now * amap.get(season_now, amap.mean())
            n1.metric("⚡ Est. load right now",
                      f"{town_now:,.1f} MW",
                      f"from live system {live['load_mw']:,.0f} MW",
                      help=formula)
            n2.metric(f"Est. {zone} zone now", f"{zone_now:,.0f} MW",
                      help=formula)
        act = latest_actual_zone()
        if len(act):
            zrow = act[act["Zone"] == zone]
            if len(zrow):
                r = zrow.iloc[0]
                n3.metric(f"Last actual {zone} hour",
                          f"{r['RtLoad_MW']:,.0f} MW",
                          f"{str(r['Timestamp'])[:16]} (prelim, ~2d lag)")
        st.caption("Estimated, not metered.")
        st.divider()

    latest = rnl.iloc[-1]
    avg12 = rnl["rnl_mw"].tail(12).mean()
    summer = rnl[rnl["month"].str[5:7].isin(["07", "08"])]["rnl_mw"].tail(2)
    tag = summer.max() if len(summer) else float("nan")
    yoy = avg12 - rnl["rnl_mw"].tail(24).head(12).mean()

    c = st.columns(4)
    c[0].metric(f"Latest RNL ({latest['month']})", f"{latest['rnl_mw']:.2f} MW")
    c[1].metric("12-mo max", f"{rnl['rnl_mw'].tail(12).max():.2f} MW")
    c[2].metric("Capacity tag (proxy)",
                f"{tag:.2f} MW" if tag == tag else "—")
    c[3].metric("Avg vs prior year", f"{yoy:+.2f} MW")
    d = st.columns(4)
    trans = avg12 * 1000 * RNS_RATE
    cap = tag * 1000 * FCA_RATE * 12 if tag == tag else 0
    d[0].metric("Transmission cost exposure", f"${trans:,.0f}/yr")
    d[1].metric("Capacity cost exposure", f"${cap:,.0f}/yr")
    d[2].metric("Total exposure", f"${trans + cap:,.0f}/yr")
    d[3].metric("1 MW shaved (12 CP)", f"${RNS_RATE * 1000:,.0f}/yr")

    sealed = Path(__file__).parent / "predictions" / "sealed_2026-07.csv"
    if sealed.exists():
        sp = pd.read_csv(sealed, comment="#")
        row = sp[sp["Town"] == town]
        if len(row):
            r = row.iloc[0]
            st.info(f"🔒 **Forecast on the record** — sealed 2026-07-22, "
                    f"scored when ISO publishes (~Sept): July 2026 RNL = "
                    f"**{r['Predicted_RNL_MW']:.2f} MW** "
                    f"[{r['Low_MW']:.2f} – {r['High_MW']:.2f}]")

    st.subheader("Settlement history — MW at each monthly transmission peak")
    fig = px.bar(rnl, x="month", y="rnl_mw",
                 labels={"rnl_mw": "MW", "month": ""})
    fig.update_traces(marker_color=ACCENT)
    fig.update_layout(height=280, margin=dict(t=10))
    st.plotly_chart(fig, use_container_width=True, key=f"hist_{town}")

    st.subheader("Estimated hourly load, last 14 days")
    alphas = get_alphas()
    zh = q("SELECT ts, rt_load_mw FROM clean_zone_demand WHERE zone=? "
           "AND rt_load_mw IS NOT NULL ORDER BY ts DESC LIMIT 336", (zone,))
    if len(zh):
        zh["ts"] = pd.to_datetime(zh["ts"], utc=True)
        zh = zh.sort_values("ts")
        zh["season"] = zh["ts"].dt.tz_convert(EASTERN).dt.month.map(
            lambda m: SEASON.get(m, "sh"))
        amap = alphas[alphas["town"] == town].set_index("season")["alpha"]
        zh["town_mw"] = zh.apply(
            lambda r: amap.get(r["season"], amap.mean()) * r["rt_load_mw"],
            axis=1)
        fig2 = px.line(zh, x="ts", y="town_mw",
                       labels={"town_mw": "MW (estimated)", "ts": ""})
        fig2.update_layout(height=260, margin=dict(t=10))
        st.plotly_chart(fig2, use_container_width=True, key=f"hr_{town}")
        st.caption("Seasonal settlement share × zone hourly load — validated "
                   "at anchor hours and against EIA-861 annual energy.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Generation portfolio")
        st.dataframe(q("SELECT tech, nameplate_mw, status FROM town_portfolio "
                       "WHERE town=? ORDER BY nameplate_mw DESC", (town,)),
                     use_container_width=True, hide_index=True)
    with col_b:
        st.subheader("Customer class mix (EIA-861)")
        mix = q("SELECT * FROM town_class_mix WHERE town=?", (town,))
        if len(mix) and pd.notna(mix["res_mwh"].iloc[0]):
            m = mix.iloc[0]
            pie = px.pie(values=[m["res_mwh"], m["com_mwh"], m["ind_mwh"]],
                         names=["Residential", "Commercial", "Industrial"],
                         hole=0.5)
            pie.update_layout(height=260, margin=dict(t=10, b=10))
            st.plotly_chart(pie, use_container_width=True, key=f"pie_{town}")
        elif len(mix):
            st.metric("Annual sales (short-form filer)",
                      f"{mix['total_mwh'].iloc[0]:,.0f} MWh")


st.title("⚡ PeakWatch")

_level, _msg = danger_days()
{"alert": st.error, "watch": st.warning, "clear": st.success}[_level](_msg)

(tab_map, tab_risk, tab_fc, tab_wx, tab_zones, tab_money,
 tab_health) = st.tabs(
    ["🗺️ Towns", "🎯 Peak Risk", "🔮 Forecast", "🌤️ Weather", "📊 History",
     "💰 Money", "🩺 Health"])


@st.cache_data(ttl=3600, show_spinner="Training forecast model (once per "
                                       "zone per hour)…")
def get_forecast(zone):
    # always compute the full 7 days; the slider only slices the display,
    # so moving it never retrains
    from peakwatch.forecast7 import train_and_forecast
    return train_and_forecast(zone, 7)

# ---------------- Map / Town pages ----------------
with tab_map:
    sel_town = st.session_state.get("sel_town")
    if sel_town:
        if st.button("← Back to map"):
            st.session_state.pop("sel_town", None)
            st.rerun()
        render_town_page(sel_town)
    else:
        gj = get_geojson()
        rnl_all_m = q("SELECT town, month, rnl_mw FROM clean_town_rnl")
        latest = (rnl_all_m.sort_values("month").groupby("town").tail(12)
                  .groupby("town")["rnl_mw"].mean())
        exposure = {t: v * 1000 * RNS_RATE / 1e6 for t, v in latest.items()}
        member_names = list(exposure)
        all_names = [f["properties"]["TOWN"] for f in gj["features"]]
        others = [n for n in all_names if n not in member_names]

        fig = go.Figure()
        fig.add_choropleth(
            geojson=gj, featureidkey="properties.TOWN", locations=others,
            z=[0] * len(others), colorscale=[[0, "#262b36"], [1, "#262b36"]],
            showscale=False, marker_line_color="#3a4150",
            marker_line_width=0.4, hoverinfo="text", text=others, name="")
        fig.add_choropleth(
            geojson=gj, featureidkey="properties.TOWN",
            locations=member_names,
            z=[exposure[t] for t in member_names], colorscale="YlOrRd",
            colorbar=dict(title="$M/yr", thickness=12, len=0.7),
            marker_line_color="#ffffff", marker_line_width=1.2,
            hovertemplate="<b>%{location}</b><br>avg RNL %{text:.1f} MW<br>"
                          "transmission ≈ $%{z:.1f}M/yr"
                          "<br><i>click to open town page</i><extra></extra>",
            text=[latest[t] for t in member_names], name="members")
        fig.update_geos(fitbounds="geojson", visible=False,
                        bgcolor="rgba(0,0,0,0)")
        fig.update_layout(height=560, margin=dict(l=0, r=0, t=10, b=0),
                          paper_bgcolor="rgba(0,0,0,0)",
                          clickmode="event+select", dragmode=False)
        st.caption("The 20 MMWEC member towns, colored by annual transmission "
                   "exposure. Click a highlighted town to open its page.")
        event = st.plotly_chart(fig, use_container_width=True, key="ma_map",
                                on_select="rerun", selection_mode="points",
                                config={"scrollZoom": False,
                                        "displayModeBar": False})
        with st.expander("❓ What am I looking at?"):
            st.markdown(
                "- **The colors** show how much each member town spends per "
                "year on transmission — charges set by its electricity use "
                "during a handful of peak hours.\n"
                "- **The banner above** is the bottom line: is a "
                "bill-setting peak hour coming up, in plain words? Green "
                "means relax; red means act.\n"
                "- **Click any glowing town** for its full picture: live "
                "load, history, forecasts, costs, and its power plants.\n"
                "- Everything updates itself each morning from ISO New "
                "England's own published data.")
        sel = None
        try:
            pts = event.selection.points
            if pts:
                sel = pts[0].get("location") or pts[0].get("customdata")
        except Exception:
            pass
        if sel and sel in member_names:
            st.session_state["sel_town"] = sel
            st.rerun()
        picked = st.selectbox("…or pick a town", ["—"] + member_names)
        if picked != "—":
            st.session_state["sel_town"] = picked
            st.rerun()

# ---------------- Peak Risk ----------------
with tab_risk:
    live = get_live()
    if live:
        c1, c2, c3 = st.columns(3)
        c1.metric("Live system load", f"{live['load_mw']:,.0f} MW")
        c2.metric("Behind-the-meter PV est.", f"{live['btm_pv_mw']:,.0f} MW")
        c3.metric("As of", str(live["timestamp"])[:16])

    st.subheader("Peak-day probability (ML model)")
    probs = get_peak_probs()
    if "p_exceed" in probs.columns and len(probs):
        cols = st.columns(min(4, len(probs)))
        for c, (_, r) in zip(cols, probs.iterrows()):
            emoji = "🔴" if r["p_exceed"] >= 0.2 else "🟢"
            c.metric(f"{emoji} {r['date']}", f"P = {r['p_exceed']:.2f}",
                     f"DA {r['da_max']:,} vs MTD {r['mtd_max']:,} MW")
        st.caption("P(day's max exceeds month-to-date max). Alert at P ≥ 0.20. "
                   "Full-history: 88.7% of monthly peaks at 6.3 alert-days/mo; "
                   "backstop rule catches 100% at 14.8.")
    else:
        st.info("Probability model warming up — needs today's DA data.")

    st.subheader("Next days — ISO forecast vs month-to-date max (backstop rule)")
    flags, mtd = risk_flags(_con())
    if len(flags):
        ann = q("SELECT MAX(mw) m FROM (SELECT ts, SUM(rt_load_mw) mw FROM "
                "clean_zone_demand WHERE ts >= date('now','start of year') "
                "GROUP BY ts HAVING COUNT(rt_load_mw)=8)")["m"].iloc[0]
        def _status(r):
            v = r["vs_mtd_max"]
            if v is None or pd.isna(v):
                return "—"
            s = ("🔴 monthly peak risk" if v >= 0.95 else
                 "🟡 elevated" if v >= 0.90 else "🟢 safe")
            if ann and r["iso_fcst_peak_mw"] >= 0.95 * ann:
                s += " ⭐ capacity-peak risk"
            return s
        flags = flags.copy()
        flags["status"] = flags.apply(_status, axis=1)
        def _row_color(r):
            v = r["vs_mtd_max"]
            if v is None or pd.isna(v):
                c = ""
            elif v >= 0.95:
                c = "background-color: rgba(220, 60, 50, 0.25)"
            elif v >= 0.90:
                c = "background-color: rgba(240, 180, 30, 0.20)"
            else:
                c = "background-color: rgba(60, 170, 90, 0.12)"
            return [c] * len(r)
        st.dataframe(flags.style.apply(_row_color, axis=1),
                     use_container_width=True, hide_index=True)
        st.caption(f"⭐ appears when a day's forecast approaches this year's "
                   f"record hour ({ann:,.0f} MW) — the hour that sets "
                   "capacity tags for the year starting next June.")

    # -- Two plain-language answers, data behind expanders --
    runway = survival_runway(climatology(_con()))
    now_l = pd.Timestamp.now(tz=EASTERN)
    season_now = ("summer" if now_l.month in (6, 7, 8) else
                  "winter" if now_l.month in (12, 1, 2) else "shoulder")
    r_season = runway[runway["season"] == season_now]
    bracket = r_season[r_season["day_of_month"] <= now_l.day]
    p_ahead = (bracket["P_peak_still_ahead"].iloc[-1]
               if len(bracket) else r_season["P_peak_still_ahead"].iloc[0])

    st.subheader("Is this month's peak already behind us?")
    st.markdown(f"It's day **{now_l.day}** of a {season_now} month. "
                f"Historically, only **{p_ahead:.0%}** of {season_now} months "
                "still had their peak ahead at this point"
                + (" — the big hour has almost certainly happened."
                   if p_ahead < 0.3 else
                   " — stay attentive; the big hour may still be coming."))
    with st.expander("how this changes through the month"):
        rs = runway[runway["season"] == season_now]
        figr = px.bar(x=rs["day_of_month"], y=rs["P_peak_still_ahead"],
                      labels={"x": f"day of a {season_now} month",
                              "y": "chance peak is still ahead"})
        figr.update_traces(marker_color=ACCENT,
                           text=[f"{v:.0%}" for v in rs["P_peak_still_ahead"]],
                           textposition="outside")
        figr.update_layout(height=260, yaxis_tickformat=".0%",
                           margin=dict(t=20))
        st.plotly_chart(figr, use_container_width=True)

    st.subheader("How trigger-happy should alerts be?")
    st.markdown("A missed monthly peak costs ~**$15,000 per MW**; an extra "
                "battery run costs almost nothing. So: better to alert too "
                "often than too rarely.")
    with st.expander("the options, measured on 54 months of history"):
        abc = alert_budget_curve(_con()).rename(columns={
            "threshold": "alert when forecast reaches…",
            "peaks_caught": "peaks caught",
            "capture_%": "success rate",
            "alert_days_per_month": "alert days per month"})
        abc["alert when forecast reaches…"] = abc[
            "alert when forecast reaches…"].map(lambda v: f"{v:.0%} of month's max")
        abc["success rate"] = abc["success rate"].map(lambda v: f"{v:.0f}%")
        st.dataframe(abc, use_container_width=True, hide_index=True)

# ---------------- Forecast ----------------
with tab_fc:
    fc1, fc2, fc3 = st.columns([1, 1, 2])
    fzone = fc1.selectbox("Zone", ["WCMA", "NEMA", "SEMA"], key="fc_zone")
    fdays = fc2.slider("Forecast length (days)", 1, 7, 3, key="fc_days")
    ftown = fc3.selectbox(
        "Scale to town (optional)",
        ["— zone total —"] + list(
            q("SELECT DISTINCT town FROM clean_town_rnl WHERE zone=? "
              "ORDER BY town", (fzone,))["town"]),
        key="fc_town")
    tail, fc = get_forecast(fzone)
    fc = fc[pd.to_datetime(fc["ts"], utc=True)
            <= pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=fdays)]

    scale, unit_label = 1.0, f"{fzone} MW"
    if ftown != "— zone total —":
        amap = get_alphas()
        am = amap[amap["town"] == ftown].set_index("season")["alpha"]
        season_now = SEASON.get(pd.Timestamp.now(tz=EASTERN).month, "sh")
        scale = float(am.get(season_now, am.mean()))
        unit_label = f"{ftown} MW (estimated)"

    fig = go.Figure()
    fig.add_scatter(x=fc["ts"], y=fc["p90"] * scale, line=dict(width=0),
                    showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=fc["ts"], y=fc["p10"] * scale, fill="tonexty",
                    fillcolor="rgba(255,107,53,0.18)", line=dict(width=0),
                    name="p10–p90 band")
    fig.add_scatter(x=fc["ts"], y=fc["p50"] * scale, name="PeakWatch p50",
                    line=dict(color=ACCENT, width=2))
    if "iso_fcst_zone" in fc.columns and fc["iso_fcst_zone"].notna().any():
        fig.add_scatter(x=fc["ts"], y=fc["iso_fcst_zone"] * scale,
                        name="ISO forecast (scaled)",
                        line=dict(dash="dot", color="#7fb3ff"))
    fig.add_scatter(x=tail["ts"], y=tail["rt_load_mw"] * scale,
                    name="Actual (recent)",
                    line=dict(color="#9aa4b2", width=1.5))

    # the line to beat: this month's max so far for the zone, and red
    # danger bands wherever the forecast's upper band threatens it
    zmtd = q("SELECT MAX(rt_load_mw) m FROM clean_zone_demand WHERE zone=? "
             "AND strftime('%Y-%m', ts) = strftime('%Y-%m', 'now')",
             (fzone,))["m"].iloc[0]
    if zmtd:
        fig.add_hline(y=zmtd * scale, line_dash="dash", line_color="#e05555",
                      annotation_text="month's max — the line to beat",
                      annotation_font_color="#e05555")
        danger = fc[fc["p90"] >= 0.95 * zmtd].copy()
        if len(danger):
            danger["gap"] = danger["ts"].diff().dt.total_seconds().div(3600).ne(1).cumsum()
            for _, gg in danger.groupby("gap"):
                fig.add_vrect(x0=gg["ts"].min(), x1=gg["ts"].max()
                              + pd.Timedelta(hours=1),
                              fillcolor="rgba(220,60,50,0.15)", line_width=0)
    fig.update_layout(height=430, yaxis_title=unit_label,
                      legend=dict(orientation="h", y=1.08))
    st.plotly_chart(fig, use_container_width=True)
    if zmtd and len(fc[fc["p90"] >= 0.95 * zmtd]):
        st.warning("Red bands: hours where the forecast's upper range comes "
                   "within 5% of this month's max — potential bill-setting "
                   "hours.")
    elif zmtd:
        st.success("No forecast hour comes near this month's max — no "
                   "bill-setting hours expected in this window.")

    peak_row = fc.loc[fc["p50"].idxmax()]
    peak_local = pd.Timestamp(peak_row["ts"]).tz_convert(EASTERN)
    st.metric(f"Predicted {fdays}-day peak ({unit_label})",
              f"{peak_row['p50'] * scale:,.1f} MW",
              f"{peak_local.strftime('%a %b %d, %H:00')} local")
    st.caption("Weather+calendar quantile model (no load lags — same skill "
               "at day 7 as day 1), residual-calibrated band. Blend of this "
               "model with ISO's forecast beats ISO alone on every window "
               "tested. Town scaling uses the seasonal settlement share.")

# ---------------- Weather outlook calendar ----------------
with tab_wx:
    st.subheader("7-day peak-weather outlook")
    st.caption("Everything that feeds load, day by day. Hot + sunny weekday "
               "= peak fuel; clouds cut rooftop solar and RAISE net load "
               "late-day.")
    wxf = q("SELECT ts, AVG(temp_c) t, AVG(ghi_wm2) g, AVG(cloud_pct) c, "
            "AVG(wind_kmh) w FROM raw_weather_fcst GROUP BY ts")
    if len(wxf):
        wxf["ts"] = pd.to_datetime(wxf["ts"], utc=True)
        wxf["date"] = wxf["ts"].dt.tz_convert(EASTERN).dt.date
        daily_wx = wxf.groupby("date").agg(
            tmax=("t", "max"), ghi=("g", "max"),
            cloud=("c", "mean"), wind=("w", "mean")).reset_index()
        cal_df = q("SELECT date, is_weekend, is_holiday FROM feature_calendar")
        cal_df["date"] = pd.to_datetime(cal_df["date"]).dt.date
        daily_wx = daily_wx.merge(cal_df, on="date", how="left")
        probs_w = get_peak_probs()
        pmap = ({pd.Timestamp(r["date"]).date(): r["p_exceed"]
                 for _, r in probs_w.iterrows()}
                if "p_exceed" in probs_w.columns else {})

        cols = st.columns(min(7, len(daily_wx)))
        for col, (_, day) in zip(cols, daily_wx.head(7).iterrows()):
            d = pd.Timestamp(day["date"])
            t_f = day["tmax"] * 9 / 5 + 32
            p = pmap.get(day["date"])
            hot = t_f >= 88 and not (day["is_weekend"] or day["is_holiday"])
            head = ("🔥" if (p or 0) >= 0.2 or t_f >= 92 else
                    "☀️" if day["cloud"] < 40 else
                    "⛅" if day["cloud"] < 75 else "☁️")
            with col:
                st.markdown(f"**{head} {d.strftime('%a')}**  \n"
                            f"{d.strftime('%b')} {d.day}")
                st.metric("high", f"{t_f:.0f}°F")
                st.caption(
                    f"☁️ {day['cloud']:.0f}% cloud  \n"
                    f"☀️ {day['ghi']:.0f} W/m² sun  \n"
                    f"💨 {day['wind']:.0f} km/h  \n"
                    + ("🏖️ weekend — low risk" if day["is_weekend"] else
                       "🎉 holiday — low risk" if day["is_holiday"] else
                       "💼 workday" + (" — peak fuel" if hot else ""))
                    + (f"  \n📈 peak chance {p:.0%}" if p is not None else ""))
        st.caption("Sun (GHI) matters twice: it drives air-conditioning AND "
                   "rooftop-solar output. A hot day that clouds over at 5 PM "
                   "is the nastiest combination — AC still roaring, solar "
                   "gone.")
    else:
        st.info("No weather forecast loaded yet — run: py -m peakwatch refresh")

# ---------------- History: when peaks happen ----------------
with tab_zones:
    st.subheader("When do the bill-setting hours actually happen?")
    sys = q("SELECT ts, SUM(rt_load_mw) mw FROM clean_zone_demand "
            "GROUP BY ts HAVING COUNT(rt_load_mw)=8")
    sys["ts"] = pd.to_datetime(sys["ts"], utc=True)
    loc = sys["ts"].dt.tz_convert(EASTERN)
    sys["month"], sys["hour"] = loc.dt.strftime("%Y-%m"), loc.dt.hour
    sys["local"] = loc

    peaks = sys.loc[sys.groupby("month")["mw"].idxmax()].sort_values("month")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Every monthly peak since 2022** — the 12 hours/year "
                    "that set transmission bills:")
        show = peaks[["month", "local", "mw"]].tail(18).copy()
        show["local"] = show["local"].dt.strftime("%a %b %d, %H:00")
        show["mw"] = show["mw"].round(0)
        st.dataframe(show.rename(columns={"local": "peak hour", "mw": "MW"}),
                     use_container_width=True, hide_index=True, height=350)
    with c2:
        st.markdown("**What time of day peaks hit** (54 months):")
        hist = peaks.groupby("hour").size().reindex(range(24), fill_value=0)
        figh = px.bar(x=hist.index, y=hist.values,
                      labels={"x": "hour of day (local)", "y": "peaks"})
        figh.update_traces(marker_color=ACCENT)
        figh.update_layout(height=280, margin=dict(t=10))
        st.plotly_chart(figh, use_container_width=True)
        st.caption("Almost every peak lands 4–7 PM. Weekends: nearly never. "
                   "That's why a 3-hour battery discharge window works.")

    st.markdown("**The 10 biggest hours ever recorded here** — these set "
                "capacity tags:")
    top = sys.nlargest(10, "mw")[["local", "mw"]].copy()
    top["local"] = top["local"].dt.strftime("%a %b %d %Y, %H:00")
    top["mw"] = top["mw"].round(0)
    st.dataframe(top.rename(columns={"local": "hour", "mw": "system MW"}),
                 use_container_width=True, hide_index=True)
    st.caption("July 2, 2026 at 6 PM — 25,321 MW — is the highest hour in "
               "this dataset and almost certainly this year's capacity-tag "
               "hour. Every member's 2027/28 capacity bill traces to it.")

# ---------------- Money ----------------
with tab_money:
    st.subheader("Dollar exposure by town")
    st.caption(f"RNS 2026: ${RNS_RATE}/kW-yr · FCA18: ${FCA_RATE}/kW-mo · "
               "tag proxied by latest summer settlement value.")
    st.info("**Why transmission exceeds capacity (today):** capacity is set "
            "by ONE hour a year — the annual coincident peak sets the tag "
            "for the commitment year starting the FOLLOWING June (July 2026 "
            f"peak → June 2027-May 2028 bills at FCA18 ${FCA_RATE}/kW-mo ≈ "
            f"${FCA_RATE * 12:.0f}/kW-yr; current bills use last summer's "
            "tag at FCA17 $2.59). Transmission (RNS) hits TWELVE hours — "
            f"each month's regional peak — at ${RNS_RATE}/kW-yr, 4×+ the "
            "capacity rate. Historical note: in the FCA9 era (2018/19) "
            "capacity was $9.55/kW-mo (~$115k per MW-year) and dominated; "
            "prices fell ~75% while transmission tripled. Twelve chances a "
            "year to save now, not one.")
    rnl_all = q("SELECT town, month, rnl_mw FROM clean_town_rnl")
    rows = []
    for t, g in rnl_all.groupby("town"):
        g = g.sort_values("month")
        avg12 = g["rnl_mw"].tail(12).mean()
        summer = g[g["month"].str[5:7].isin(["07", "08"])]["rnl_mw"].tail(2)
        tag = summer.max() if len(summer) else float("nan")
        trans, cap = avg12 * 1000 * RNS_RATE, tag * 1000 * FCA_RATE * 12
        rows.append({"Town": t, "Avg RNL (MW)": round(avg12, 1),
                     "Transmission $/yr": trans, "Capacity $/yr": cap,
                     "Total $/yr": trans + cap})
    money = pd.DataFrame(rows).sort_values("Total $/yr", ascending=False)
    total = money["Total $/yr"].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("Membership total exposure", f"${total / 1e6:,.1f}M/yr")
    c2.metric("1 MW shaved, all 12 monthly peaks", f"${RNS_RATE * 1000:,.0f}/yr")
    c3.metric("1 MW off the annual peak hour",
              f"${FCA_RATE * 1000 * 12:,.0f}/yr")
    for c in ["Transmission $/yr", "Capacity $/yr", "Total $/yr"]:
        money[c] = money[c].map(lambda v: f"${v:,.0f}")
    st.dataframe(money, use_container_width=True, hide_index=True)

# ---------------- Health ----------------
with tab_health:
    st.subheader("Latest validation run")
    ql = q("SELECT check_name, target, passed, detail FROM quality_log "
           "WHERE run_at=(SELECT MAX(run_at) FROM quality_log) "
           "ORDER BY check_name")
    ql["passed"] = ql["passed"].map({1: "✅", 0: "❌"})
    st.dataframe(ql, use_container_width=True, hide_index=True)

    st.subheader("Model scorecard (latest zoo run)")
    sc = q("SELECT model, target, metric, value FROM forecast_scorecard "
           "WHERE run_at=(SELECT MAX(run_at) FROM forecast_scorecard "
           "WHERE model LIKE 'zoo_%') AND model LIKE 'zoo_%' "
           "ORDER BY target, value")
    if len(sc):
        st.dataframe(sc.round(2), use_container_width=True, hide_index=True)

    st.subheader("Coverage")
    cov = q("SELECT zone, COUNT(*) hours, MIN(ts) first_ts, MAX(ts) last_ts "
            "FROM clean_zone_demand GROUP BY zone")
    st.dataframe(cov, use_container_width=True, hide_index=True)
    st.caption("All numbers reconcile against independently published truth: "
               "zone labels vs /locations, pool peaks vs settlement pool "
               "values (±0.84%), town estimates vs EIA-861 annual sales.")
