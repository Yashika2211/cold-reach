import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_secret, encrypt_secret
from app.models import SendingAccount
from app.models.enums import SendingAccountProvider
from app.providers.email.api_provider import ApiProvider
from app.providers.email.base import EmailProvider
from app.providers.email.gmail_oauth_provider import GmailOAuthProvider
from app.providers.email.smtp_provider import SmtpProvider


def encrypt_credentials(data: dict) -> str:
    return encrypt_secret(json.dumps(data))


def decrypt_credentials(ciphertext: str) -> dict:
    return json.loads(decrypt_secret(ciphertext))


def build_provider(account: SendingAccount, db: AsyncSession | None = None) -> EmailProvider:
    credentials = decrypt_credentials(account.encrypted_credentials or "{}")

    if account.provider_type == SendingAccountProvider.smtp:
        return SmtpProvider(credentials)

    if account.provider_type == SendingAccountProvider.gmail_oauth:

        async def persist_refreshed_tokens(updated_credentials: dict) -> None:
            if db is None:
                return
            account.encrypted_credentials = encrypt_credentials(updated_credentials)
            db.add(account)
            await db.commit()

        return GmailOAuthProvider(credentials, on_token_refreshed=persist_refreshed_tokens)

    if account.provider_type in (
        SendingAccountProvider.api_resend,
        SendingAccountProvider.api_sendgrid,
    ):
        return ApiProvider(credentials)

    raise ValueError(f"Unsupported provider type: {account.provider_type}")
