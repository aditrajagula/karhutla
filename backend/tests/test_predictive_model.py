"""
Unit test untuk modul prediksi machine learning dan klien cuaca Open-Meteo.
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
    # Menguji fallback jika base URL tidak valid / offline
    client = WeatherClient(base_url="https://invalid-non-existent-weather-url.test", timeout_seconds=0.5)
    res = client.fetch_weather_features(-1.84, 112.92)
    
    assert res["source"] == "CLIMATOLOGY_FALLBACK"
    assert res["t2m"] == KALIMANTAN_CLIMATE_DEFAULTS["t2m"]
    assert res["h2m"] == KALIMANTAN_CLIMATE_DEFAULTS["h2m"]
    assert res["w10"] == KALIMANTAN_CLIMATE_DEFAULTS["w10"]
    assert res["tp"] == KALIMANTAN_CLIMATE_DEFAULTS["tp"]


def test_prediction_service_inference():
    service = get_prediction_service()
    if not service.is_available():
        pytest.skip("Model artifacts not available in current test environment")

    # Uji titik Kalimantan Tengah
    res = service.predict_fire_risk(lat=-1.84, lon=112.92, province="Kalimantan Tengah")
    
    assert res["status"] == "SUCCESS"
    assert 0.0 <= res["risk_probability"] <= 1.0
    assert 0.0 <= res["risk_percentage"] <= 100.0
    assert res["risk_level"] in ("RENDAH", "SEDANG", "TINGGI")
    assert res["risk_color"] in ("GREEN", "YELLOW", "RED")
    assert len(res["primary_drivers"]) > 0
    assert "feature" in res["primary_drivers"][0]
    assert "impact" in res["primary_drivers"][0]
