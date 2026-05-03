import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_bytes(payload: bytes) -> bytes:
    return _fernet().encrypt(payload)


def decrypt_bytes(payload: bytes) -> bytes:
    return _fernet().decrypt(payload)
