import ee
import json
import os
import sys
from google.oauth2 import service_account
from datetime import datetime, timedelta

# -----------------------------
# FIX IMPORT PATHS (CRITICAL)
# -----------------------------
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from backend import database

# -----------------------------
# MODE CONFIG
# -----------------------------
MODE = os.getenv("MODE", "SIMULATION")


# -----------------------------
# GEE AUTHENTICATION
# -----------------------------
def authenticate_gee():
    try:
        print("🔐 Authenticating GEE...")

        json_key = os.environ.get("GEE_JSON_KEY")
        if not json_key:
            raise ValueError("GEE_JSON_KEY missing")

        info = json.loads(json_key.replace("\\n", "\n"))

        credentials = service_account.Credentials.from_service_account_info(info)

        ee.Initialize(
            credentials=credentials,
            project=os.getenv("GEE_PROJECT_ID")
        )

        print("✅ GEE Authenticated")

    except Exception as e:
        print(f"❌ GEE Auth Failed: {e}")
        raise


# -----------------------------
# NDVI CALCULATION
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
            print("❌ Invalid geometry")
            return None

        print(f"   🛰 Fetching imagery {start_date} → {end_date}")

        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(area)
            .filterDate(
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
            )
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))  # relaxed
        )

        size = collection.size().getInfo()
        print(f"   📡 Images found: {size}")

        if size == 0:
            return None

        # Cloud mask
        def mask(img):
            qa = img.select("QA60")
            mask = qa.bitwiseAnd(1 << 10).eq(0).And(
                qa.bitwiseAnd(1 << 11).eq(0)
            )
            return img.updateMask(mask)

        image = (
            collection.map(mask)
            .sort("CLOUDY_PIXEL_PERCENTAGE")
            .first()
        )

        ndvi = image.normalizedDifference(["B8", "B4"]).rename("nd")

        result = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=area,
            scale=10
        )

        value = result.get("nd").getInfo()

        print(f"   🌱 NDVI VALUE: {value}")

        return value

    except Exception as e:
        print(f"⚠️ NDVI Error: {e}")
        return None


# -----------------------------
# MAIN ENGINE
# -----------------------------
def run_intelligence_cycle():
    print("\n🚀 ENGINE STARTING...")
    print(f"🌍 MODE: {MODE}")

    authenticate_gee()

    print("📡 Connecting to DB...")
    conn = database.connect_db(settings.DB_URL)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, farmer_name, ST_AsGeoJSON(geom),
               last_processed_date, ndvi_history, phone_number
        FROM farms;
    """)

    farms = cur.fetchall()

    print(f"📊 FOUND {len(farms)} FARMS")

    if len(farms) == 0:
        print("❌ NO FARMS FOUND → CHECK DATABASE")
        return

    for fid, name, geojson_str, last_date, history, phone in farms:

        print(f"\n👨‍🌾 Processing: {name}")

        # -----------------------------
        # TIME ENGINE
        # -----------------------------
        if MODE == "SIMULATION":
            base_date = last_date if last_date else datetime(2023, 1, 1).date()
            step = 3
        else:
            base_date = last_date if last_date else (datetime.utcnow().date() - timedelta(days=7))
            step = 1

        new_start = base_date + timedelta(days=step)
        new_end = new_start + timedelta(days=10)

        print(f"   ⏳ Window: {new_start} → {new_end}")

        # -----------------------------
        # NDVI FETCH
        # -----------------------------
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
        # SAVE TO DB
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

        # -----------------------------
        # ALERT (READY)
        # -----------------------------
        if alert:
            print(f"   📩 ALERT READY FOR {phone}")

    conn.commit()
    cur.close()
    conn.close()

    print("\n🏁 ENGINE COMPLETE")


# -----------------------------
# ENTRY POINT (NON-NEGOTIABLE)
# -----------------------------
if __name__ == "__main__":
    print("🚀 ENGINE BOOTING...")

    try:
        run_intelligence_cycle()
        print("✅ ENGINE FINISHED SUCCESSFULLY")
    except Exception as e:
        print(f"❌ CRITICAL FAILURE: {e}")
        sys.exit(1)