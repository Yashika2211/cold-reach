import pytest


@pytest.mark.asyncio
async def test_create_get_update_delete_company(auth_client):
    create_resp = await auth_client.post("/companies", json={"name": "Acme Corp", "domain": "acme.com"})
    assert create_resp.status_code == 201
    company = create_resp.json()

    get_resp = await auth_client.get(f"/companies/{company['id']}")
    assert get_resp.status_code == 200

    update_resp = await auth_client.patch(
        f"/companies/{company['id']}", json={"research_summary": "Series B, hiring fast."}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["research_summary"] == "Series B, hiring fast."

    delete_resp = await auth_client.delete(f"/companies/{company['id']}")
    assert delete_resp.status_code == 204

    missing_resp = await auth_client.get(f"/companies/{company['id']}")
    assert missing_resp.status_code == 404


@pytest.mark.asyncio
async def test_list_companies_search(auth_client):
    await auth_client.post("/companies", json={"name": "Acme Corp", "domain": "acme.com"})
    await auth_client.post("/companies", json={"name": "Beta Inc", "domain": "beta.io"})

    resp = await auth_client.get("/companies", params={"search": "Acme"})
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["name"] == "Acme Corp"
