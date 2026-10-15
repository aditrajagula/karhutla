"""
Modul Pembersihan Data dan Deduplikasi.
Mendeteksi baris duplikat berdasarkan aturan terdokumentasi dan mencatat metrik penolakan.
"""

from typing import Any, Dict, List, Set, Tuple
from .models import HotspotRecord, RejectionStats
from .validation import parse_and_validate_row


def clean_and_deduplicate(raw_rows: List[Dict[str, Any]]) -> Tuple[List[HotspotRecord], RejectionStats]:
    """
    Memvalidasi dan mendeduplikasi baris-baris data mentah.

    Aturan Deduplikasi:
    Sebuah rekaman dianggap duplikat jika memiliki kesamaan pada:
    (round(latitude, 5), round(longitude, 5), acq_date, acq_time, satellite).

    Mengembalikan:
        (daftar HotspotRecord unik yang lolos validasi, RejectionStats rincian audit)
    """
    stats = RejectionStats(
        total_initial_records=len(raw_rows),
        total_valid_records=0,
        total_rejected_records=0,
        reasons={}
    )

    valid_records: List[HotspotRecord] = []
    seen_keys: Set[Tuple[float, float, str, str, str]] = set()

    for row in raw_rows:
        record, reject_reason = parse_and_validate_row(row)

        if reject_reason is not None:
            stats.total_rejected_records += 1
            stats.reasons[reject_reason] = stats.reasons.get(reject_reason, 0) + 1
            continue

        # Cek duplikasi
        # Gunakan pembulatan koordinat 5 desimal (~1.1 meter) untuk konsistensi float
        sat_key = record.satellite or ""
        dedup_key = (
            round(record.latitude, 5),
            round(record.longitude, 5),
            record.acq_date,
            record.acq_time,
            sat_key
        )

        if dedup_key in seen_keys:
            stats.total_rejected_records += 1
            stats.reasons["duplicate_record"] = stats.reasons.get("duplicate_record", 0) + 1
            continue

        seen_keys.add(dedup_key)
        valid_records.append(record)

    stats.total_valid_records = len(valid_records)
    return valid_records, stats
