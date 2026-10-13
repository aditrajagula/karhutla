"""
Pengujian Unit untuk Deduplikasi dan Audit Penolakan Rekaman.
"""

from app.cleaner import clean_and_deduplicate


def test_clean_and_deduplicate_with_duplicates():
    """Menguji eliminasi baris duplikat dan pencatatan alasan penolakan."""
    raw_data = [
        # Baris unik A
        {"latitude": "0.5", "longitude": "101.5", "acq_date": "2026-10-13", "acq_time": "0400", "satellite": "20"},
        # Baris duplikat persis dari A
        {"latitude": "0.5", "longitude": "101.5", "acq_date": "2026-10-13", "acq_time": "0400", "satellite": "20"},
        # Baris unik B
        {"latitude": "-2.0", "longitude": "113.0", "acq_date": "2026-10-13", "acq_time": "0405", "satellite": "20"},
        # Baris invalid (koordinat rusak)
        {"latitude": "invalid", "longitude": "113.0", "acq_date": "2026-10-13", "acq_time": "0405", "satellite": "20"}
    ]

    valid_records, stats = clean_and_deduplicate(raw_data)

    assert len(valid_records) == 2
    assert stats.total_initial_records == 4
    assert stats.total_valid_records == 2
    assert stats.total_rejected_records == 2
    assert stats.reasons.get("duplicate_record") == 1
    assert stats.reasons.get("invalid_coordinates") == 1


def test_deduplication_different_satellites_preserved():
    """
    Titik dengan koordinat dan waktu persis sama, TETAPI berasal dari satelit berbeda
    (misal NOAA-20 dan NOAA-21) WAJIB DIPERTAHANKAN sebagai observasi terpisah.
    """
    raw_data = [
        {"latitude": "0.5", "longitude": "101.5", "acq_date": "2026-10-13", "acq_time": "0400", "satellite": "20"},
        {"latitude": "0.5", "longitude": "101.5", "acq_date": "2026-10-13", "acq_time": "0400", "satellite": "21"},
    ]
    valid_records, stats = clean_and_deduplicate(raw_data)
    assert len(valid_records) == 2
    assert stats.total_valid_records == 2
    assert stats.total_rejected_records == 0


def test_deduplication_different_times_preserved():
    """Titik dengan koordinat sama tetapi waktu observasi berbeda tidak boleh digabung."""
    raw_data = [
        {"latitude": "0.5", "longitude": "101.5", "acq_date": "2026-10-13", "acq_time": "0400", "satellite": "20"},
        {"latitude": "0.5", "longitude": "101.5", "acq_date": "2026-10-13", "acq_time": "0415", "satellite": "20"},
        {"latitude": "0.5", "longitude": "101.5", "acq_date": "2026-10-14", "acq_time": "0400", "satellite": "20"},
    ]
    valid_records, stats = clean_and_deduplicate(raw_data)
    assert len(valid_records) == 3
    assert stats.total_valid_records == 3
    assert stats.total_rejected_records == 0


def test_deduplication_distinct_close_coordinates():
    """Titik dengan beda koordinat > 1 meter (perbedaan desimal ke-5) tetap dianggap unik."""
    raw_data = [
        {"latitude": "0.53000", "longitude": "101.44000", "acq_date": "2026-10-13", "acq_time": "0400", "satellite": "20"},
        {"latitude": "0.53005", "longitude": "101.44000", "acq_date": "2026-10-13", "acq_time": "0400", "satellite": "20"},
    ]
    valid_records, stats = clean_and_deduplicate(raw_data)
    assert len(valid_records) == 2
    assert stats.total_valid_records == 2
    assert stats.total_rejected_records == 0

