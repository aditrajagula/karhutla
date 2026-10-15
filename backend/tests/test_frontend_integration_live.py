"""
Pengujian Integrasi Komprehensif Frontend (Vite) dan Backend (FastAPI).
Memverifikasi:
1. Vite dev server berjalan dan menyajikan antarmuka React.
2. CORS Headers mengizinkan origin Vite (http://127.0.0.1:5173).
3. Endpoint /api/v1/hotspots mengembalikan GeoJSON FeatureCollection terfilter.
4. Endpoint /api/v1/provenance mengembalikan status LIVE_API / snapshot.
5. Endpoint /api/v1/context-layers mengembalikan informasi layer konteks.
"""

import httpx

def test_frontend_backend_integration():
    origin = "http://127.0.0.1:5173"

    # 1. Vite Dev Server (diuji jika dev server aktif di port 5173)
    try:
        r_vite = httpx.get("http://127.0.0.1:5173/", timeout=2.0)
        assert r_vite.status_code == 200
        assert 'id="root"' in r_vite.text
        assert '/src/main.tsx' in r_vite.text
    except (httpx.ConnectError, httpx.TimeoutException):
        pass

    # 2. CORS Preflight & Backend Live Check
    try:
        r_cors = httpx.options(
            "http://127.0.0.1:8000/api/v1/hotspots",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET"
            },
            timeout=2.0
        )
    except (httpx.ConnectError, httpx.TimeoutException):
        import pytest
        pytest.skip("Backend live server (port 8000) tidak aktif, pengujian live server di-skip.")

    assert r_cors.status_code == 200
    assert r_cors.headers.get("access-control-allow-origin") == origin

    # 3. Hotspots API via Frontend Origin
    r_hotspots = httpx.get(
        "http://127.0.0.1:8000/api/v1/hotspots?days=2",
        headers={"Origin": origin},
        timeout=30.0
    )
    assert r_hotspots.status_code == 200
    assert r_hotspots.headers.get("access-control-allow-origin") == origin
    h_data = r_hotspots.json()
    assert h_data["type"] == "FeatureCollection"
    features = h_data.get("features", [])
    assert len(features) > 0

    first_feat = features[0]
    coords = first_feat["geometry"]["coordinates"]
    # RFC 7946: [lon, lat]
    lon, lat = coords
    assert 95.0 <= lon <= 141.5
    assert -11.0 <= lat <= 6.0
    props = first_feat["properties"]
    assert "province" in props
    assert "acq_date" in props
    assert "acq_time" in props
    assert "satellite" in props

    # 4. Provenance API
    r_prov = httpx.get(
        "http://127.0.0.1:8000/api/v1/provenance",
        headers={"Origin": origin},
        timeout=10.0
    )
    assert r_prov.status_code == 200
    p_data = r_prov.json()
    assert p_data["status"] in ("LIVE_API", "FALLBACK_LOCAL_SNAPSHOT")
    assert "audit_stats" in p_data

    # 5. Context Layers API
    r_ctx = httpx.get(
        "http://127.0.0.1:8000/api/v1/context-layers",
        headers={"Origin": origin},
        timeout=10.0
    )
    assert r_ctx.status_code == 200
    c_data = r_ctx.json()
    assert c_data["forest_layer"]["available"] is False
    assert c_data["peatland_layer"]["available"] is False
    assert c_data["boundary_layer"]["available"] is True
    assert c_data["boundary_layer"]["feature_count"] == 5

    # 6. Citizen Reports API via Frontend Origin
    r_rep = httpx.get(
        "http://127.0.0.1:8000/api/v1/reports",
        headers={"Origin": origin},
        timeout=10.0
    )
    assert r_rep.status_code == 200
    assert r_rep.headers.get("access-control-allow-origin") == origin
    rep_data = r_rep.json()
    assert "records" in rep_data
    assert "features" in rep_data
