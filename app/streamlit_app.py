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
# PAGE CONFIG (MUST BE FIRST)
# -----------------------------
st.set_page_config(page_title="FarmSight Dashboard", layout="wide")

st.title("🌾 FarmSight Agricultural Intelligence Dashboard")

# -----------------------------
# CACHE WEATHER API
# -----------------------------
@st.cache_data(ttl=3600)
def cached_irrigation_advice(lon, lat):
    return get_irrigation_advice(lon, lat)

# -----------------------------
# DATABASE CONNECTION
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
# SAFE PROCESSING
# -----------------------------
for fid, name, crop, geojson_str, last_ndvi, history in farm_data:

    try:
        geo = json.loads(geojson_str)
    except:
        continue

    coords = geo.get("coordinates", None)
    if not coords:
        continue

    # -----------------------------
    # SAFE CENTROID (Polygon only MVP-safe)
    # -----------------------------
    try:
        ring = coords[0]
        lons = [c[0] for c in ring]
        lats = [c[1] for c in ring]

        lon = sum(lons) / len(lons)
        lat = sum(lats) / len(lats)

    except:
        continue

    farm_locations.append({
        "farmer": name,
        "lat": lat,
        "lon": lon,
        "ndvi": last_ndvi or 0
    })

    # -----------------------------
    # CLEAN NDVI HISTORY
    # -----------------------------
    clean_history = []

    if history:
        try:
            for entry in history:

                # valid format only
                if isinstance(entry, dict):
                    if entry.get("date") and entry.get("ndvi") is not None:
                        clean_history.append(entry)

        except:
            pass

    if clean_history:
        ndvi_series[name] = clean_history

    # -----------------------------
    # STATUS ENGINE
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
    # WEATHER LAYER
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
        "Irrigation Advice": advice
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
# NDVI TRENDS (SAFE VERSION)
# -----------------------------
st.subheader("📈 NDVI Trends")

if ndvi_series:

    for name, history in ndvi_series.items():

        try:
            df_hist = pd.DataFrame(history)

            if "date" in df_hist.columns:
                df_hist["date"] = pd.to_datetime(df_hist["date"], errors="coerce")
                df_hist = df_hist.dropna(subset=["date"])
                df_hist = df_hist.sort_values("date")

                if not df_hist.empty:
                    st.write(f"👨‍🌾 {name}")
                    st.line_chart(df_hist.set_index("date")["ndvi"])

        except:
            continue

# -----------------------------
# ALERT TABLE
# -----------------------------
st.subheader("🚨 Insights & Recommendations")

st.dataframe(df_alerts, use_container_width=True)

# -----------------------------
# FOOTER
# -----------------------------
st.info(
    "FarmSight converts satellite NDVI + weather into actionable farming intelligence."
)