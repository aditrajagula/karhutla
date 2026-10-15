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

# Konstanta Parameter Elipsoid Geodesik WGS84 (EPSG:7030 / EPSG:4326)
WGS84_A = 6378137.0  # Sumbu semi-major (equatorial radius) dalam meter
WGS84_F = 1.0 / 298.257223563  # Flattening (pemepatan elipsoid)
WGS84_B = WGS84_A * (1.0 - WGS84_F)  # Sumbu semi-minor (polar radius) ~ 6356752.314245 meter
WGS84_E2 = 2.0 * WGS84_F - WGS84_F * WGS84_F  # Kuadrat eksentrisitas pertama (e^2) ~ 0.00669437999014
WGS84_E = math.sqrt(WGS84_E2)  # Eksentrisitas pertama (e) ~ 0.0818191908426
SQ_METERS_PER_HECTARE = 10000.0

# Backward-compatibility alias
EARTH_RADIUS_METERS = WGS84_A

# Resolusi Spasial Hansen Global Forest Change v1.13:
# Grid UMD memiliki 40.000 piksel per tile 10°x10°:
# 10° / 40.000 = 0.00025° = 0.9 arc-second (~27.83 meter pada khatulistiwa)
HANSEN_PIXEL_DEGREES = 0.00025
HANSEN_ARCSEC_PER_PIXEL = 0.9

# Alias kompatibilitas mundur
DEGREES_PER_PIXEL = HANSEN_PIXEL_DEGREES
ARCSEC_PER_PIXEL = HANSEN_ARCSEC_PER_PIXEL

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


def _wgs84_q(phi_rad: float) -> float:
    """
    Fungsi authalic latitude Q(phi) pada elipsoid oblat WGS84:
    Q(phi) = (sin(phi) / (1 - e^2 * sin^2(phi))) + (1 / (2*e)) * ln((1 + e*sin(phi)) / (1 - e*sin(phi)))
    Digunakan untuk integrasi analitik luas permukaan elipsoid antara dua lintang paralel.
    """
    sin_p = math.sin(phi_rad)
    e_sin_p = WGS84_E * sin_p
    # Safety clamping jika nilai mendekati batas kutub
    if e_sin_p >= 1.0:
        e_sin_p = 0.999999999999999
    elif e_sin_p <= -1.0:
        e_sin_p = -0.999999999999999

    term1 = sin_p / (1.0 - WGS84_E2 * sin_p * sin_p)
    term2 = (1.0 / (2.0 * WGS84_E)) * math.log((1.0 + e_sin_p) / (1.0 - e_sin_p))
    return term1 + term2


def wgs84_ellipsoid_cell_area_ha(
    lat_south_deg: float,
    lat_north_deg: float,
    d_lon_deg: float,
) -> float:
    """
    Menghitung luas sel kuadrilateral pada elipsoid WGS84 secara eksak
    melalui integrasi analitik zona authalic:
    Area = 0.5 * b^2 * |d_lambda| * |Q(phi_north) - Q(phi_south)|
    Hasil dikonversi ke satuan hektare (1 ha = 10.000 m^2).
    """
    p_south = max(-90.0, min(90.0, lat_south_deg))
    p_north = max(-90.0, min(90.0, lat_north_deg))
    if p_south > p_north:
        p_south, p_north = p_north, p_south

    phi1_rad = math.radians(p_south)
    phi2_rad = math.radians(p_north)
    d_lambda_rad = math.radians(abs(d_lon_deg))

    q1 = _wgs84_q(phi1_rad)
    q2 = _wgs84_q(phi2_rad)

    sq_meters = 0.5 * (WGS84_B ** 2) * d_lambda_rad * abs(q2 - q1)
    return sq_meters / SQ_METERS_PER_HECTARE


def calculate_pixel_area_ha(
    latitude_deg: float,
    degrees_per_pixel: float = HANSEN_PIXEL_DEGREES,
    degrees_per_pixel_y: Optional[float] = None,
    lat_south_deg: Optional[float] = None,
    lat_north_deg: Optional[float] = None,
) -> float:
    """
    Menghitung luas sel piksel raster dalam satuan hektare pada garis lintang tertentu
    menggunakan integrasi luas analitik elipsoid WGS84 sejati (EPSG:4326 / EPSG:7030),
    bukan pendekatan bola konstan R=a.
    
    Metode:
    Mengintegrasikan secara analitik luas permukaan elipsoid antara batas lintang
    selatan (phi_south) dan utara (phi_north) untuk rentang bujur d_lambda:
    Area = 0.5 * b^2 * |d_lambda| * |Q(phi_north) - Q(phi_south)|
    di mana b adalah sumbu semi-minor WGS84 (~6.356.752,31 m) dan Q(phi) adalah
    fungsi authalic latitude elipsoid.
    
    Nilai acuan sel 0.00025° x 0.00025° Hansen GFC v1.13:
    - Ekuator (0°): ~0.07693 ha (~769.32 m²)
    - Lintang -2.25° (Kalimantan Tengah): ~0.07687 ha (~768.74 m²)
    """
    if degrees_per_pixel_y is None:
        degrees_per_pixel_y = degrees_per_pixel

    d_x = abs(degrees_per_pixel)
    d_y = abs(degrees_per_pixel_y)

    if lat_south_deg is not None and lat_north_deg is not None:
        s = lat_south_deg
        n = lat_north_deg
    else:
        half_dy = d_y / 2.0
        s = max(-90.0, latitude_deg - half_dy)
        n = min(90.0, latitude_deg + half_dy)

    return wgs84_ellipsoid_cell_area_ha(s, n, d_x)


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
            "Perhitungan luas berbasis integrasi analitik elipsoid WGS84 (authalic latitude) "
            "per sel piksel raster resolusi 0,00025° x 0,00025° (~0,9 arc-detik, bukan satu arc-detik penuh). "
            "Luas sel piksel bervariasi menurut garis lintang: ~0,07693 ha pada khatulistiwa (0°) "
            "hingga ~0,07687 ha pada lintang -2,25° (Kalimantan Tengah)."
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
            "untuk menghasilkan nilai agregat definitif per batas provinsi."
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
    use_official: Optional[bool] = None,
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
            "is_official": False,
            "source_type": "UNAVAILABLE",
            "manifest_info": None,
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
            "pixel_resolution_approx_m": 27.83,
            "pixel_area_ha": round(pixel_area_ha, 4),
            "data_period": "2000–2025 (Hansen GFC)",
            "data_status": "demonstration",
            "data_verified": False,
            "raster_available": True,
            "is_official": False,
            "source_type": "DEMO_SYNTHETIC",
            "manifest_info": None,
            "pixel_data": {
                "loss_detected": loss_detected,
                "loss_year": loss_year,
                "canopy_density_pct": canopy_density,
            },
            "matching_rule": f"Pemeriksaan piksel raster Hansen GFC v1.13 resolusi 30m di {prov_resolved or 'Kalimantan'}.",
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
        use_official=use_official,
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
            "is_official": False,
            "source_type": "UNAVAILABLE",
            "manifest_info": None,
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
            "data_status": res.data_status,
            "data_verified": res.data_verified,
            "is_official": res.is_official,
            "source_type": res.source_type,
            "manifest_info": res.manifest_info,
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
            "matching_rule": res.matching_rule or f"Pemeriksaan piksel raster Hansen GFC v1.13 resolusi 30m di {prov_resolved}.",
            "verification_notes": res.verification_notes,
            "scientific_caveat": res.scientific_caveat,
            "pixel_center_lat": res.pixel_center_lat,
            "pixel_center_lon": res.pixel_center_lon,
            "transform_verified": res.transform_verified,
            "coordinate_audit": res.coordinate_audit,
            "latency_ms": res.latency_ms,
            "cache_hit": res.cache_hit,
            "access_method": res.access_method,
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
            "data_status": res.data_status,
            "data_verified": res.data_verified,
            "is_official": res.is_official,
            "source_type": res.source_type,
            "manifest_info": res.manifest_info,
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
            "verification_notes": res.verification_notes,
            "scientific_caveat": res.scientific_caveat,
            "pixel_center_lat": res.pixel_center_lat,
            "pixel_center_lon": res.pixel_center_lon,
            "transform_verified": res.transform_verified,
            "coordinate_audit": res.coordinate_audit,
            "latency_ms": res.latency_ms,
            "cache_hit": res.cache_hit,
            "access_method": res.access_method,
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
            "data_status": res.data_status,
            "data_verified": res.data_verified,
            "is_official": res.is_official,
            "source_type": res.source_type,
            "manifest_info": res.manifest_info,
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
            "pixel_center_lat": res.pixel_center_lat,
            "pixel_center_lon": res.pixel_center_lon,
            "transform_verified": res.transform_verified,
            "coordinate_audit": res.coordinate_audit,
            "latency_ms": res.latency_ms,
            "cache_hit": res.cache_hit,
            "access_method": res.access_method,
        }

    # Kasus fallback: STATUS_INSUFFICIENT_DATA (tile tidak ada lokal, corrupt, atau error)
    prov_baseline = HANSEN_PROVINCIAL_BASELINE_HA.get(prov_resolved, 0.0)
    return {
        "status": "INSUFFICIENT_DATA",
        "internal_status": STATUS_INSUFFICIENT_DATA,
        "category_result": "Belum dapat dinilai",
        "province": prov_resolved,
        "pixel_resolution_approx_m": 27.83,
        "pixel_area_ha": round(pixel_area_ha, 4),
        "data_period": "2000–2025 (Hansen GFC)",
        "data_status": res.data_status,
        "data_verified": res.data_verified,
        "is_official": res.is_official,
        "source_type": res.source_type,
        "manifest_info": res.manifest_info,
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
        "latency_ms": res.latency_ms,
        "cache_hit": res.cache_hit,
        "access_method": res.access_method,
    }
