import requests
import json
import time
import math

# GANTI DENGAN BASE URL YANG LU DAPET DARI BROWSER
BASE_URL = "https://kspservices.big.go.id/satupeta/rest/services/PUBLIK/KEHUTANAN/MapServer" 
LAYER_ID = 0
OUTPUT_FILE = "kawasan_hutan_kalimantan.geojson"
query_url = f"{BASE_URL}/{LAYER_ID}/query"

# Bounding Box Kalimantan (Filter langsung di server biar cepat!)
BBOX_KALIMANTAN = "108.5,-4.5,119.5,4.5"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://gis.bnpb.go.id/" # Sesuaikan jika server beda
}

print("1. Cek total feature Kawasan Hutan di Kalimantan...")
count_params = {
    "where": "1=1",
    "geometry": BBOX_KALIMANTAN,
    "geometryType": "esriGeometryEnvelope",
    "spatialRel": "esriSpatialRelIntersects",
    "returnCountOnly": "true",
    "f": "json"
}
resp = requests.get(query_url, params=count_params, headers=headers, timeout=60)
total = resp.json().get("count", 0)
print(f"   Total feature: {total}")

if total == 0:
    print("   Tidak ada data. Cek BASE_URL atau BBOX.")
    exit()

all_features = []
batch_size = 1000
total_batches = math.ceil(total / batch_size)

print(f"2. Mulai download {total_batches} batch...")
for i in range(total_batches):
    offset = i * batch_size
    print(f"   -> Batch {i+1}/{total_batches} (offset={offset})...")
    
    params = {
        "where": "1=1",
        "geometry": BBOX_KALIMANTAN,
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "objectid,nkws,fungsitap,nosktap,kode_prov", # Ambil yang penting aja
        "outSR": "4326",
        "f": "geojson",
        "resultRecordCount": batch_size,
        "resultOffset": offset
    }
    
    try:
        resp = requests.get(query_url, params=params, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features: break
        all_features.extend(features)
        print(f"      ✅ Berhasil ambil {len(features)} feature.")
    except Exception as e:
        print(f"      ❌ ERROR: {e}")
        time.sleep(10)
        
    time.sleep(2.5) # Jeda sopan

print(f"\n3. Selesai! Total terkumpul: {len(all_features)}")

geojson = {
    "type": "FeatureCollection",
    "name": "kawasan_hutan_kalimantan",
    "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4326"}},
    "features": all_features
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(geojson, f)
print(f"💾 Data disimpan di: {OUTPUT_FILE}")