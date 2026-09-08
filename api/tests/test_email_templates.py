import pytest


@pytest.mark.asyncio
async def test_crud_lifecycle(auth_client):
    create_resp = await auth_client.post(
        "/email-templates",
        json={
            "name": "Cold outreach - engineering",
            "subject_skeleton": "{company} + {name}",
            "body_skeleton": "Hi {name}, ...",
            "llm_instructions": "Keep it casual.",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    template_id = create_resp.json()["id"]

    list_resp = await auth_client.get("/email-templates")
    assert len(list_resp.json()) == 1

    patch_resp = await auth_client.patch(
        f"/email-templates/{template_id}", json={"llm_instructions": "Be more formal."}
    )
    assert patch_resp.json()["llm_instructions"] == "Be more formal."

    delete_resp = await auth_client.delete(f"/email-templates/{template_id}")
    assert delete_resp.status_code == 204

    missing_resp = await auth_client.get(f"/email-templates/{template_id}")
    assert missing_resp.status_code == 404
