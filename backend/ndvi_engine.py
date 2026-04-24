import ee
import json
import os
import sys
from google.oauth2 import service_account
from datetime import datetime, timedelta

# Fix imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from backend import database

# -----------------------------
# MODE CONFIG
# -----------------------------
MODE = os.getenv("MODE", "SIMULATION")

# -----------------------------
# GEE AUTH
# -----------------------------
def authenticate_gee():
    try:
        json_key = os.environ.get("GEE_JSON_KEY")

        if not json_key:
            raise ValueError("GEE_JSON_KEY is missing")

        # Fix GitHub secrets formatting issues
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
# NDVI ENGINE
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

        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(area)
            .filterDate(
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
            )
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
        )

        if collection.size().getInfo() == 0:
            return None

        # Cloud masking
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

        if image is None:
            return None

        ndvi = image.normalizedDifference(["B8", "B4"]).rename("nd")

        result = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=area,
            scale=10
        )

        return result.get("nd").getInfo()

    except Exception as e:
        print(f"⚠️ NDVI Error: {e}")
        return None


# -----------------------------
# MAIN ENGINE
# -----------------------------
def run_intelligence_cycle():
    print(f"\n🌍 FarmSight Engine | MODE: {MODE}")

    authenticate_gee()

    conn = database.connect_db(settings.DB_URL)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, farmer_name, ST_AsGeoJSON(geom),
               last_processed_date, ndvi_history, phone_number
        FROM farms;
    """)

    farms = cur.fetchall()

    for fid, name, geojson_str, last_date, history, phone in farms:

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

        # LIVE MODE FIX (no fake future data)
        if MODE == "LIVE":
            new_end = new_start
        else:
            new_end = new_start + timedelta(days=5)

        print(f"\n👨‍🌾 {name} | {new_start} → {new_end}")

        # -----------------------------
        # NDVI FETCH
        # -----------------------------
        geojson = json.loads(geojson_str)
        current_ndvi = get_smart_ndvi(geojson, new_start, new_end)

        # -----------------------------
        # HANDLE NO DATA
        # -----------------------------
        history_list = list(history) if history else []

        if current_ndvi is None:
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

            print("   ☁️ No Data (stored)")
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
        # DATABASE UPDATE
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
        # ALERT HOOK (READY FOR SMS)
        # -----------------------------
        if alert:
            print(f"   📩 ALERT READY → {phone}")
            # send_sms(phone, f"FarmSight Alert: {status} for {name}")

    conn.commit()
    cur.close()
    conn.close()

    print("\n🏁 Cycle Complete")


# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    run_intelligence_cycle()