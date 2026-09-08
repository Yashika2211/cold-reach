from email.message import EmailMessage as MimeEmailMessage
from email.utils import make_msgid

from app.providers.email.base import SendEmailRequest


def build_mime_message(request: SendEmailRequest) -> tuple[MimeEmailMessage, str]:
    """Shared by every provider so header/threading/attachment handling never drifts
    between them. Returns the message and the Message-ID header it generated."""
    msg = MimeEmailMessage()
    msg["From"] = f"{request.from_name} <{request.from_email}>"
    msg["To"] = f"{request.to_name} <{request.to_email}>" if request.to_name else request.to_email
    msg["Subject"] = request.subject
    if request.reply_to:
        msg["Reply-To"] = request.reply_to

    message_id = make_msgid()
    msg["Message-ID"] = message_id

    if request.in_reply_to_message_id:
        msg["In-Reply-To"] = request.in_reply_to_message_id
    if request.references:
        msg["References"] = " ".join(request.references)

    msg.set_content(request.body_text)

    for attachment in request.attachments:
        maintype, _, subtype = attachment.mime_type.partition("/")
        msg.add_attachment(
            attachment.content,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=attachment.filename,
        )

    return msg, message_id
