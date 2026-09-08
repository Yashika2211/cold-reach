from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.companies import router as companies_router
from app.api.routes.contact_import import router as contact_import_router
from app.api.routes.contacts import router as contacts_router
from app.api.routes.health import router as health_router
from app.api.routes.suppression import router as suppression_router
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
