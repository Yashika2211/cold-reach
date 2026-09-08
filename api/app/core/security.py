import bcrypt
from cryptography.fernet import Fernet

from app.core.config import get_settings


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def _fernet() -> Fernet:
    key = get_settings().credentials_encryption_key
    if not key:
        raise RuntimeError(
            "CREDENTIALS_ENCRYPTION_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"`"
        )
    return Fernet(key.encode())


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
