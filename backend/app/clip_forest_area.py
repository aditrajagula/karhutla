import geopandas as gpd
from shapely.geometry import box

INPUT_FILE = "kawasan_hutan_kalimantan.geojson"  # GANTI dengan nama file mentah lu
OUTPUT_FILE = "forest_kalimantan_STRICT.geojson"    # File baru yang bakal di-save

print("1. Memuat file hutan mentah...")
forest = gpd.read_file(INPUT_FILE)
print(f"   Total feature mentah: {len(forest)}")

# 2. Buat Bounding Box KALIMANTAN yang KETAT
# Format: (minx, miny, maxx, maxy)
# Sulawesi mulai dari ~119.5° BT. Kita cut di 118.5° biar aman & tidak ada yang nyelonong.
print("2. Membuat Bounding Box Kalimantan (Strict)...")
bbox_kalimantan = box(108.0, -5.0, 118.5, 5.0) 
bbox_gdf = gpd.GeoDataFrame([1], geometry=[bbox_kalimantan], crs="EPSG:4326")

# 3. Eksekusi Clip
print("3. Memotong (Clipping) data...")
forest_clipped = gpd.clip(forest, bbox_gdf)
print(f"   Total feature setelah clip: {len(forest_clipped)}")

# 4. Simpan ke file BARU
print(f"4. Menyimpan ke {OUTPUT_FILE}...")
forest_clipped.to_file(OUTPUT_FILE, driver="GeoJSON")

print("\n✅ SELESAI! File siap dipakai.")
print("⚠️  PENTING: Pastikan di Frontend/Backend lu, path data hutan sudah diganti ke file BARU ini!")