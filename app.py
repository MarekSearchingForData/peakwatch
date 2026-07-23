"""PeakWatch dashboard — streamlit run app.py (or run_dashboard.bat).
Map-first navigation: click a member town -> full town page with a
mini-MA locator. Reads only from the store.
"""
import json
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from peakwatch.analytics import (alert_budget_curve, climatology, risk_flags,
                                 survival_runway)
from peakwatch.isone import ISONEClient
from peakwatch.peaks import EASTERN
from peakwatch.store import DB_PATH
from peakwatch.townhourly import SEASON, _seasonal_alphas

st.set_page_config(page_title="PeakWatch — ISO-NE", page_icon="⚡", layout="wide")

RNS_RATE, FCA_RATE = 183.71, 3.58  # $/kW-yr (2026), $/kW-mo (FCA18)
ACCENT = "#ff6b35"


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
        n1, n2, n3 = st.columns(3)
        if zfrac:
            zone_now = live["load_mw"] * zfrac
            town_now = zone_now * amap.get(season_now, amap.mean())
            n1.metric("⚡ Est. load right now",
                      f"{town_now:,.1f} MW",
                      f"from live system {live['load_mw']:,.0f} MW")
            n2.metric(f"Est. {zone} zone now", f"{zone_now:,.0f} MW")
        act = latest_actual_zone()
        if len(act):
            zrow = act[act["Zone"] == zone]
            if len(zrow):
                r = zrow.iloc[0]
                n3.metric(f"Last actual {zone} hour",
                          f"{r['RtLoad_MW']:,.0f} MW",
                          f"{str(r['Timestamp'])[:16]} (prelim, ~2d lag)")
        st.caption("Live estimate = 5-min system load × zone share for this "
                   "hour/season × town settlement share. Estimated, not "
                   "metered — the honest label matters.")
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
st.caption("Peak intelligence for municipal utilities. Capacity tags and "
           "transmission charges are set in a handful of hours — these are they.")

tab_map, tab_risk, tab_fc, tab_zones, tab_money, tab_health = st.tabs(
    ["🗺️ Towns", "🎯 Peak Risk", "🔮 Forecast", "📈 Zones", "💰 Money",
     "🩺 Health"])


@st.cache_data(ttl=3600)
def get_forecast(zone, days):
    from peakwatch.forecast7 import train_and_forecast
    return train_and_forecast(zone, days)

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
                                on_select="rerun", selection_mode="points")
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
        st.dataframe(flags, use_container_width=True, hide_index=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Peak runway")
        st.dataframe(survival_runway(climatology(_con())).round(2),
                     use_container_width=True, hide_index=True)
        st.caption("P(monthly peak still ahead | day of month), from history.")
    with col_b:
        st.subheader("Alert budget menu")
        st.dataframe(alert_budget_curve(_con()), use_container_width=True,
                     hide_index=True)
        st.caption("Capture vs alert-days tradeoff; a missed monthly peak "
                   "costs ~$15.3k/MW.")

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
    with st.spinner("Training forecast model…"):
        tail, fc = get_forecast(fzone, fdays)

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
                    name="Actual (last 3 days)",
                    line=dict(color="#9aa4b2", width=1.5))
    fig.update_layout(height=430, yaxis_title=unit_label,
                      legend=dict(orientation="h", y=1.08))
    st.plotly_chart(fig, use_container_width=True)

    peak_row = fc.loc[fc["p50"].idxmax()]
    peak_local = pd.Timestamp(peak_row["ts"]).tz_convert(EASTERN)
    st.metric(f"Predicted {fdays}-day peak ({unit_label})",
              f"{peak_row['p50'] * scale:,.1f} MW",
              f"{peak_local.strftime('%a %b %d, %H:00')} local")
    st.caption("Weather+calendar quantile model (no load lags — same skill "
               "at day 7 as day 1), residual-calibrated band. Blend of this "
               "model with ISO's forecast beats ISO alone on every window "
               "tested. Town scaling uses the seasonal settlement share.")

# ---------------- Zones ----------------
with tab_zones:
    zones = q("SELECT DISTINCT zone FROM clean_zone_demand ORDER BY zone")["zone"]
    zone_pick = st.selectbox(
        "Zone", zones,
        index=list(zones).index("WCMA") if "WCMA" in list(zones) else 0)
    zd = q("SELECT ts, da_load_mw, rt_load_mw FROM clean_zone_demand "
           "WHERE zone=? ORDER BY ts", (zone_pick,))
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    zd["date"] = zd["ts"].dt.tz_convert(EASTERN).dt.date
    daily = zd.groupby("date")[["da_load_mw", "rt_load_mw"]].max()
    daily.index = pd.to_datetime(daily.index)
    daily = daily.reindex(pd.date_range(daily.index.min(), daily.index.max()))
    fig = go.Figure()
    fig.add_scatter(x=daily.index, y=daily["rt_load_mw"],
                    name="Actual daily max", connectgaps=False)
    fig.add_scatter(x=daily.index, y=daily["da_load_mw"],
                    name="Day-ahead daily max", line=dict(dash="dot"),
                    connectgaps=False)
    fig.update_layout(height=380, yaxis_title="MW")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Full history 2022 → today. Our LightGBM+ISO blend beats ISO's "
               "day-ahead on every window tested (latest: 3.24% vs 3.66%).")

# ---------------- Money ----------------
with tab_money:
    st.subheader("Dollar exposure by town")
    st.caption(f"RNS 2026: ${RNS_RATE}/kW-yr · FCA18: ${FCA_RATE}/kW-mo · "
               "tag proxied by latest summer settlement value.")
    st.info("**Why transmission exceeds capacity:** capacity is set by ONE "
            "hour a year (the annual coincident peak → the capacity tag, "
            f"billed at ${FCA_RATE}/kW-mo = ${FCA_RATE * 12:.0f}/kW-yr). "
            "Transmission (RNS) is charged on TWELVE hours — each month's "
            f"regional peak — at ${RNS_RATE}/kW-yr, over 4× the capacity "
            "rate. A decade ago capacity dominated; New England transmission "
            "rates have since tripled, flipping the ledger. Upside: twelve "
            "chances a year to save, not one.")
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
