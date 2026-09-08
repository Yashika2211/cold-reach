import pytest
from sqlalchemy import select

from app.models import Contact

MAPPING = {
    "first_name": "First Name",
    "last_name": "Last Name",
    "email": "Email",
    "title": "Title",
    "company_name": "Company",
    "linkedin_url": None,
    "notes": None,
}


def build_csv(n_unique: int = 42) -> str:
    """A 50-row CSV: n_unique fresh rows, 3 in-file duplicates of earlier rows, and 5
    malformed rows (missing email / invalid email format)."""
    header = "First Name,Last Name,Email,Title,Company"
    lines = [header]

    unique_rows = []
    for i in range(n_unique):
        row = f"Person{i},Test,person{i}@example{i}.com,Recruiter,Company{i}"
        unique_rows.append(row)
        lines.append(row)

    # 3 deliberate duplicates of earlier rows
    lines.append(unique_rows[0])
    lines.append(unique_rows[5])
    lines.append(unique_rows[10])

    # 5 deliberate malformed rows
    lines.append("NoEmail,Person,,Recruiter,BadCo")  # missing email
    lines.append("Bad,Format,not-an-email,Recruiter,BadCo")  # no @-sign
    lines.append("Bad,Domain,someone@,Recruiter,BadCo")  # no domain
    lines.append(",,,,")  # entirely blank row
    lines.append("Another,Bad,also-not-an-email,Recruiter,BadCo")

    csv_text = "\n".join(lines) + "\n"
    assert len(lines) - 1 == 50  # 50 data rows, not counting the header
    return csv_text


@pytest.mark.asyncio
async def test_import_50_row_csv_with_duplicates_and_malformed_rows(auth_client, db_session):
    csv_text = build_csv()

    parse_resp = await auth_client.post("/contacts/import/parse-text", json={"text": csv_text})
    assert parse_resp.status_code == 200, parse_resp.text
    parsed = parse_resp.json()
    assert parsed["row_count"] == 50
    assert parsed["suggested_mapping"]["email"] == "Email"
    token = parsed["import_token"]

    preview_resp = await auth_client.post(
        "/contacts/import/preview", json={"import_token": token, "mapping": MAPPING}
    )
    assert preview_resp.status_code == 200, preview_resp.text
    preview = preview_resp.json()

    assert preview["summary"] == {"create": 42, "skip_duplicate": 3, "error": 5}

    error_reasons = {r["row_number"]: r["error"] for r in preview["results"] if r["action"] == "error"}
    assert len(error_reasons) == 5

    commit_resp = await auth_client.post(
        "/contacts/import/commit", json={"import_token": token, "mapping": MAPPING}
    )
    assert commit_resp.status_code == 200, commit_resp.text
    commit = commit_resp.json()

    assert commit["created"] == 42
    assert commit["skipped_duplicate"] == 3
    assert commit["skipped_invalid"] == 5
    assert len(commit["errors"]) == 5

    # correct rows actually landed in the database
    result = await db_session.execute(select(Contact))
    contacts = result.scalars().all()
    assert len(contacts) == 42
    assert {c.email for c in contacts} == {f"person{i}@example{i}.com" for i in range(42)}

    # the import token is single-use: it should be gone after commit
    replay_resp = await auth_client.post(
        "/contacts/import/preview", json={"import_token": token, "mapping": MAPPING}
    )
    assert replay_resp.status_code == 404


@pytest.mark.asyncio
async def test_reimporting_same_csv_skips_everything_as_duplicate(auth_client, db_session):
    csv_text = build_csv()

    async def do_import():
        parse_resp = await auth_client.post("/contacts/import/parse-text", json={"text": csv_text})
        token = parse_resp.json()["import_token"]
        return await auth_client.post(
            "/contacts/import/commit", json={"import_token": token, "mapping": MAPPING}
        )

    first = await do_import()
    assert first.json()["created"] == 42

    second = await do_import()
    body = second.json()
    assert body["created"] == 0
    assert body["skipped_duplicate"] == 45  # 42 unique + 3 in-file duplicates, all now in DB
    assert body["skipped_invalid"] == 5


@pytest.mark.asyncio
async def test_import_respects_row_cap(auth_client):
    header = "First Name,Last Name,Email,Title,Company\n"
    rows = "\n".join(f"P{i},T,p{i}@example.com,Recruiter,Co{i}" for i in range(2001))
    huge_csv = header + rows

    response = await auth_client.post("/contacts/import/parse-text", json={"text": huge_csv})
    assert response.status_code == 400
    assert "2000" in response.text
