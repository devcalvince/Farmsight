import psycopg2
import json

def connect_db(db_url):
    return psycopg2.connect(db_url)

def init_db(db_url):
    conn = connect_db(db_url)
    cur = conn.cursor()
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS farms (
                id SERIAL PRIMARY KEY,
                farmer_name TEXT,
                phone_number TEXT,
                crop_type TEXT,
                last_ndvi FLOAT DEFAULT 0,
                ndvi_history JSONB DEFAULT '[]'::jsonb,
                geom GEOMETRY(POLYGON, 4326)
            );
        """)
        cur.execute("ALTER TABLE farms ADD COLUMN IF NOT EXISTS geom GEOMETRY(POLYGON, 4326);")
        conn.commit()
        print("✅ Database Schema Verified")
    finally:
        cur.close()
        conn.close()

def add_farmer(name, phone, crop, geojson_str, db_url):
    conn = connect_db(db_url)
    cur = conn.cursor()
    try:
        # Check for existing farmer by name and geometry
        cur.execute("""
            SELECT id FROM farms WHERE farmer_name = %s 
            AND ST_Equals(geom, ST_GeomFromGeoJSON(%s))
        """, (name, geojson_str))
        
        if cur.fetchone():
            print(f"✔️ {name} already exists. Skipping.")
        else:
            cur.execute("""
                INSERT INTO farms (farmer_name, phone_number, crop_type, geom)
                VALUES (%s, %s, %s, ST_GeomFromGeoJSON(%s))
            """, (name, phone, crop, geojson_str))
            conn.commit()
            print(f"✅ Added {name}")
    finally:
        cur.close()
        conn.close()
