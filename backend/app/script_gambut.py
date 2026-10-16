import requests
import json
import time
import math

BASE_URL = "https://kspservices.big.go.id/satupeta/rest/services/PUBLIK/SUMBER_DAYA_ALAM_DAN_LINGKUNGAN/MapServer"
LAYER_ID = 6
OUTPUT_FILE = "peat_kalimantan_big_official.geojson"

query_url = f"{BASE_URL}/{LAYER_ID}/query"

# Filter hanya poligon Gambut dan Kubah Gambut
where_clause = "landform LIKE '%Gambut%' OR landform LIKE '%Kubah%'"

# Headers browser asli agar tidak diblokir WAF server BIG
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*"
}

print("1. Cek total feature gambut di server BIG...")
count_params = {
    "where": where_clause,
    "returnCountOnly": "true",
    "f": "json"
}
resp = requests.get(query_url, params=count_params, headers=headers, timeout=60)
total = resp.json().get("count", 0)
print(f"Total feature gambut: {total}")

if total == 0:
    print("Tidak ada data yang cocok. Cek kembali where_clause.")
    exit()

all_features = []
batch_size = 1000  # maxRecordCount dari server BIG
total_batches = math.ceil(total / batch_size)

print(f"2. Mulai download {total_batches} batch...")
for i in range(total_batches):
    offset = i * batch_size
    print(f"   -> Download batch {i+1}/{total_batches} (offset={offset})...")
    
    params = {
        "where": where_clause,
        "outFields": "*",
        "outSR": "4326",
        "f": "geojson",
        "resultRecordCount": batch_size,
        "resultOffset": offset
    }
    
    try:
        resp = requests.get(query_url, params=params, headers=headers, timeout=90)
        resp.raise_for_status()
        data = resp.json()
        
        features = data.get("features", [])
        if not features:
            print("   Batch kosong, selesai.")
            break
            
        all_features.extend(features)
        print(f"   Berhasil ambil {len(features)} feature.")
        
    except Exception as e:
        print(f"   ERROR di batch {i+1}: {e}")
        print("   Server BIG mungkin sedang lambat. Tunggu 10 detik lalu coba lagi...")
        time.sleep(10)
        # Retry sekali
        resp = requests.get(query_url, params=params, headers=headers, timeout=120)
        data = resp.json()
        all_features.extend(data.get("features", []))

    # PENTING: Kasih jeda 2-3 detik agar IP lu tidak di-banned oleh firewall BIG
    time.sleep(2.5) 

print(f"\n3. Selesai! Total feature terkumpul: {len(all_features)}")

# Simpan ke GeoJSON
geojson = {
    "type": "FeatureCollection",
    "name": "peat_kalimantan_big_official",
    "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4326"}},
    "features": all_features
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(geojson, f)

print(f"Data berhasil disimpan di: {OUTPUT_FILE}")