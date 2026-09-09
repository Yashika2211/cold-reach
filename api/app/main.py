from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.campaign_contact_actions import router as campaign_contact_actions_router
from app.api.routes.campaigns import router as campaigns_router
from app.api.routes.companies import router as companies_router
from app.api.routes.contact_import import router as contact_import_router
from app.api.routes.contacts import router as contacts_router
from app.api.routes.email_generation import router as email_generation_router
from app.api.routes.email_templates import router as email_templates_router
from app.api.routes.health import router as health_router
from app.api.routes.resume_variants import router as resume_variants_router
from app.api.routes.scheduler import router as scheduler_router
from app.api.routes.sending_accounts import router as sending_accounts_router
from app.api.routes.suppression import router as suppression_router
from app.api.routes.unsubscribe import router as unsubscribe_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(debug=settings.debug)

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie=settings.session_cookie_name,
    max_age=settings.session_max_age_seconds,
    same_site="lax",
    https_only=settings.environment == "production",
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(companies_router)
app.include_router(contacts_router)
app.include_router(contact_import_router)
app.include_router(suppression_router)
app.include_router(sending_accounts_router)
app.include_router(unsubscribe_router)
app.include_router(resume_variants_router)
app.include_router(email_templates_router)
app.include_router(email_generation_router)
app.include_router(campaigns_router)
app.include_router(campaign_contact_actions_router)
app.include_router(scheduler_router)
