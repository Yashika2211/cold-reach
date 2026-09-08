from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Contact
from app.models.enums import SuppressionReason, SuppressionSource
from app.services.suppression import add_suppression
from app.services.unsubscribe import verify_unsubscribe_token

router = APIRouter(tags=["unsubscribe"])

_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>ColdReach</title>
<style>body{{font-family:system-ui,sans-serif;max-width:32rem;margin:4rem auto;padding:0 1rem;
color:#111}}</style></head>
<body><p>{message}</p></body></html>"""


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe(token: str, db: AsyncSession = Depends(get_db)):
    # Deliberately generic either way: this is the one unauthenticated route in the
    # app, and it must never reveal whether a given address exists in the system.
    contact_id = verify_unsubscribe_token(token)
    if contact_id is None:
        return HTMLResponse(_PAGE.format(message="This unsubscribe link is invalid."), status_code=400)

    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()

    if contact is not None:
        await add_suppression(
            db, contact.email, reason=SuppressionReason.opt_out, source=SuppressionSource.system
        )
        await db.commit()

    return HTMLResponse(_PAGE.format(message="You've been unsubscribed and won't receive further emails."))
