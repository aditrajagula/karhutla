import json
import os
from shapely.geometry import shape, mapping

input_path = "backend/app/kawasan_hutan_kalimantan.geojson"
output_path = "backend/app/kawasan_hutan_kalimantan_display.geojson"

print("Reading kawasan_hutan_kalimantan.geojson...")
with open(input_path, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Total features: {len(data['features'])}")

FUNGSITAP_MAP = {
    "100100": "Kawasan Suaka Alam / Pelestarian Alam (KSA/KPA)",
    "100200": "Hutan Lindung (HL)",
    "100210": "Hutan Lindung (HL)",
    "100220": "Hutan Suaka Alam",
    "100240": "Taman Wisata Alam (TWA)",
    "100250": "Taman Hutan Raya (Tahura)",
    "100260": "Suaka Margasatwa",
    "100300": "Hutan Produksi Terbatas (HPT)",
    "100400": "Hutan Produksi Tetap (HP)",
    "100500": "Hutan Produksi yang dapat Dikonversi (HPK)",
    "100000": "Kawasan Hutan",
    "500300": "Kawasan Khusus / Konservasi",
}

simplified_features = []
for feat in data["features"]:
    props = feat.get("properties", {})
    fungsi_code = str(props.get("fungsitap", ""))
    props["fungsi_label"] = FUNGSITAP_MAP.get(fungsi_code, f"Kawasan Hutan ({fungsi_code})")
    
    geom = shape(feat["geometry"])
    # Simplify 0.002 degrees (~220m) for fast web display
    simp_geom = geom.simplify(0.002, preserve_topology=True)
    if not simp_geom.is_empty:
        feat["geometry"] = mapping(simp_geom)
        simplified_features.append(feat)

data["features"] = simplified_features

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(data, f, separators=(",", ":"))

sz = os.path.getsize(output_path)
print(f"Done! Display output size: {sz / 1024 / 1024:.2f} MB ({len(simplified_features)} features)")
