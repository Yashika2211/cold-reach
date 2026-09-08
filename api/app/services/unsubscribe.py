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


_FOOTER_MARKER = "\n\n---\nDon't want future emails? Unsubscribe: "


def append_unsubscribe_footer(body: str, contact_id: uuid.UUID) -> str:
    """The single place a footer gets attached, so every code path — LLM generation
    and hand edits alike — carries an unsubscribe link the operator never has to
    (and never can) tamper with. Strips any footer-looking suffix first, so calling
    this on already-footered text never produces two footers."""
    return strip_unsubscribe_footer(body).rstrip() + _FOOTER_MARKER + build_unsubscribe_url(contact_id)


def strip_unsubscribe_footer(body: str) -> str:
    marker_index = body.find(_FOOTER_MARKER)
    return body[:marker_index] if marker_index != -1 else body
