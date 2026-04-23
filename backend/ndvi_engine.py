import ee
import json
import os
from google.oauth2 import service_account

def authenticate_gee():
    # Pull the JSON string from Environment Variables
    json_key = os.getenv('GEE_JSON_KEY')
    if not json_key:
        raise Exception("❌ GEE_JSON_KEY not found in Environment Variables!")
    
    # Parse the JSON string
    info = json.loads(json_key)
    credentials = service_account.Credentials.from_service_account_info(info)
    
    # Initialize Earth Engine with Service Account credentials
    ee.Initialize(credentials=credentials, project=os.getenv('GEE_PROJECT_ID'))

def get_ndvi_for_date(geojson_obj, date):
    # Ensure we are authenticated before any call
    try:
        authenticate_gee()
    except Exception as e:
        print(f"Auth Error: {e}")
        return None

    area = ee.Geometry(geojson_obj)
    start = ee.Date(date).advance(-5, 'day')
    end = start.advance(10, 'day') # 10-day window increases chance of clear image
    
    collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterBounds(area) \
        .filterDate(start, end) \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40))

    if collection.size().getInfo() == 0:
        return None

    image = collection.median()
    image = image.updateMask(image.select('QA60').eq(0)) # Proper cloud masking
    ndvi = image.normalizedDifference(['B8', 'B4'])
    
    stats = ndvi.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=area,
        scale=10
    )
    return stats.get('nd').getInfo()
