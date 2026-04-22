%%writefile database.py
import psycopg2
import json

def connect_db(db_url):
    return psycopg2.connect(db_url)

def init_db(db_url):
    conn = connect_db(db_url)
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    cur.execute("TRUNCATE TABLE farms RESTART IDENTITY;")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS farms (
            id SERIAL PRIMARY KEY,
            farmer_name TEXT,
            phone_number TEXT,
            crop_type TEXT,
            last_ndvi FLOAT DEFAULT 0,
            ndvi_history JSONB
        );
    """)
    cur.execute("ALTER TABLE farms DROP COLUMN IF EXISTS lon;")
    cur.execute("ALTER TABLE farms ADD COLUMN IF NOT EXISTS lat;")
    cur.execute("ALTER TABLE farms ADD COLUMN IF NOT EXISTS geom GEOMETRY(POLYGON, 4326);")
    cur.execute("SELECT constraint_name FROM information_schema.table_constraints WHERE table_schema = current_schema() AND table_name = 'farms' AND constraint_name = 'unique_farmer';")
    constraint_exists = cur.fetchone()
    if constraint_exists:
        cur.execute("ALTER TABLE farms DROP CONSTRAINT unique_farmer;")
        print("Dropped unique_farmer constraint.")
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database Ready")

def add_farmer(name, phone, crop, geojson_str, db_url):
    conn = connect_db(db_url)
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM farms WHERE farmer_name = %s AND ST_Equals(geom, ST_GeomFromGeoJSON(%s))
    """, (name, geojson_str))
    if cur.fetchone() is not None:
        print(f"✔️ Processed {name}")
    else:
        cur.execute("""
            INSERT INTO farms (farmer_name, phone_number, crop_type, geom)
            VALUES (%s, %s, %s, ST_GeomFromGeoJSON(%s))
        """, (name, phone, crop, geojson_str))
        conn.commit()
        print(f"✅ Added {name}")
    cur.close()
    conn.close()

def cleanup_duplicates(db_url):
    conn = connect_db(db_url)
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM farms a USING farms b
        WHERE a.id > b.id AND a.farmer_name = b.farmer_name;
    """)
    conn.commit()
    cur.close()
    conn.close()