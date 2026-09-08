import secrets
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.config import get_settings
from app.core.redis import get_redis
from app.db.session import get_db
from app.models import ResumeVariant, SendingAccount
from app.models.enums import SendingAccountProvider
from app.providers.email.base import EmailProviderError, ReauthRequiredError
from app.schemas.sending_account import (
    ConnectionTestResult,
    SendingAccountCreate,
    SendingAccountRead,
    SendingAccountUpdate,
    SendTestEmailRequest,
    SendTestEmailResponse,
)
from app.services import google_oauth
from app.services.sending import SuppressedRecipientError, send_test_email
from app.services.sending_accounts import build_provider, decrypt_credentials, encrypt_credentials

router = APIRouter(
    prefix="/sending-accounts", tags=["sending-accounts"], dependencies=[Depends(get_current_admin)]
)

OAUTH_STATE_TTL_SECONDS = 10 * 60


async def _get_account_or_404(db: AsyncSession, account_id: uuid.UUID) -> SendingAccount:
    result = await db.execute(
        select(SendingAccount).where(
            SendingAccount.id == account_id, SendingAccount.deleted_at.is_(None)
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sending account not found")
    return account


@router.get("", response_model=list[SendingAccountRead])
async def list_sending_accounts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SendingAccount)
        .where(SendingAccount.deleted_at.is_(None))
        .order_by(SendingAccount.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=SendingAccountRead, status_code=status.HTTP_201_CREATED)
async def create_sending_account(payload: SendingAccountCreate, db: AsyncSession = Depends(get_db)):
    if payload.provider_type == SendingAccountProvider.gmail_oauth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gmail accounts are connected via /sending-accounts/oauth/gmail/start, "
            "not created directly.",
        )

    if payload.provider_type == SendingAccountProvider.smtp:
        if payload.smtp_credentials is None:
            raise HTTPException(status_code=400, detail="smtp_credentials is required for provider_type=smtp")
        credentials = payload.smtp_credentials.model_dump()
    else:
        if payload.api_credentials is None:
            raise HTTPException(
                status_code=400, detail="api_credentials is required for this provider_type"
            )
        credentials = payload.api_credentials.model_dump()

    account = SendingAccount(
        display_name=payload.display_name,
        from_address=payload.from_address,
        provider_type=payload.provider_type,
        daily_cap=payload.daily_cap,
        encrypted_credentials=encrypt_credentials(credentials),
        health_metrics={},
        is_active=True,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("/{account_id}", response_model=SendingAccountRead)
async def get_sending_account(account_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _get_account_or_404(db, account_id)


@router.patch("/{account_id}", response_model=SendingAccountRead)
async def update_sending_account(
    account_id: uuid.UUID, payload: SendingAccountUpdate, db: AsyncSession = Depends(get_db)
):
    account = await _get_account_or_404(db, account_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    await db.commit()
    await db.refresh(account, attribute_names=["updated_at"])
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sending_account(account_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    account = await _get_account_or_404(db, account_id)
    account.deleted_at = datetime.now(UTC)
    await db.commit()


@router.post("/{account_id}/test", response_model=ConnectionTestResult)
async def test_sending_account(account_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    account = await _get_account_or_404(db, account_id)
    provider = build_provider(account, db)
    try:
        await provider.verify_credentials()
    except ReauthRequiredError as exc:
        return ConnectionTestResult(ok=False, detail=str(exc), needs_reauth=True)
    except EmailProviderError as exc:
        return ConnectionTestResult(ok=False, detail=str(exc))
    return ConnectionTestResult(ok=True)


@router.post("/{account_id}/send-test", response_model=SendTestEmailResponse)
async def send_test(
    account_id: uuid.UUID, payload: SendTestEmailRequest, db: AsyncSession = Depends(get_db)
):
    account = await _get_account_or_404(db, account_id)

    resume_variant = None
    if payload.resume_variant_id is not None:
        resume_variant = await db.get(ResumeVariant, payload.resume_variant_id)
        if resume_variant is None:
            raise HTTPException(status_code=404, detail="Resume variant not found")

    try:
        email_message = await send_test_email(
            db, account, payload.to_email, payload.subject, payload.body_text, resume_variant
        )
    except SuppressedRecipientError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ReauthRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except EmailProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return SendTestEmailResponse(
        email_message_id=email_message.id,
        provider_message_id=email_message.provider_message_id,
        sent_at=email_message.sent_at,
    )


@router.get("/oauth/gmail/status")
async def gmail_oauth_status():
    return {"configured": google_oauth.is_configured()}


@router.get("/oauth/gmail/start")
async def gmail_oauth_start(redis: Redis = Depends(get_redis)):
    if not google_oauth.is_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth is not configured on this server (GOOGLE_OAUTH_CLIENT_ID/SECRET).",
        )

    state = secrets.token_urlsafe(32)
    await redis.set(f"oauth_state:gmail:{state}", "1", ex=OAUTH_STATE_TTL_SECONDS)
    return RedirectResponse(google_oauth.build_authorization_url(state))


@router.get("/oauth/gmail/callback")
async def gmail_oauth_callback(
    request: Request, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)
):
    settings = get_settings()
    error = request.query_params.get("error")
    if error:
        return RedirectResponse(f"{settings.web_origin}/settings?gmail_error={error}")

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state from Google")

    state_key = f"oauth_state:gmail:{state}"
    if not await redis.get(state_key):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    await redis.delete(state_key)

    try:
        tokens = await google_oauth.exchange_code_for_tokens(code)
    except httpx.HTTPStatusError:
        return RedirectResponse(f"{settings.web_origin}/settings?gmail_error=token_exchange_failed")

    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in", 3600)
    expiry = (datetime.now(UTC) + timedelta(seconds=expires_in)).isoformat()

    gmail_address = await google_oauth.fetch_gmail_address(access_token)

    result = await db.execute(
        select(SendingAccount).where(
            SendingAccount.provider_type == SendingAccountProvider.gmail_oauth,
            SendingAccount.from_address == gmail_address,
            SendingAccount.deleted_at.is_(None),
        )
    )
    account = result.scalar_one_or_none()

    credentials = {
        "access_token": access_token,
        "refresh_token": refresh_token or (
            _existing_refresh_token(account) if account else None
        ),
        "token_expiry": expiry,
        "gmail_address": gmail_address,
    }

    if not credentials["refresh_token"]:
        return RedirectResponse(f"{settings.web_origin}/settings?gmail_error=no_refresh_token")

    if account:
        account.encrypted_credentials = encrypt_credentials(credentials)
        account.deleted_at = None
    else:
        account = SendingAccount(
            display_name=f"Gmail: {gmail_address}",
            from_address=gmail_address,
            provider_type=SendingAccountProvider.gmail_oauth,
            daily_cap=get_settings().default_daily_send_cap,
            encrypted_credentials=encrypt_credentials(credentials),
            health_metrics={},
            is_active=True,
        )
        db.add(account)

    await db.commit()
    return RedirectResponse(f"{settings.web_origin}/settings?gmail_connected=1")


def _existing_refresh_token(account: SendingAccount) -> str | None:
    try:
        return decrypt_credentials(account.encrypted_credentials or "{}").get("refresh_token")
    except Exception:
        return None
