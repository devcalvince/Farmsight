# Farmsight
FarmSight Crop Health Monitoring System
This project provides a robust system for monitoring crop health using satellite imagery, weather data, and PostgreSQL with PostGIS for spatial data management. It leverages Google Earth Engine (GEE) for NDVI calculations, Open-Meteo for irrigation advice, and Africa's Talking for SMS alerts to farmers. A Streamlit dashboard offers a user-friendly interface for visualization and monitoring.

Features
NDVI Calculation: Utilizes Sentinel-2 satellite data via Google Earth Engine to compute Normalized Difference Vegetation Index (NDVI) for farm plots.
Time-Series Analysis: Implements a rolling average to detect significant drops in crop health and trigger alerts.
Weather Integration: Fetches real-time precipitation forecasts to provide context-aware irrigation advice.
SMS Alerts: Notifies farmers via SMS about critical changes in crop health and recommended actions.
PostGIS Database: Stores farm geometries, farmer details, and NDVI history efficiently.
Streamlit Dashboard: Provides an interactive web interface to visualize farm locations, NDVI trends, and alert logs.
Components
settings.py: Manages API keys and database connection strings securely using Colab secrets.
database.py: Handles all database operations, including schema initialization, adding farmers, and data cleanup.
ndvi_engine.py: Contains the logic for fetching and calculating NDVI from GEE.
weather_engine.py: Provides functions to retrieve weather data and generate irrigation advice.
alert_engine.py: Manages sending SMS alerts to farmers.
streamlit_app.py: The main script for the Streamlit web dashboard.
Setup and Usage
Install Dependencies: Run pip install -r requirements.txt (or the individual packages listed).
Google Earth Engine (GEE) Setup:
Authenticate with ee.Authenticate().
Initialize GEE with your GEE_PROJECT_ID.
Colab Secrets: Set up DB_URL, AT_API_KEY, and GEE_PROJECT_ID as Colab secrets.
Database Initialization: Run the init_db function to set up your PostgreSQL database.
Add Farmers: Use the add_farmer function to register farm plots.
Run Time-Series Check: Execute the run_time_series_check function to perform NDVI analysis and trigger alerts.
Launch Streamlit Dashboard: Run streamlit run streamlit_app.py in your terminal or Colab cell.