import uuid

from app.models import Contact
from app.models.enums import ContactSource
from app.schemas.generation import GeneratedEmail
from app.services.quality_gate import run_quality_gate
from app.services.unsubscribe import build_unsubscribe_url

GOOD_BODY = (
    "Hi Priya, saw TechFlow just closed a Series B and is doubling the backend team — "
    "that kind of scale-up is exactly the environment I want to build in. I've spent the "
    "last year shipping a real-time data pipeline that handled 40x traffic growth without "
    "a rewrite, which sounds close to the problem you're probably fighting right now. "
    "I'm a final-year CS student graduating in 2027, and I'd love to trade notes on how "
    "you're approaching the scaling work — even fifteen minutes would help me understand "
    "if there's a fit here. Would it make sense to talk sometime next week? "
    "Happy to work around your schedule, and I can share more specifics on the pipeline "
    "project if useful. Thanks for considering it, and congrats again on the raise."
)


def make_contact(first_name: str | None = "Priya") -> Contact:
    return Contact(
        id=uuid.uuid4(),
        first_name=first_name,
        last_name="Sharma",
        email="priya@techflow.io",
        normalized_email="priya@techflow.io",
        source=ContactSource.manual,
    )


def make_body_with_unsubscribe(contact: Contact, body: str = GOOD_BODY) -> str:
    url = build_unsubscribe_url(contact.id)
    return f"{body}\n\n---\nDon't want future emails? Unsubscribe: {url}"


def test_good_email_passes():
    contact = make_contact()
    generated = GeneratedEmail(
        subject="noticed techflow's series b",
        body=GOOD_BODY,
        personalization_rationale="Referenced the Series B funding round from company research.",
        needs_more_context=False,
    )
    result = run_quality_gate(generated, make_body_with_unsubscribe(contact), contact, step_number=0)
    assert result.passed is True, result.failures


def test_needs_more_context_fails():
    contact = make_contact()
    generated = GeneratedEmail(
        subject="hello",
        body=GOOD_BODY,
        personalization_rationale="n/a",
        needs_more_context=True,
    )
    result = run_quality_gate(generated, make_body_with_unsubscribe(contact), contact, step_number=0)
    assert result.passed is False
    assert any("needs_more_context" in f for f in result.failures)


def test_placeholder_leakage_fails():
    contact = make_contact()
    generated = GeneratedEmail(
        subject="hello [Name]",
        body=GOOD_BODY,
        personalization_rationale="n/a",
    )
    result = run_quality_gate(generated, make_body_with_unsubscribe(contact), contact, step_number=0)
    assert result.passed is False
    assert any("Placeholder" in f for f in result.failures)


def test_initial_email_too_short_fails():
    contact = make_contact()
    generated = GeneratedEmail(subject="hi", body="Way too short.", personalization_rationale="n/a")
    result = run_quality_gate(generated, make_body_with_unsubscribe(contact), contact, step_number=0)
    assert result.passed is False
    assert any("words" in f for f in result.failures)


def test_followup_over_60_words_fails():
    contact = make_contact()
    long_followup = " ".join(["word"] * 70)
    generated = GeneratedEmail(subject="following up", body=long_followup, personalization_rationale="n/a")
    result = run_quality_gate(generated, make_body_with_unsubscribe(contact), contact, step_number=1)
    assert result.passed is False
    assert any("70 words" in f for f in result.failures)


def test_short_followup_passes_length_check():
    contact = make_contact()
    short_followup = " ".join(["word"] * 40)
    generated = GeneratedEmail(
        subject="one more thing",
        body=short_followup,
        personalization_rationale="n/a",
    )
    result = run_quality_gate(generated, make_body_with_unsubscribe(contact), contact, step_number=1)
    assert not any("words" in f for f in result.failures)


def test_spam_phrase_fails():
    contact = make_contact()
    generated = GeneratedEmail(
        subject="act now for this offer",
        body=GOOD_BODY,
        personalization_rationale="n/a",
    )
    result = run_quality_gate(generated, make_body_with_unsubscribe(contact), contact, step_number=0)
    assert result.passed is False
    assert any("Spam-trigger" in f for f in result.failures)


def test_subject_with_exclamation_fails():
    contact = make_contact()
    generated = GeneratedEmail(subject="loved your product!", body=GOOD_BODY, personalization_rationale="n/a")
    result = run_quality_gate(generated, make_body_with_unsubscribe(contact), contact, step_number=0)
    assert any("exclamation" in f for f in result.failures)


def test_subject_all_caps_fails():
    contact = make_contact()
    generated = GeneratedEmail(subject="LOVED YOUR PRODUCT", body=GOOD_BODY, personalization_rationale="n/a")
    result = run_quality_gate(generated, make_body_with_unsubscribe(contact), contact, step_number=0)
    assert any("ALL CAPS" in f for f in result.failures)


def test_subject_fake_re_prefix_fails():
    contact = make_contact()
    generated = GeneratedEmail(
        subject="re: your role at techflow", body=GOOD_BODY, personalization_rationale="n/a"
    )
    result = run_quality_gate(generated, make_body_with_unsubscribe(contact), contact, step_number=0)
    assert any("Re:/Fwd:" in f for f in result.failures)


def test_subject_too_long_fails():
    contact = make_contact()
    generated = GeneratedEmail(
        subject="a" * 61, body=GOOD_BODY, personalization_rationale="n/a"
    )
    result = run_quality_gate(generated, make_body_with_unsubscribe(contact), contact, step_number=0)
    assert any("chars" in f for f in result.failures)


def test_missing_unsubscribe_link_fails():
    contact = make_contact()
    generated = GeneratedEmail(subject="hello", body=GOOD_BODY, personalization_rationale="n/a")
    result = run_quality_gate(generated, GOOD_BODY, contact, step_number=0)  # no footer appended
    assert result.passed is False
    assert any("unsubscribe" in f.lower() for f in result.failures)


def test_unsubscribe_token_for_wrong_contact_fails():
    contact = make_contact()
    other_contact = make_contact()
    generated = GeneratedEmail(subject="hello", body=GOOD_BODY, personalization_rationale="n/a")
    # body carries a validly-signed token, but for a DIFFERENT contact
    body_with_wrong_token = make_body_with_unsubscribe(other_contact)
    result = run_quality_gate(generated, body_with_wrong_token, contact, step_number=0)
    assert result.passed is False
    assert any("does not resolve" in f for f in result.failures)


def test_missing_recipient_name_fails():
    contact = make_contact(first_name="Zephyrine")
    generated = GeneratedEmail(subject="hello", body=GOOD_BODY, personalization_rationale="n/a")
    result = run_quality_gate(generated, make_body_with_unsubscribe(contact), contact, step_number=0)
    assert result.passed is False
    assert any("Zephyrine" in f for f in result.failures)


def test_no_recipient_name_available_skips_check():
    contact = make_contact(first_name=None)
    generated = GeneratedEmail(subject="hello", body=GOOD_BODY, personalization_rationale="n/a")
    result = run_quality_gate(generated, make_body_with_unsubscribe(contact), contact, step_number=0)
    assert not any("first name" in f.lower() for f in result.failures)
