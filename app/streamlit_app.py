# -----------------------------
# IMPORT FIX (RENDER SAFE)
# -----------------------------
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# -----------------------------
# IMPORTS
# -----------------------------
import streamlit as st
import psycopg2
import pandas as pd
import json
import plotly.express as px

from config import settings
from backend import database
from backend.weather_engine import get_irrigation_advice

# -----------------------------
# PAGE CONFIG (MUST BE FIRST STREAMLIT CALL)
# -----------------------------
st.set_page_config(page_title="FarmSight Dashboard", layout="wide")

st.title("🌾 FarmSight Agricultural Intelligence Dashboard")

# -----------------------------
# CACHE WEATHER
# -----------------------------
@st.cache_data(ttl=3600)
def cached_irrigation_advice(lon, lat):
    return get_irrigation_advice(lon, lat)

# -----------------------------
# DB CONNECTION
# -----------------------------
conn = database.connect_db(settings.DB_URL)
cur = conn.cursor()

cur.execute("""
    SELECT id, farmer_name, crop_type,
           ST_AsGeoJSON(geom),
           last_ndvi,
           ndvi_history
    FROM farms;
""")

farm_data = cur.fetchall()

farm_locations = []
alert_logs = []
ndvi_series = {}

# -----------------------------
# SAFE GEO + DATA PROCESSING
# -----------------------------
for fid, name, crop, geojson_str, last_ndvi, history in farm_data:

    geo = json.loads(geojson_str)

    # SAFE CENTROID (Polygon only MVP-safe version)
    coords = geo["coordinates"][0]

    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]

    lon = sum(lons) / len(lons)
    lat = sum(lats) / len(lats)

    farm_locations.append({
        "farmer": name,
        "lat": lat,
        "lon": lon,
        "ndvi": last_ndvi or 0
    })

    # -----------------------------
    # NDVI HISTORY NORMALIZATION
    # -----------------------------
    if history:
        try:
            # Accept BOTH formats safely
            if isinstance(history[0], dict):
                ndvi_series[name] = history
            else:
                ndvi_series[name] = [
                    {"date": str(i), "ndvi": v}
                    for i, v in enumerate(history)
                ]
        except:
            pass

    # -----------------------------
    # STATUS LOGIC
    # -----------------------------
    if last_ndvi is None:
        status = "⚪ No Data"
    elif last_ndvi >= 0.6:
        status = "🟢 Healthy"
    elif last_ndvi >= 0.4:
        status = "🟡 Moderate"
    else:
        status = "🔴 At Risk"

    # -----------------------------
    # WEATHER INSIGHT
    # -----------------------------
    try:
        advice = cached_irrigation_advice(lon, lat)
    except:
        advice = "⚠ Weather unavailable"

    alert_logs.append({
        "Farmer": name,
        "Crop": crop,
        "NDVI": round(last_ndvi or 0, 3),
        "Status": status,
        "Irrigation": advice
    })

cur.close()
conn.close()

# -----------------------------
# DATAFRAMES
# -----------------------------
df = pd.DataFrame(farm_locations)
df_alerts = pd.DataFrame(alert_logs)

# -----------------------------
# KPI METRICS
# -----------------------------
st.subheader("📊 System Overview")

col1, col2, col3 = st.columns(3)

col1.metric("🌾 Total Farms", len(df))
col2.metric("👨‍🌾 Farmers", df["farmer"].nunique() if not df.empty else 0)
col3.metric("📈 Avg NDVI", round(df["ndvi"].mean(), 3) if not df.empty else 0)

st.divider()

# -----------------------------
# MAP
# -----------------------------
st.subheader("🗺 Farm Locations")

if not df.empty:
    st.map(df[["lat", "lon"]])
else:
    st.warning("No farm data available")

# -----------------------------
# NDVI DISTRIBUTION
# -----------------------------
st.subheader("📊 NDVI Distribution")

if not df.empty:
    fig = px.histogram(df, x="ndvi", nbins=10)
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# NDVI TRENDS (CLEAN VERSION)
# -----------------------------
st.subheader("📈 NDVI Trends")

if ndvi_series:
    for name, history in ndvi_series.items():
        df_hist = pd.DataFrame(history)

        if "date" in df_hist.columns:
            df_hist["date"] = pd.to_datetime(df_hist["date"])
            df_hist = df_hist.sort_values("date")
            st.write(f"👨‍🌾 {name}")
            st.line_chart(df_hist.set_index("date")["ndvi"])

# -----------------------------
# ALERTS TABLE
# -----------------------------
st.subheader("🚨 Insights")

st.dataframe(df_alerts, use_container_width=True)

# -----------------------------
# FOOTER
# -----------------------------
st.info("FarmSight transforms satellite NDVI + weather into actionable farming intelligence.")