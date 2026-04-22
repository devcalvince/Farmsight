🌾 FarmSight – Agricultural Intelligence System

FarmSight is a satellite-driven agricultural intelligence platform that helps farmers and agricultural organizations monitor crop health, detect stress early, and receive actionable recommendations using AI, remote sensing, and weather forecasting.

It bridges the gap between space-based data and real-world farming decisions in low-resource environments.

🚨 Problem Statement

Farmers often make decisions without real-time field data.

This leads to:

Low crop yield
Delayed disease detection
Inefficient irrigation
Poor resource allocation

FarmSight solves this by turning satellite imagery into simple, actionable SMS-based insights.

🧠 System Overview

FarmSight integrates multiple data sources:

Satellite imagery (Sentinel-2)
Weather forecasting (Open-Meteo API)
Spatial database (PostgreSQL + PostGIS)
SMS alerts (Africa’s Talking)
AI-based trend detection
⚙️ Core Features
🌱 Crop Health Monitoring

NDVI-based vegetation analysis using Sentinel-2 imagery.

📈 Time-Series Intelligence

Rolling average + trend detection for anomaly identification.

🌦 Irrigation Advisory System

Weather-based irrigation recommendations using Open-Meteo.

📩 SMS Alert System

Real-time alerts sent to farmers via Africa’s Talking.

🗺 Spatial Farm Mapping

PostGIS-powered farm polygon storage and queries.

📊 Streamlit Dashboard

Interactive visualization of farms, NDVI trends, and alerts.

🏗 System Architecture
Satellite Data (Sentinel-2)
        ↓
NDVI Processing Engine
        ↓
Time-Series Trend Analyzer
        ↓
Weather API Integration
        ↓
Decision Engine (Risk + Irrigation Logic)
        ↓
PostGIS Database
        ↓
SMS Alert System
        ↓
Streamlit Dashboard
📁 Project Structure
farmsight/
│
├── backend/
│   ├── ndvi_engine.py
│   ├── weather_engine.py
│   ├── alert_engine.py
│   ├── database.py
│
├── app/
│   ├── streamlit_app.py
│
├── config/
│   ├── settings.py
│
├── requirements.txt
└── README.md
🚀 Setup & Installation
1. Install dependencies
pip install -r requirements.txt
2. Environment Variables

Set the following securely:

DB_URL → PostgreSQL connection string
AT_API_KEY → Africa’s Talking API key
GEE_PROJECT_ID → Google Earth Engine project ID
3. Google Earth Engine Setup
ee.Authenticate()
ee.Initialize(project=GEE_PROJECT_ID)
4. Initialize Database
from database import init_db
init_db()
5. Add Test Farmers
add_farmer(...)
6. Run System
NDVI Pipeline
run_time_series_check()
Dashboard
streamlit run streamlit_app.py
📊 Key Technologies
Google Earth Engine
Sentinel-2 Satellite Data
PostgreSQL + PostGIS
Streamlit
Open-Meteo API
Africa’s Talking SMS API
🧪 MVP Status

✔ Crop Health Monitoring
✔ Time-Series NDVI Analysis
✔ SMS Alert System
✔ Weather-Based Irrigation Advice
✔ Spatial Database Integration
⚠ Farm Boundary UI (manual GeoJSON)

🌍 Future Vision

FarmSight will evolve into a full agricultural intelligence and fintech system providing:

Crop yield prediction
Climate risk forecasting
Farm credit scoring (Farm Trust Score)
Agricultural supply chain optimization
