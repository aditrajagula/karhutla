import os
import requests
import pandas as pd
import datetime
from dotenv import load_dotenv, find_dotenv

# Load .env dari root project
load_dotenv(find_dotenv())

# PASTIKAN INI KEY BARU LU!
KEY = os.environ.get("FIRMS_MAP_KEY")
if not KEY:
    raise SystemExit("FIRMS_MAP_KEY tidak ditemukan di .env")

# GUNAKAN BOUNDING BOX KALIMANTAN (west,south,east,north)
# 108.5 (Barat), -4.5 (Selatan), 119.5 (Timur), 4.5 (Utara)
AREA_KALIMANTAN = "108.5,-4.5,119.5,4.5" 
DAYS = 3   # Ambil data 3 hari terakhir (NRT)

# List sensor (NOAA-20 dan NOAA-21)
SENSORS = ["VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]

rows = []
for sensor in SENSORS:
    # URL dengan Bounding Box
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{KEY}/{sensor}/{AREA_KALIMANTAN}/{DAYS}"
    
    print(f"Fetching {sensor} untuk Kalimantan...")
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        
        # Cek kalau response bukan HTML error
        if "html" in r.headers.get('Content-Type', '').lower():
            print(f"  ⚠️ {sensor} HTML error. Skip.")
            continue

        df = pd.read_csv(pd.io.common.StringIO(r.text))
        if not df.empty:
            rows.append(df)
            print(f"  ✅ Berhasil: {len(df)} hotspot ditemukan.")
        else:
            print(f"  ℹ️ Kosong: Tidak ada hotspot untuk {sensor} dalam {DAYS} hari terakhir.")
            
    except requests.exceptions.HTTPError as e:
        print(f"  ❌ Gagal HTTP: {e}")
    except Exception as e:
        print(f"  ❌ Error lain: {e}")

if not rows:
    print("\n⚠️ Tidak ada data hotspot yang berhasil diambil. Cek MAP_KEY baru lu atau coba tambah DAYS.")
else:
    hot = pd.concat(rows, ignore_index=True)
    
    # Simpan ke CSV
    output_file = "firms_kalimantan.csv"
    hot.to_csv(output_file, index=False)
    print(f"\n🎉 Selesai! Total {len(hot)} hotspot disimpan ke {output_file}")

    # Simpan Manifest (Penting untuk label Freshness di UI)
    manifest = {
        "source": "NASA FIRMS API",
        "sensors": SENSORS,
        "area_bbox": AREA_KALIMANTAN,
        "days": DAYS,
        "fetched_at_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "total_records": len(hot)
    }
    import json
    with open("firms_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    print("📄 Manifest freshness disimpan ke firms_manifest.json")