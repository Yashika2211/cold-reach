import re

from app.models import Contact
from app.schemas.generation import GeneratedEmail, QualityGateResult
from app.services.unsubscribe import verify_unsubscribe_token

PLACEHOLDER_MARKERS = ["{{", "}}", "[name]", "[company]", "[position]", "[role]", "todo"]

SPAM_TRIGGER_PHRASES = [
    "act now",
    "limited time",
    "click here",
    "guarantee",
    "no obligation",
    "risk-free",
    "100% free",
    "buy now",
    "order now",
    "congratulations",
    "winner",
    "$$$",
    "quick question",
]

INITIAL_WORD_RANGE = (120, 160)
FOLLOW_UP_MAX_WORDS = 60
SUBJECT_MAX_CHARS = 60

_UNSUBSCRIBE_URL_RE = re.compile(r"https?://\S+/unsubscribe/(\S+)")


def run_quality_gate(
    generated: GeneratedEmail, final_body: str, contact: Contact, step_number: int
) -> QualityGateResult:
    failures: list[str] = []

    if generated.needs_more_context:
        failures.append(
            "Model flagged needs_more_context — nothing specific enough to personalize on honestly"
        )

    _check_placeholders(generated, failures)
    _check_length(generated, step_number, failures)
    _check_spam_phrases(generated, failures)
    _check_subject_style(generated, failures)
    _check_unsubscribe_token(final_body, contact, failures)
    _check_recipient_name(final_body, contact, failures)

    return QualityGateResult(passed=len(failures) == 0, failures=failures)


def _check_placeholders(generated: GeneratedEmail, failures: list[str]) -> None:
    combined = f"{generated.subject}\n{generated.body}".lower()
    for marker in PLACEHOLDER_MARKERS:
        if marker in combined:
            failures.append(f"Placeholder leakage: found {marker!r}")


def _check_length(generated: GeneratedEmail, step_number: int, failures: list[str]) -> None:
    word_count = len(generated.body.split())
    if step_number == 0:
        low, high = INITIAL_WORD_RANGE
        if not (low <= word_count <= high):
            failures.append(f"Initial email is {word_count} words; must be {low}-{high}")
    else:
        if word_count > FOLLOW_UP_MAX_WORDS:
            failures.append(f"Follow-up is {word_count} words; must be under {FOLLOW_UP_MAX_WORDS}")


def _check_spam_phrases(generated: GeneratedEmail, failures: list[str]) -> None:
    combined = f"{generated.subject}\n{generated.body}".lower()
    for phrase in SPAM_TRIGGER_PHRASES:
        if phrase in combined:
            failures.append(f"Spam-trigger phrase detected: {phrase!r}")


def _check_subject_style(generated: GeneratedEmail, failures: list[str]) -> None:
    subject = generated.subject.strip()
    if not subject:
        failures.append("Subject is empty")
        return

    if len(subject) > SUBJECT_MAX_CHARS:
        failures.append(f"Subject is {len(subject)} chars; must be under {SUBJECT_MAX_CHARS}")
    if "!" in subject:
        failures.append("Subject contains an exclamation mark")
    if _contains_emoji(subject):
        failures.append("Subject contains an emoji")
    if subject.lower().startswith(("re:", "fwd:")):
        failures.append("Subject uses a fake Re:/Fwd: prefix")
    letters = [c for c in subject if c.isalpha()]
    if letters and subject == subject.upper():
        failures.append("Subject is in ALL CAPS")


def _contains_emoji(text: str) -> bool:
    for ch in text:
        codepoint = ord(ch)
        if (
            0x1F300 <= codepoint <= 0x1FAFF
            or 0x2600 <= codepoint <= 0x27BF
            or codepoint in (0x2764, 0xFE0F)
        ):
            return True
    return False


def _check_unsubscribe_token(final_body: str, contact: Contact, failures: list[str]) -> None:
    match = _UNSUBSCRIBE_URL_RE.search(final_body)
    if not match:
        failures.append("Missing unsubscribe link")
        return

    token = match.group(1)
    resolved_contact_id = verify_unsubscribe_token(token)
    if resolved_contact_id != contact.id:
        failures.append("Unsubscribe token is missing or does not resolve to this contact")


def _check_recipient_name(final_body: str, contact: Contact, failures: list[str]) -> None:
    if not contact.first_name:
        return
    if contact.first_name.lower() not in final_body.lower():
        failures.append(f"Recipient's first name {contact.first_name!r} not found in the body")
