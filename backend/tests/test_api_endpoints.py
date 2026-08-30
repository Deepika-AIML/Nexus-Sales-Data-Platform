"""
API endpoint tests using FastAPI's TestClient against a SQLite-backed
session (see conftest.py). These exercise the real upload -> profile ->
mapping -> confirm -> quality -> history -> download-report flow end to
end at the HTTP layer.

The `/api/process` endpoint's actual Bronze/Silver/Gold execution needs a
real PySpark + MySQL environment (see docker-compose.yml) and is NOT run
here — `test_process_start_schedules_background_job` monkeypatches the
heavy execution function to verify the API contract (validation, job
creation, response shape) without requiring Spark to be installed.
Run with: pytest tests/test_api_endpoints.py -v
"""
import io


def _upload_superstore(client, superstore_csv_bytes):
    files = {"file": ("Sample_-_Superstore.csv", io.BytesIO(superstore_csv_bytes), "text/csv")}
    resp = client.post("/api/upload", files=files)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_health_check(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_upload_rejects_non_csv(client):
    files = {"file": ("data.txt", io.BytesIO(b"hello"), "text/plain")}
    resp = client.post("/api/upload", files=files)
    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]


def test_upload_rejects_oversized_file(client):
    files = {"file": ("huge.csv", io.BytesIO(b"a" * (26 * 1024 * 1024)), "text/csv")}
    resp = client.post("/api/upload", files=files)
    assert resp.status_code == 400
    assert "25 MB" in resp.json()["detail"]


def test_full_workflow_upload_through_quality(client, superstore_df):
    csv_bytes = superstore_df.to_csv(index=False).encode("utf-8")
    uploaded = _upload_superstore(client, csv_bytes)
    dataset_id = uploaded["dataset_id"]
    assert uploaded["row_count"] == 9994

    profile_resp = client.get(f"/api/profile/{dataset_id}")
    assert profile_resp.status_code == 200
    assert profile_resp.json()["column_count"] == 21

    suggest_resp = client.post(f"/api/mapping/{dataset_id}")
    assert suggest_resp.status_code == 200
    suggestions = suggest_resp.json()["suggestions"]
    assert any(s["best_field"] == "sales" for s in suggestions)

    mappings = [
        {"source_column": s["source_column"], "canonical_field": s["best_field"]}
        for s in suggestions
    ]
    confirm_resp = client.post(f"/api/mapping/{dataset_id}/confirm", json={"mappings": mappings})
    assert confirm_resp.status_code == 200
    confirm_body = confirm_resp.json()
    assert confirm_body["can_proceed"] is True
    assert confirm_body["missing_required_fields"] == []

    quality_resp = client.get(f"/api/quality/{dataset_id}")
    assert quality_resp.status_code == 200
    assert quality_resp.json()["score_overall"] > 90

    history_resp = client.get("/api/history")
    assert history_resp.status_code == 200
    assert history_resp.json()["total"] >= 1


def test_dataset_not_found_returns_404(client):
    resp = client.get("/api/profile/does-not-exist")
    assert resp.status_code == 404


def test_process_blocked_when_sales_not_mapped(client, superstore_df):
    """Uploading a dataset with Sales removed and confirming a mapping
    that has no `sales` field must block processing with a clear message
    — without ever touching Spark."""
    reduced = superstore_df.drop(columns=["Sales"])
    csv_bytes = reduced.to_csv(index=False).encode("utf-8")
    uploaded = _upload_superstore(client, csv_bytes)
    dataset_id = uploaded["dataset_id"]

    suggest_resp = client.post(f"/api/mapping/{dataset_id}")
    suggestions = suggest_resp.json()["suggestions"]
    mappings = [
        {"source_column": s["source_column"], "canonical_field": s["best_field"]}
        for s in suggestions
    ]
    client.post(f"/api/mapping/{dataset_id}/confirm", json={"mappings": mappings})

    process_resp = client.post(f"/api/process/{dataset_id}", json={"write_to_mysql": False})
    assert process_resp.status_code == 422
    assert "sales" in process_resp.json()["detail"].lower()


def test_process_start_schedules_background_job(client, superstore_df, monkeypatch):
    """Verifies the orchestration contract (fast validation, job creation,
    background scheduling) without requiring a real PySpark/MySQL
    environment — the heavy execution function is replaced with a no-op."""
    from app.services import processing_service

    calls = []
    monkeypatch.setattr(
        processing_service, "execute_processing_job",
        lambda dataset_id, job_id, write_to_mysql=True: calls.append((dataset_id, job_id)),
    )

    csv_bytes = superstore_df.to_csv(index=False).encode("utf-8")
    uploaded = _upload_superstore(client, csv_bytes)
    dataset_id = uploaded["dataset_id"]

    suggest_resp = client.post(f"/api/mapping/{dataset_id}")
    suggestions = suggest_resp.json()["suggestions"]
    mappings = [
        {"source_column": s["source_column"], "canonical_field": s["best_field"]}
        for s in suggestions
    ]
    client.post(f"/api/mapping/{dataset_id}/confirm", json={"mappings": mappings})

    process_resp = client.post(f"/api/process/{dataset_id}", json={"write_to_mysql": False})
    assert process_resp.status_code == 202
    body = process_resp.json()
    assert body["status"] == "queued"
    assert len(calls) == 1
    assert calls[0][0] == dataset_id
