%%writefile streamlit_app.py
import streamlit as st
import psycopg2
import pandas as pd
import json
import settings
import database

st.title("FarmSight Dashboard")

# --- Fetch Data from Database ---
conn = database.connect_db(settings.DB_URL)
cur = conn.cursor()

# Fetch farm locations and details
cur.execute("SELECT id, farmer_name, crop_type, ST_AsGeoJSON(geom), last_ndvi, ndvi_history FROM farms;")
farm_data = cur.fetchall()

# Prepare data for Streamlit
farm_locations = []
alert_logs = []
ndvi_history_data = {}

for farm in farm_data:
    fid, name, crop, geojson_str, last_ndvi, history_json = farm
    geojson_obj = json.loads(geojson_str)

    # For st.map, we need central coordinates (e.g., centroid of the polygon)
    # This is a simplified approach, a proper centroid calculation might be needed for complex polygons
    # For simplicity, let's use the first coordinate of the first polygon ring as a proxy
    if geojson_obj and geojson_obj['coordinates']:
        lon = geojson_obj['coordinates'][0][0][0]
        lat = geojson_obj['coordinates'][0][0][1]
    else:
        lon, lat = 0, 0 # Fallback for invalid geometry

    farm_locations.append({
        'id': fid,
        'farmer_name': name,
        'crop_type': crop,
        'latitude': lat,
        'longitude': lon,
        'last_ndvi': last_ndvi
    })

    # Store NDVI history for line chart
    if history_json:
        ndvi_history_data[name] = history_json

    # Simulate alert logs (based on last_ndvi for demonstration)
    if last_ndvi < 0.5:
        alert_logs.append({
            'Farm ID': fid,
            'Farmer': name,
            'Crop': crop,
            'Last NDVI': f"{last_ndvi:.2f}",
            'Status': '🔴 Low Vegetation',
            'Action': 'Alert Sent'
        })
    elif last_ndvi < 0.7:
        alert_logs.append({
            'Farm ID': fid,
            'Farmer': name,
            'Crop': crop,
            'Last NDVI': f"{last_ndvi:.2f}",
            'Status': '🟡 Medium Vegetation',
            'Action': 'Monitor'
        })

cur.close()
conn.close()

# Convert to DataFrames
if farm_locations:
    df_farm_locations = pd.DataFrame(farm_locations)

    # Add a color column based on last_ndvi for st.map
    def get_ndvi_color(ndvi):
        if ndvi < 0.5: # Low vegetation
            return [255, 0, 0] # Red
        elif ndvi < 0.7: # Medium vegetation
            return [255, 165, 0] # Orange
        else: # High vegetation
            return [0, 255, 0] # Green

    df_farm_locations['ndvi_color'] = df_farm_locations['last_ndvi'].apply(get_ndvi_color)

else:
    df_farm_locations = pd.DataFrame(columns=['id', 'farmer_name', 'crop_type', 'latitude', 'longitude', 'last_ndvi', 'ndvi_color'])

if alert_logs:
    df_alert_logs = pd.DataFrame(alert_logs)
else:
    df_alert_logs = pd.DataFrame(columns=['Farm ID', 'Farmer', 'Crop', 'Last NDVI', 'Status', 'Action'])

# For line chart, create a DataFrame suitable for plotting multiple series
# This example just plots the raw history for each farmer, needs dates for proper X-axis
if ndvi_history_data:
    df_ndvi_history = pd.DataFrame.from_dict(ndvi_history_data, orient='index').transpose()
    st.subheader("NDVI History")
    st.line_chart(df_ndvi_history)

# --- Streamlit Components ---
st.subheader("Farm Locations")
st.map(df_farm_locations, latitude='latitude', longitude='longitude', size='last_ndvi', color='ndvi_color')

st.subheader("Alert Log")
st.dataframe(df_alert_logs)