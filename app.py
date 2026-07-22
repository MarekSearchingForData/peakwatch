"""PeakWatch dashboard — streamlit run app.py
Reads ONLY from the store (peakwatch.db); collectors fill it via
`py -m peakwatch refresh`.
"""
import sqlite3

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from peakwatch.analytics import climatology, risk_flags, survival_runway
from peakwatch.isone import ISONEClient
from peakwatch.peaks import EASTERN
from peakwatch.store import DB_PATH

st.set_page_config(page_title="PeakWatch — ISO-NE", page_icon="⚡", layout="wide")


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


st.title("⚡ PeakWatch")
st.caption("Peak intelligence for municipal utilities — capacity tags and "
           "transmission charges are set in a handful of hours; these are they.")

tab_risk, tab_towns, tab_zones, tab_health = st.tabs(
    ["🎯 Peak Risk", "🏘️ Towns", "📈 Zones", "🩺 Health"])

# ---------------- Peak Risk ----------------
with tab_risk:
    live = get_live()
    if live:
        c1, c2, c3 = st.columns(3)
        c1.metric("Live system load", f"{live['load_mw']:,.0f} MW")
        c2.metric("Behind-the-meter PV est.", f"{live['btm_pv_mw']:,.0f} MW")
        c3.metric("As of", str(live["timestamp"])[:16])

    st.subheader("Next days — ISO forecast vs month-to-date max")
    flags, mtd = risk_flags(_con())
    if len(flags):
        st.dataframe(flags, use_container_width=True, hide_index=True)
        st.caption(f"Month-to-date actual max: "
                   f"{'n/a — awaiting current-month data' if mtd != mtd else f'{mtd:,.0f} MW'}. "
                   "Flag = ISO's forecast peak ≥ 95% of month-to-date max.")

    st.subheader("Peak runway (from history)")
    clim = climatology(_con())
    st.dataframe(survival_runway(clim).round(2), use_container_width=True,
                 hide_index=True)
    st.caption("Empirical P(monthly peak is still ahead) given the day of the "
               "month — winter peaks come early, summer risk stays live longer.")

# ---------------- Towns ----------------
with tab_towns:
    towns = q("SELECT DISTINCT town FROM clean_town_rnl ORDER BY town")["town"]
    town = st.selectbox("Town", towns)

    rnl = q("SELECT month, rnl_mw FROM clean_town_rnl WHERE town=? ORDER BY month",
            (town,))
    c1, c2, c3 = st.columns(3)
    if len(rnl):
        latest = rnl.iloc[-1]
        c1.metric(f"Latest settlement RNL ({latest['month']})",
                  f"{latest['rnl_mw']:.2f} MW")
        c2.metric("12-mo max", f"{rnl['rnl_mw'].tail(12).max():.2f} MW")
        yoy = rnl["rnl_mw"].tail(12).mean() - rnl["rnl_mw"].tail(24).head(12).mean()
        c3.metric("Avg vs prior year", f"{yoy:+.2f} MW")

    st.subheader("Monthly peak-hour load (settlement truth)")
    fig = px.bar(rnl, x="month", y="rnl_mw", labels={"rnl_mw": "MW", "month": ""})
    fig.update_layout(height=320)
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Generation portfolio")
        pf = q("SELECT tech, nameplate_mw, status, confidence FROM town_portfolio "
               "WHERE town=? ORDER BY nameplate_mw DESC", (town,))
        st.dataframe(pf, use_container_width=True, hide_index=True)
    with col_b:
        st.subheader("Customer class mix (EIA-861)")
        mix = q("SELECT * FROM town_class_mix WHERE town=?", (town,))
        if len(mix) and pd.notna(mix["res_mwh"].iloc[0]):
            m = mix.iloc[0]
            pie = px.pie(values=[m["res_mwh"], m["com_mwh"], m["ind_mwh"]],
                         names=["Residential", "Commercial", "Industrial"], hole=0.5)
            pie.update_layout(height=280, margin=dict(t=10, b=10))
            st.plotly_chart(pie, use_container_width=True)
        elif len(mix):
            st.metric("Annual sales (short-form filer, no class detail)",
                      f"{mix['total_mwh'].iloc[0]:,.0f} MWh")

    score = q("SELECT run_at, model, metric, value FROM forecast_scorecard "
              "WHERE target=? AND model LIKE 'zoo_%' "
              "AND run_at=(SELECT MAX(run_at) FROM forecast_scorecard "
              "WHERE target=? AND model LIKE 'zoo_%') ORDER BY value", (town, town))
    if len(score):
        st.subheader("Model zoo — latest scores")
        st.dataframe(score[["model", "metric", "value"]].round(2),
                     use_container_width=True, hide_index=True)

# ---------------- Zones ----------------
with tab_zones:
    zones = q("SELECT DISTINCT zone FROM clean_zone_demand ORDER BY zone")["zone"]
    zone = st.selectbox("Zone", zones,
                        index=list(zones).index("WCMA") if "WCMA" in list(zones) else 0)
    zd = q("SELECT ts, da_load_mw, rt_load_mw FROM clean_zone_demand "
           "WHERE zone=? ORDER BY ts", (zone,))
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    zd["date"] = zd["ts"].dt.tz_convert(EASTERN).dt.date
    daily = zd.groupby("date")[["da_load_mw", "rt_load_mw"]].max()
    # reindex to full calendar so ungathered stretches render as gaps,
    # not as a misleading straight connector line
    daily.index = pd.to_datetime(daily.index)
    daily = daily.reindex(pd.date_range(daily.index.min(), daily.index.max()))
    missing_days = int(daily["rt_load_mw"].isna().sum())
    fig = go.Figure()
    fig.add_scatter(x=daily.index, y=daily["rt_load_mw"], name="Actual daily max",
                    connectgaps=False)
    fig.add_scatter(x=daily.index, y=daily["da_load_mw"], name="Day-ahead daily max",
                    line=dict(dash="dot"), connectgaps=False)
    fig.update_layout(height=380, yaxis_title="MW")
    st.plotly_chart(fig, use_container_width=True)
    if missing_days:
        st.info(f"{missing_days} days not yet ingested (backfill in progress) — "
                "shown as blank, never interpolated.")

# ---------------- Health ----------------
with tab_health:
    st.subheader("Latest validation run")
    ql = q("SELECT * FROM quality_log WHERE run_at=(SELECT MAX(run_at) "
           "FROM quality_log) ORDER BY check_name")
    ql["passed"] = ql["passed"].map({1: "✅", 0: "❌"})
    st.dataframe(ql, use_container_width=True, hide_index=True)

    st.subheader("Data coverage")
    cov = q("SELECT zone, COUNT(*) hours, MIN(ts) first_ts, MAX(ts) last_ts, "
            "SUM(rt_load_mw IS NULL) unsettled FROM clean_zone_demand GROUP BY zone")
    st.dataframe(cov, use_container_width=True, hide_index=True)
    st.caption("Zone labels verified against ISO-NE /locations (2026-07-22); "
               "town regions cross-checked against settlement reports.")
