import uuid

from app.services.unsubscribe import (
    append_unsubscribe_footer,
    strip_unsubscribe_footer,
    verify_unsubscribe_token,
)


def test_append_adds_a_valid_footer():
    contact_id = uuid.uuid4()
    body = append_unsubscribe_footer("Hello there.", contact_id)

    assert body.startswith("Hello there.")
    assert "/unsubscribe/" in body

    token = body.rsplit("/unsubscribe/", 1)[1]
    assert verify_unsubscribe_token(token) == contact_id


def test_append_is_idempotent_never_doubles_the_footer():
    contact_id = uuid.uuid4()
    once = append_unsubscribe_footer("Hello there.", contact_id)
    twice = append_unsubscribe_footer(once, contact_id)

    assert twice.count("Unsubscribe:") == 1
    assert twice == once


def test_append_replaces_a_footer_pointing_at_a_different_contact():
    """Guards against an operator copy-pasting another contact's draft text — the
    footer must always resolve to the CURRENT contact, never a stale one."""
    contact_a = uuid.uuid4()
    contact_b = uuid.uuid4()

    body_for_a = append_unsubscribe_footer("Hello there.", contact_a)
    body_for_b = append_unsubscribe_footer(body_for_a, contact_b)

    assert body_for_b.count("Unsubscribe:") == 1
    token = body_for_b.rsplit("/unsubscribe/", 1)[1]
    assert verify_unsubscribe_token(token) == contact_b


def test_strip_removes_footer():
    contact_id = uuid.uuid4()
    with_footer = append_unsubscribe_footer("Hello there.", contact_id)
    assert strip_unsubscribe_footer(with_footer) == "Hello there."


def test_strip_is_a_noop_without_a_footer():
    assert strip_unsubscribe_footer("Hello there.") == "Hello there."
