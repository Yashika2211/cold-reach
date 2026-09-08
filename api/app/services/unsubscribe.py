import uuid

from itsdangerous import BadSignature, URLSafeSerializer

from app.core.config import get_settings

_SALT = "unsubscribe-v1"


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().secret_key, salt=_SALT)


def generate_unsubscribe_token(contact_id: uuid.UUID) -> str:
    return _serializer().dumps(str(contact_id))


def verify_unsubscribe_token(token: str) -> uuid.UUID | None:
    try:
        raw = _serializer().loads(token)
        return uuid.UUID(raw)
    except (BadSignature, ValueError):
        return None


def build_unsubscribe_url(contact_id: uuid.UUID) -> str:
    token = generate_unsubscribe_token(contact_id)
    return f"{get_settings().api_public_url}/unsubscribe/{token}"
