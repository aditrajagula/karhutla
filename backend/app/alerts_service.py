"""
Alert Telegram untuk hotspot prediktif harian berdasarkan radius lokasi pengguna.

Alur: aplikasi web membuat langganan "pending" (lokasi + radius) dan mendapat token.
Pengguna membuka t.me/<bot>?start=<token>; bot mengaitkan token itu ke chat_id.
Alert dikirim begitu ada hotspot prediktif SEDANG/TINGGI dalam radius lokasi (tanpa jadwal jam tetap).
Satu chat boleh punya beberapa lokasi (maks. ALERTS_MAX_LOCATIONS).
"""

import asyncio
import logging
import math
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import Boolean, Column, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import declarative_base

from .config import (
    ALERTS_MAX_LOCATIONS,
    ALERTS_CHECK_INTERVAL_MINUTES,
    TELEGRAM_BOT_TOKEN,
)
from .reports_storage import reports_repo

logger = logging.getLogger(__name__)
# httpx mencatat URL request di level INFO, dan URL Telegram memuat token bot.
logging.getLogger("httpx").setLevel(logging.WARNING)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
ALERT_LEVELS = ("SEDANG", "TINGGI")
MAX_HOTSPOTS_PER_LOCATION = 5
PENDING_TOKEN_TTL_HOURS = 24
MIN_RADIUS_KM = 5.0
MAX_RADIUS_KM = 200.0

AlertBase = declarative_base()


class TelegramSubscriptionModel(AlertBase):
    __tablename__ = "telegram_subscriptions"

    id = Column(String(36), primary_key=True)
    link_token = Column(String(64), unique=True, index=True, nullable=False)
    chat_id = Column(String(32), index=True, nullable=True)  # NULL = belum di-Start
    label = Column(String(60), nullable=False, default="Lokasi")
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    radius_km = Column(Float, nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(String(40), nullable=False)


class AlertLogModel(AlertBase):
    __tablename__ = "telegram_alert_log"
    __table_args__ = (UniqueConstraint("subscription_id", "hotspot_id", name="uq_alert_sub_hotspot"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    subscription_id = Column(String(36), index=True, nullable=False)
    hotspot_id = Column(String(120), nullable=False)
    sent_at = Column(String(40), nullable=False)


AlertBase.metadata.create_all(bind=reports_repo.engine)


def _session():
    return reports_repo.SessionLocal()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp_radius(radius_km: float) -> float:
    return max(MIN_RADIUS_KM, min(MAX_RADIUS_KM, float(radius_km)))


# --------------------------------------------------------------------------
# Langganan
# --------------------------------------------------------------------------
def create_pending_subscription(lat: float, lon: float, radius_km: float, label: Optional[str]) -> str:
    """Membuat langganan belum aktif dan mengembalikan token untuk deep link bot."""
    token = secrets.token_urlsafe(16)
    session = _session()
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=PENDING_TOKEN_TTL_HOURS)).isoformat()
        session.query(TelegramSubscriptionModel).filter(
            TelegramSubscriptionModel.chat_id.is_(None),
            TelegramSubscriptionModel.created_at < cutoff,
        ).delete()
        session.add(
            TelegramSubscriptionModel(
                id=str(uuid.uuid4()),
                link_token=token,
                label=(label or "Lokasi").strip()[:60] or "Lokasi",
                lat=round(float(lat), 2),
                lon=round(float(lon), 2),
                radius_km=_clamp_radius(radius_km),
                is_active=False,
                created_at=_now_iso(),
            )
        )
        session.commit()
        return token
    finally:
        session.close()


def activate_subscription(token: str, chat_id: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Mengaitkan token ke chat. Status: ok | invalid | used | limit."""
    session = _session()
    try:
        sub = session.query(TelegramSubscriptionModel).filter_by(link_token=token).first()
        if not sub:
            return "invalid", None
        if sub.chat_id is not None:
            return "used", None
        active = session.query(TelegramSubscriptionModel).filter_by(chat_id=chat_id, is_active=True).count()
        if active >= ALERTS_MAX_LOCATIONS:
            return "limit", None
        sub.chat_id = chat_id
        sub.is_active = True
        session.commit()
        return "ok", {"label": sub.label, "lat": sub.lat, "lon": sub.lon, "radius_km": sub.radius_km}
    finally:
        session.close()


def list_subscriptions(chat_id: str) -> List[TelegramSubscriptionModel]:
    session = _session()
    try:
        rows = (
            session.query(TelegramSubscriptionModel)
            .filter_by(chat_id=chat_id, is_active=True)
            .order_by(TelegramSubscriptionModel.created_at)
            .all()
        )
        session.expunge_all()
        return rows
    finally:
        session.close()


def _delete_subs(session, subs: List[TelegramSubscriptionModel]) -> None:
    ids = [s.id for s in subs]
    if ids:
        session.query(AlertLogModel).filter(AlertLogModel.subscription_id.in_(ids)).delete(synchronize_session=False)
        session.query(TelegramSubscriptionModel).filter(TelegramSubscriptionModel.id.in_(ids)).delete(
            synchronize_session=False
        )


def delete_subscription_by_index(chat_id: str, index: int) -> Optional[str]:
    """Hapus lokasi nomor `index` (mulai 1). Mengembalikan label, atau None jika tidak ada."""
    session = _session()
    try:
        rows = (
            session.query(TelegramSubscriptionModel)
            .filter_by(chat_id=chat_id, is_active=True)
            .order_by(TelegramSubscriptionModel.created_at)
            .all()
        )
        if index < 1 or index > len(rows):
            return None
        target = rows[index - 1]
        label = target.label
        _delete_subs(session, [target])
        session.commit()
        return label
    finally:
        session.close()


def set_radius_by_index(chat_id: str, index: int, radius_km: float) -> Optional[float]:
    session = _session()
    try:
        rows = (
            session.query(TelegramSubscriptionModel)
            .filter_by(chat_id=chat_id, is_active=True)
            .order_by(TelegramSubscriptionModel.created_at)
            .all()
        )
        if index < 1 or index > len(rows):
            return None
        rows[index - 1].radius_km = _clamp_radius(radius_km)
        session.commit()
        return rows[index - 1].radius_km
    finally:
        session.close()


def delete_all_for_chat(chat_id: str) -> int:
    session = _session()
    try:
        rows = session.query(TelegramSubscriptionModel).filter_by(chat_id=chat_id).all()
        count = len(rows)
        _delete_subs(session, rows)
        session.commit()
        return count
    finally:
        session.close()


# --------------------------------------------------------------------------
# Pengiriman pesan
# --------------------------------------------------------------------------
def send_message(chat_id: str, text: str) -> int:
    """Kirim pesan teks. Mengembalikan HTTP status (0 jika gagal koneksi)."""
    try:
        resp = httpx.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=10.0,
        )
        return resp.status_code
    except httpx.HTTPError as exc:
        logger.warning("Gagal mengirim pesan Telegram ke %s: %s", chat_id, type(exc).__name__)
        return 0


def _hit_line(hit: Dict[str, Any]) -> str:
    return (
        f"=== {hit['name']} - {hit['level']} ({hit['pct']:.0f}%), "
        f"{hit['dist_km']:.1f} km dari lokasi Anda"
    )


def format_alert(groups: List[Tuple[TelegramSubscriptionModel, List[Dict[str, Any]]]], date_str: str, is_test: bool = False) -> str:
    title = "[UJI] Alert Hotspot Prediktif JagaBorneo" if is_test else "Alert Hotspot Prediktif JagaBorneo"
    lines = [title, f"Tanggal: {date_str}", ""]
    for sub, hits in groups:
        lines.append(f"Lokasi: {sub.label} (radius {sub.radius_km:.0f} km)")
        shown = hits[:MAX_HOTSPOTS_PER_LOCATION]
        lines.extend(_hit_line(h) for h in shown)
        if len(hits) > len(shown):
            lines.append(f"... dan {len(hits) - len(shown)} titik lainnya")
        lines.append("")
    lines.append(
        "Ini indikasi kerawanan dari model cuaca dan tutupan lahan, BUKAN titik api "
        "yang terdeteksi satelit. Tetap waspada dan lakukan pencegahan."
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Siklus alert
# --------------------------------------------------------------------------
def _load_features() -> List[Dict[str, Any]]:
    from .prediction_service import get_prediction_service

    return get_prediction_service().get_daily_predictive_hotspots().get("features", [])


def _hits_for_sub(sub: TelegramSubscriptionModel, features: List[Dict[str, Any]], levels: Tuple[str, ...]) -> List[Dict[str, Any]]:
    hits = []
    for feat in features:
        props = feat.get("properties", {})
        if props.get("risk_level") not in levels:
            continue
        dist = haversine_km(sub.lat, sub.lon, props["latitude"], props["longitude"])
        if dist <= sub.radius_km:
            hits.append(
                {
                    "id": props["id"],
                    "name": props.get("location_name", "Hotspot"),
                    "level": props["risk_level"],
                    "pct": float(props.get("risk_percentage") or 0),
                    "dist_km": dist,
                }
            )
    hits.sort(key=lambda h: (-h["pct"], h["dist_km"]))
    return hits


def run_alert_cycle(
    features: Optional[List[Dict[str, Any]]] = None,
    dry_run: bool = False,
    force: bool = False,
    only_chat_id: Optional[str] = None,
    levels: Tuple[str, ...] = ALERT_LEVELS,
) -> Dict[str, Any]:
    """
    Kirim alert ke semua langganan aktif. `force` mengabaikan dedupe harian.
    Hotspot yang sama (id memuat tanggal) tidak dikirim dua kali untuk lokasi yang sama.
    """
    if features is None:
        features = _load_features()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    session = _session()
    summary = {"chats_notified": 0, "hotspots_sent": 0, "messages_dry_run": [], "blocked_chats": 0}
    try:
        query = session.query(TelegramSubscriptionModel).filter_by(is_active=True)
        if only_chat_id:
            query = query.filter_by(chat_id=only_chat_id)
        by_chat: Dict[str, List[TelegramSubscriptionModel]] = {}
        for sub in query.order_by(TelegramSubscriptionModel.created_at).all():
            by_chat.setdefault(sub.chat_id, []).append(sub)

        for chat_id, subs in by_chat.items():
            groups = []
            for sub in subs:
                hits = _hits_for_sub(sub, features, levels)
                if not force:
                    sent_ids = {
                        r.hotspot_id
                        for r in session.query(AlertLogModel).filter_by(subscription_id=sub.id).all()
                    }
                    hits = [h for h in hits if h["id"] not in sent_ids]
                if hits:
                    groups.append((sub, hits))
            if not groups:
                continue

            text = format_alert(groups, date_str)
            if dry_run:
                logger.info("[DRY RUN] Alert untuk chat %s:\n%s", chat_id, text)
                summary["messages_dry_run"].append({"chat_id": chat_id, "text": text})
                continue

            status = send_message(chat_id, text)
            if status == 200:
                summary["chats_notified"] += 1
                now = _now_iso()
                for sub, hits in groups:
                    for h in hits:
                        exists = session.query(AlertLogModel).filter_by(subscription_id=sub.id, hotspot_id=h["id"]).first()
                        if not exists:
                            session.add(AlertLogModel(subscription_id=sub.id, hotspot_id=h["id"], sent_at=now))
                        summary["hotspots_sent"] += 1
                session.commit()
            elif status == 403:
                # Pengguna memblokir bot: hapus langganannya
                _delete_subs(session, subs)
                session.commit()
                summary["blocked_chats"] += 1
            else:
                logger.warning("Alert ke chat %s gagal (HTTP %s), dicoba lagi pada siklus berikutnya.", chat_id, status)
        return summary
    finally:
        session.close()


# --------------------------------------------------------------------------
# Perintah bot
# --------------------------------------------------------------------------
HELP_TEXT = (
    "Bot Alert JagaBorneo\n"
    "Anda akan mendapat peringatan jika ada hotspot prediktif level SEDANG atau TINGGI di sekitar lokasi Anda.\n\n"
    "Perintah:\n"
    "/lokasi - daftar lokasi yang dipantau\n"
    "/hapus N - hapus lokasi nomor N\n"
    "/radius N KM - ubah radius lokasi nomor N (5-200 km)\n"
    "/tes - kirim ulang alert hotspot yang ada saat ini\n"
    "/stop - berhenti dan hapus semua lokasi\n\n"
    "Untuk menambah lokasi, tekan tombol Aktifkan Alert Telegram di aplikasi JagaBorneo."
)


def _locations_text(chat_id: str) -> str:
    subs = list_subscriptions(chat_id)
    if not subs:
        return "Belum ada lokasi yang dipantau. Aktifkan lewat aplikasi JagaBorneo."
    lines = ["Lokasi yang dipantau:"]
    for i, s in enumerate(subs, 1):
        lines.append(f"{i}. {s.label} ({s.lat:.2f}, {s.lon:.2f}) radius {s.radius_km:.0f} km")
    return "\n".join(lines)


def _test_text(chat_id: str) -> str:
    subs = list_subscriptions(chat_id)
    if not subs:
        return "Belum ada lokasi yang dipantau. Aktifkan lewat aplikasi JagaBorneo."
    try:
        features = _load_features()
    except Exception as exc:
        logger.warning("Gagal memuat hotspot prediktif untuk /tes: %s", exc)
        return "Data hotspot prediktif belum tersedia. Coba lagi beberapa saat."
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    groups = [(s, h) for s in subs if (h := _hits_for_sub(s, features, ("SEDANG", "TINGGI")))]
    if not groups:
        return (
            "[UJI] Tidak ada hotspot prediktif (SEDANG/TINGGI) dalam radius lokasi Anda hari ini.\n"
            "Alert dikirim otomatis begitu ada hotspot SEDANG/TINGGI di sekitar lokasi Anda."
        )
    return format_alert(groups, date_str, is_test=True)


def handle_command(chat_id: str, text: str) -> str:
    """Memproses pesan masuk dari pengguna dan mengembalikan teks balasan."""
    parts = text.strip().split()
    if not parts:
        return HELP_TEXT
    cmd = parts[0].split("@")[0].lower()
    args = parts[1:]

    if cmd == "/start":
        if not args:
            return HELP_TEXT
        status, info = activate_subscription(args[0], chat_id)
        if status == "ok":
            return (
                f"Alert aktif untuk {info['label']} (radius {info['radius_km']:.0f} km).\n"
                "Anda akan diberi tahu jika ada hotspot prediktif level SEDANG atau TINGGI di area ini.\n"
                "Ketik /tes untuk contoh alert atau /bantuan untuk daftar perintah."
            )
        if status == "limit":
            return f"Batas {ALERTS_MAX_LOCATIONS} lokasi tercapai. Hapus salah satu dengan /hapus N, lalu coba lagi."
        if status == "used":
            return "Link ini sudah dipakai. Buat link baru dari aplikasi JagaBorneo."
        return "Link tidak valid atau kedaluwarsa. Buat link baru dari aplikasi JagaBorneo."
    if cmd in ("/bantuan", "/help"):
        return HELP_TEXT
    if cmd == "/lokasi":
        return _locations_text(chat_id)
    if cmd == "/hapus":
        if not args or not args[0].isdigit():
            return "Format: /hapus N (nomor dari /lokasi)"
        label = delete_subscription_by_index(chat_id, int(args[0]))
        return f"Lokasi {label} dihapus." if label else "Nomor lokasi tidak ditemukan. Cek /lokasi."
    if cmd == "/radius":
        try:
            idx, km = int(args[0]), float(args[1])
        except (IndexError, ValueError):
            return "Format: /radius N KM, contoh: /radius 1 75"
        new_km = set_radius_by_index(chat_id, idx, km)
        return f"Radius lokasi {idx} diubah menjadi {new_km:.0f} km." if new_km else "Nomor lokasi tidak ditemukan. Cek /lokasi."
    if cmd == "/tes":
        return _test_text(chat_id)
    if cmd == "/stop":
        count = delete_all_for_chat(chat_id)
        return f"Berhenti berlangganan. {count} lokasi dihapus." if count else "Anda belum punya langganan aktif."
    return HELP_TEXT


# --------------------------------------------------------------------------
# Loop latar belakang (dipakai di lifespan FastAPI)
# --------------------------------------------------------------------------
async def telegram_polling_loop() -> None:
    """Long-polling getUpdates (tidak butuh URL publik). Cocok untuk lokal dan deploy sederhana."""
    offset: Optional[int] = None
    async with httpx.AsyncClient(timeout=40.0) as client:
        try:
            # Polling tidak jalan jika webhook masih terpasang
            await client.post(f"{TELEGRAM_API}/deleteWebhook")
        except httpx.HTTPError:
            pass
        logger.info("Polling bot Telegram dimulai.")
        while True:
            try:
                params: Dict[str, Any] = {"timeout": 25}
                if offset is not None:
                    params["offset"] = offset
                resp = await client.get(f"{TELEGRAM_API}/getUpdates", params=params)
                for upd in resp.json().get("result", []):
                    offset = upd["update_id"] + 1
                    msg = upd.get("message") or {}
                    text, chat = msg.get("text"), (msg.get("chat") or {}).get("id")
                    if text and chat is not None:
                        reply = await asyncio.to_thread(handle_command, str(chat), text)
                        await asyncio.to_thread(send_message, str(chat), reply)
                        if text.startswith("/start") and reply.startswith("Alert aktif"):
                            # Lokasi baru: kirim hotspot yang sudah ada di radiusnya tanpa menunggu pemeriksaan berikutnya
                            await asyncio.to_thread(run_alert_cycle, None, False, False, str(chat))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Polling Telegram error: %s", type(exc).__name__)
                await asyncio.sleep(5)


async def hotspot_watch_loop() -> None:
    """
    Memantau hotspot prediktif dan mengirim alert begitu ada hotspot SEDANG/TINGGI baru dalam radius
    lokasi pengguna. Tidak ada jam tetap: hotspot yang sama tidak dikirim ulang (dedupe per hotspot).
    """
    from .config import ALERTS_DRY_RUN

    while True:
        try:
            summary = await asyncio.to_thread(run_alert_cycle, None, ALERTS_DRY_RUN)
            if summary["chats_notified"]:
                logger.info("Alert hotspot terkirim: %s chat, %s hotspot", summary["chats_notified"], summary["hotspots_sent"])
        except Exception as exc:
            logger.warning("Pemeriksaan hotspot untuk alert gagal: %s", exc)
        await asyncio.sleep(ALERTS_CHECK_INTERVAL_MINUTES * 60)
