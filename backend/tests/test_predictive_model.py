"""
Unit test untuk modul inferensi risiko karhutla, klien cuaca Open-Meteo,
dan kontrak transparansi kualitas data (tanpa klaim performa semu).
"""

try:
    import pytest
except ImportError:
    class MockPytest:
        @staticmethod
        def skip(reason=""):
            pass
    pytest = MockPytest()

from app.weather_client import WeatherClient, KALIMANTAN_CLIMATE_DEFAULTS
from app.prediction_service import FireRiskPredictionService, get_prediction_service


def test_weather_client_query_builder():
    """Menguji bahwa query builder mematuhi batas resmi Open-Meteo API (past_days <= 92)."""
    client = WeatherClient()
    params = client.build_query_params(lat=-1.8423, lon=112.9231)
    
    assert params["latitude"] == -1.8423
    assert params["longitude"] == 112.9231
    assert params["wind_speed_unit"] == "ms"
    assert params["past_days"] == 92
    assert params["forecast_days"] == 1
    assert "temperature_2m" in params["current"]
    assert "precipitation_sum" in params["daily"]


def test_weather_client_fallback_resilience():
    """Menguji bahwa fallback klimatologi menggunakan mean pelatihan netral saat API offline."""
    client = WeatherClient(base_url="https://invalid-non-existent-weather-url.test", timeout_seconds=0.5)
    res = client.fetch_weather_features(-1.84, 112.92)
    
    assert res["source"] == "CLIMATOLOGY_FALLBACK"
    assert res["t2m"] == KALIMANTAN_CLIMATE_DEFAULTS["t2m"]
    assert res["h2m"] == KALIMANTAN_CLIMATE_DEFAULTS["h2m"]
    assert res["w10"] == KALIMANTAN_CLIMATE_DEFAULTS["w10"]
    assert res["tp"] == KALIMANTAN_CLIMATE_DEFAULTS["tp"]
    assert "precipitation_metadata" in res
    assert res["precipitation_metadata"]["calendar_aligned"] is False


def test_precipitation_lag_order_and_units():
    """Menguji bahwa curah hujan berskala bulanan (bukan instan per jam) dan metadata lag dicatat."""
    client = WeatherClient()
    features = client.fetch_weather_features(-1.84, 112.92)
    
    # Satuan mm: tp bulanan normal di wilayah tropis berada di atas 0 mm
    assert features["tp"] >= 0.0
    assert "precipitation_metadata" in features
    meta = features["precipitation_metadata"]
    assert "measured_lags" in meta
    assert "unavailable_lags" in meta
    # Lags 4 & 5 harus dicatat sebagai unavailable jika rentang API forecast hanya 92 hari
    assert "tp_4" in meta["unavailable_lags"]
    assert "tp_5" in meta["unavailable_lags"]


def test_prediction_metadata_has_no_hardcoded_auc():
    """Memverifikasi bahwa payload API SAMA SEKALI TIDAK memuat klaim performa statis 'roc_auc_evaluation: 0.81'."""
    service = get_prediction_service()
    if not service.is_available():
        pytest.skip("Model artifacts not available in current test environment")

    # Gunakan koordinat dalam chip raster demo Kalimantan Tengah
    res = service.predict_fire_risk(lat=-2.14, lon=113.84, province="Kalimantan Tengah")
    assert res["status"] == "SUCCESS"
    assert "model_metadata" in res
    metadata = res["model_metadata"]
    
    # Klaim statis 0.81 harus SUDAH DIHAPUS dari respon publik
    assert "roc_auc_evaluation" not in metadata
    assert metadata.get("operational_readiness") == "PROTOTIPE_EKSPERIMENTAL"
    assert "target_type" in metadata


def test_prediction_service_reports_data_quality():
    """Menguji bahwa respon inferensi secara eksplisit melaporkan status kualitas data parsial tanpa klaim Aman."""
    service = get_prediction_service()
    if not service.is_available():
        pytest.skip("Model artifacts not available in current test environment")

    res = service.predict_fire_risk(lat=-2.14, lon=113.84, province="Kalimantan Tengah")
    assert res["status"] == "SUCCESS"
    assert "data_quality" in res
    dq = res["data_quality"]
    assert dq["status"] == "PARTIAL"
    assert dq["imputation_method"] == "TECHNICAL_NEUTRAL_MEAN"
    assert len(dq["missing_or_imputed_features"]) > 0
    # Pastikan label risiko tidak mengklaim lokasi 'Aman' secara absolut
    assert "Aman" not in res.get("risk_label", "")
    assert res.get("risk_label") in ("Rendah (Data Terbatas)", "Sedang", "Tinggi")


def test_driver_contributions_use_local_logit():
    """Menguji bahwa faktor penentu dihitung berdasarkan kontribusi lokal logit (beta * z), bukan koefisien statis."""
    service = get_prediction_service()
    if not service.is_available():
        pytest.skip("Model artifacts not available in current test environment")

    res = service.predict_fire_risk(lat=-2.14, lon=113.84, province="Kalimantan Tengah")
    assert len(res["primary_drivers"]) > 0
    top_driver = res["primary_drivers"][0]
    
    assert "contribution_to_logit" in top_driver
    assert "z_score" in top_driver
    assert "impact" in top_driver
    # Driver teratas harus memiliki nilai mutlak kontribusi logit terbesar
    first_contrib = abs(top_driver["contribution_to_logit"])
    for d in res["primary_drivers"][1:]:
        assert first_contrib >= abs(d["contribution_to_logit"])


def test_prediction_service_inference():
    """Menguji inferensi dasar model dan rentang probabilitas yang valid."""
    service = get_prediction_service()
    if not service.is_available():
        pytest.skip("Model artifacts not available in current test environment")

    res = service.predict_fire_risk(lat=-2.14, lon=113.84, province="Kalimantan Tengah")
    
    assert res["status"] == "SUCCESS"
    assert 0.0 <= res["risk_probability"] <= 1.0
    assert 0.0 <= res["risk_percentage"] <= 100.0
    assert res["risk_level"] in ("RENDAH", "SEDANG", "TINGGI")
    assert res["risk_color"] in ("GREEN", "YELLOW", "RED")
    assert res["risk_label"] in ("Rendah (Data Terbatas)", "Sedang", "Tinggi")


def test_prediction_service_with_out_of_bounds_coords():
    """Menguji bahwa koordinat di luar batas spasial Kalimantan ditolak dengan status OUT_OF_SCOPE."""
    service = get_prediction_service()
    if not service.is_available():
        pytest.skip("Model artifacts not available in current test environment")

    # Uji titik Jakarta (di luar 5 provinsi Kalimantan)
    res = service.predict_fire_risk(lat=-6.2088, lon=106.8456)
    assert res["status"] == "OUT_OF_SCOPE"
    assert res["risk_level"] == "TIDAK_DAPAT_DINILAI"
    assert res["risk_probability"] is None
    assert res["risk_percentage"] is None
    assert res["data_quality"]["status"] == "OUT_OF_SCOPE"
    assert "Aman" not in res.get("risk_label", "")


def test_prediction_service_with_insufficient_data():
    """Menguji bahwa titik tanpa data raster kanopi dilaporkan sebagai INSUFFICIENT_DATA (bukan diasumsikan aman)."""
    service = get_prediction_service()
    if not service.is_available():
        pytest.skip("Model artifacts not available in current test environment")

    # Titik di Kalimantan yang berada di luar chip raster demo
    res = service.predict_fire_risk(lat=-1.84, lon=112.92, province="Kalimantan Tengah")
    assert res["status"] == "INSUFFICIENT_DATA"
    assert res["risk_level"] == "TIDAK_DAPAT_DINILAI"
    assert res["risk_probability"] is None
    assert res["risk_percentage"] is None
    assert res["data_quality"]["status"] == "INSUFFICIENT_DATA"
    assert "Aman" not in res.get("risk_label", "")


def test_predict_fire_risk_api_endpoint():
    """Menguji endpoint HTTP GET /api/v1/predict/fire-risk untuk berbagai kondisi cakupan spasial."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    
    # 1. Titik di dalam chip raster demo Kalimantan
    resp_valid = client.get("/api/v1/predict/fire-risk", params={"latitude": -2.14, "longitude": 113.84})
    assert resp_valid.status_code == 200
    data_valid = resp_valid.json()
    assert data_valid["status"] == "SUCCESS"
    assert "risk_level" in data_valid
    assert "risk_percentage" in data_valid
    assert "primary_drivers" in data_valid
    assert "data_quality" in data_valid
    assert "Aman" not in data_valid.get("risk_label", "")
    assert "roc_auc_evaluation" not in data_valid.get("model_metadata", {})

    # 2. Titik di luar cakupan wilayah (Jakarta)
    resp_oob = client.get("/api/v1/predict/fire-risk", params={"latitude": -6.2088, "longitude": 106.8456})
    assert resp_oob.status_code == 200
    data_oob = resp_oob.json()
    assert data_oob["status"] == "OUT_OF_SCOPE"
    assert data_oob["risk_probability"] is None
    assert data_oob["risk_level"] == "TIDAK_DAPAT_DINILAI"
