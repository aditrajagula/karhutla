import pandas as pd
import geopandas as gpd
from shapely.geometry import box

print("=== SPATIAL JOIN: HOTSPOT x GAMBUT x KAWASAN HUTAN ===\n")

# ==========================
# 1. LOAD DATA
# ==========================
# A. Load Hotspot (Support CSV atau GeoJSON)
hotspot_file = "firms_kalimantan.csv" # GANTI kalau nama file lu beda
if hotspot_file.endswith('.csv'):
    df = pd.read_csv(hotspot_file)
    df.columns = [c.strip().lower() for c in df.columns] # Bersihkan nama kolom
    gdf_hotspot = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326"
    )
else:
    gdf_hotspot = gpd.read_file(hotspot_file).to_crs("EPSG:4326")

# B. Load Gambut (BIG)
gdf_peat = gpd.read_file("peat_kalimantan_big_official.geojson").to_crs("EPSG:4326") # GANTI nama file

# C. Load Kawasan Hutan (KLHK)
gdf_forest_raw = gpd.read_file("kawasan_hutan_kalimantan.geojson").to_crs("EPSG:4326") # GANTI nama file

# FILTER OTOMATIS: Karena JSON Kawasan Hutan extent-nya seluruh Indonesia, 
# kita potong (clip) pakai Bounding Box Kalimantan biar data luar pulau ikut terbuang.
bbox_kalimantan = box(108.5, -4.5, 119.5, 4.5)
gdf_forest = gdf_forest_raw[gdf_forest_raw.intersects(bbox_kalimantan)].copy()

print(f"Loaded: {len(gdf_hotspot)} Hotspot | {len(gdf_peat)} Poligon Gambut | {len(gdf_forest)} Poligon Hutan (Kalimantan Only)\n")

# ==========================
# 2. SPATIAL JOIN: HOTSPOT x GAMBUT
# ==========================
print("1. Joining Hotspot dengan Lahan Gambut...")
# Ambil cuma geometri dan landform (jenis gambut)
peat_join = gpd.sjoin(gdf_hotspot, gdf_peat[['geometry', 'landform']], how='left', predicate='intersects')
peat_join = peat_join[~peat_join.index.duplicated(keep='first')] # Cegah duplikat kalau 1 titik kena 2 poligon

gdf_hotspot['in_peat'] = peat_join['landform'].notna()
gdf_hotspot['peat_landform'] = peat_join['landform'].fillna('Non-Gambut')

# ==========================
# 3. SPATIAL JOIN: HOTSPOT x KAWASAN HUTAN
# ==========================
print("2. Joining Hotspot dengan Kawasan Hutan...")
# Ambil cuma geometri, fungsitap (fungsi kawasan), dan nkws (nama kawasan)
forest_join = gpd.sjoin(gdf_hotspot, gdf_forest[['geometry', 'fungsitap', 'nkws']], how='left', predicate='intersects')
forest_join = forest_join[~forest_join.index.duplicated(keep='first')]

gdf_hotspot['in_forest'] = forest_join['fungsitap'].notna()
gdf_hotspot['forest_fungsi'] = forest_join['fungsitap'].fillna('Non-Kawasan Hutan')
gdf_hotspot['forest_name'] = forest_join['nkws'].fillna('-')

# ==========================
# 4. HITUNG FLAG FOKUS
# ==========================
# Hotspot fokus = Berada di Gambut ATAU di Kawasan Hutan
gdf_hotspot['is_focus_hotspot'] = gdf_hotspot['in_peat'] | gdf_hotspot['in_forest']

# ==========================
# 5. RINGKASAN & SAVE
# ==========================
print("\n=== RINGKASAN HASIL ===")
print(f"Total Hotspot: {len(gdf_hotspot)}")
print(f"Hotspot di Lahan Gambut: {gdf_hotspot['in_peat'].sum()}")
print(f"Hotspot di Kawasan Hutan: {gdf_hotspot['in_forest'].sum()}")
print(f"Hotspot FOKUS (Gambut OR Hutan): {gdf_hotspot['is_focus_hotspot'].sum()}")

# Simpan ke GeoJSON (untuk Frontend Peta)
gdf_hotspot.to_file("final_hotspots_segmentation.geojson", driver="GeoJSON")

# Simpan ke CSV (untuk Database / Tabel)
gdf_hotspot.drop(columns=['geometry']).to_csv("final_hotspots_segmentation.csv", index=False)

print("\n✅ SELESAI!")
print("File tersimpan: final_hotspots_segmentation.geojson & .csv")