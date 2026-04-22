%%writefile ndvi_engine.py
import ee

def get_ndvi_for_date(geojson_obj, date):
    area = ee.Geometry(geojson_obj)
    start = ee.Date(date).advance(-7, 'day')
    end = start.advance(7, 'day')
    collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterBounds(area) \
        .filterDate(start, end) \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 50))

    if collection.size().getInfo() == 0:
        return None

    image = collection.median()
    image = image.updateMask(image.select('QA60').Not())
    ndvi = image.normalizedDifference(['B8', 'B4'])
    stats = ndvi.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=area,
        scale=10
    )
    value = stats.get('nd').getInfo()
    return value