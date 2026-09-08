from pathlib import Path

import pytest

from app.core.config import get_settings


@pytest.mark.asyncio
async def test_create_get_update_delete(auth_client):
    create_resp = await auth_client.post(
        "/resume-variants",
        json={
            "name": "Backend/Data",
            "role_family": "data-engineering",
            "positioning_summary": "Ships production data pipelines.",
            "highlight_projects": ["Pipeline handling 40x traffic growth"],
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    variant = create_resp.json()
    assert variant["has_pdf"] is False

    get_resp = await auth_client.get(f"/resume-variants/{variant['id']}")
    assert get_resp.status_code == 200

    patch_resp = await auth_client.patch(
        f"/resume-variants/{variant['id']}", json={"positioning_summary": "Updated summary"}
    )
    assert patch_resp.json()["positioning_summary"] == "Updated summary"

    delete_resp = await auth_client.delete(f"/resume-variants/{variant['id']}")
    assert delete_resp.status_code == 204

    missing_resp = await auth_client.get(f"/resume-variants/{variant['id']}")
    assert missing_resp.status_code == 404


@pytest.mark.asyncio
async def test_setting_default_clears_other_defaults_in_same_role_family(auth_client):
    first = (
        await auth_client.post(
            "/resume-variants",
            json={"name": "SDE v1", "role_family": "swe", "is_default": True},
        )
    ).json()
    second = (
        await auth_client.post(
            "/resume-variants",
            json={"name": "SDE v2", "role_family": "swe", "is_default": True},
        )
    ).json()

    first_after = (await auth_client.get(f"/resume-variants/{first['id']}")).json()
    second_after = (await auth_client.get(f"/resume-variants/{second['id']}")).json()

    assert first_after["is_default"] is False
    assert second_after["is_default"] is True


@pytest.mark.asyncio
async def test_upload_and_download_pdf(auth_client):
    create_resp = await auth_client.post("/resume-variants", json={"name": "Test Resume"})
    variant_id = create_resp.json()["id"]

    fake_pdf_bytes = b"%PDF-1.4 fake pdf content for testing"
    upload_resp = await auth_client.post(
        f"/resume-variants/{variant_id}/upload",
        files={"file": ("resume.pdf", fake_pdf_bytes, "application/pdf")},
    )
    assert upload_resp.status_code == 200, upload_resp.text
    assert upload_resp.json()["has_pdf"] is True

    download_resp = await auth_client.get(f"/resume-variants/{variant_id}/file")
    assert download_resp.status_code == 200
    assert download_resp.content == fake_pdf_bytes

    Path(get_settings().resume_storage_dir, f"{variant_id}.pdf").unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_upload_rejects_non_pdf(auth_client):
    create_resp = await auth_client.post("/resume-variants", json={"name": "Test Resume"})
    variant_id = create_resp.json()["id"]

    upload_resp = await auth_client.post(
        f"/resume-variants/{variant_id}/upload",
        files={"file": ("resume.txt", b"not a pdf", "text/plain")},
    )
    assert upload_resp.status_code == 400
