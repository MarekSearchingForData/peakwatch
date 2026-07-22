"""PeakWatch dashboard — run with: streamlit run app.py"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from peakwatch.isone import ISONEClient, MA_ZONES
from peakwatch.peaks import (EASTERN, backtest_rule, daily_summary,
                             load_zone_demand, monthly_peaks)

st.set_page_config(page_title="PeakWatch — ISO-NE", page_icon="⚡", layout="wide")

ALERT_THRESHOLD = 0.97


@st.cache_data(ttl=900)
def get_demand():
    return load_zone_demand()


@st.cache_data(ttl=300)
def get_live():
    try:
        return ISONEClient().five_minute_system_load_current()
    except Exception:
        return {}


st.title("⚡ PeakWatch — ISO-NE Peak Intelligence")
st.caption("Peak-day alerting for municipal utilities: capacity tags and "
           "transmission charges are set in a handful of hours — these are they.")

try:
    df = get_demand()
except FileNotFoundError:
    st.error("No consolidated demand data yet. Run: py scripts/ingest_load.py")
    st.stop()

tab_risk, tab_zones, tab_health = st.tabs(
    ["🎯 Peak Risk", "📈 Zones & History", "🩺 Data Health"])

# ---------- Peak Risk ----------
with tab_risk:
    live = get_live()
    if live:
        c1, c2, c3 = st.columns(3)
        c1.metric("Live system load", f"{live['load_mw']:,.0f} MW")
        c2.metric("Native load", f"{live['native_load_mw']:,.0f} MW")
        c3.metric("As of", str(live["timestamp"]))

    today = pd.Timestamp.now(tz=EASTERN).normalize().tz_localize(None)
    st.subheader(f"Peak-day risk — {today.date()}")
    rows = []
    for zone, label in [(None, "SYSTEM")] + [(z, z) for z in MA_ZONES]:
        daily = daily_summary(df, zone)
        month_days = daily[daily["month"] == today.to_period("M")]
        if today not in daily.index:
            continue
        da_today = daily.loc[today, "da_max"]
        prior = month_days[month_days.index < today]
        running_max = prior["rt_max"].max()
        ratio = da_today / running_max if running_max and running_max > 0 else float("inf")
        alert = ratio >= ALERT_THRESHOLD
        # predicted peak window from today's DA hourly profile
        if zone:
            prof = df[(df["Zone"] == zone) & (df["Local"].dt.date == today.date())]
        else:
            prof = (df[df["Local"].dt.date == today.date()]
                    .groupby("Local", as_index=False)["DaLoad_MW"].sum())
        peak_hr = (prof.loc[prof["DaLoad_MW"].idxmax(), "Local"].hour
                   if len(prof) and prof["DaLoad_MW"].notna().any() else None)
        rows.append({
            "Zone": label,
            "Today DA max (MW)": None if pd.isna(da_today) else round(da_today),
            "Month-to-date actual max (MW)":
                None if pd.isna(running_max) else round(running_max),
            "Ratio": None if ratio == float("inf") else round(ratio, 3),
            "Predicted peak hour": f"{peak_hr}:00" if peak_hr is not None else "—",
            "ALERT": "🔴 PEAK RISK" if alert else "🟢 low",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(f"Alert rule: today's ISO day-ahead max ≥ {ALERT_THRESHOLD:.0%} of the "
                   "month-to-date actual max. Transparent by design — every number above "
                   "is traceable to ISO-NE published data.")
    else:
        st.info("Today's day-ahead data not ingested yet. Run: py scripts/ingest_load.py")

# ---------- Zones & History ----------
with tab_zones:
    zone_pick = st.selectbox("Zone", ["SYSTEM"] + MA_ZONES + ["ME", "NH", "VT", "CT", "RI"])
    zsel = None if zone_pick == "SYSTEM" else zone_pick
    daily = daily_summary(df, zsel)

    st.subheader("Daily peak load")
    fig = go.Figure()
    fig.add_scatter(x=daily.index, y=daily["rt_max"], name="Actual (RT) daily max",
                    mode="lines")
    fig.add_scatter(x=daily.index, y=daily["da_max"], name="Day-ahead daily max",
                    mode="lines", line=dict(dash="dot"))
    fig.update_layout(height=400, yaxis_title="MW")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Monthly coincident peaks")
    peaks = monthly_peaks(daily)
    peaks_disp = peaks.copy()
    peaks_disp.index = peaks_disp.index.astype(str)
    st.dataframe(peaks_disp.rename(columns={
        "rt_max": "Peak (MW)", "rt_peak_hour": "Hour", "peak_day": "Day"}),
        use_container_width=True)

    st.subheader("Backtest: would the alert rule have caught the peaks?")
    r = backtest_rule(daily, zone_pick, ALERT_THRESHOLD)
    c1, c2, c3 = st.columns(3)
    c1.metric("Monthly peaks caught", f"{r.hits}/{r.months}")
    c2.metric("Hit rate", f"{r.hit_rate:.0%}" if r.months else "—")
    c3.metric("Avg alert days / month", f"{r.alert_days_per_month:.1f}")

# ---------- Data Health ----------
with tab_health:
    st.subheader("Coverage")
    daily_sys = daily_summary(df)
    c1, c2, c3 = st.columns(3)
    c1.metric("Days ingested", len(daily_sys))
    c2.metric("Span", f"{daily_sys.index.min().date()} → {daily_sys.index.max().date()}")
    c3.metric("Days awaiting RT settlement", int(daily_sys["rt_max"].isna().sum()))

    st.subheader("Day-ahead vs actual agreement (sanity check)")
    rows = []
    for zone, g in df.dropna(subset=["DaLoad_MW", "RtLoad_MW"]).groupby("Zone"):
        rows.append({"Zone": zone,
                     "Correlation": round(g["DaLoad_MW"].corr(g["RtLoad_MW"]), 3),
                     "Mean bias (MW)": round((g["DaLoad_MW"] - g["RtLoad_MW"]).mean())})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("Zone labels verified against ISO-NE /locations on 2026-07-22. "
               "CT should be the largest zone, VT the smallest.")

    st.subheader("Mean zone load ranking")
    means = df.groupby("Zone")["RtLoad_MW"].mean().sort_values(ascending=False)
    st.plotly_chart(px.bar(means, labels={"value": "Mean MW", "Zone": ""}),
                    use_container_width=True)
