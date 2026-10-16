"""Tes alert Telegram: pencocokan radius, dedupe, multi-lokasi, perintah bot (tanpa jaringan)."""

import uuid

import pytest

from app import alerts_service as al


def _feat(fid, lat, lon, level="TINGGI", pct=80, name="Titik"):
    return {
        "type": "Feature",
        "properties": {
            "id": fid,
            "latitude": lat,
            "longitude": lon,
            "risk_level": level,
            "risk_percentage": pct,
            "location_name": name,
        },
    }


PALANGKA = (-2.2085, 113.9167)
PONTIANAK = (-0.0263, 109.3425)


@pytest.fixture
def chat():
    chat_id = f"test_{uuid.uuid4().hex[:8]}"
    yield chat_id
    al.delete_all_for_chat(chat_id)


@pytest.fixture
def sent(monkeypatch):
    messages = []

    def fake_send(chat_id, text):
        messages.append((chat_id, text))
        return 200

    monkeypatch.setattr(al, "send_message", fake_send)
    return messages


def _subscribe(chat_id, coords, radius=50, label="Lokasi"):
    token = al.create_pending_subscription(coords[0], coords[1], radius, label)
    status, _ = al.activate_subscription(token, chat_id)
    assert status == "ok"
    return token


def test_haversine_known_distance():
    # Pontianak - Palangka Raya sekitar 565 km
    d = al.haversine_km(*PONTIANAK, *PALANGKA)
    assert 540 < d < 590


def test_alert_sent_only_for_hotspot_inside_radius(chat, sent):
    _subscribe(chat, PALANGKA, radius=50)
    feats = [
        _feat("near", -2.25, 113.95, name="Dekat"),
        _feat("far", *PONTIANAK, name="Jauh"),
    ]
    summary = al.run_alert_cycle(features=feats, only_chat_id=chat)
    assert summary["chats_notified"] == 1
    assert "Dekat" in sent[0][1] and "Jauh" not in sent[0][1]


def test_sedang_is_alerted_but_rendah_is_not(chat, sent):
    _subscribe(chat, PALANGKA)
    al.run_alert_cycle(features=[_feat("a", -2.25, 113.95, level="RENDAH")], only_chat_id=chat)
    assert sent == []
    al.run_alert_cycle(features=[_feat("b", -2.25, 113.95, level="SEDANG", name="Sedang")], only_chat_id=chat)
    assert len(sent) == 1 and "SEDANG" in sent[0][1]


def test_dedupe_same_day_and_force(chat, sent):
    _subscribe(chat, PALANGKA)
    feats = [_feat("h1", -2.25, 113.95)]
    al.run_alert_cycle(features=feats, only_chat_id=chat)
    al.run_alert_cycle(features=feats, only_chat_id=chat)
    assert len(sent) == 1
    al.run_alert_cycle(features=feats, only_chat_id=chat, force=True)
    assert len(sent) == 2


def test_new_day_hotspot_id_alerts_again(chat, sent):
    _subscribe(chat, PALANGKA)
    al.run_alert_cycle(features=[_feat("h_2026-10-16", -2.25, 113.95)], only_chat_id=chat)
    al.run_alert_cycle(features=[_feat("h_2026-10-17", -2.25, 113.95)], only_chat_id=chat)
    assert len(sent) == 2


def test_dry_run_sends_nothing_and_does_not_log(chat, sent):
    _subscribe(chat, PALANGKA)
    feats = [_feat("h1", -2.25, 113.95)]
    summary = al.run_alert_cycle(features=feats, only_chat_id=chat, dry_run=True)
    assert sent == [] and len(summary["messages_dry_run"]) == 1
    al.run_alert_cycle(features=feats, only_chat_id=chat)
    assert len(sent) == 1


def test_multi_location_single_message_grouped(chat, sent):
    _subscribe(chat, PALANGKA, label="Rumah")
    _subscribe(chat, PONTIANAK, label="Kantor")
    feats = [_feat("a", -2.25, 113.95, name="A"), _feat("b", -0.05, 109.35, name="B")]
    al.run_alert_cycle(features=feats, only_chat_id=chat)
    assert len(sent) == 1
    text = sent[0][1]
    assert "Rumah" in text and "Kantor" in text and "A -" in text and "B -" in text


def test_message_limits_to_five_hotspots(chat, sent):
    _subscribe(chat, PALANGKA, radius=100)
    feats = [_feat(f"h{i}", -2.2 - i * 0.01, 113.9, pct=90 - i) for i in range(8)]
    al.run_alert_cycle(features=feats, only_chat_id=chat)
    assert "dan 3 titik lainnya" in sent[0][1]
    assert "bukan titik api".lower() in sent[0][1].lower()


def test_location_limit(chat, monkeypatch):
    monkeypatch.setattr(al, "ALERTS_MAX_LOCATIONS", 2)
    _subscribe(chat, PALANGKA)
    _subscribe(chat, PONTIANAK)
    token = al.create_pending_subscription(0.5, 110.0, 50, "Ketiga")
    status, _ = al.activate_subscription(token, chat)
    assert status == "limit"


def test_token_invalid_and_single_use(chat):
    assert al.activate_subscription("tidak-ada", chat)[0] == "invalid"
    token = _subscribe(chat, PALANGKA)
    assert al.activate_subscription(token, chat)[0] == "used"


def test_blocked_chat_is_removed(chat, monkeypatch):
    _subscribe(chat, PALANGKA)
    monkeypatch.setattr(al, "send_message", lambda c, t: 403)
    summary = al.run_alert_cycle(features=[_feat("h", -2.25, 113.95)], only_chat_id=chat)
    assert summary["blocked_chats"] == 1
    assert al.list_subscriptions(chat) == []


def test_failed_send_does_not_mark_as_sent(chat, monkeypatch):
    _subscribe(chat, PALANGKA)
    feats = [_feat("h", -2.25, 113.95)]
    monkeypatch.setattr(al, "send_message", lambda c, t: 500)
    al.run_alert_cycle(features=feats, only_chat_id=chat)
    messages = []
    monkeypatch.setattr(al, "send_message", lambda c, t: messages.append(t) or 200)
    al.run_alert_cycle(features=feats, only_chat_id=chat)
    assert len(messages) == 1


def test_bot_commands(chat):
    token = al.create_pending_subscription(*PALANGKA, 50, "Rumah")
    assert "Alert aktif" in al.handle_command(chat, f"/start {token}")
    assert "Rumah" in al.handle_command(chat, "/lokasi")
    assert "75" in al.handle_command(chat, "/radius 1 75")
    assert "radius 75 km" in al.handle_command(chat, "/lokasi")
    assert "Format" in al.handle_command(chat, "/hapus")
    assert "tidak ditemukan" in al.handle_command(chat, "/hapus 9")
    assert "dihapus" in al.handle_command(chat, "/hapus 1")
    assert "Belum ada lokasi" in al.handle_command(chat, "/lokasi")
    assert "Bot Alert" in al.handle_command(chat, "/start")
    assert "tidak valid" in al.handle_command(chat, "/start salah")


def test_stop_deletes_everything(chat):
    _subscribe(chat, PALANGKA)
    _subscribe(chat, PONTIANAK)
    assert "2 lokasi dihapus" in al.handle_command(chat, "/stop")
    assert al.list_subscriptions(chat) == []


def test_test_command_uses_sedang_and_ignores_dedupe(chat, monkeypatch):
    _subscribe(chat, PALANGKA)
    monkeypatch.setattr(al, "_load_features", lambda: [_feat("x", -2.25, 113.95, level="SEDANG", name="Uji")])
    text = al.handle_command(chat, "/tes")
    assert "[UJI]" in text and "Uji" in text


def test_subscribe_endpoint(monkeypatch):
    pytest.importorskip('rasterio')
    from fastapi.testclient import TestClient
    from app import main

    monkeypatch.setattr(main, "TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setattr(main, "TELEGRAM_BOT_USERNAME", "testbot")
    client = TestClient(main.app)
    res = client.post("/api/v1/alerts/subscribe", json={"latitude": -2.2, "longitude": 113.9, "radius_km": 50})
    assert res.status_code == 200
    body = res.json()
    assert body["deep_link"] == f"https://t.me/testbot?start={body['token']}"
    bad = client.post("/api/v1/alerts/subscribe", json={"latitude": 999, "longitude": 113.9})
    assert bad.status_code == 422
    assert client.post("/api/v1/alerts/run").status_code == 403


def test_watch_loop_alerts_when_new_hotspot_appears_without_schedule(chat, sent, monkeypatch):
    """Tanpa jam tetap: hotspot baru yang muncul pada pemeriksaan berikutnya langsung dikirim, yang lama tidak diulang."""
    import asyncio

    _subscribe(chat, PALANGKA)
    state = {"features": []}
    monkeypatch.setattr(al, "_load_features", lambda: state["features"])
    monkeypatch.setattr(al, "ALERTS_CHECK_INTERVAL_MINUTES", 0.0005)  # ~0,03 detik

    async def scenario():
        task = asyncio.create_task(al.hotspot_watch_loop())
        await asyncio.sleep(0.3)
        assert [m for m in sent if m[0] == chat] == []  # belum ada hotspot -> tidak ada alert
        state["features"] = [_feat("h_new", -2.25, 113.95, level="SEDANG", name="Baru")]
        await asyncio.sleep(0.4)
        state["features"].append(_feat("h_new2", -2.26, 113.96, level="TINGGI", name="BaruLagi"))
        await asyncio.sleep(0.4)
        task.cancel()

    asyncio.run(scenario())
    mine = [m[1] for m in sent if m[0] == chat]
    assert len(mine) == 2
    assert "Baru" in mine[0] and "BaruLagi" not in mine[0]
    assert "BaruLagi" in mine[1] and "Baru -" not in mine[1]


def test_start_command_triggers_immediate_alert(chat, sent, monkeypatch):
    """Setelah /start berhasil, hotspot yang sudah ada di radius dikirim tanpa menunggu pemeriksaan berikutnya."""
    import asyncio

    token = al.create_pending_subscription(*PALANGKA, 50, "Rumah")
    monkeypatch.setattr(al, "_load_features", lambda: [_feat("h_now", -2.25, 113.95, name="SudahAda")])

    async def fake_get(self, url, params=None):
        class R:
            def json(_):
                return {"result": [{"update_id": 1, "message": {"text": f"/start {token}", "chat": {"id": chat}}}]}
        if params and params.get("offset"):
            raise asyncio.CancelledError
        return R()

    async def fake_post(self, url, **kw):
        return None

    monkeypatch.setattr(al.httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(al.httpx.AsyncClient, "post", fake_post)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(al.telegram_polling_loop())
    texts = [m[1] for m in sent if m[0] == chat]
    assert any("Alert aktif" in t for t in texts)
    assert any("SudahAda" in t for t in texts)
