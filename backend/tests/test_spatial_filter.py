"""
Pengujian Unit untuk Filter Geospasial Point-in-Polygon Indonesia.
"""

from pathlib import Path
from app.config import BOUNDARIES_PATH
from app.models import HotspotRecord
from app.spatial_filter import IndonesiaSpatialFilter


def test_spatial_filter_indonesia_points():
    """Menguji bahwa titik-titik di dalam Indonesia terdeteksi valid dan konteks provinsinya terambil."""
    spatial_filter = IndonesiaSpatialFilter(BOUNDARIES_PATH)

    # Titik Riau (Sumatera)
    inside_riau, prov_riau = spatial_filter.is_inside(101.44, 0.53)
    assert inside_riau is True
    assert prov_riau is not None
    assert "Riau" in prov_riau

    # Titik Palangkaraya (Kalimantan Tengah)
    inside_kalteng, prov_kalteng = spatial_filter.is_inside(113.92, -2.21)
    assert inside_kalteng is True
    assert prov_kalteng is not None
    assert "Kalimantan Tengah" in prov_kalteng

    # Titik Pontianak (Kalimantan Barat)
    inside_kalbar, prov_kalbar = spatial_filter.is_inside(109.33, -0.02)
    assert inside_kalbar is True
    assert prov_kalbar is not None
    assert "Kalimantan Barat" in prov_kalbar


def test_spatial_filter_outer_islands():
    """Menguji pulau-pulau terluar dan ujung kepulauan Indonesia."""
    spatial_filter = IndonesiaSpatialFilter(BOUNDARIES_PATH)

    # Ujung Barat: Sabang / Pulau Weh (Aceh)
    inside_sabang, prov_sabang = spatial_filter.is_inside(95.31, 5.89)
    assert inside_sabang is True
    assert "Aceh" in prov_sabang

    # Batam (Kepulauan Riau)
    inside_batam, prov_batam = spatial_filter.is_inside(104.03, 1.13)
    assert inside_batam is True
    assert "Kepulauan Riau" in prov_batam

    # Ujung Selatan: Rote Ndao (Nusa Tenggara Timur)
    inside_rote, prov_rote = spatial_filter.is_inside(123.05, -10.74)
    assert inside_rote is True
    assert "Nusa Tenggara Timur" in prov_rote

    # Ujung Timur: Merauke (Papua)
    inside_merauke, prov_merauke = spatial_filter.is_inside(140.40, -8.49)
    assert inside_merauke is True
    assert "Papua" in prov_merauke

    # Bali
    inside_bali, prov_bali = spatial_filter.is_inside(115.18, -8.40)
    assert inside_bali is True
    assert "Bali" in prov_bali



def test_spatial_filter_outside_points():
    """Menguji bahwa titik-titik di luar Indonesia (negara tetangga & laut lepas) ditolak."""
    spatial_filter = IndonesiaSpatialFilter(BOUNDARIES_PATH)

    # Kuala Lumpur (Malaysia)
    inside_my, _ = spatial_filter.is_inside(101.68, 3.13)
    assert inside_my is False

    # Laut Cina Selatan (Utara Natuna)
    inside_sea, _ = spatial_filter.is_inside(108.00, 8.00)
    assert inside_sea is False

    # Samudera Hindia (Selatan Jawa)
    inside_ocean, _ = spatial_filter.is_inside(95.00, -15.00)
    assert inside_ocean is False


def test_filter_records_workflow():
    """Menguji penyaringan daftar HotspotRecord dan pencatatan audit penolakan."""
    spatial_filter = IndonesiaSpatialFilter(BOUNDARIES_PATH)

    records = [
        # Titik dalam Indonesia (Riau)
        HotspotRecord(
            latitude=0.53, longitude=101.44, acq_date="2026-10-13",
            acq_time="0400", observation_time_utc="2026-10-13T04:00:00Z"
        ),
        # Titik luar Indonesia (Malaysia)
        HotspotRecord(
            latitude=3.13, longitude=101.68, acq_date="2026-10-13",
            acq_time="0400", observation_time_utc="2026-10-13T04:00:00Z"
        )
    ]

    filtered, stats = spatial_filter.filter_records(records)

    assert len(filtered) == 1
    assert filtered[0].latitude == 0.53
    assert filtered[0].province is not None
    assert stats.total_valid_records == 1
    assert stats.total_rejected_records == 1
    assert stats.reasons.get("outside_indonesia_boundary") == 1


def test_spatial_filter_exact_boundary_touches():
    """
    Menguji titik yang terletak TEPAT pada garis batas luar poligon (verteks batas).
    Berdasarkan standar spasial OGC/DE-9IM:
    - geom.contains(pt) = False (karena titik berada di boundary, bukan interior)
    - geom.touches(pt) = True (karena bersentuhan dengan boundary)
    Implementasi is_inside() WAJIB mengembalikan True dan nama provinsi yang sesuai.
    """
    spatial_filter = IndonesiaSpatialFilter(BOUNDARIES_PATH)

    # Ambil verteks batas nyata dari poligon Bali
    bali_geom = [g for i, g in enumerate(spatial_filter.geometries) if spatial_filter.feature_props[i].get('state') == 'Bali'][0]
    poly0 = bali_geom.geoms[0] if hasattr(bali_geom, 'geoms') else bali_geom
    bx, by = poly0.exterior.coords[0]

    # Uji logika OGC
    from shapely.geometry import Point
    pt = Point(bx, by)
    assert bali_geom.contains(pt) is False
    assert bali_geom.touches(pt) is True

    # Uji method is_inside
    inside, prov = spatial_filter.is_inside(bx, by)
    assert inside is True
    assert prov == "Bali"


def test_spatial_filter_cross_border_pairs():
    """
    Menguji pasangan titik perbatasan darat dan laut internasional:
    - Titik di sisi Indonesia lolos dan provinsinya terisi.
    - Titik di sisi negara tetangga ditolak.
    """
    spatial_filter = IndonesiaSpatialFilter(BOUNDARIES_PATH)

    # Perbatasan Kalbar - Sarawak
    in_entikong, prov_entikong = spatial_filter.is_inside(110.35, 0.99)
    assert in_entikong is True
    assert "Kalimantan Barat" in prov_entikong

    in_tebedu, prov_tebedu = spatial_filter.is_inside(110.35, 1.03) # Sarawak, Malaysia
    assert in_tebedu is False
    assert prov_tebedu is None

    # Batas Timur Papua - PNG (garis bujur 141 BT)
    in_wutung, _ = spatial_filter.is_inside(141.03, -2.61) # Sandaun, PNG
    assert in_wutung is False

    # Tetangga regional lain
    in_sg, _ = spatial_filter.is_inside(103.81, 1.35) # Singapura
    assert in_sg is False

    in_darwin, _ = spatial_filter.is_inside(130.84, -12.46) # Darwin, Australia
    assert in_darwin is False

