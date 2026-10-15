import pandas as pd
import geopandas as gpd
import json
import os

print("1. Membaca Hotspot FIRMS dari CSV...")
df_hotspots = pd.read_csv("firms_kalimantan.csv")

# Bersihkan nama kolom (kadang FIRMS ngasih spasi di depan)
df_hotspots.columns = df_hotspots.columns.str.strip().str.lower()

# Pastikan ada kolom latitude dan longitude
if 'latitude' not in df_hotspots.columns or 'longitude' not in df_hotspots.columns:
    raise ValueError("Kolom latitude/longitude tidak ditemukan di CSV FIRMS!")

# Ubah ke GeoDataFrame
gdf_hotspots = gpd.GeoDataFrame(
    df_hotspots, 
    geometry=gpd.points_from_xy(df_hotspots.longitude, df_hotspots.latitude),
    crs="EPSG:4326"
)
print(f"   Total hotspot loaded: {len(gdf_hotspots)}")

print("2. Membaca Layer Gambut Resmi BIG...")
# Pastikan nama file sesuai dengan hasil download lu sebelumnya
peat_file = "peat_kalimantan_big_official.geojson" 
if not os.path.exists(peat_file):
    raise FileNotFoundError(f"File {peat_file} tidak ditemukan!")
    
gdf_peat = gpd.read_file(peat_file)
print(f"   Total poligon gambut loaded: {len(gdf_peat)}")

print("3. Melakukan SPATIAL JOIN (Mencari hotspot yang jatuh di gambut)...")
# Kita hanya butuh kolom 'landform' dari gambut untuk klasifikasi
joined = gpd.sjoin(
    gdf_hotspots, 
    gdf_peat[['geometry', 'landform']], 
    how='left', 
    predicate='intersects'
)

# Handle kalau ada 1 titik yang nyangkut di 2 poligon (ambil yang pertama)
joined = joined[~joined.index.duplicated(keep='first')]

# Masukkan hasil join kembali ke dataframe utama
gdf_hotspots['in_peat'] = joined['landform'].notna()
gdf_hotspots['peat_class'] = joined['landform'].fillna('Non-Gambut')

# Bikin kategori prioritas (Biar gampang di-filter di Frontend)
def get_priority(row):
    if not row['in_peat']:
        return 'Rendah (Non-Gambut)'
    
    landform = str(row['peat_class']).lower()
    if 'kubah' in landform and ('> 700' in landform or '500' in landform or '300' in landform):
        return 'KRITIS (Kubah Gambut Dalam)'
    elif 'kubah' in landform or 'tepi kubah' in landform:
        return 'Tinggi (Tepi/Kubah Dangkal)'
    else:
        return 'Sedang (Gambut Topogen/Lainnya)'

gdf_hotspots['fire_risk_priority'] = gdf_hotspots.apply(get_priority, axis=1)

print("\n--- RINGKASAN HASIL ---")
print(f"Total Hotspot: {len(gdf_hotspots)}")
print(f"Hotspot di Lahan Gambut: {gdf_hotspots['in_peat'].sum()}")
print(f"Hotspot di LUAR Gambut: {(~gdf_hotspots['in_peat']).sum()}")
print("\nBreakdown Prioritas:")
print(gdf_hotspots['fire_risk_priority'].value_counts())

print("\n4. Menyimpan hasil ke GeoJSON (untuk Frontend Peta)...")
# Hapus kolom geometry dari CSV biasa, tapi simpan di GeoJSON
gdf_hotspots.to_file("hotspots_kalimantan_final.geojson", driver="GeoJSON")

# Simpan juga versi CSV untuk database/tabel
df_out = gdf_hotspots.drop(columns=['geometry'])
df_out.to_csv("hotspots_kalimantan_final.csv", index=False)

print("🎉 SELESAI! File 'hotspots_kalimantan_final.geojson' siap di-serve ke Frontend!")