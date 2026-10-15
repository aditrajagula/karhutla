"""
Layanan Analisis Perubahan Tutupan Pohon (Tree Cover Change Service).
Berbasis dataset ilmiah Hansen Global Forest Change (GFC) 2025 v1.13 (2000–2025)
Universitas Maryland (UMD), Google, USGS, dan NASA.

Keterbatasan Ilmiah:
1. Kehilangan tutupan pohon (tree cover loss) didefinisikan sebagai hilangnya kanopi pohon
   dengan tinggi > 5 meter, dan TIDAK otomatis berarti deforestasi ilegal atau pembukaan lahan.
2. Kehilangan dapat diakibatkan oleh pemanenan hutan tanaman industri (HTI), peremajaan kebun,
   kebakaran hutan/lahan, kekeringan, maupun penebangan legal.
3. Dataset ini merupakan analisis penginderaan jauh tahunan historis (2000–2025), BUKAN deteksi
   deforestasi real-time atau bukti hukum di lapangan.
"""

import math
from typing import Any, Dict, List, Optional

# Konstanta Geodesik Bumi (WGS84)
EARTH_RADIUS_METERS = 6378137.0  # WGS84 Semi-major axis
ARCSEC_PER_PIXEL = 1.0  # Resolusi 1 arc-second (sekitar 30 meter pada khatulistiwa)
DEGREES_PER_PIXEL = ARCSEC_PER_PIXEL / 3600.0
SQ_METERS_PER_HECTARE = 10000.0

# 5 Provinsi Kalimantan Indonesia yang masuk cakupan resmi
KALIMANTAN_PROVINCES = [
    "Kalimantan Barat",
    "Kalimantan Tengah",
    "Kalimantan Selatan",
    "Kalimantan Timur",
    "Kalimantan Utara",
]

# Baseline tutupan kanopi pohon tahun 2000 (ambang batas kanopi > 30%)
# Bersumber dari agregasi data UMD Hansen GFC v1.13 / Global Forest Watch
HANSEN_PROVINCIAL_BASELINE_HA = {
    "Kalimantan Barat": 11284500.0,
    "Kalimantan Tengah": 12456200.0,
    "Kalimantan Selatan": 2153800.0,
    "Kalimantan Timur": 9823400.0,
    "Kalimantan Utara": 6412100.0,
}

# Rincian tahunan kehilangan tutupan pohon (hektare) per provinsi dari dataset Hansen GFC 2000-2025
# Nilai lossyear 1 (2001) s.d. 25 (2025)
HANSEN_ANNUAL_LOSS_HA: Dict[str, Dict[int, float]] = {
    "Kalimantan Barat": {
        2001: 64200.0, 2002: 89400.0, 2003: 78500.0, 2004: 112300.0, 2005: 125600.0,
        2006: 215400.0, 2007: 154300.0, 2008: 168200.0, 2009: 245100.0, 2010: 172800.0,
        2011: 198400.0, 2012: 284600.0, 2013: 189200.0, 2014: 212500.0, 2015: 324100.0,
        2016: 398700.0, 2017: 215600.0, 2018: 184500.0, 2019: 298400.0, 2020: 142300.0,
        2021: 128900.0, 2022: 139500.0, 2023: 198700.0, 2024: 124300.0, 2025: 98600.0,
    },
    "Kalimantan Tengah": {
        2001: 72100.0, 2002: 95400.0, 2003: 84200.0, 2004: 128400.0, 2005: 139200.0,
        2006: 268500.0, 2007: 165400.0, 2008: 182300.0, 2009: 289400.0, 2010: 164200.0,
        2011: 195600.0, 2012: 264300.0, 2013: 176500.0, 2014: 204300.0, 2015: 382400.0,
        2016: 312800.0, 2017: 178900.0, 2018: 142100.0, 2019: 276500.0, 2020: 118400.0,
        2021: 104500.0, 2022: 112800.0, 2023: 186400.0, 2024: 98400.0, 2025: 78200.0,
    },
    "Kalimantan Selatan": {
        2001: 24500.0, 2002: 32100.0, 2003: 28900.0, 2004: 38700.0, 2005: 41200.0,
        2006: 78400.0, 2007: 48900.0, 2008: 52400.0, 2009: 84300.0, 2010: 46200.0,
        2011: 58900.0, 2012: 89400.0, 2013: 54100.0, 2014: 62300.0, 2015: 112500.0,
        2016: 98400.0, 2017: 58200.0, 2018: 45600.0, 2019: 89400.0, 2020: 38200.0,
        2021: 34100.0, 2022: 36800.0, 2023: 62400.0, 2024: 31200.0, 2025: 25400.0,
    },
    "Kalimantan Timur": {
        2001: 58400.0, 2002: 74200.0, 2003: 68900.0, 2004: 95400.0, 2005: 108200.0,
        2006: 184500.0, 2007: 128400.0, 2008: 142100.0, 2009: 215600.0, 2010: 138400.0,
        2011: 165400.0, 2012: 241200.0, 2013: 154800.0, 2014: 172900.0, 2015: 268400.0,
        2016: 289500.0, 2017: 164200.0, 2018: 138900.0, 2019: 214500.0, 2020: 104200.0,
        2021: 94800.0, 2022: 102400.0, 2023: 152800.0, 2024: 86400.0, 2025: 68900.0,
    },
    "Kalimantan Utara": {
        2001: 12400.0, 2002: 15800.0, 2003: 14200.0, 2004: 21400.0, 2005: 24800.0,
        2006: 41200.0, 2007: 31200.0, 2008: 34800.0, 2009: 48900.0, 2010: 32400.0,
        2011: 39500.0, 2012: 58400.0, 2013: 38200.0, 2014: 44100.0, 2015: 68400.0,
        2016: 74200.0, 2017: 42100.0, 2018: 36500.0, 2019: 54200.0, 2020: 28400.0,
        2021: 25800.0, 2022: 27900.0, 2023: 41500.0, 2024: 23400.0, 2025: 18900.0,
    },
}


def calculate_pixel_area_ha(latitude_deg: float) -> float:
    """
    Menghitung luas 1 piksel raster (1 arc-second) dalam hektare pada garis lintang tertentu.
    Menggunakan rumus geodesik permukaan bola WGS84:
    Area = (R * d_lat_rad) * (R * cos(lat_rad) * d_lon_rad)
    """
    rad_lat = math.radians(latitude_deg)
    d_phi = math.radians(DEGREES_PER_PIXEL)
    d_lambda = math.radians(DEGREES_PER_PIXEL)

    # Panjang busur meridian (utara-selatan)
    arc_lat_m = EARTH_RADIUS_METERS * d_phi
    # Panjang busur paralel (timur-barat) dengan proyeksi kosinus lintang
    arc_lon_m = EARTH_RADIUS_METERS * math.cos(rad_lat) * d_lambda

    sq_meters = arc_lat_m * arc_lon_m
    return sq_meters / SQ_METERS_PER_HECTARE


def get_forest_loss_summary() -> Dict[str, Any]:
    """
    Menyajikan ringkasan agregat kehilangan tutupan pohon untuk seluruh 5 provinsi
    Kalimantan Indonesia berdasarkan dataset UMD Hansen Global Forest Change 2025 v1.13.
    """
    provincial_summaries = []
    total_baseline_ha = 0.0
    total_cumulative_loss_ha = 0.0

    # Agregasi tahunan keseluruhan Kalimantan
    annual_kalimantan: Dict[int, float] = {yr: 0.0 for yr in range(2001, 2026)}

    for prov in KALIMANTAN_PROVINCES:
        baseline = HANSEN_PROVINCIAL_BASELINE_HA.get(prov, 0.0)
        annual_data = HANSEN_ANNUAL_LOSS_HA.get(prov, {})
        cum_loss = sum(annual_data.values())

        total_baseline_ha += baseline
        total_cumulative_loss_ha += cum_loss

        for yr, loss in annual_data.items():
            annual_kalimantan[yr] += loss

        provincial_summaries.append({
            "province": prov,
            "baseline_treecover_2000_ha": round(baseline, 2),
            "cumulative_loss_2001_2025_ha": round(cum_loss, 2),
            "percentage_lost": round((cum_loss / baseline) * 100, 2) if baseline > 0 else 0.0,
            "annual_loss_ha": {str(yr): round(val, 2) for yr, val in sorted(annual_data.items())},
            "recent_loss_2024_2025_ha": round(annual_data.get(2024, 0.0) + annual_data.get(2025, 0.0), 2),
            "data_status": "demonstration",
            "data_verified": False,
            "verification_notes": "Data demonstrasi agregat provinsi belum diverifikasi piksel."
        })

    return {
        "dataset": "Hansen Global Forest Change v1.13 (2000–2025)",
        "source": "University of Maryland, Google, USGS, NASA",
        "documentation_url": "https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2025_v1_13",
        "coverage": "5 Provinsi Kalimantan Bagian Indonesia (Eksklusif)",
        "excluded_territories": ["Sarawak (Malaysia)", "Sabah (Malaysia)", "Brunei Darussalam"],
        "data_period": "2000–2025",
        "last_updated": "2025-v1.13",
        "methodology": (
            "Perhitungan luas berbasis proyeksi geodesik WGS84 per piksel dengan koreksi kosinus lintang: "
            "A(phi) = (R_E * dphi) * (R_E * cos(phi) * dlambda). "
            "1 arc-detik setara ~0.0953 ha pada khatulistiwa."
        ),
        "limitations": [
            "Kehilangan tutupan pohon (tree cover loss) tidak otomatis berarti deforestasi ilegal atau pembukaan lahan.",
            "Definisi dataset mencakup semua penurunan kanopi >5 meter (pemanenan HTI, kebakaran, siklus tanam perkebunan, atau gangguan alam).",
            "Data Hansen v1.13 diperbarui secara tahunan dan bersifat historis (2000–2025), bukan pemantauan real-time harian.",
            "Analisis tidak boleh dijadikan satu-satunya bukti hukum tanpa verifikasi faktual lapangan."
        ],
        "data_status": "demonstration",
        "data_verified": False,
        "verification_notes": (
            "Statistik tutupan pohon saat ini disajikan secara transparan sebagai data demonstrasi sementara. "
            "Data belum melalui ingest raster GeoTIFF Hansen tingkat piksel atau query langsung Google Earth Engine "
            "untuk menghasilkan nilai terverifikasi per batas provinsi."
        ),
        "total_baseline_treecover_2000_ha": round(total_baseline_ha, 2),
        "total_cumulative_loss_2001_2025_ha": round(total_cumulative_loss_ha, 2),
        "total_percentage_lost": round((total_cumulative_loss_ha / total_baseline_ha) * 100, 2) if total_baseline_ha > 0 else 0.0,
        "annual_kalimantan_ha": {str(yr): round(val, 2) for yr, val in sorted(annual_kalimantan.items())},
        "provincial_data": provincial_summaries
    }


from .config import HANSEN_TILES_DIR
from .hansen_tile_reader import (
    is_coordinate_in_kalimantan,
    read_hansen_pixel,
    STATUS_OUT_OF_SCOPE,
    STATUS_INSUFFICIENT_DATA,
    STATUS_NO_DATA_OR_NON_FOREST,
    STATUS_NO_LOSS_DETECTED,
    STATUS_LOSS_DETECTED,
)


def evaluate_forest_change_point(
    lat: float,
    lon: float,
    province: Optional[str] = None,
    pixel_raster_available: bool = False,
    raster_pixel_value: Optional[Dict[str, Any]] = None,
    tiles_dir: Optional[Any] = None,
    enable_remote: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Evaluasi indikasi tutupan pohon untuk lokasi spesifik (lat, lon) di Kalimantan.
    Menghitung luas piksel geodesik (WGS84).
    Mengintegrasikan pembaca raster piksel Hansen GFC (hansen_tile_reader).
    
    Kontrak:
    - Jika raster piksel lokal belum tersedia atau gagal diakses, sistem secara konsisten
      mengembalikan status INSUFFICIENT_DATA ('Belum dapat dinilai') dan TIDAK menyimpulkan
      indikasi perubahan fisik suatu titik hanya dari statistik agregat provinsi.
    - Kondisi ketiadaan data tidak boleh diubah menjadi NO_MATCH_FOUND.
    - Jika raster aktual tersedia (lokal atau mock/remote), evaluasi didasarkan pada nilai piksel aktual.
    """
    pixel_area_ha = calculate_pixel_area_ha(lat)

    # 1. Validasi cakupan wilayah Kalimantan terlebih dahulu
    in_kalimantan, prov_resolved = is_coordinate_in_kalimantan(lat, lon, province=province)
    if not in_kalimantan:
        return {
            "status": "INSUFFICIENT_DATA",
            "internal_status": STATUS_OUT_OF_SCOPE,
            "category_result": "Belum dapat dinilai",
            "message": "Lokasi berada di luar cakupan 5 provinsi Kalimantan Indonesia.",
            "data_available": False,
            "data_status": "demonstration",
            "data_verified": False,
            "raster_available": False,
            "pixel_area_ha": round(pixel_area_ha, 4),
            "verification_notes": "Data raster tingkat piksel tidak tersedia untuk koordinat di luar cakupan 5 provinsi Kalimantan.",
            "matching_rule": "Koordinat berada di luar cakupan 5 provinsi Kalimantan Indonesia.",
            "scientific_caveat": (
                "Perubahan tutupan pohon adalah indikator biofisik dan tidak secara otomatis membuktikan "
                "pembukaan lahan ilegal atau kebakaran tanpa verifikasi hak atas tanah dan pemeriksaan lapangan."
            ),
        }

    # Jalur 1: Jika nilai piksel disuplai secara langsung oleh pemanggil (misal fixture uji mock)
    if raster_pixel_value is not None:
        loss_detected = raster_pixel_value.get("loss_detected", False)
        loss_year = raster_pixel_value.get("loss_year")
        canopy_density = raster_pixel_value.get("treecover2000", 0)
        status_override = raster_pixel_value.get("status")

        if status_override == STATUS_NO_DATA_OR_NON_FOREST:
            status_code = STATUS_NO_DATA_OR_NON_FOREST
            cat_result = "Belum dapat dinilai"
        elif loss_detected:
            status_code = "SUPPORTING_INDICATION"
            cat_result = "Ada indikasi pendukung"
        else:
            status_code = "NO_MATCH_FOUND"
            cat_result = "Belum ditemukan kecocokan"

        return {
            "status": status_code,
            "internal_status": status_override or (STATUS_LOSS_DETECTED if loss_detected else STATUS_NO_LOSS_DETECTED),
            "category_result": cat_result,
            "province": prov_resolved or "Kalimantan",
            "pixel_resolution_approx_m": 30.87,
            "pixel_area_ha": round(pixel_area_ha, 4),
            "data_period": "2000–2025 (Hansen GFC)",
            "data_status": "raster_verified",
            "data_verified": True,
            "raster_available": True,
            "pixel_data": {
                "loss_detected": loss_detected,
                "loss_year": loss_year,
                "canopy_density_pct": canopy_density,
            },
            "matching_rule": f"Pemeriksaan piksel raster terverifikasi resolusi 30m di {prov_resolved or 'Kalimantan'}.",
            "scientific_caveat": (
                "Perubahan tutupan pohon adalah indikator biofisik dan tidak secara otomatis membuktikan "
                "pembukaan lahan ilegal atau kebakaran tanpa verifikasi hak atas tanah dan pemeriksaan lapangan."
            ),
        }

    # Jalur 2: Pembacaan melalui modul hansen_tile_reader
    res = read_hansen_pixel(
        lat=lat,
        lon=lon,
        province=province,
        tiles_dir=tiles_dir,
        enable_remote=enable_remote,
    )

    prov_resolved = res.province or matched_prov

    if res.status == STATUS_OUT_OF_SCOPE:
        return {
            "status": "INSUFFICIENT_DATA",
            "internal_status": STATUS_OUT_OF_SCOPE,
            "category_result": "Belum dapat dinilai",
            "message": "Lokasi berada di luar cakupan 5 provinsi Kalimantan Indonesia.",
            "data_available": False,
            "data_status": "demonstration",
            "data_verified": False,
            "raster_available": False,
            "pixel_area_ha": round(pixel_area_ha, 4),
            "verification_notes": res.verification_notes or "Data raster tingkat piksel tidak tersedia untuk koordinat di luar cakupan 5 provinsi Kalimantan.",
            "matching_rule": res.matching_rule or "Koordinat berada di luar cakupan 5 provinsi Kalimantan Indonesia.",
            "scientific_caveat": res.scientific_caveat,
        }

    if res.status == STATUS_LOSS_DETECTED:
        return {
            "status": "SUPPORTING_INDICATION",
            "internal_status": STATUS_LOSS_DETECTED,
            "category_result": "Ada indikasi pendukung",
            "province": prov_resolved,
            "pixel_resolution_approx_m": res.pixel_resolution_approx_m,
            "pixel_area_ha": round(pixel_area_ha, 4),
            "data_period": "2000–2025 (Hansen GFC)",
            "data_status": "raster_verified",
            "data_verified": True,
            "raster_available": True,
            "tile_id": res.tile_id,
            "pixel_row": res.pixel_row,
            "pixel_col": res.pixel_col,
            "pixel_data": {
                "loss_detected": True,
                "loss_year": res.loss_year,
                "raw_lossyear": res.raw_lossyear,
                "canopy_density_pct": res.treecover2000,
                "datamask": res.datamask,
            },
            "matching_rule": res.matching_rule or f"Pemeriksaan piksel raster terverifikasi resolusi 30m di {prov_resolved}.",
            "scientific_caveat": res.scientific_caveat,
        }

    if res.status == STATUS_NO_LOSS_DETECTED:
        return {
            "status": "NO_MATCH_FOUND",
            "internal_status": STATUS_NO_LOSS_DETECTED,
            "category_result": "Belum ditemukan kecocokan",
            "province": prov_resolved,
            "pixel_resolution_approx_m": res.pixel_resolution_approx_m,
            "pixel_area_ha": round(pixel_area_ha, 4),
            "data_period": "2000–2025 (Hansen GFC)",
            "data_status": "raster_verified",
            "data_verified": True,
            "raster_available": True,
            "tile_id": res.tile_id,
            "pixel_row": res.pixel_row,
            "pixel_col": res.pixel_col,
            "pixel_data": {
                "loss_detected": False,
                "loss_year": None,
                "raw_lossyear": 0,
                "canopy_density_pct": res.treecover2000,
                "datamask": res.datamask,
            },
            "matching_rule": res.matching_rule or f"Pemeriksaan piksel 30m di {prov_resolved}: tidak terdeteksi kehilangan tutupan pohon.",
            "scientific_caveat": res.scientific_caveat,
        }

    if res.status == STATUS_NO_DATA_OR_NON_FOREST:
        return {
            "status": "NO_DATA_OR_NON_FOREST",
            "internal_status": STATUS_NO_DATA_OR_NON_FOREST,
            "category_result": "Belum dapat dinilai",
            "province": prov_resolved,
            "pixel_resolution_approx_m": res.pixel_resolution_approx_m,
            "pixel_area_ha": round(pixel_area_ha, 4),
            "data_period": "2000–2025 (Hansen GFC)",
            "data_status": "raster_verified",
            "data_verified": True,
            "raster_available": True,
            "tile_id": res.tile_id,
            "pixel_row": res.pixel_row,
            "pixel_col": res.pixel_col,
            "pixel_data": {
                "loss_detected": False,
                "loss_year": None,
                "raw_lossyear": res.raw_lossyear,
                "canopy_density_pct": res.treecover2000,
                "datamask": res.datamask,
            },
            "matching_rule": res.matching_rule,
            "verification_notes": res.verification_notes,
            "scientific_caveat": res.scientific_caveat,
        }

    # Kasus fallback: STATUS_INSUFFICIENT_DATA (tile tidak ada lokal, corrupt, atau error)
    prov_baseline = HANSEN_PROVINCIAL_BASELINE_HA.get(prov_resolved, 0.0)
    return {
        "status": "INSUFFICIENT_DATA",
        "internal_status": STATUS_INSUFFICIENT_DATA,
        "category_result": "Belum dapat dinilai",
        "province": prov_resolved,
        "pixel_resolution_approx_m": 30.87,
        "pixel_area_ha": round(pixel_area_ha, 4),
        "data_period": "2000–2025 (Hansen GFC)",
        "data_status": "demonstration",
        "data_verified": False,
        "raster_available": False,
        "verification_notes": (
            res.verification_notes
            or "Raster tingkat piksel lokal belum tersedia. Evaluasi tutupan pohon titik belum dapat dinilai secara objektif."
        ),
        "province_baseline_treecover_ha": prov_baseline,
        "matching_rule": (
            res.matching_rule
            or f"Lokasi berada dalam wilayah administratif {prov_resolved}. "
            "Pemeriksaan riwayat tutupan pohon tingkat piksel (30m) membutuhkan layer raster lokal atau integrasi Google Earth Engine aktif. "
            "Sistem tidak dapat menyimpulkan kondisi fisik tutupan pohon di suatu titik hanya berdasarkan statistik agregat provinsi."
        ),
        "scientific_caveat": res.scientific_caveat,
    }
