import geopandas as gpd

peat = gpd.read_file("peat_kalimantan_big_official.geojson")
print("Total feature:", len(peat))
print("Bounds:", peat.total_bounds)   # harusnya sekitar [108.8, -3.5, 118.6, 4.1]