import ee
import json
import os
import sys
from google.oauth2 import service_account
from datetime import datetime, timedelta

# -----------------------------
# IMPORT PATH FIX
# -----------------------------
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from backend import database

# -----------------------------
# MODE CONFIG
# -----------------------------
MODE = os.getenv("MODE", "SIMULATION")


# -----------------------------
# 🔐 GEE AUTH (HARDENED)
# -----------------------------
def authenticate_gee():
    try:
        print("🔐 Authenticating GEE...")

        raw = os.environ.get("GEE_JSON_KEY")
        if not raw:
            raise ValueError("GEE_JSON_KEY missing in Environment Variables")

        raw = raw.strip()

        # Fix common GitHub Secret formatting issues
        try:
            info = json.loads(raw)
        except json.JSONDecodeError:
            print("🔧 Repairing JSON formatting...")
            fixed = raw.replace("\r", "").replace("\n", "\\n")
            info = json.loads(fixed)

        # ✅ EXACT SCOPES (Must be these specific URLs)
        scopes = [
            "https://googleapis.com",
            "https://googleapis.com"
        ]

        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=scopes
        )

        ee.Initialize(
            credentials=credentials,
            project=os.getenv("GEE_PROJECT_ID")
        )

        print("✅ GEE Authenticated Successfully")

    except Exception as e:
        print(f"❌ GEE Auth Failed: {e}")
        raise

# -----------------------------
# 🌱 NDVI ENGINE
# -----------------------------
def get_smart_ndvi(geojson_obj, start_date, end_date):
    try:
        if not geojson_obj:
            return None

        g_type = geojson_obj.get("type")
        if g_type == "Polygon":
            area = ee.Geometry.Polygon(geojson_obj["coordinates"])
        elif g_type == "MultiPolygon":
            area = ee.Geometry.MultiPolygon(geojson_obj["coordinates"])
        else:
            return None

        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(area)
            .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
        )

        if collection.size().getInfo() == 0:
            return None

        def mask(img):
            qa = img.select("QA60")
            return img.updateMask(qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0)))

        image = collection.map(mask).median()
        ndvi = image.normalizedDifference(["B8", "B4"]).rename("nd")

        result = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=area,
            scale=10,
            maxPixels=1e9
        )

        return result.get("nd").getInfo()

    except Exception as e:
        print(f"⚠️ NDVI ERROR: {e}")
        return None


# -----------------------------
# 🚀 MAIN ENGINE
# -----------------------------
def run_intelligence_cycle():
    print("\n🚀 ENGINE STARTING...")
    authenticate_gee()

    conn = database.connect_db(settings.DB_URL)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, farmer_name, ST_AsGeoJSON(geom),
               last_processed_date, ndvi_history, phone_number
        FROM farms;
    """)

    farms = cur.fetchall()
    print(f"📊 Farms found: {len(farms)}")

    for fid, name, geojson_str, last_date, history, phone in farms:
        print(f"\n👨‍🌾 Processing: {name}")

        base_date = last_date if last_date else datetime(2023, 1, 1).date()
        new_start = base_date + timedelta(days=5)
        new_end = new_start + timedelta(days=10)

        current_ndvi = get_smart_ndvi(json.loads(geojson_str), new_start, new_end)
        history_list = list(history) if history else []

        if current_ndvi is None:
            print("   ☁️ No Data")
            history_list.append({"date": str(new_start), "ndvi": None})
        else:
            # Trend Analysis
            prev = next((h["ndvi"] for h in reversed(history_list) if isinstance(h, dict) and h.get("ndvi") is not None), None)
            delta = current_ndvi - prev if prev is not None else 0
            
            status = "🚨 DROPPING" if delta < -0.10 else "📈 IMPROVING" if delta > 0.08 else "✅ STABLE"
            
            history_list.append({"date": str(new_start), "ndvi": round(current_ndvi, 3)})
            if len(history_list) > 15: history_list.pop(0)

            cur.execute("""
                UPDATE farms SET last_ndvi = %s, last_processed_date = %s, ndvi_history = %s WHERE id = %s
            """, (current_ndvi, new_start, json.dumps(history_list), fid))
            print(f"   {status} | NDVI={current_ndvi:.3f} | Δ={delta:.3f}")

    conn.commit()
    cur.close()
    conn.close()
    print("\n🏁 CYCLE COMPLETE")

if __name__ == "__main__":
    try:
        run_intelligence_cycle()
    except Exception as e:
        print(f"❌ FATAL: {e}")
        sys.exit(1)
