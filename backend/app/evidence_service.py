"""
Modul Penilaian Bukti Laporan Warga (Citizen Report Evidence Assessment Engine).
Memisahkan status penyimpanan teknis laporan (PENDING) dari hasil analisis bukti faktual.

Kategori Hasil Analisis:
1. Ada indikasi pendukung (SUPPORTING_INDICATION)
2. Belum ditemukan kecocokan (NO_MATCH_FOUND)
3. Belum dapat dinilai (NOT_ASSESSED)

Aturan Khusus:
- Kategori 'kebakaran': Dicocokkan dengan anomali termal NASA FIRMS (radius <= 10 km, waktu +- 3 hari).
  Jika tidak ada titik api, dijelaskan bahwa ketiadaan hotspot bukan bukti tidak adanya kebakaran
  (bisa terhalang awan, kebakaran gambut bawah tanah/smoldering, atau celah waktu orbit).
- Kategori 'pembukaan_lahan' dan 'perubahan_tutupan': Dicocokkan dengan dataset Hansen GFC 2025 v1.13.
  Hotspot TIDAK DIGUNAKAN sebagai bukti pembukaan lahan. Kehilangan tutupan pohon tidak otomatis
  berarti deforestasi ilegal.
"""

import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .forest_change_service import (
    calculate_pixel_area_ha,
    evaluate_forest_change_point,
    KALIMANTAN_PROVINCES,
)


def calculate_haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Menghitung jarak geodetik (km) antara dua koordinat WGS84."""
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def parse_iso_utc(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        clean = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def assess_report_evidence(
    report: Dict[str, Any],
    hotspots: Optional[List[Dict[str, Any]]] = None,
    firms_available: bool = True,
    coverage_date_range: Optional[Dict[str, Optional[str]]] = None,
) -> Dict[str, Any]:
    """
    Melakukan penilaian bukti ilmiah terhadap laporan warga berdasarkan kategori laporan.
    """
    category = report.get("category", "")
    category = {
        "asap_kebakaran": "kebakaran",
        "kebakaran_hutan": "kebakaran",
        "deforestasi": "pembukaan_lahan",
        "land_clearing": "pembukaan_lahan",
        "illegal_logging": "penebangan_liar",
        "pembalakan_liar": "penebangan_liar",
        "perambahan": "perambahan_hutan",
        "alih_fungsi_bekas_karhutla": "perubahan_tutupan",
    }.get(category, category)
    lat = float(report.get("latitude", 0.0))
    lon = float(report.get("longitude", 0.0))
    observed_at_str = report.get("observed_at_utc", "")
    province = report.get("province")

    # =========================================================================
    # Kategori 1: Kebakaran atau kemunculan asap
    # =========================================================================
    if category == "kebakaran":
        if not firms_available or hotspots is None:
            return {
                "assessment_code": "INSUFFICIENT_DATA",
                "category_result": "Belum dapat dinilai",
                "evidence_type": "thermal_anomaly_satellite",
                "summary": "Data anomali termal satelit tidak tersedia atau sinkronisasi data FIRMS gagal.",
                "matching_rule": "Pencarian hotspot FIRMS dalam radius 10 km dan rentang waktu ±3 hari (72 jam).",
                "details": None,
                "limitations_caveat": (
                    "Sinkronisasi atau pengambilan data anomali termal satelit NASA FIRMS tidak tersedia atau mengalami kegagalan. "
                    "Ketiadaan data BUKAN bukti bahwa tidak ada kebakaran. Penilaian bukti belum dapat dilakukan."
                )
            }

        target_dt = parse_iso_utc(observed_at_str)
        max_dist_km = 10.0
        max_time_diff_hours = 72.0  # +- 3 hari

        # Validasi apakah jendela waktu pengamatan laporan masuk dalam cakupan data satelit yang tersedia
        if target_dt:
            cov_min_str = coverage_date_range.get("min") if coverage_date_range else None
            cov_max_str = coverage_date_range.get("max") if coverage_date_range else None
            if not cov_min_str or not cov_max_str:
                all_acq_dates = [
                    h.get("properties", h).get("acq_date")
                    for h in hotspots
                    if h.get("properties", h).get("acq_date")
                ]
                if all_acq_dates:
                    cov_min_str = min(all_acq_dates)
                    cov_max_str = max(all_acq_dates)

            if cov_min_str and cov_max_str:
                window_start_str = (target_dt - timedelta(days=3)).strftime("%Y-%m-%d")
                window_end_str = (target_dt + timedelta(days=3)).strftime("%Y-%m-%d")
                # Jika jendela pengamatan laporan sama sekali tidak beririsan dengan tanggal data yang tersedia
                if window_end_str < cov_min_str or window_start_str > cov_max_str:
                    return {
                        "assessment_code": "INSUFFICIENT_DATA",
                        "category_result": "Belum dapat dinilai",
                        "evidence_type": "thermal_anomaly_satellite",
                        "summary": (
                            f"Data anomali termal satelit FIRMS untuk rentang tanggal observasi laporan "
                            f"({target_dt.strftime('%Y-%m-%d')}) belum tersedia dalam cakupan data saat ini ({cov_min_str} s.d. {cov_max_str})."
                        ),
                        "matching_rule": "Pencarian hotspot FIRMS dalam radius 10 km dan rentang waktu ±3 hari (72 jam).",
                        "details": {
                            "report_observed_at": observed_at_str,
                            "coverage_available": {"min": cov_min_str, "max": cov_max_str},
                        },
                        "limitations_caveat": (
                            "Data penginderaan jauh satelit pada tanggal observasi historis ini belum tersedia dalam cakupan data. "
                            "Ketiadaan data BUKAN bukti bahwa tidak ada kebakaran. Penilaian bukti belum dapat dilakukan."
                        )
                    }

        nearest_match = None
        min_distance = float("inf")

        for h in hotspots:
            h_coords = h.get("geometry", {}).get("coordinates", [])
            if len(h_coords) >= 2:
                h_lon, h_lat = h_coords[0], h_coords[1]
            elif "latitude" in h and "longitude" in h:
                h_lat, h_lon = float(h["latitude"]), float(h["longitude"])
            else:
                continue

            dist = calculate_haversine_km(lat, lon, h_lat, h_lon)
            if dist <= max_dist_km:
                props = h.get("properties", h)
                acq_date = props.get("acq_date")
                acq_time = props.get("acq_time", "0000")

                time_matched = True
                if target_dt and acq_date:
                    try:
                        time_str = str(acq_time).zfill(4)
                        h_dt_str = f"{acq_date}T{time_str[:2]}:{time_str[2:]}:00+00:00"
                        h_dt = datetime.fromisoformat(h_dt_str)
                        diff_h = abs((target_dt - h_dt).total_seconds()) / 3600.0
                        if diff_h > max_time_diff_hours:
                            time_matched = False
                    except Exception:
                        pass

                if time_matched and dist < min_distance:
                    min_distance = dist
                    nearest_match = {
                        "distance_km": round(dist, 2),
                        "satellite": props.get("satellite", "VIIRS"),
                        "instrument": props.get("instrument", "VIIRS"),
                        "acq_date": props.get("acq_date"),
                        "acq_time": props.get("acq_time"),
                        "confidence": props.get("confidence"),
                        "frp_mw": props.get("frp"),
                    }

        if nearest_match is not None:
            return {
                "assessment_code": "SUPPORTING_INDICATION",
                "category_result": "Ada indikasi pendukung",
                "evidence_type": "thermal_anomaly_satellite",
                "summary": (
                    f"Ditemukan anomali termal satelit {nearest_match['satellite']} berjarak "
                    f"{nearest_match['distance_km']} km dari lokasi pengamatan."
                ),
                "matching_rule": f"Radius spasial <= 10.0 km dan rentang waktu <= 72 jam (±3 hari).",
                "details": nearest_match,
                "limitations_caveat": (
                    "Hotspot adalah indikasi anomali termal suhu tinggi di permukaan bumi yang terdeteksi "
                    "sensor satelit, BUKAN bukti otomatis terjadinya kebakaran hutan terbuka."
                )
            }
        else:
            return {
                "assessment_code": "NO_MATCH_FOUND",
                "category_result": "Belum ditemukan kecocokan",
                "evidence_type": "thermal_anomaly_satellite",
                "summary": "Belum terdeteksi anomali termal satelit NASA FIRMS yang cocok di sekitar lokasi dan waktu ini.",
                "matching_rule": f"Pencarian dalam radius 10.0 km dan jendela waktu ±3 hari.",
                "details": {"searched_radius_km": max_dist_km, "searched_window_hours": max_time_diff_hours},
                "limitations_caveat": (
                    "Ketiadaan deteksi hotspot BUKAN bukti bahwa tidak ada kebakaran. "
                    "Anomali termal dapat tidak terdeteksi satelit karena tertutup awan hujan/asap tebal, "
                    "terjadi di antara waktu perlintasan orbit satelit (hanya lewat 1-2 kali sehari), "
                    "atau berupa kebakaran gambut bawah tanah (smoldering peat fire) dengan suhu permukaan rendah."
                )
            }

    # =========================================================================
    # Kategori Deforestasi: Pembukaan lahan, penebangan liar, perambahan hutan, tutupan pohon
    # =========================================================================
    elif category in ("pembukaan_lahan", "perubahan_tutupan", "penebangan_liar", "perambahan_hutan"):
        point_eval = evaluate_forest_change_point(lat=lat, lon=lon, province=province)

        glad_extent_info = None
        try:
            from .glad_forest_reader import lookup_forest_extent
            glad_res = lookup_forest_extent(lat=lat, lon=lon)
            if glad_res:
                glad_extent_info = {
                    "classification": glad_res.classification,
                    "status": glad_res.status,
                    "raster_available": glad_res.raster_available,
                    "definition": "Tutupan pohon tinggi >= 5m (GLAD 2020 baseline)",
                }
        except Exception:
            glad_extent_info = None

        if point_eval.get("status") == "SUPPORTING_INDICATION":
            matched_prov = point_eval.get("province", "Kalimantan")
            return {
                "assessment_code": "SUPPORTING_INDICATION",
                "category_result": "Ada indikasi pendukung",
                "evidence_type": "hansen_gfc_treecover_loss",
                "summary": (
                    f"Lokasi berada di {matched_prov} dengan indikasi deteksi riwayat kehilangan tutupan kanopi "
                    f"pada dataset Hansen Global Forest Change v1.13."
                ),
                "matching_rule": point_eval.get("matching_rule"),
                "details": {
                    "dataset": "Hansen GFC 2025 v1.13",
                    "province": matched_prov,
                    "category": category,
                    "pixel_area_ha": point_eval.get("pixel_area_ha"),
                    "data_period": "2000–2025",
                    "satellite_sources": "Landsat (USGS/NASA) / UMD",
                    "data_status": point_eval.get("data_status", "demonstration"),
                    "data_verified": point_eval.get("data_verified", False),
                    "pixel_data": point_eval.get("pixel_data"),
                    "forest_extent_2020": glad_extent_info,
                },
                "limitations_caveat": (
                    "PERINGATAN ILMIAH: Hotspot satelit TIDAK DIGUNAKAN sebagai bukti pembukaan lahan. "
                    "Kehilangan tutupan pohon didefinisikan sebagai hilangnya kanopi >5m (bisa berasal dari "
                    "pemanenan HTI, perkebunan berizin, atau bencana alam) dan TIDAK menyatakan tindakan ilegal "
                    "maupun deforestasi yang disengaja tanpa pembuktian hak atas tanah dan izin resmi."
                )
            }
        elif point_eval.get("status") == "NO_DATA_OR_NON_FOREST":
            matched_prov = point_eval.get("province", "Kalimantan")
            return {
                "assessment_code": "INSUFFICIENT_DATA",
                "category_result": "Belum dapat dinilai",
                "evidence_type": "hansen_gfc_treecover_loss",
                "summary": point_eval.get(
                    "verification_notes",
                    "Piksel teridentifikasi sebagai badan air atau area bukan tutupan kanopi pada baseline 2000."
                ),
                "matching_rule": point_eval.get("matching_rule", "Pemeriksaan piksel raster Hansen GFC v1.13 resolusi 30m."),
                "details": {
                    "province": matched_prov,
                    "category": category,
                    "data_status": point_eval.get("data_status", "demonstration"),
                    "data_verified": point_eval.get("data_verified", False),
                    "raster_available": True,
                    "pixel_area_ha": point_eval.get("pixel_area_ha"),
                    "pixel_data": point_eval.get("pixel_data"),
                    "forest_extent_2020": glad_extent_info,
                },
                "limitations_caveat": (
                    "PERINGATAN ILMIAH: Piksel teridentifikasi sebagai badan air permanen, area tanpa data pemetaan kanopi, "
                    "atau bukan hutan pada baseline tahun 2000. Sistem tidak dapat menilai kehilangan tutupan pohon pada area non-kanopi."
                )
            }
        elif point_eval.get("status") == "INSUFFICIENT_DATA":
            matched_prov = point_eval.get("province")
            summary_text = (
                f"Data raster piksel Hansen GFC belum tersedia untuk evaluasi tutupan pohon titik di {matched_prov}."
                if matched_prov else
                "Lokasi berada di luar cakupan 5 provinsi Kalimantan Indonesia atau data raster belum memadai."
            )
            return {
                "assessment_code": "INSUFFICIENT_DATA",
                "category_result": "Belum dapat dinilai",
                "evidence_type": "hansen_gfc_treecover_loss",
                "summary": summary_text,
                "matching_rule": point_eval.get(
                    "matching_rule",
                    "Pemeriksaan riwayat tutupan pohon tingkat piksel (30m) membutuhkan layer raster lokal Hansen GFC v1.13."
                ),
                "details": {
                    "province": matched_prov,
                    "category": category,
                    "data_status": point_eval.get("data_status", "demonstration"),
                    "data_verified": point_eval.get("data_verified", False),
                    "raster_available": False,
                    "pixel_area_ha": point_eval.get("pixel_area_ha"),
                    "forest_extent_2020": glad_extent_info,
                },
                "limitations_caveat": (
                    "PERINGATAN ILMIAH: Status 'Belum dapat dinilai' (INSUFFICIENT_DATA) diberikan karena data raster "
                    "tingkat piksel belum tersedia di sistem. Status ini BUKAN 'Belum ditemukan kecocokan' (NO_MATCH_FOUND). "
                    "Kehilangan tutupan pohon tidak secara otomatis membuktikan pembukaan lahan ilegal atau kebakaran."
                )
            }
        elif point_eval.get("status") == "NO_MATCH_FOUND":
            dt_details = point_eval.get("pixel_data") or {}
            if isinstance(dt_details, dict):
                dt_details["forest_extent_2020"] = glad_extent_info
                dt_details["category"] = category
            return {
                "assessment_code": "NO_MATCH_FOUND",
                "category_result": "Belum ditemukan kecocokan",
                "evidence_type": "hansen_gfc_treecover_loss",
                "summary": "Pemeriksaan raster Hansen GFC v1.13 tidak menemukan riwayat kehilangan tutupan pohon pada piksel ini.",
                "matching_rule": point_eval.get("matching_rule", "Pemeriksaan piksel 30m."),
                "details": dt_details,
                "limitations_caveat": (
                    "Ketiadaan deteksi kehilangan kanopi bukan jaminan ketiadaan aktivitas pembukaan lahan minor di bawah kanopi."
                )
            }
        else:
            return {
                "assessment_code": "INSUFFICIENT_DATA",
                "category_result": "Belum dapat dinilai",
                "evidence_type": "hansen_gfc_treecover_loss",
                "summary": "Lokasi berada di luar 5 provinsi cakupan Kalimantan Indonesia.",
                "matching_rule": "Hanya 5 provinsi Kalimantan Indonesia yang dianalisis dalam versi ini.",
                "details": None,
                "limitations_caveat": (
                    "Analisis tutupan pohon dibatasi secara ketat untuk 5 provinsi Kalimantan Indonesia. "
                    "Wilayah lain belum tersedia dalam modul analisis ini."
                )
            }

    # Kategori tidak dikenal
    return {
        "assessment_code": "INSUFFICIENT_DATA",
        "category_result": "Belum dapat dinilai",
        "evidence_type": "unknown",
        "summary": "Kategori laporan tidak memiliki model penilaian bukti otomatis.",
        "matching_rule": "-",
        "details": None,
        "limitations_caveat": "Penilaian otomatis hanya tersedia untuk kebakaran dan perubahan tutupan pohon."
    }
