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
MODE = os.getenv("MODE", "LIVE")


# -----------------------------
# 🔐 GEE AUTH (FINAL + CORRECT)
# -----------------------------
def authenticate_gee():
    try:
        print("🔐 Authenticating GEE...")

        raw = os.environ.get("GEE_JSON_KEY")
        if not raw:
            raise ValueError("GEE_JSON_KEY missing in Environment Variables")

        raw = raw.strip()

        # Fix GitHub secret formatting issues
        try:
            info = json.loads(raw)
        except json.JSONDecodeError:
            print("🔧 Repairing JSON formatting...")
            fixed = raw.replace("\r", "").replace("\n", "\\n")
            info = json.loads(fixed)

        # ✅ CORRECT EARTH ENGINE SCOPE
        scopes = ["https://www.googleapis.com/auth/earthengine"]

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
# 🌱 NDVI ENGINE (STABLE)
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
            print("❌ Invalid geometry type")
            return None

        print(f"   🛰 Window: {start_date} → {end_date}")

        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(area)
            .filterDate(
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 90))
        )

        size = collection.size().getInfo()
        print(f"   📡 Images found: {size}")

        if size == 0:
            print("   ⚠️ No satellite data available")
            return None

        # Cloud masking
        def mask(img):
            qa = img.select("QA60")
            cloud = qa.bitwiseAnd(1 << 10).eq(0)
            cirrus = qa.bitwiseAnd(1 << 11).eq(0)
            return img.updateMask(cloud.And(cirrus))

        # 🔥 Use MEDIAN composite (stable NDVI)
        image = collection.map(mask).median()

        ndvi = image.normalizedDifference(["B8", "B4"]).rename("nd")

        result = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=area,
            scale=10,
            maxPixels=1e9
        )

        value = result.get("nd").getInfo()

        print(f"   🌱 NDVI VALUE: {value}")

        return value

    except Exception as e:
        print(f"⚠️ NDVI ERROR: {e}")
        return None


# -----------------------------
# 🚀 MAIN ENGINE (LIVE DATA)
# -----------------------------
def run_intelligence_cycle():
    print("\n🚀 ENGINE STARTING...")
    print(f"🌍 MODE: {MODE}")

    authenticate_gee()

    print("📡 Connecting to Database...")
    conn = database.connect_db(settings.DB_URL)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, farmer_name, ST_AsGeoJSON(geom),
               last_processed_date, ndvi_history, phone_number
        FROM farms;
    """)

    farms = cur.fetchall()
    print(f"📊 Farms found: {len(farms)}")

    if len(farms) == 0:
        print("❌ No farms found in database")
        return

    for fid, name, geojson_str, last_date, history, phone in farms:

        print(f"\n👨‍🌾 Processing: {name}")

        # 🔥 REAL DATA WINDOW (last 30 days)
        new_end = datetime.utcnow().date()
        new_start = new_end - timedelta(days=30)

        print(f"   ⏳ Window: {new_start} → {new_end}")

        geojson = json.loads(geojson_str)
        current_ndvi = get_smart_ndvi(geojson, new_start, new_end)

        history_list = list(history) if history else []

        # -----------------------------
        # NO DATA CASE
        # -----------------------------
        if current_ndvi is None:
            print("   ☁️ No NDVI data")

            history_list.append({
                "date": str(new_start),
                "ndvi": None
            })

            cur.execute("""
                UPDATE farms
                SET last_processed_date = %s,
                    ndvi_history = %s
                WHERE id = %s
            """, (new_start, json.dumps(history_list), fid))

            continue

        # -----------------------------
        # TREND ANALYSIS
        # -----------------------------
        prev = None
        for h in reversed(history_list):
            if isinstance(h, dict) and h.get("ndvi") is not None:
                prev = h["ndvi"]
                break

        delta = current_ndvi - prev if prev is not None else 0

        if delta < -0.10:
            status = "🚨 DROPPING"
            alert = True
        elif delta > 0.08:
            status = "📈 IMPROVING"
            alert = False
        else:
            status = "✅ STABLE"
            alert = False

        # -----------------------------
        # UPDATE HISTORY
        # -----------------------------
        history_list.append({
            "date": str(new_start),
            "ndvi": round(current_ndvi, 3)
        })

        if len(history_list) > 15:
            history_list.pop(0)

        # -----------------------------
        # SAVE TO DATABASE
        # -----------------------------
        cur.execute("""
            UPDATE farms
            SET last_ndvi = %s,
                last_processed_date = %s,
                ndvi_history = %s
            WHERE id = %s
        """, (
            current_ndvi,
            new_start,
            json.dumps(history_list),
            fid
        ))

        print(f"   {status} | NDVI={current_ndvi:.3f} | Δ={delta:.3f}")

        if alert:
            print(f"   📩 ALERT READY → {phone}")

    conn.commit()
    cur.close()
    conn.close()

    print("\n🏁 ENGINE COMPLETE")


# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    print("🚀 BOOTING FARMSIGHT ENGINE...")

    try:
        run_intelligence_cycle()
        print("✅ SUCCESS")
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")
        sys.exit(1)