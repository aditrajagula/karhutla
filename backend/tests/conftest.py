"""
Fixtures Pengujian Sintetis (TEST ONLY).
PERINGATAN: Seluruh data dalam file ini adalah data buatan untuk pengujian unit.
DILARANG menggunakan data sintetis ini sebagai observasi nyata dalam demo atau analisis.
"""

import pytest


@pytest.fixture
def synthetic_csv_content() -> str:
    """
    Kumpulan rekaman sintetis berlabel TEST ONLY.
    Mencakup:
    - 3 Titik valid di dalam wilayah Indonesia (Riau, Palangkaraya, Pontianak)
    - 2 Titik duplikat (identik dengan titik valid)
    - 3 Titik di luar wilayah Indonesia (Kuala Lumpur, Laut Cina Selatan, Samudera Hindia)
    - 3 Titik invalid (lat > 90, string non-numerik, timestamp corrupt)
    - 1 Titik valid dengan nilai opsional kosong (FRP dan confidence null)
    """
    return """latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight
0.53,101.44,325.4,0.4,0.4,2026-10-12,0630,20,VIIRS,nominal,2.0NRT,295.1,12.4,D
-2.21,113.92,340.1,0.5,0.4,2026-10-12,0632,20,VIIRS,high,2.0NRT,301.2,25.8,D
-0.02,109.33,315.0,0.4,0.4,2026-10-13,0145,21,VIIRS,low,2.0NRT,290.0,8.1,N
0.53,101.44,325.4,0.4,0.4,2026-10-12,0630,20,VIIRS,nominal,2.0NRT,295.1,12.4,D
-2.21,113.92,340.1,0.5,0.4,2026-10-12,0632,20,VIIRS,high,2.0NRT,301.2,25.8,D
3.13,101.68,330.0,0.4,0.4,2026-10-12,0630,20,VIIRS,nominal,2.0NRT,296.0,14.0,D
8.00,108.00,320.0,0.4,0.4,2026-10-12,0630,20,VIIRS,nominal,2.0NRT,292.0,10.0,D
-15.00,95.00,310.0,0.4,0.4,2026-10-12,0630,20,VIIRS,nominal,2.0NRT,290.0,5.0,N
95.00,100.00,320.0,0.4,0.4,2026-10-12,0630,20,VIIRS,nominal,2.0NRT,292.0,10.0,D
abc,100.00,320.0,0.4,0.4,2026-10-12,0630,20,VIIRS,nominal,2.0NRT,292.0,10.0,D
-2.21,113.92,320.0,0.4,0.4,invalid-date,9999,20,VIIRS,nominal,2.0NRT,292.0,10.0,D
-6.20,106.81,318.5,0.4,0.4,2026-10-13,0415,20,VIIRS,,,2.0NRT,,NaN,D
"""
