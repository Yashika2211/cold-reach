import pytest


@pytest.mark.asyncio
async def test_suppress_email_flags_matching_contact(auth_client):
    create_resp = await auth_client.post(
        "/contacts", json={"email": "target@example.com", "first_name": "Target"}
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["is_suppressed"] is False

    suppress_resp = await auth_client.post(
        "/suppression", json={"email": "target@example.com", "reason": "manual_block"}
    )
    assert suppress_resp.status_code == 201

    get_resp = await auth_client.get(f"/contacts/{create_resp.json()['id']}")
    assert get_resp.json()["is_suppressed"] is True


@pytest.mark.asyncio
async def test_suppression_is_idempotent(auth_client):
    first = await auth_client.post("/suppression", json={"email": "dup@example.com"})
    second = await auth_client.post("/suppression", json={"email": "DUP@Example.com"})
    assert first.json()["id"] == second.json()["id"]

    listing = await auth_client.get("/suppression")
    assert listing.json()["total"] == 1


@pytest.mark.asyncio
async def test_bulk_suppress_contacts(auth_client):
    ids = []
    for i in range(3):
        resp = await auth_client.post("/contacts", json={"email": f"bulk{i}@example.com"})
        ids.append(resp.json()["id"])

    bulk_resp = await auth_client.post("/contacts/bulk-suppress", json={"contact_ids": ids})
    assert bulk_resp.status_code == 200
    assert bulk_resp.json() == {"suppressed": 3}

    for contact_id in ids:
        get_resp = await auth_client.get(f"/contacts/{contact_id}")
        assert get_resp.json()["is_suppressed"] is True
        assert get_resp.json()["status"] == "suppressed"

    listing = await auth_client.get("/suppression")
    assert listing.json()["total"] == 3


@pytest.mark.asyncio
async def test_delete_suppression_entry(auth_client):
    create_resp = await auth_client.post("/suppression", json={"email": "temp@example.com"})
    entry_id = create_resp.json()["id"]

    delete_resp = await auth_client.delete(f"/suppression/{entry_id}")
    assert delete_resp.status_code == 204

    listing = await auth_client.get("/suppression")
    assert listing.json()["total"] == 0
