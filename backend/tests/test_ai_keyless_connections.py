"""Configurable endpoints exercise Gamma's real catalog and inference transports."""
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import login, make_user


@pytest.fixture
def account(client):
    name = 'keyless_' + uuid.uuid4().hex[:10]
    make_user(name, 'test-only-password')
    return name, login(name, 'test-only-password')


@pytest.fixture
def endpoint():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, value, status=200):
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(value).encode())

        def do_GET(self):
            calls.append((self.path, dict(self.headers), None))
            self.reply({'data': [{'id': 'local-model'}, {'id': 'another-model'}], 'has_more': False})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append((self.path, dict(self.headers), body))
            if self.path == '/v1/messages':
                self.reply({'content': [{'type': 'text', 'text': 'ok'}], 'stop_reason': 'end_turn',
                            'usage': {'input_tokens': 1, 'output_tokens': 1}})
            elif self.path == '/v1/chat/completions':
                self.reply({'choices': [{'message': {'content': 'ok'}, 'finish_reason': 'stop'}],
                            'usage': {'prompt_tokens': 1, 'completion_tokens': 1}})
            else:
                self.reply({'error': {'message': 'unknown protocol'}}, 404)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', calls
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


@pytest.mark.parametrize('protocol', ['openai', 'anthropic'])
@pytest.mark.parametrize('no_auth', [True, False])
def test_catalog_probe_and_saved_configuration(account, endpoint, protocol, no_auth):
    name, user = account
    base, calls = endpoint
    fields = {'protocol': protocol, 'base_url': base + ('/v1' if protocol == 'openai' else ''),
              'no_auth': no_auth, 'models': 'manual-model', 'name': 'My endpoint'}
    if not no_auth:
        fields['api_key'] = 'test-only-upstream-key'
    listing = user.post('/api/ai/model-catalog', json={k: v for k, v in fields.items() if k not in ('models', 'name')})
    assert listing.status_code == 200, listing.text
    assert set(listing.json()['models']) == {'local-model', 'another-model'}
    saved = user.post('/api/ai/providers', json=fields)
    assert saved.status_code == 200, saved.text
    entry = saved.json()['providers'][0]
    assert entry['no_auth'] is no_auth
    assert entry['base_url'] == fields['base_url']
    assert 'test-only-upstream-key' not in saved.text
    # A fresh login reloads the persisted per-account connection and model.
    fresh = login(name, 'test-only-password')
    assert fresh.get('/api/ai/settings').json()['providers'][0] == entry
    assert fresh.get('/api/ai/models').json()['models'][0]['model'] == 'manual-model'
    listing = fresh.post('/api/ai/model-catalog', json={'provider_id': entry['id']})
    assert listing.status_code == 200, listing.text
    probe = fresh.post(f"/api/ai/providers/{entry['id']}/test")
    assert probe.status_code == 200 and probe.json()['ok'], probe.text
    inference = [c for c in calls if c[2] is not None]
    assert inference and inference[-1][2]['model'] == 'manual-model'
    assert inference[-1][0] == ('/v1/chat/completions' if protocol == 'openai' else '/v1/messages')
    for _, headers, _ in calls:
        lowered = {k.lower(): v for k, v in headers.items()}
        if no_auth:
            assert 'authorization' not in lowered and 'x-api-key' not in lowered
        else:
            assert lowered.get('authorization' if protocol == 'openai' else 'x-api-key') == (
                'Bearer test-only-upstream-key' if protocol == 'openai' else 'test-only-upstream-key')


def test_keyless_never_falls_back_to_a_default_provider(account):
    _, user = account
    for base in ('', None):
        fields = {'protocol': 'openai', 'no_auth': True, 'base_url': base, 'models': 'local-model'}
        assert user.post('/api/ai/providers', json=fields).status_code == 400
        assert user.post('/api/ai/model-catalog', json=fields).status_code == 400
    assert user.get('/api/ai/settings').json()['providers'] == []
    assert user.post('/api/ai/providers', json={'protocol': 'openai', 'base_url': 'http://127.0.0.1:1'}).status_code == 400
    assert user.post('/api/ai/providers', json={'protocol': 'chatgpt', 'no_auth': True, 'base_url': 'http://127.0.0.1:1'}).status_code == 400


def test_switching_auth_modes_forgets_the_old_key_and_requires_a_new_one(account, endpoint):
    _, user = account
    base, _ = endpoint
    entry = user.post('/api/ai/providers', json={
        'protocol': 'openai', 'base_url': base, 'api_key': 'test-only-original-key', 'models': 'local-model',
    }).json()['providers'][0]
    path = '/api/ai/providers/' + entry['id']
    changed = user.put(path, json={'no_auth': True}).json()['providers'][0]
    assert changed['no_auth'] is True and not changed['key_hint']
    # No forgotten key can silently return when switching authentication on.
    assert user.put(path, json={'no_auth': False}).status_code == 400
    assert user.get('/api/ai/settings').json()['providers'][0]['no_auth'] is True
    assert user.put(path, json={'base_url': ''}).status_code == 400
    restored = user.put(path, json={'no_auth': False, 'api_key': 'test-only-replacement-key'})
    assert restored.status_code == 200 and restored.json()['providers'][0]['no_auth'] is False


def test_keyless_configuration_is_per_account_and_shared_entries_work(account, endpoint):
    _, user = account
    base, _ = endpoint
    fields = {'protocol': 'openai', 'no_auth': True, 'base_url': base, 'models': 'local-model'}
    assert user.post('/api/ai/providers', json=fields).status_code == 200
    name = 'keyless_admin_' + uuid.uuid4().hex[:8]
    make_user(name, 'test-only-password', is_admin=1)
    admin = login(name, 'test-only-password')
    assert admin.get('/api/ai/settings').json()['providers'] == []
    result = admin.post('/api/admin/ai-providers', json={**fields, 'access': {'who': 'selected', 'users': [], 'guests': False}})
    assert result.status_code == 200, result.text
    entry = result.json()['providers'][0]
    assert entry['no_auth'] is True
    probe = admin.post(f"/api/ai/providers/{entry['id']}/test")
    assert probe.json()['ok'], probe.text
    # Remove the shared test connection so later tests have no global configuration.
    assert admin.delete('/api/admin/ai-providers/' + entry['id']).status_code == 200
