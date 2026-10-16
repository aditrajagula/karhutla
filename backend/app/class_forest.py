import geopandas as gpd

forest = gpd.read_file("forest_kalimantan_klhk_2024.geojson")

def classify_forest_risk(id_penutu4):
    # Primer = risiko tertinggi (karena hutan utuh, kebakaran = bencana ekologis)
    if id_penutu4 in [2001, 2005, 2004]:
        return "Hutan Primer (KRITIS)"
    # Sekunder = risiko tinggi
    if id_penutu4 in [2002, 20041, 20051]:
        return "Hutan Sekunder (TINGGI)"
    # Hutan Tanaman = sedang (bisa diganti, tapi tetap biomassa)
    if id_penutu4 == 2006:
        return "Hutan Tanaman (SEDANG)"
    return "Non-Hutan"

forest["forest_risk"] = forest["ID_Penutu4"].apply(classify_forest_risk)
forest.to_file("forest_kalimantan_classified.geojson", driver="GeoJSON")