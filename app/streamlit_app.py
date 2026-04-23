import streamlit as st
import psycopg2
import pandas as pd
import json
import settings
import database
import plotly.express as px
from weather_engine import get_irrigation_advice

@st.cache_data(ttl=3600)  # Cache weather for 1 hour
def cached_irrigation_advice(lon, lat):
    return get_irrigation_advice(lon, lat)

st.set_page_config(page_title="FarmSight Dashboard", layout="wide")

st.title("🌾 FarmSight Agricultural Intelligence Dashboard")

# -----------------------------
# DB CONNECTION
# -----------------------------
conn = database.connect_db(settings.DB_URL)
cur = conn.cursor()

cur.execute("""
    SELECT id, farmer_name, crop_type, ST_AsGeoJSON(geom), last_ndvi, ndvi_history
    FROM farms;
""")

farm_data = cur.fetchall()

farm_locations = []
alert_logs = []

# -----------------------------
# PROCESS DATA
# -----------------------------
for farm in farm_data:
    fid, name, crop, geojson_str, last_ndvi, history = farm

    geo = json.loads(geojson_str)

    # ✅ SAFE CENTROID 
    coords = geo["coordinates"][0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]

    lon = sum(lons) / len(lons)
    lat = sum(lats) / len(lats)

    farm_locations.append({
        "id": fid,
        "farmer": name,
        "crop": crop,
        "lat": lat,
        "lon": lon,
        "ndvi": last_ndvi or 0
    })

    # -----------------------------
    # REAL INSIGHT LAYER
    # -----------------------------
    if last_ndvi is None:
        status = "⚪ No Data"
    elif last_ndvi >= 0.6:
        status = "🟢 Healthy"
    elif last_ndvi >= 0.4:
        status = "🟡 Moderate"
    else:
        status = "🔴 At Risk"

    # Irrigation advice (real value layer)
    try:
        advice = get_irrigation_advice(lon, lat)
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

df = pd.DataFrame(farm_locations)
df_alerts = pd.DataFrame(alert_logs)

# -----------------------------
# KPI METRICS
# -----------------------------
col1, col2, col3 = st.columns(3)

col1.metric("🌾 Total Farms", len(df))
col2.metric("👨‍🌾 Farmers", df["farmer"].nunique() if not df.empty else 0)
col3.metric("📊 Avg NDVI", round(df["ndvi"].mean(), 3) if not df.empty else 0)

st.divider()

# -----------------------------
# MAP VIEW
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
    fig = px.histogram(df, x="ndvi", nbins=10, title="NDVI Spread Across Farms")
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# ALERT + INSIGHTS TABLE
# -----------------------------
st.subheader("🚨 Farm Insights & Recommendations")

st.dataframe(df_alerts, use_container_width=True)

# -----------------------------
# FOOTER INSIGHT
# -----------------------------
st.info(
    "FarmSight converts satellite NDVI + weather data into actionable farming decisions."
)