from uuid import UUID


def test_create_audit_returns_created_record(client, queued_audit_ids):
    response = client.post(
        "/audits",
        json={
            "query": "buy plastic windows ekaterinburg",
            "target_url": "https://example.com",
        },
    )

    assert response.status_code == 201
    payload = response.json()

    UUID(payload["id"])
    assert payload["query"] == "buy plastic windows ekaterinburg"
    assert payload["target_url"] == "https://example.com/"
    assert payload["top_n"] == 10
    assert payload["status"] == "queued"
    assert payload["created_at"]
    assert payload["target_fetch_status"] is None
    assert payload["warnings"] is None
    assert queued_audit_ids == [payload["id"]]


def test_get_audit_returns_existing_record(client):
    created = client.post(
        "/audits",
        json={
            "query": "plastic windows",
            "target_url": "https://example.com",
        },
    )
    audit_id = created.json()["id"]

    response = client.get(f"/audits/{audit_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == audit_id
    assert payload["query"] == "plastic windows"
    assert payload["target_url"] == "https://example.com/"
    assert payload["top_n"] == 10
    assert payload["status"] == "queued"
    assert payload["target_fetch_method"] is None


def test_list_audits_returns_created_items(client):
    client.post(
        "/audits",
        json={
            "query": "seo audit",
            "target_url": "https://example.com",
        },
    )

    response = client.get("/audits")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) >= 1
    assert payload[0]["query"] == "seo audit"


def test_get_audit_results_returns_structured_payload(client):
    created = client.post(
        "/audits",
        json={
            "query": "seo audit",
            "target_url": "https://example.com",
        },
    )
    audit_id = created.json()["id"]

    response = client.get(f"/audits/{audit_id}/results")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_id"] == audit_id
    assert payload["status"] == "queued"
    assert payload["score"] is None
    assert payload["target_fetch_status"] is None
    assert payload["warnings"] is None


def test_get_audit_recommendations_returns_list(client):
    created = client.post(
        "/audits",
        json={
            "query": "seo audit",
            "target_url": "https://example.com",
        },
    )
    audit_id = created.json()["id"]

    response = client.get(f"/audits/{audit_id}/recommendations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_id"] == audit_id
    assert payload["status"] == "queued"
    assert payload["recommendations"] == []


def test_get_audit_returns_404_for_unknown_id(client):
    response = client.get("/audits/0fd2bce7-8f57-417f-9f62-3aebf7cc4da8")

    assert response.status_code == 404
    assert response.json() == {"detail": "Аудит не найден"}


def test_create_audit_rejects_empty_query(client):
    response = client.post(
        "/audits",
        json={
            "query": "   ",
            "target_url": "https://example.com",
        },
    )

    assert response.status_code == 422


def test_create_audit_rejects_invalid_url(client):
    response = client.post(
        "/audits",
        json={
            "query": "plastic windows",
            "target_url": "not-a-url",
        },
    )

    assert response.status_code == 422
