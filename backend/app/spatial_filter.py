"""
Modul Filter Geospasial Wilayah Indonesia (Point-in-Polygon).
Menggunakan Shapely 2.x STRtree untuk mengecek apakah titik anomali termal
berada di dalam poligon wilayah daratan Indonesia (EPSG:4326).
"""

import json
from pathlib import Path
from typing import List, Optional, Tuple
from shapely.geometry import Point, shape
from shapely.validation import make_valid
from shapely.strtree import STRtree

from .config import KALIMANTAN_HOTSPOT_MASK_PATH
from .models import HotspotRecord, RejectionStats


class IndonesiaSpatialFilter:
    """
    Filter spasial Point-in-Polygon menggunakan batas administratif terverifikasi.
    """

    def __init__(
        self,
        geojson_path: Path,
        kalimantan_hotspot_mask_path: Path = KALIMANTAN_HOTSPOT_MASK_PATH,
    ):
        self.geojson_path = Path(geojson_path)
        self.kalimantan_hotspot_mask_path = Path(kalimantan_hotspot_mask_path)
        self.geometries = []
        self.feature_props = []
        self.tree: Optional[STRtree] = None
        self.kalimantan_hotspot_geometries = []
        self.kalimantan_hotspot_feature_props = []
        self.kalimantan_hotspot_tree: Optional[STRtree] = None
        self._load_boundaries()
        self._load_kalimantan_hotspot_mask()

    def _load_boundaries(self) -> None:
        if not self.geojson_path.exists():
            raise FileNotFoundError(
                f"File batas wilayah tidak ditemukan di: {self.geojson_path}. "
                "Periksa dokumentasi data/boundaries/SOURCES.md untuk petunjuk sumber data."
            )

        with open(self.geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        features = data.get("features", [])
        if not features:
            raise ValueError(f"File {self.geojson_path} tidak memiliki fitur poligon.")

        for feat in features:
            raw_geom = shape(feat["geometry"])
            # Perbaiki self-intersection atau artefak topologi agar 100% valid
            valid_geom = make_valid(raw_geom)
            self.geometries.append(valid_geom)
            self.feature_props.append(feat.get("properties", {}))

        # Bangun spatial index STRtree (vektorisasi C)
        self.tree = STRtree(self.geometries)

    def _load_kalimantan_hotspot_mask(self) -> None:
        if not self.kalimantan_hotspot_mask_path.is_file():
            raise FileNotFoundError(
                f"Mask hotspot Kalimantan tidak ditemukan di: {self.kalimantan_hotspot_mask_path}."
            )
        with self.kalimantan_hotspot_mask_path.open("r", encoding="utf-8") as source_file:
            data = json.load(source_file)

        features = data.get("features", [])
        if data.get("type") != "FeatureCollection" or not features:
            raise ValueError(
                f"File {self.kalimantan_hotspot_mask_path} bukan FeatureCollection dengan fitur."
            )

        for feature in features:
            raw_geometry = shape(feature["geometry"])
            valid_geometry = make_valid(raw_geometry)
            if valid_geometry.is_empty:
                raise ValueError(
                    f"File {self.kalimantan_hotspot_mask_path} memiliki geometri kosong."
                )
            self.kalimantan_hotspot_geometries.append(valid_geometry)
            self.kalimantan_hotspot_feature_props.append(feature.get("properties", {}))

        self.kalimantan_hotspot_tree = STRtree(self.kalimantan_hotspot_geometries)

    def is_inside(self, lon: float, lat: float) -> Tuple[bool, Optional[str]]:
        """
        Memeriksa apakah koordinat (lon, lat) berada di dalam poligon Indonesia.
        Mengembalikan (True, nama_provinsi) jika di dalam, atau (False, None) jika di luar.
        """
        if self.tree is None:
            return False, None

        # Point dalam WGS84: (longitude, latitude)
        pt = Point(lon, lat)

        # Kueri calon geometri poligon yang melingkupi titik via bounding box index
        candidate_indices = self.tree.query(pt)

        for idx in candidate_indices:
            geom = self.geometries[idx]
            # Uji Point-in-Polygon eksak
            if geom.contains(pt) or geom.touches(pt):
                props = self.feature_props[idx]
                province_name = props.get("state") or props.get("NAME_1") or props.get("name")
                return True, province_name

        return False, None

    def is_inside_kalimantan(self, lon: float, lat: float) -> Tuple[bool, Optional[str]]:
        """
        Memeriksa apakah koordinat (lon, lat) berada di dalam 5 provinsi Kalimantan Indonesia:
        Kalimantan Barat, Kalimantan Tengah, Kalimantan Selatan, Kalimantan Timur, Kalimantan Utara.
        Wilayah Malaysia (Sarawak, Sabah) dan Brunei Darussalam secara tegas mengembalikan (False, None).
        """
        kalimantan_provinces = {
            "Kalimantan Barat",
            "Kalimantan Tengah",
            "Kalimantan Selatan",
            "Kalimantan Timur",
            "Kalimantan Utara",
        }
        inside, prov_name = self.is_inside(lon, lat)
        if inside and prov_name in kalimantan_provinces:
            return True, prov_name
        return False, None

    def is_inside_kalimantan_hotspot(self, lon: float, lat: float) -> Tuple[bool, Optional[str]]:
        """Use the detailed land mask and border-uncertainty exclusion for hotspot points."""
        if self.kalimantan_hotspot_tree is None:
            return False, None

        point = Point(lon, lat)
        for index in self.kalimantan_hotspot_tree.query(point):
            if self.kalimantan_hotspot_geometries[index].covers(point):
                province = self.kalimantan_hotspot_feature_props[index].get("province")
                return True, province
        return False, None

    def filter_records(
        self, records: List[HotspotRecord], stats: Optional[RejectionStats] = None
    ) -> Tuple[List[HotspotRecord], RejectionStats]:
        """
        Menyaring daftar rekaman dan membuang titik yang berada di luar Indonesia.
        Memperbarui objek RejectionStats.
        """
        if stats is None:
            stats = RejectionStats(
                total_initial_records=len(records),
                total_valid_records=0,
                total_rejected_records=0,
                reasons={}
            )

        filtered_records: List[HotspotRecord] = []

        for rec in records:
            inside, prov_name = self.is_inside(rec.longitude, rec.latitude)
            if inside:
                # Simpan konteks nama wilayah
                rec.province = prov_name
                filtered_records.append(rec)
            else:
                stats.total_rejected_records += 1
                stats.reasons["outside_indonesia_boundary"] = (
                    stats.reasons.get("outside_indonesia_boundary", 0) + 1
                )

        stats.total_valid_records = len(filtered_records)
        return filtered_records, stats

    def filter_kalimantan_records(
        self, records: List[HotspotRecord], stats: Optional[RejectionStats] = None
    ) -> Tuple[List[HotspotRecord], RejectionStats]:
        """
        Menyaring rekaman khusus untuk 5 provinsi Kalimantan Indonesia.
        Membuang titik yang berada di luar Kalimantan (termasuk Malaysia dan Brunei).
        """
        if stats is None:
            stats = RejectionStats(
                total_initial_records=len(records),
                total_valid_records=0,
                total_rejected_records=0,
                reasons={}
            )

        filtered_records: List[HotspotRecord] = []

        for rec in records:
            inside, prov_name = self.is_inside_kalimantan(rec.longitude, rec.latitude)
            if inside:
                rec.province = prov_name
                filtered_records.append(rec)
            else:
                stats.total_rejected_records += 1
                stats.reasons["outside_kalimantan_boundary"] = (
                    stats.reasons.get("outside_kalimantan_boundary", 0) + 1
                )

        stats.total_valid_records = len(filtered_records)
        return filtered_records, stats
