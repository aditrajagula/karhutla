"""
Skrip Audit Cakupan Raster dan Agregasi Statistik Zonal Hansen GFC v1.13
untuk 5 Provinsi Kalimantan Indonesia.

Metodologi Ilmiah:
1. Batas Geografis & Geometri:
   - Poligon administratif resmi dari data/boundaries/indonesia_provinces.geojson.
   - Mengatasi tumpang tindih historis Kaltim-Kaltara (pemekaran 2012) dengan difference-clipping.
2. Penentuan Keanggotaan Piksel (Boundary Handling):
   - Standar OGC/GIS: Pixel Center Point-in-Polygon (All-Touched = False).
   - Suatu sel piksel (0.00025° x 0.00025°) dihitung masuk ke suatu provinsi jika dan hanya jika
     titik pusat piksel (pixel center) berada di dalam poligon provinsi tersebut.
   - Konvensi ini memastikan penjumlahan luas antar-provinsi bersifat partisi mutually-exclusive
     (tidak ada double-counting piksel perbatasan).
3. Perhitungan Luas Geodesik:
   - Menggunakan integrasi authalic elipsoid WGS84 analitik per baris lintang (latitude-dependent):
     Area(phi) = 0.5 * b^2 * |d_lon| * |Q(phi_north) - Q(phi_south)|
4. Pemisahan Kelas Semantik:
   - Valid Land: datamask == 1
   - Permanent Water: datamask == 2
   - NoData / Marine: datamask == 0
   - Baseline Forest 2000: treecover2000 > 0 (juga dihitung untuk kanopi >= 30%)
   - Tree Cover Loss 2001–2025: lossyear dalam [1..25]
   - Stable Forest: lossyear == 0 and treecover2000 > 0
   - Baseline Non-Forest: treecover2000 == 0 and lossyear == 0
"""

import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import Window
from shapely.geometry import shape
from shapely.validation import make_valid

# Tambahkan root dan backend ke path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from app.config import BOUNDARIES_PATH, HANSEN_OFFICIAL_DIR
from app.forest_change_service import calculate_pixel_area_ha

TILES = ["00N_100E", "00N_110E", "10N_100E", "10N_110E"]
TILE_BOUNDS = {
    "00N_100E": (100.0, -10.0, 110.0, 0.0),
    "00N_110E": (110.0, -10.0, 120.0, 0.0),
    "10N_100E": (100.0, 0.0, 110.0, 10.0),
    "10N_110E": (110.0, 0.0, 120.0, 10.0),
}

KALIMANTAN_PROVINCES = [
    "Kalimantan Barat",
    "Kalimantan Tengah",
    "Kalimantan Selatan",
    "Kalimantan Timur",
    "Kalimantan Utara",
]


def compute_polygon_geodesic_area_ha(geom) -> float:
    """
    Menghitung luas poligon WGS84 dalam hektare menggunakan integrasi
    luas sferis authalic elipsoid WGS84 (R_a = 6371007.1809 m).
    """
    R_a = 6371007.1809  # WGS84 authalic radius (m)

    def ring_area(coords):
        if len(coords) < 3:
            return 0.0
        tot = 0.0
        n = len(coords)
        for i in range(n):
            lon_prev = math.radians(coords[i - 1][0])
            lon_next = math.radians(coords[(i + 1) % n][0])
            lat = math.radians(coords[i][1])
            tot += (lon_next - lon_prev) * math.sin(lat)
        return abs(tot * (R_a ** 2) * 0.5)

    if geom.geom_type == "Polygon":
        a = ring_area(geom.exterior.coords)
        for hole in geom.interiors:
            a -= ring_area(hole.coords)
        return a / 10000.0
    elif geom.geom_type == "MultiPolygon":
        return sum(compute_polygon_geodesic_area_ha(p) for p in geom.geoms)
    return 0.0


def load_cleaned_provinces():
    """Memuat dan membersihkan 5 poligon provinsi Kalimantan."""
    with open(BOUNDARIES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    prov_geoms = {}
    for feat in data["features"]:
        props = feat.get("properties", {})
        p_name = props.get("state") or props.get("NAME_1") or props.get("name") or props.get("Propinsi") or ""
        for kp in KALIMANTAN_PROVINCES:
            if kp.lower() in p_name.lower():
                raw = shape(feat["geometry"])
                prov_geoms[kp] = make_valid(raw)

    # Bersihkan tumpang tindih Kaltim vs Kaltara
    if "Kalimantan Timur" in prov_geoms and "Kalimantan Utara" in prov_geoms:
        kaltim = prov_geoms["Kalimantan Timur"]
        kaltara = prov_geoms["Kalimantan Utara"]
        if kaltim.intersects(kaltara):
            prov_geoms["Kalimantan Timur"] = make_valid(kaltim.difference(kaltara))

    return prov_geoms


def audit_provincial_zonal_stats():
    start_total = time.perf_counter()
    prov_geoms = load_cleaned_provinces()

    report = {
        "dataset_version": "GFC-2025-v1.13",
        "methodology": {
            "coordinate_reference_system": "EPSG:4326 (WGS84)",
            "spatial_resolution_deg": 0.00025,
            "approx_ground_resolution_m": 27.83,
            "pixel_boundary_rule": "Pixel Center Point-in-Polygon (all_touched=False, mutually exclusive partition)",
            "area_calculation_method": "WGS84 analytic authalic ellipsoid integration per latitude row",
            "semantic_taxonomy": {
                "valid_land": "datamask == 1",
                "permanent_water": "datamask == 2 (sungai/danau permanen, bukan non-hutan atau zero-loss)",
                "nodata_or_marine": "datamask == 0 (laut terbuka / area luar observasi)",
                "treecover_baseline_2000": "treecover2000 > 0% (dan metrik turunan >= 30%)",
                "treecover_loss_2001_2025": "lossyear in [1..25] pada daratan valid (indikasi biofisik hilangnya kanopi >5m, BUKAN kebakaran/deforestasi ilegal)",
                "stable_forest": "lossyear == 0 and treecover2000 > 0 pada daratan valid",
                "non_forest_baseline": "lossyear == 0 and treecover2000 == 0 pada daratan valid"
            }
        },
        "audit_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "provinces": {}
    }

    print(f"Memulai audit zonal statistik raster untuk 5 provinsi...")

    for prov_name in KALIMANTAN_PROVINCES:
        t0_prov = time.perf_counter()
        geom = prov_geoms[prov_name]
        poly_area_ha = compute_polygon_geodesic_area_ha(geom)
        poly_bounds = geom.bounds  # (min_lon, min_lat, max_lon, max_lat)

        print(f"\n[{prov_name}]")
        print(f"  Batas: {poly_bounds}")
        print(f"  Luas Poligon WGS84: {poly_area_ha:,.2f} ha ({poly_area_ha/100:,.2f} km²)")

        # Inisialisasi akumulator statistik provinsi
        stats = {
            "administrative_bounds": {
                "min_lon": round(poly_bounds[0], 6),
                "min_lat": round(poly_bounds[1], 6),
                "max_lon": round(poly_bounds[2], 6),
                "max_lat": round(poly_bounds[3], 6),
            },
            "polygon_area_ha": round(poly_area_ha, 2),
            "polygon_area_km2": round(poly_area_ha / 100.0, 2),
            "intersecting_tiles": [],
            "pixel_counts": {
                "total_inside_polygon": 0,
                "valid_land": 0,
                "permanent_water": 0,
                "nodata_marine": 0,
                "baseline_treecover_gt0": 0,
                "baseline_treecover_ge30": 0,
                "baseline_non_forest": 0,
                "loss_total_2001_2025": 0,
                "stable_forest": 0,
                "loss_by_year": {str(yr): 0 for yr in range(2001, 2026)}
            },
            "areas_ha": {
                "total_inside_polygon": 0.0,
                "valid_land": 0.0,
                "permanent_water": 0.0,
                "nodata_marine": 0.0,
                "baseline_treecover_gt0": 0.0,
                "baseline_treecover_ge30": 0.0,
                "baseline_non_forest": 0.0,
                "loss_total_2001_2025": 0.0,
                "stable_forest": 0.0,
                "loss_by_year": {str(yr): 0.0 for yr in range(2001, 2026)}
            }
        }

        # Cari tile yang beririsan
        for tile_id in TILES:
            t_min_lon, t_min_lat, t_max_lon, t_max_lat = TILE_BOUNDS[tile_id]
            # Cek overlap bounding box
            if (poly_bounds[0] < t_max_lon and poly_bounds[2] > t_min_lon and
                poly_bounds[1] < t_max_lat and poly_bounds[3] > t_min_lat):

                stats["intersecting_tiles"].append(tile_id)

                # Jalur berkas raster
                dm_path = HANSEN_OFFICIAL_DIR / f"Hansen_GFC-2025-v1.13_datamask_{tile_id}_official.tif"
                tc_path = HANSEN_OFFICIAL_DIR / f"Hansen_GFC-2025-v1.13_treecover2000_{tile_id}_official.tif"
                ly_path = HANSEN_OFFICIAL_DIR / f"Hansen_GFC-2025-v1.13_lossyear_{tile_id}_official.tif"

                if not (dm_path.exists() and tc_path.exists() and ly_path.exists()):
                    print(f"  [PERINGATAN] Berkas tile {tile_id} tidak lengkap di {HANSEN_OFFICIAL_DIR}")
                    continue

                # Buka raster datamask untuk mengambil transform dan window overlap
                with rasterio.open(dm_path) as dm_src, \
                     rasterio.open(tc_path) as tc_src, \
                     rasterio.open(ly_path) as ly_src:

                    # Hitung irisan jendela spasial dalam derajat
                    w_min_lon = max(poly_bounds[0], t_min_lon)
                    w_max_lon = min(poly_bounds[2], t_max_lon)
                    w_min_lat = max(poly_bounds[1], t_min_lat)
                    w_max_lat = min(poly_bounds[3], t_max_lat)

                    # Konversi derajat ke piksel
                    # transform.c = left_lon, transform.a = 0.00025
                    # transform.f = top_lat, transform.e = -0.00025
                    col_start = int(math.floor((w_min_lon - dm_src.transform.c) / dm_src.transform.a))
                    col_end = int(math.ceil((w_max_lon - dm_src.transform.c) / dm_src.transform.a))
                    row_start = int(math.floor((dm_src.transform.f - w_max_lat) / (-dm_src.transform.e)))
                    row_end = int(math.ceil((dm_src.transform.f - w_min_lat) / (-dm_src.transform.e)))

                    col_start = max(0, min(dm_src.width, col_start))
                    col_end = max(0, min(dm_src.width, col_end))
                    row_start = max(0, min(dm_src.height, row_start))
                    row_end = max(0, min(dm_src.height, row_end))

                    win_width = col_end - col_start
                    win_height = row_end - row_start

                    if win_width <= 0 or win_height <= 0:
                        continue

                    print(f"  Tile {tile_id}: window [{row_start}:{row_end}, {col_start}:{col_end}] ({win_width}x{win_height} px)")

                    # Proses dalam chunk baris (chunk size: 2000 baris) agar hemat RAM
                    CHUNK_ROWS = 2000
                    for chunk_r in range(row_start, row_end, CHUNK_ROWS):
                        c_h = min(CHUNK_ROWS, row_end - chunk_r)
                        w = Window(col_off=col_start, row_off=chunk_r, width=win_width, height=c_h)

                        # Window transform
                        win_transform = rasterio.windows.transform(w, dm_src.transform)

                        # geometry_mask menghasilkan True di luar poligon, False di dalam poligon
                        # all_touched=False menerapkan Pixel Center Point-in-Polygon
                        mask_out = geometry_mask(
                            [geom],
                            out_shape=(c_h, win_width),
                            transform=win_transform,
                            all_touched=False,
                            invert=False
                        )
                        inside_mask = ~mask_out

                        if not np.any(inside_mask):
                            continue

                        # Baca data raster pada window
                        dm_arr = dm_src.read(1, window=w)
                        tc_arr = tc_src.read(1, window=w)
                        ly_arr = ly_src.read(1, window=w)

                        # Hitung luas piksel per baris lintang pada chunk ini
                        # Tiap baris chunk memiliki lintang tengah:
                        row_indices = np.arange(c_h)
                        # Latitude = top - (chunk_r + row_idx + 0.5) * res
                        lats = dm_src.transform.f - (chunk_r + row_indices + 0.5) * dm_src.transform.a
                        row_areas_ha = np.array([calculate_pixel_area_ha(lat) for lat in lats], dtype=np.float64)
                        # Broadcast ke bentuk 2D (c_h, win_width) agar cocok dengan shape mask
                        area_grid = np.broadcast_to(row_areas_ha[:, np.newaxis], (c_h, win_width))

                        # 1. Total piksel di dalam poligon
                        n_inside = np.count_nonzero(inside_mask)
                        stats["pixel_counts"]["total_inside_polygon"] += int(n_inside)
                        stats["areas_ha"]["total_inside_polygon"] += float(np.sum(area_grid[inside_mask]))

                        # 2. Valid Land (datamask == 1)
                        land_mask = inside_mask & (dm_arr == 1)
                        n_land = np.count_nonzero(land_mask)
                        stats["pixel_counts"]["valid_land"] += int(n_land)
                        stats["areas_ha"]["valid_land"] += float(np.sum(area_grid[land_mask]))

                        # 3. Permanent Water (datamask == 2)
                        water_mask = inside_mask & (dm_arr == 2)
                        n_water = np.count_nonzero(water_mask)
                        stats["pixel_counts"]["permanent_water"] += int(n_water)
                        stats["areas_ha"]["permanent_water"] += float(np.sum(area_grid[water_mask]))

                        # 4. NoData / Marine (datamask == 0)
                        nodata_mask = inside_mask & (dm_arr == 0)
                        n_nodata = np.count_nonzero(nodata_mask)
                        stats["pixel_counts"]["nodata_marine"] += int(n_nodata)
                        stats["areas_ha"]["nodata_marine"] += float(np.sum(area_grid[nodata_mask]))

                        # 5. Baseline Treecover 2000 pada Daratan Valid
                        tc_land = tc_arr[land_mask]
                        area_land = area_grid[land_mask]

                        gt0_mask = tc_land > 0
                        stats["pixel_counts"]["baseline_treecover_gt0"] += int(np.count_nonzero(gt0_mask))
                        stats["areas_ha"]["baseline_treecover_gt0"] += float(np.sum(area_land[gt0_mask]))

                        ge30_mask = tc_land >= 30
                        stats["pixel_counts"]["baseline_treecover_ge30"] += int(np.count_nonzero(ge30_mask))
                        stats["areas_ha"]["baseline_treecover_ge30"] += float(np.sum(area_land[ge30_mask]))

                        # 6. Lossyear pada Daratan Valid
                        ly_land = ly_arr[land_mask]

                        # Non-forest baseline: tc == 0 dan ly == 0
                        non_forest_mask = (tc_land == 0) & (ly_land == 0)
                        stats["pixel_counts"]["baseline_non_forest"] += int(np.count_nonzero(non_forest_mask))
                        stats["areas_ha"]["baseline_non_forest"] += float(np.sum(area_land[non_forest_mask]))

                        # Stable forest: tc > 0 dan ly == 0
                        stable_mask = (tc_land > 0) & (ly_land == 0)
                        stats["pixel_counts"]["stable_forest"] += int(np.count_nonzero(stable_mask))
                        stats["areas_ha"]["stable_forest"] += float(np.sum(area_land[stable_mask]))

                        # Total loss in [1..25]
                        loss_mask = (ly_land >= 1) & (ly_land <= 25)
                        stats["pixel_counts"]["loss_total_2001_2025"] += int(np.count_nonzero(loss_mask))
                        stats["areas_ha"]["loss_total_2001_2025"] += float(np.sum(area_land[loss_mask]))

                        # Loss per tahun
                        for yr_code in range(1, 26):
                            yr_mask = (ly_land == yr_code)
                            yr_name = str(2000 + yr_code)
                            stats["pixel_counts"]["loss_by_year"][yr_name] += int(np.count_nonzero(yr_mask))
                            stats["areas_ha"]["loss_by_year"][yr_name] += float(np.sum(area_land[yr_mask]))

        # Pembulatan metrik luas
        for k in stats["areas_ha"]:
            if isinstance(stats["areas_ha"][k], dict):
                for yr in stats["areas_ha"][k]:
                    stats["areas_ha"][k][yr] = round(stats["areas_ha"][k][yr], 2)
            else:
                stats["areas_ha"][k] = round(stats["areas_ha"][k], 2)

        # Hitung persentase cakupan
        a_sampled = stats["areas_ha"]["total_inside_polygon"]
        a_land = stats["areas_ha"]["valid_land"]
        a_water = stats["areas_ha"]["permanent_water"]
        a_nodata = stats["areas_ha"]["nodata_marine"]
        a_loss = stats["areas_ha"]["loss_total_2001_2025"]
        a_tc_gt0 = stats["areas_ha"]["baseline_treecover_gt0"]
        a_tc_ge30 = stats["areas_ha"]["baseline_treecover_ge30"]

        stats["coverage_metrics"] = {
            "discretization_error_pct": round(abs(a_sampled - poly_area_ha) / poly_area_ha * 100.0, 3),
            "valid_land_pct_of_poly": round(a_land / poly_area_ha * 100.0, 2),
            "water_pct_of_poly": round(a_water / poly_area_ha * 100.0, 2),
            "nodata_pct_of_poly": round(a_nodata / poly_area_ha * 100.0, 2),
            "total_data_coverage_pct": round((a_land + a_water) / poly_area_ha * 100.0, 2),
            "raster_availability_pct": 100.0 if stats["pixel_counts"]["total_inside_polygon"] > 0 else 0.0,
            "baseline_treecover_pct_of_land": round(a_tc_gt0 / a_land * 100.0, 2) if a_land > 0 else 0.0,
            "baseline_treecover_ge30_pct_of_land": round(a_tc_ge30 / a_land * 100.0, 2) if a_land > 0 else 0.0,
            "cumulative_loss_pct_of_land": round(a_loss / a_land * 100.0, 2) if a_land > 0 else 0.0,
            "cumulative_loss_pct_of_baseline_gt0": round(a_loss / a_tc_gt0 * 100.0, 2) if a_tc_gt0 > 0 else 0.0,
            "cumulative_loss_pct_of_baseline_ge30": round(a_loss / a_tc_ge30 * 100.0, 2) if a_tc_ge30 > 0 else 0.0,
        }

        # Status verifikasi provinsi tetap DEMONSTRATION sesuai batasan ilmiah
        stats["audit_status"] = {
            "data_status": "demonstration",
            "data_verified": False,
            "scientific_notes": (
                "Statistik agregat provinsi dihitung langsung dari grid raster resmi UMD Hansen GFC v1.13 "
                "dengan mask poligon batas administratif resmi. Status tetap disajikan sebagai 'demonstration' "
                "dan data_verified: false untuk mematuhi kebijakan transparansi ilmiah FireGuard."
            )
        }

        t1_prov = time.perf_counter()
        stats["processing_duration_seconds"] = round(t1_prov - t0_prov, 2)
        report["provinces"][prov_name] = stats

        print(f"  Selesai dalam {t1_prov - t0_prov:.2f} s")
        print(f"  Piksel Daratan: {stats['pixel_counts']['valid_land']:,} ({a_land:,.2f} ha)")
        print(f"  Piksel Air: {stats['pixel_counts']['permanent_water']:,} ({a_water:,.2f} ha)")
        print(f"  Piksel NoData: {stats['pixel_counts']['nodata_marine']:,} ({a_nodata:,.2f} ha)")
        print(f"  Cakupan Data Total: {stats['coverage_metrics']['total_data_coverage_pct']}%")
        print(f"  Kehilangan Kanopi 2001–2025: {a_loss:,.2f} ha ({stats['coverage_metrics']['cumulative_loss_pct_of_land']}% dari daratan)")

    total_duration = round(time.perf_counter() - start_total, 2)
    report["total_audit_duration_seconds"] = total_duration

    out_file = HANSEN_OFFICIAL_DIR / "provincial_zonal_coverage_report.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nAudit statistik zonal seluruh provinsi berhasil diselesaikan dalam {total_duration} detik.")
    print(f"Laporan lengkap disimpan di: {out_file}")


if __name__ == "__main__":
    audit_provincial_zonal_stats()
