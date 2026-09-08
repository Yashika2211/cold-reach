import pytest


@pytest.mark.asyncio
async def test_create_get_update_delete_contact(auth_client):
    create_resp = await auth_client.post(
        "/contacts",
        json={"email": "jane.doe@example.com", "first_name": "Jane", "last_name": "Doe"},
    )
    assert create_resp.status_code == 201
    contact = create_resp.json()
    assert contact["normalized_email"] == "jane.doe@example.com"
    assert contact["source"] == "manual"

    get_resp = await auth_client.get(f"/contacts/{contact['id']}")
    assert get_resp.status_code == 200

    update_resp = await auth_client.patch(f"/contacts/{contact['id']}", json={"title": "CTO"})
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "CTO"

    delete_resp = await auth_client.delete(f"/contacts/{contact['id']}")
    assert delete_resp.status_code == 204

    missing_resp = await auth_client.get(f"/contacts/{contact['id']}")
    assert missing_resp.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_email_rejected(auth_client):
    payload = {"email": "same@example.com", "first_name": "First"}
    first = await auth_client.post("/contacts", json=payload)
    assert first.status_code == 201

    second = await auth_client.post("/contacts", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_list_contacts_filters_by_status_and_search(auth_client):
    await auth_client.post("/contacts", json={"email": "alice@acme.com", "first_name": "Alice"})
    await auth_client.post("/contacts", json={"email": "bob@acme.com", "first_name": "Bob"})

    search_resp = await auth_client.get("/contacts", params={"search": "Alice"})
    assert search_resp.json()["total"] == 1
    assert search_resp.json()["items"][0]["first_name"] == "Alice"

    status_resp = await auth_client.get("/contacts", params={"status": "new"})
    assert status_resp.json()["total"] == 2
