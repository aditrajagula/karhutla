"""
Klien NASA FIRMS Area API.
Mengimplementasikan pemanggilan aman dengan chunking rentang hari (maksimal 5 hari per panggilan),
penanganan error kuota/jaringan, serta deteksi respons error teks.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
import httpx

from .snapshot_manager import parse_csv_content

FIRMS_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


class FirmsAPIError(Exception):
    """Pengecualian khusus untuk kesalahan panggilan NASA FIRMS API."""
    pass


class FirmsClient:
    """Klien untuk mengambil data anomali termal dari NASA FIRMS Area API."""

    def __init__(
        self,
        map_key: str,
        timeout_seconds: int = 20,
        default_source: str = "VIIRS_NOAA20_NRT",
        bbox: str = "95.0,-11.0,141.5,6.0"
    ):
        self.map_key = map_key.strip()
        self.timeout_seconds = timeout_seconds
        self.default_source = default_source
        self.bbox = bbox

    def _fetch_single_window(
        self, source: str, day_range: int, date_str: Optional[str] = None
    ) -> str:
        """
        Mengambil satu jendela data (1 s.d. 5 hari).
        URL format:
        Tanpa tanggal: .../api/area/csv/{map_key}/{source}/{bbox}/{day_range}
        Dengan tanggal: .../api/area/csv/{map_key}/{source}/{bbox}/{day_range}/{date_str}
        """
        if not self.map_key:
            raise FirmsAPIError(
                "FIRMS_MAP_KEY belum dikonfigurasi. Kunci wajib diatur di .env (hanya pada backend)."
            )

        if not (1 <= day_range <= 5):
            raise ValueError("Kueri NASA FIRMS Area API dibatasi 1 hingga 5 hari per panggilan.")

        url = f"{FIRMS_BASE_URL}/{self.map_key}/{source}/{self.bbox}/{day_range}"
        if date_str:
            url += f"/{date_str}"

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url)
        except httpx.RequestError as exc:
            raise FirmsAPIError(f"Koneksi jaringan ke NASA FIRMS gagal: {str(exc)}") from exc

        if response.status_code in (401, 403):
            raise FirmsAPIError(
                f"Akses ditolak oleh NASA FIRMS (HTTP {response.status_code}): "
                "Periksa apakah FIRMS_MAP_KEY valid dan aktif di environment backend."
            )
        elif response.status_code == 429:
            raise FirmsAPIError(
                "Batas transaksi/kuota permintaan NASA FIRMS terlampaui (HTTP 429). "
                "Tunggu beberapa saat sebelum mencoba kembali."
            )
        elif response.status_code >= 500:
            raise FirmsAPIError(
                f"Layanan server NASA FIRMS sedang mengalami gangguan (HTTP {response.status_code}): "
                f"{response.text[:150]}"
            )
        elif response.status_code != 200:
            raise FirmsAPIError(
                f"NASA FIRMS API mengembalikan status HTTP {response.status_code}: {response.text[:200]}"
            )

        content = response.text.strip()

        # Deteksi respons halaman error HTML (misal gateway timeout / cloudflare block)
        content_lower = content.lower()
        if content_lower.startswith("<!doctype") or content_lower.startswith("<html"):
            raise FirmsAPIError(
                "NASA FIRMS mengembalikan respons halaman web HTML (gateway/server error), bukan format data CSV."
            )

        # Deteksi pesan error teks dari FIRMS (meskipun berstatus HTTP 200)
        error_indicators = [
            ("invalid map_key", "FIRMS_MAP_KEY tidak valid menurut server NASA."),
            ("transaction limit", "Batas transaksi/kuota harian NASA FIRMS terlampaui."),
            ("bad request", "Permintaan ditolak oleh NASA FIRMS (bad request)."),
            ("invalid area", "Parameter area koordinat tidak valid untuk NASA FIRMS."),
            ("invalid date", "Parameter tanggal kueri tidak valid untuk NASA FIRMS."),
            ("error:", f"NASA FIRMS melaporkan kesalahan: {content[:100]}"),
        ]
        for indicator, error_msg in error_indicators:
            if indicator in content_lower:
                raise FirmsAPIError(error_msg)

        # Validasi struktur minimal header CSV
        if content:
            first_line = content.splitlines()[0].lower()
            if "latitude" not in first_line or "longitude" not in first_line:
                raise FirmsAPIError(
                    f"Format respons NASA FIRMS tidak memiliki header kolom standar ('latitude', 'longitude'): {content[:100]}"
                )

        return content

    def fetch_area_hotspots(
        self,
        source: Optional[str] = None,
        total_days: int = 7,
        end_date: Optional[str] = None
    ) -> str:
        """
        Mengambil data hotspot dengan memecah (chunking) rentang hari yang lebih dari 5 hari.
        Contoh: total_days=7 dipecah menjadi chunk 5 hari dan 2 hari.
        """
        active_source = source or self.default_source

        if total_days <= 5:
            start_param = None
            if end_date:
                ref_dt = datetime.strptime(end_date, "%Y-%m-%d")
                start_param = (ref_dt - timedelta(days=total_days - 1)).strftime("%Y-%m-%d")
            return self._fetch_single_window(active_source, total_days, start_param)

        # Pemecahan jendela waktu (chunking): parameter tanggal FIRMS adalah START DATE
        if end_date:
            ref_dt = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            ref_dt = datetime.now(timezone.utc)

        chunks_data: List[str] = []
        days_remaining = total_days
        current_end = ref_dt
        is_first_chunk = True

        while days_remaining > 0:
            window_days = min(5, days_remaining)
            if is_first_chunk and not end_date:
                date_param = None
            else:
                start_dt = current_end - timedelta(days=window_days - 1)
                date_param = start_dt.strftime("%Y-%m-%d")

            csv_part = self._fetch_single_window(active_source, window_days, date_param)
            chunks_data.append(csv_part)

            days_remaining -= window_days
            current_end = current_end - timedelta(days=window_days)
            is_first_chunk = False

        # Gabungkan hasil CSV dan buang baris header duplikat
        return self._merge_csv_chunks(chunks_data)

    def _merge_csv_chunks(self, chunks: List[str]) -> str:
        """Menggabungkan beberapa respons CSV menjadi satu CSV dengan header tunggal."""
        if not chunks:
            return ""

        merged_rows = []
        header = None

        for chunk in chunks:
            rows = parse_csv_content(chunk)
            if not rows:
                continue
            if header is None:
                header = list(rows[0].keys())
            merged_rows.extend(rows)

        if not header:
            return chunks[0] if chunks else ""

        # Rekonstruksi CSV
        import csv
        import io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=header)
        writer.writeheader()
        writer.writerows(merged_rows)
        return output.getvalue()
