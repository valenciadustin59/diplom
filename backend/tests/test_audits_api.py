from uuid import UUID
def test_create_audit_returns_created_record(client, queued_audit_ids):
    response = client.post(
        '/audits',
        json={
            'query': 'buy plastic windows ekaterinburg',
            'target_url': 'https://example.com',
        },
    )
    assert response.status_code == 201
    payload = response.json()
    UUID(payload['id'])
    assert payload['query'] == 'buy plastic windows ekaterinburg'
    assert payload['target_url'] == 'https://example.com/'
    assert payload['top_n'] == 10
    assert payload['status'] == 'queued'
    assert payload['created_at']
    assert payload['target_fetch_status'] is None
    assert payload['warnings'] is None
    assert queued_audit_ids == [payload['id']]
def test_get_audit_returns_existing_record(client):
    created = client.post(
        '/audits',
        json={
            'query': 'plastic windows',
            'target_url': 'https://example.com',
        },
    )
    audit_id = created.json()['id']
    response = client.get(f'/audits/{audit_id}')
    assert response.status_code == 200
    payload = response.json()
    assert payload['id'] == audit_id
    assert payload['query'] == 'plastic windows'
    assert payload['target_url'] == 'https://example.com/'
    assert payload['top_n'] == 10
    assert payload['status'] == 'queued'
    assert payload['target_fetch_method'] is None
def test_list_audits_returns_created_items(client):
    client.post(
        '/audits',
        json={
            'query': 'seo audit',
            'target_url': 'https://example.com',
        },
    )
    response = client.get('/audits')
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) >= 1
    assert payload[0]['query'] == 'seo audit'
def test_get_audit_results_returns_structured_payload(client):
    created = client.post(
        '/audits',
        json={
            'query': 'seo audit',
            'target_url': 'https://example.com',
        },
    )
    audit_id = created.json()['id']
    response = client.get(f'/audits/{audit_id}/results')
    assert response.status_code == 200
    payload = response.json()
    assert payload['audit_id'] == audit_id
    assert payload['status'] == 'queued'
    assert payload['score'] is None
    assert payload['target_fetch_status'] is None
    assert payload['warnings'] is None
def test_get_audit_recommendations_returns_list(client):
    created = client.post(
        '/audits',
        json={
            'query': 'seo audit',
            'target_url': 'https://example.com',
        },
    )
    audit_id = created.json()['id']
    response = client.get(f'/audits/{audit_id}/recommendations')
    assert response.status_code == 200
    payload = response.json()
    assert payload['audit_id'] == audit_id
    assert payload['status'] == 'queued'
    assert payload['recommendations'] == []


def test_get_audit_events_returns_empty_timeline_for_new_audit(client):
    created = client.post(
        '/audits',
        json={
            'query': 'seo audit',
            'target_url': 'https://example.com',
        },
    )
    audit_id = created.json()['id']

    response = client.get(f'/audits/{audit_id}/events')

    assert response.status_code == 200
    assert response.json() == {
        'audit_id': audit_id,
        'processing_version': None,
        'events': [],
    }
def test_create_audit_runs_full_lifecycle_and_returns_completed_payloads(integration_client, monkeypatch):
    monkeypatch.setattr(
        'app.tasks.fetch_page',
        lambda url, use_browser=True: {
            'status': 'success',
            'fetch_method': 'http',
            'fetch_error_code': None,
            'fetch_error_message': None,
            'final_url': url,
            'http_status': 200,
            'html': '<html><body><h1>Title</h1><p>Body</p></body></html>',
            'text': 'Title Body',
        },
    )
    monkeypatch.setattr(
        'app.tasks.build_features',
        lambda html, text, query: {
            'text_length_chars': 10,
            'query_in_text': 1,
            'semantic_similarity': 0.81,
        },
    )
    monkeypatch.setattr(
        'app.tasks.explain_score',
        lambda features: {
            'final_score': 77.5,
            'rule_score': 74.0,
            'ml_score': 84.0,
            'methodology': '╨в╨╡╤Б╤В╨╛╨▓╨░╤П ╨╝╨╡╤В╨╛╨┤╨╛╨╗╨╛╨│╨╕╤П',
            'model_info': {'source': 'bootstrap'},
            'positives': [],
            'negatives': [],
            'factors': [],
        },
    )
    monkeypatch.setattr(
        'app.tasks.search_competitor_pages',
        lambda query, target_url, limit: [
            {
                'url': 'https://competitor-a.example',
                'domain': 'competitor-a.example',
                'title': 'Competitor A',
                'snippet': 'Snippet A',
                'rank': 1,
                'serp_page': 0,
            },
            {
                'url': 'https://competitor-b.example',
                'domain': 'competitor-b.example',
                'title': 'Competitor B',
                'snippet': 'Snippet B',
                'rank': 2,
                'serp_page': 0,
            },
        ],
    )
    monkeypatch.setattr(
        'app.tasks.analyze_competitor_page',
        lambda result, query: {
            'url': str(result['url']),
            'domain': str(result['domain']),
            'title': str(result['title']),
            'snippet': str(result['snippet']),
            'serp_rank': int(result['rank']),
            'serp_page': int(result['serp_page']),
            'fetch_status': 'success' if 'competitor-a' in str(result['url']) else 'failed',
            'fetch_method': 'http' if 'competitor-a' in str(result['url']) else 'browser',
            'fetch_error_code': None if 'competitor-a' in str(result['url']) else 'http_403',
            'fetch_error_message': None if 'competitor-a' in str(result['url']) else 'HTTP 403',
            'score': 82.4 if 'competitor-a' in str(result['url']) else None,
            'features': {
                'text_length_chars': 18,
                'query_in_text': 1,
                'semantic_similarity': 0.87,
            }
            if 'competitor-a' in str(result['url'])
            else None,
        },
    )
    monkeypatch.setattr(
        'app.tasks.build_comparison_summary',
        lambda user_features, user_score, competitor_results: {
            'user_score': 77.5,
            'competitors_average_score': 82.4,
            'score_difference': -4.9,
            'competitors_count': 1,
            'competitors_found': 2,
            'competitors_analyzed': 1,
            'competitors_failed': 1,
        },
    )
    monkeypatch.setattr(
        'app.tasks.generate_recommendations',
        lambda page_features, page_score, competitor_pages_features: [
            {
                'code': 'TEST_REC',
                'priority': 'medium',
                'message': 'Test recommendation',
            }
        ],
    )
    created = integration_client.post(
        '/audits',
        json={
            'query': 'seo audit',
            'target_url': 'https://example.com',
            'top_n': 5,
        },
    )
    assert created.status_code == 201
    created_payload = created.json()
    audit_id = created_payload['id']
    assert created_payload['status'] == 'queued'
    assert created_payload['score'] is None
    assert created_payload['target_fetch_status'] is None
    assert created_payload['failure_context'] is None
    assert created_payload['recommendations'] is None
    assert created_payload['warnings'] is None
    status_response = integration_client.get(f'/audits/{audit_id}')
    results_response = integration_client.get(f'/audits/{audit_id}/results')
    recommendations_response = integration_client.get(f'/audits/{audit_id}/recommendations')
    events_response = integration_client.get(f'/audits/{audit_id}/events')
    assert status_response.status_code == 200
    assert results_response.status_code == 200
    assert recommendations_response.status_code == 200
    assert events_response.status_code == 200
    status_payload = status_response.json()
    results_payload = results_response.json()
    recommendations_payload = recommendations_response.json()
    events_payload = events_response.json()
    assert status_payload['status'] == 'completed_with_warnings'
    assert status_payload['score'] == 77.5
    assert status_payload['comparison_summary']['competitors_found'] == 2
    assert results_payload['audit_id'] == audit_id
    assert results_payload['status'] == 'completed_with_warnings'
    assert results_payload['score_breakdown']['final_score'] == 77.5
    assert results_payload['features']['semantic_similarity'] == 0.81
    assert results_payload['target_fetch_method'] == 'http'
    assert len(results_payload['competitor_results']) == 2
    assert recommendations_payload == {
        'audit_id': audit_id,
        'status': 'completed_with_warnings',
        'recommendations': [
            {
                'code': 'TEST_REC',
                'priority': 'medium',
                'message': 'Test recommendation',
            }
        ],
        'failure_context': None,
        'error_message': None,
    }
    assert events_payload['audit_id'] == audit_id
    assert events_payload['processing_version'] == 1
    assert len(events_payload['events']) > 0
    assert events_payload['events'][0]['stage'] == 'pipeline'
    assert events_payload['events'][0]['event'] == 'started'
    assert any(event['stage'] == 'fetch' and event['event'] == 'started' for event in events_payload['events'])
    assert any(event['stage'] == 'fetch' and event['event'] == 'completed' and event['duration_ms'] is not None for event in events_payload['events'])
    assert any(event['event'] == 'dispatched' for event in events_payload['events'])
    assert any(event['stage'] == 'pipeline' and event['event'] == 'completed' for event in events_payload['events'])
def test_create_audit_runs_full_lifecycle_and_returns_failed_payloads(integration_client, monkeypatch):
    monkeypatch.setattr(
        'app.tasks.fetch_page',
        lambda url, use_browser=True: {
            'status': 'failed',
            'fetch_method': 'browser',
            'fetch_error_code': 'http_403',
            'fetch_error_message': 'HTTP 403',
            'final_url': url,
            'http_status': 403,
            'html': None,
            'text': None,
        },
    )
    created = integration_client.post(
        '/audits',
        json={
            'query': 'seo audit',
            'target_url': 'https://blocked.example.com',
        },
    )
    assert created.status_code == 201
    created_payload = created.json()
    audit_id = created_payload['id']
    assert created_payload['status'] == 'queued'
    assert created_payload['error_message'] is None
    assert created_payload['target_fetch_status'] is None
    assert created_payload['target_fetch_error_code'] is None
    assert created_payload['failure_context'] is None
    assert created_payload['score'] is None
    assert created_payload['recommendations'] is None
    status_response = integration_client.get(f'/audits/{audit_id}')
    results_response = integration_client.get(f'/audits/{audit_id}/results')
    recommendations_response = integration_client.get(f'/audits/{audit_id}/recommendations')
    assert status_response.status_code == 200
    assert results_response.status_code == 200
    assert recommendations_response.status_code == 200
    status_payload = status_response.json()
    results_payload = results_response.json()
    recommendations_payload = recommendations_response.json()
    assert status_payload['status'] == 'failed'
    assert status_payload['error_message'] == 'HTTP 403'
    assert status_payload['failure_context'] == {
        'stage': 'fetch',
        'code': 'http_403',
        'message': 'HTTP 403',
        'details': {
            'fetch_method': 'browser',
            'http_status': 403,
        },
    }
    assert results_payload == {
        'audit_id': audit_id,
        'status': 'failed',
        'score': None,
        'extracted_text': None,
        'features': None,
        'score_breakdown': None,
        'competitor_results': None,
        'comparison_summary': None,
        'target_fetch_status': 'failed',
        'target_fetch_method': 'browser',
        'target_fetch_error_code': 'http_403',
        'target_fetch_error_message': 'HTTP 403',
        'failure_context': {
            'stage': 'fetch',
            'code': 'http_403',
            'message': 'HTTP 403',
            'details': {
                'fetch_method': 'browser',
                'http_status': 403,
            },
        },
        'warnings': [],
        'error_message': 'HTTP 403',
    }
    assert recommendations_payload == {
        'audit_id': audit_id,
        'status': 'failed',
        'recommendations': [],
        'failure_context': {
            'stage': 'fetch',
            'code': 'http_403',
            'message': 'HTTP 403',
            'details': {
                'fetch_method': 'browser',
                'http_status': 403,
            },
        },
        'error_message': 'HTTP 403',
    }

def test_create_audit_returns_scoring_failure_context(integration_client, monkeypatch):
    from app.tasks import process_audit

    def inline_enqueue_ignore_failures(audit_id: str) -> None:
        try:
            process_audit.run(audit_id)
        except RuntimeError:
            pass

    monkeypatch.setattr('app.api.routes.audits.enqueue_audit_processing', inline_enqueue_ignore_failures)
    monkeypatch.setattr(
        'app.tasks.fetch_page',
        lambda url, use_browser=True: {
            'status': 'success',
            'fetch_method': 'http',
            'fetch_error_code': None,
            'fetch_error_message': None,
            'final_url': url,
            'http_status': 200,
            'html': '<html><body><h1>Title</h1><p>Body</p></body></html>',
            'text': 'Title Body',
        },
    )
    monkeypatch.setattr(
        'app.tasks.build_features',
        lambda html, text, query: {
            'text_length_chars': 10,
            'query_in_text': 1,
            'semantic_similarity': 0.81,
        },
    )
    def fail_scoring(features):
        raise RuntimeError('model calibration failed')
    monkeypatch.setattr('app.tasks.explain_score', fail_scoring)
    created = integration_client.post(
        '/audits',
        json={
            'query': 'seo audit',
            'target_url': 'https://example.com',
        },
    )
    assert created.status_code == 201
    audit_id = created.json()['id']
    status_response = integration_client.get(f'/audits/{audit_id}')
    results_response = integration_client.get(f'/audits/{audit_id}/results')
    recommendations_response = integration_client.get(f'/audits/{audit_id}/recommendations')
    assert status_response.status_code == 200
    assert results_response.status_code == 200
    assert recommendations_response.status_code == 200
    expected_failure_context = {
        'stage': 'scoring',
        'code': 'runtime_error',
        'message': 'model calibration failed',
        'details': None,
    }
    assert status_response.json()['failure_context'] == expected_failure_context
    assert status_response.json()['error_message'] == 'model calibration failed'
    assert results_response.json()['failure_context'] == expected_failure_context
    assert results_response.json()['error_message'] == 'model calibration failed'
    assert recommendations_response.json()['failure_context'] == expected_failure_context
    assert recommendations_response.json()['error_message'] == 'model calibration failed'


def test_create_audit_exposes_failed_timeline_for_exception_path(integration_client, monkeypatch):
    from app.tasks import process_audit

    def inline_enqueue_ignore_failures(audit_id: str) -> None:
        try:
            process_audit.run(audit_id)
        except RuntimeError:
            pass

    monkeypatch.setattr('app.api.routes.audits.enqueue_audit_processing', inline_enqueue_ignore_failures)
    monkeypatch.setattr(
        'app.tasks.fetch_page',
        lambda url, use_browser=True: {
            'status': 'success',
            'fetch_method': 'http',
            'fetch_error_code': None,
            'fetch_error_message': None,
            'final_url': url,
            'http_status': 200,
            'html': '<html><body><h1>Title</h1><p>Body</p></body></html>',
            'text': 'Title Body',
        },
    )
    monkeypatch.setattr(
        'app.tasks.build_features',
        lambda html, text, query: {
            'text_length_chars': 10,
            'query_in_text': 1,
            'semantic_similarity': 0.81,
        },
    )

    def fail_scoring(features):
        raise RuntimeError('model calibration failed')

    monkeypatch.setattr('app.tasks.explain_score', fail_scoring)

    created = integration_client.post(
        '/audits',
        json={
            'query': 'seo audit',
            'target_url': 'https://example.com',
        },
    )

    assert created.status_code == 201
    audit_id = created.json()['id']

    events_response = integration_client.get(f'/audits/{audit_id}/events')

    assert events_response.status_code == 200
    events_payload = events_response.json()
    assert events_payload['audit_id'] == audit_id
    assert events_payload['processing_version'] == 1
    assert events_payload['events'][0]['stage'] == 'pipeline'
    assert events_payload['events'][0]['event'] == 'started'
    assert any(
        event['stage'] == 'scoring'
        and event['event'] == 'failed'
        and event['duration_ms'] is not None
        for event in events_payload['events']
    )
    assert any(
        event['stage'] == 'pipeline'
        and event['event'] == 'failed'
        and event['details'] is not None
        and event['details'].get('failure_stage') == 'scoring'
        for event in events_payload['events']
    )
def test_create_audit_returns_search_failure_context(integration_client, monkeypatch):
    from app.tasks import process_audit

    def inline_enqueue_ignore_failures(audit_id: str) -> None:
        try:
            process_audit.run(audit_id)
        except RuntimeError:
            pass

    monkeypatch.setattr('app.api.routes.audits.enqueue_audit_processing', inline_enqueue_ignore_failures)
    monkeypatch.setattr(
        'app.tasks.fetch_page',
        lambda url, use_browser=True: {
            'status': 'success',
            'fetch_method': 'http',
            'fetch_error_code': None,
            'fetch_error_message': None,
            'final_url': url,
            'http_status': 200,
            'html': '<html><body><h1>Title</h1><p>Body</p></body></html>',
            'text': 'Title Body',
        },
    )
    monkeypatch.setattr(
        'app.tasks.build_features',
        lambda html, text, query: {
            'text_length_chars': 10,
            'query_in_text': 1,
            'semantic_similarity': 0.81,
        },
    )
    monkeypatch.setattr(
        'app.tasks.explain_score',
        lambda features: {
            'final_score': 77.5,
            'rule_score': 74.0,
            'ml_score': 84.0,
            'methodology': 'Test methodology',
            'model_info': {'source': 'bootstrap'},
            'positives': [],
            'negatives': [],
            'factors': [],
        },
    )
    def fail_search(query, target_url, limit):
        raise RuntimeError('SERP provider unavailable')
    monkeypatch.setattr('app.tasks.search_competitor_pages', fail_search)
    created = integration_client.post(
        '/audits',
        json={
            'query': 'seo audit',
            'target_url': 'https://example.com',
        },
    )
    assert created.status_code == 201
    audit_id = created.json()['id']
    status_response = integration_client.get(f'/audits/{audit_id}')
    results_response = integration_client.get(f'/audits/{audit_id}/results')
    recommendations_response = integration_client.get(f'/audits/{audit_id}/recommendations')
    expected_failure_context = {
        'stage': 'search',
        'code': 'runtime_error',
        'message': 'SERP provider unavailable',
        'details': None,
    }
    assert status_response.json()['failure_context'] == expected_failure_context
    assert status_response.json()['error_message'] == 'SERP provider unavailable'
    assert results_response.json()['failure_context'] == expected_failure_context
    assert results_response.json()['error_message'] == 'SERP provider unavailable'
    assert recommendations_response.json()['failure_context'] == expected_failure_context
    assert recommendations_response.json()['error_message'] == 'SERP provider unavailable'
def test_get_audit_returns_404_for_unknown_id(client):
    response = client.get('/audits/0fd2bce7-8f57-417f-9f62-3aebf7cc4da8')
    assert response.status_code == 404
    assert response.json() == {'detail': '\u0410\u0443\u0434\u0438\u0442 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d'}
def test_create_audit_rejects_empty_query(client):
    response = client.post(
        '/audits',
        json={
            'query': '   ',
            'target_url': 'https://example.com',
        },
    )
    assert response.status_code == 422
def test_create_audit_rejects_invalid_url(client):
    response = client.post(
        '/audits',
        json={
            'query': 'plastic windows',
            'target_url': 'not-a-url',
        },
    )
    assert response.status_code == 422
