"""Database-backed API tests for batch results, export, and history.

Skipped automatically when ``TEST_DATABASE_URL`` is unset (see conftest.py).
Run locally against the Docker MySQL with::

    docker-compose up -d
    set TEST_DATABASE_URL=mysql+pymysql://ipo_user:ipo_password@localhost:3306/ipo_checker
    venv\\Scripts\\python.exe -m pytest tests/test_results_api.py -v
"""

from datetime import datetime

from api import security
from db.models import (
    AllotmentResult,
    Client,
    IPO,
    IPOStatus,
    Registrar,
    ResultStatus,
    UploadBatch,
)

AUTH = None  # built lazily so a missing DB never blocks token creation


def auth_headers():
    global AUTH
    if AUTH is None:
        AUTH = {"Authorization": f"Bearer {security.create_access_token()}"}
    return AUTH


def _seed_batch(db) -> int:
    """Create one fully-linked allotted result and return its batch id."""
    registrar = Registrar(
        name="KFin Technologies", priority=1, endpoint_type="api", active=True
    )
    client = Client(name="Test Client", pan="ABCDE1234F", client_code="CL001")
    ipo = IPO(name="Test IPO Ltd", status=IPOStatus.Closed)

    db.add_all([registrar, client, ipo])
    db.flush()

    batch = UploadBatch(
        file_name="test.xlsx",
        row_count=1,
        valid_row_count=1,
        invalid_row_count=0,
        status="Completed",
    )
    db.add(batch)
    db.flush()

    db.add(
        AllotmentResult(
            client_id=client.id,
            ipo_id=ipo.id,
            batch_id=batch.id,
            registrar_id=registrar.id,
            status=ResultStatus.Allotted,
            checked_at=datetime.utcnow(),
            served_from_cache=False,
        )
    )
    db.commit()
    return batch.id


def test_summary_counts_statuses(db_client, db_session):
    batch_id = _seed_batch(db_session)

    res = db_client.get(
        f"/api/results/batch/{batch_id}/summary", headers=auth_headers()
    )

    assert res.status_code == 200
    body = res.json()
    assert body["total_processed"] == 1
    assert body["allotted"] == 1
    assert body["not_allotted"] == 0
    assert body["errors"] == 0


def test_summary_404_for_missing_batch(db_client):
    res = db_client.get("/api/results/batch/9999/summary", headers=auth_headers())

    assert res.status_code == 404


def test_results_json_masks_full_pan(db_client, db_session):
    batch_id = _seed_batch(db_session)

    res = db_client.get(f"/api/results/batch/{batch_id}", headers=auth_headers())

    assert res.status_code == 200
    rows = res.json()["data"]
    assert rows[0]["pan"] == "***234F"
    # A raw PAN must never leak through the JSON API.
    assert "ABCDE1234F" not in res.text


def test_export_returns_an_xlsx_attachment(db_client, db_session):
    batch_id = _seed_batch(db_session)

    res = db_client.get(
        f"/api/results/batch/{batch_id}/export", headers=auth_headers()
    )

    assert res.status_code == 200
    assert res.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert f"IPO_Results_Batch_{batch_id}.xlsx" in res.headers["content-disposition"]
    assert len(res.content) > 0


def test_export_404_for_missing_batch(db_client):
    res = db_client.get("/api/results/batch/9999/export", headers=auth_headers())

    assert res.status_code == 404


def test_history_lists_completed_batches(db_client, db_session):
    batch_id = _seed_batch(db_session)

    res = db_client.get("/api/history/batches", headers=auth_headers())

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["data"][0]["id"] == batch_id
    assert body["data"][0]["file_name"] == "test.xlsx"
