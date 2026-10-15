"""Authentication and session helpers for citizen-report workflows."""

import hashlib
import secrets
import threading
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, Optional, Tuple

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Header, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from .config import PETUGAS_REGISTRATION_CODE
from .reports_storage import (
    UserModel,
    UserSessionModel,
    reports_repo,
)

SESSION_LIFETIME = timedelta(hours=12)
_password_hasher = PasswordHasher()
_rate_lock = threading.Lock()
_rate_events: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)


def enforce_rate_limit(request: Request, action: str, limit: int, window_seconds: int = 60) -> None:
    now = datetime.now(timezone.utc).timestamp()
    client_host = request.client.host if request.client else "unknown"
    key = (action, client_host)
    with _rate_lock:
        events = _rate_events[key]
        while events and now - events[0] >= window_seconds:
            events.popleft()
        if len(events) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Terlalu banyak permintaan. Silakan coba kembali beberapa saat lagi.",
            )
        events.append(now)


def register_user(
    username: str,
    email: Optional[str],
    password: str,
    role: str,
    institution_code: Optional[str],
) -> UserModel:
    clean_username = username.strip().lower()
    clean_email = email.strip().lower() if email and email.strip() else None
    if role not in {"warga", "petugas"}:
        raise HTTPException(status_code=422, detail="Role hanya dapat berupa warga atau petugas.")
    if role == "petugas":
        if not PETUGAS_REGISTRATION_CODE:
            raise HTTPException(
                status_code=503,
                detail="Registrasi petugas belum dikonfigurasi oleh administrator.",
            )
        if not institution_code or not secrets.compare_digest(
            institution_code, PETUGAS_REGISTRATION_CODE
        ):
            raise HTTPException(status_code=403, detail="Kode instansi tidak valid.")

    session = reports_repo.SessionLocal()
    user = UserModel(
        id=str(uuid.uuid4()),
        username=clean_username,
        email=clean_email,
        password_hash=_password_hasher.hash(password),
        role=role,
        status="aktif",
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    try:
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Username atau email sudah digunakan.",
        ) from exc
    finally:
        session.close()

    reports_repo.write_audit_log("registrasi_akun", actor_user_id=user_id, details={"role": role})
    return get_user_by_id(user_id)


def get_user_by_id(user_id: str) -> UserModel:
    session = reports_repo.SessionLocal()
    try:
        user = session.query(UserModel).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="Akun tidak tersedia.")
        return user
    finally:
        session.close()


def login_user(identifier: str, password: str) -> Tuple[UserModel, str, datetime]:
    clean_identifier = identifier.strip().lower()
    session = reports_repo.SessionLocal()
    try:
        user = (
            session.query(UserModel)
            .filter(
                (UserModel.username == clean_identifier)
                | (UserModel.email == clean_identifier)
            )
            .first()
        )
        if not user or user.status != "aktif":
            reports_repo.write_audit_log("login_gagal", details={"reason": "invalid_credentials"})
            raise HTTPException(status_code=401, detail="Username/email atau password tidak valid.")
        try:
            _password_hasher.verify(user.password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            reports_repo.write_audit_log(
                "login_gagal", actor_user_id=user.id, details={"reason": "invalid_password"}
            )
            raise HTTPException(
                status_code=401,
                detail="Username/email atau password tidak valid.",
            ) from None

        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires_at = now + SESSION_LIFETIME
        session.add(
            UserSessionModel(
                id=str(uuid.uuid4()),
                user_id=user.id,
                token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                expires_at_utc=expires_at.isoformat(),
                created_at_utc=now.isoformat(),
            )
        )
        session.commit()
        user_id = user.id
    finally:
        session.close()

    reports_repo.write_audit_log("login_berhasil", actor_user_id=user_id)
    return get_user_by_id(user_id), token, expires_at


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login diperlukan untuk melakukan tindakan ini.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token autentikasi tidak valid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token.strip()


def get_current_user(authorization: Optional[str] = Header(None)) -> UserModel:
    token = _extract_bearer_token(authorization)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    session = reports_repo.SessionLocal()
    try:
        stored_session = (
            session.query(UserSessionModel).filter_by(token_hash=token_hash).first()
        )
        if not stored_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesi tidak valid atau sudah berakhir. Silakan login kembali.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        expires_at = datetime.fromisoformat(stored_session.expires_at_utc)
        if expires_at <= datetime.now(timezone.utc):
            session.delete(stored_session)
            session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesi telah berakhir. Silakan login kembali.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = session.query(UserModel).filter_by(id=stored_session.user_id).first()
        if not user or user.status != "aktif":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Akun tidak aktif.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        session.expunge(user)
        return user
    finally:
        session.close()


def logout_user(authorization: Optional[str], user: UserModel) -> None:
    token = _extract_bearer_token(authorization)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    session = reports_repo.SessionLocal()
    try:
        session.query(UserSessionModel).filter_by(
            token_hash=token_hash, user_id=user.id
        ).delete()
        session.commit()
    finally:
        session.close()
    reports_repo.write_audit_log("logout", actor_user_id=user.id)


def require_role(user: UserModel, role: str) -> None:
    if user.role != role:
        raise HTTPException(status_code=403, detail="Aksi ini memerlukan role petugas.")
