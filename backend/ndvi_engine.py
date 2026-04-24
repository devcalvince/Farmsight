import ee
import json
import os
import sys
from google.oauth2 import service_account
from datetime import datetime, timedelta

# -----------------------------
# FIX IMPORT PATHS (CRITICAL)
# -----------------------------
# This allows the script to find 'config' and 'database' folders in your repo
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from backend import database

# -----------------------------
# MODE CONFIG
# -----------------------------
MODE = os.getenv("MODE", "SIMULATION")


# -----------------------------
# GEE AUTH (HARDENED FOR GITHUB ACTIONS)
# -----------------------------
def authenticate_gee():
    """
    Connects to Google Earth Engine using raw JSON text from Environment Variables.
    This fixes the 'File Not Found' error by reading data directly from memory.
    """
    try:
        print("🔐 Authenticating GEE...")

        # 1. Get the JSON text from GitHub Secrets (passed via .yml)
        json_key_text = os.environ.get("GEE_JSON_KEY")

        if not json_key_text:
            raise ValueError("❌ GEE_JSON_KEY environment variable is empty!")

        # 2. Convert text string into a Python dictionary
        # Fixes escaped newlines that commonly occur in GitHub secret storage
        info = json.loads(json_key_text.replace('\\n', '\n'))

        # 3. Authenticate using 'info' (In-Memory) instead of 'file' (On-Disk)
        credentials = service_account.Credentials.from_service_account_info(info)

        ee.Initialize(
            credentials=credentials,
            project=os.getenv("GEE_PROJECT_ID")
        )

        print("✅ GEE Authenticated Successfully")

    except Exception as e:
        print(f"❌ GEE Auth Failed: {e}")
        # Raising the error ensures the GitHub Action shows a RED failure
        raise


# -----------------------------
# NDVI CALCULATION ENGINE
# -----------------------------
def get_smart_ndvi(geojson_obj, start_date, end_date):
    """Fetches clean NDVI imagery for a specific time window."""
    try:
        if not geojson_obj:
            return None

        # Handle Polygon and MultiPolygon logic
        g_type = geojson_obj.get("type")
        if g_type == "Polygon":
            area = ee.Geometry.Polygon(geojson_obj["coordinates"])
        elif g_type == "MultiPolygon":
            area = ee.Geometry.MultiPolygon(geojson_obj["coordinates"])
        else:
            print(f"   ❌ Unsupported geometry type: {g_type}")
            return None

        print(f"   🛰 Fetching imagery: {start_date} → {end_date}")

        # Query Sentinel-2 Collection
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(area)
            .filterDate(
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
            )
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
        )

        size = collection.size().getInfo()
        if size == 0:
            return None

        # Cloud masking logic (QA60)
        def mask(img):
            qa = img.select("QA60")
            mask_layer = qa.bitwiseAnd(1 << 10).eq(0).And(
                qa.bitwiseAnd(1 << 11).eq(0)
            )
            return img.updateMask(mask_layer)

        # Get the cleanest image in the collection
        image = (
            collection.map(mask)
            .sort("CLOUDY_PIXEL_PERCENTAGE")
            .first()
        )

        if image is None:
            return None

        # Calculate NDVI
        ndvi = image.normalizedDifference(["B8", "B4"]).rename("nd")

        # Reduce to mean value for the farm polygon
        result = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=area,
            scale=10
        )

        value = result.get("nd").getInfo()
        return value

    except Exception as e:
        print(f"   ⚠️ NDVI Calculation Error: {e}")
        return None


# -----------------------------
# MAIN MONITORING CYCLE
# -----------------------------
def run_intelligence_cycle():
    print("\n🚀 ENGINE STARTING...")
    print(f"🌍 MODE: {MODE}")

    # Step 1: Login
    authenticate_gee()

    # Step 2: Connect to Neon Database
    print("📡 Connecting to DB...")
    conn = database.connect_db(settings.DB_URL)
    cur = conn.cursor()

    # Step 3: Fetch Farmers
    cur.execute("""
        SELECT id, farmer_name, ST_AsGeoJSON(geom),
               last_processed_date, ndvi_history, phone_number
        FROM farms;
    """)
    farms = cur.fetchall()

    print(f"📊 FOUND {len(farms)} FARMS TO PROCESS")

    if len(farms) == 0:
        print("❌ NO FARMS FOUND. CHECK NEON DATABASE ENTRIES.")
        return

    # Step 4: Process Each Farm
    for fid, name, geojson_str, last_date, history, phone in farms:

        print(f"\n👨‍🌾 Processing: {name}")

        # Time Management
        if MODE == "SIMULATION":
            base_date = last_date if last_date else datetime(2023, 1, 1).date()
            step = 3
        else:
            base_date = last_date if last_date else (datetime.utcnow().date() - timedelta(days=7))
            step = 1

        new_start = base_date + timedelta(days=step)
        new_end = new_start + timedelta(days=15) # Wider search window for simulation

        print(f"   ⏳ Current Window: {new_start} → {new_end}")

        # Fetch NDVI
        geojson = json.loads(geojson_str)
        current_ndvi = get_smart_ndvi(geojson, new_start, new_end)

        history_list = list(history) if history else []

        # Handle No Data (Cloudy)
        if current_ndvi is None:
            print("   ☁️ Status: No clear satellite data found.")
            history_list.append({"date": str(new_start), "ndvi": None})
            
            cur.execute("""
                UPDATE farms SET last_processed_date = %s, ndvi_history = %s WHERE id = %s
            """, (new_start, json.dumps(history_list), fid))
            continue

        # Trend Analysis (Compare against last valid history point)
        prev_val = None
        for h in reversed(history_list):
            if isinstance(h, dict) and h.get("ndvi") is not None:
                prev_val = h["ndvi"]
                break

        delta = current_ndvi - prev_val if prev_val is not None else 0

        # Status Logic
        if delta < -0.10:
            status = "🚨 DROPPING"
            alert = True
        elif delta > 0.08:
            status = "📈 IMPROVING"
            alert = False
        else:
            status = "✅ STABLE"
            alert = False

        # Update History List
        history_list.append({"date": str(new_start), "ndvi": round(current_ndvi, 3)})
        if len(history_list) > 15:
            history_list.pop(0)

        # Save to Database
        cur.execute("""
            UPDATE farms
            SET last_ndvi = %s,
                last_processed_date = %s,
                ndvi_history = %s
            WHERE id = %s
        """, (current_ndvi, new_start, json.dumps(history_list), fid))

        print(f"   {status} | NDVI={current_ndvi:.3f} | Δ={delta:.3f}")

        if alert:
            print(f"   📩 SMS ALERT PREPARED FOR: {phone}")

    # Step 5: Finalize
    conn.commit()
    cur.close()
    conn.close()

    print("\n🏁 ENGINE CYCLE COMPLETE")


# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    print("🚀 BOOTING FARMSIGHT ENGINE...")
    try:
        run_intelligence_cycle()
        print("✅ SUCCESSFUL FINISH")
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")
        sys.exit(1)
