#!/usr/bin/env python3
"""Private localhost callback relay for a browser using a remote Gamma server.

Start the relay, then start ChatGPT sign-in from Gamma's connection form.
It accepts only attempts Gamma validates for the account in the supplied
protected credential file. OAuth tokens and PKCE stay on Gamma's server.
"""
import argparse
import html
import http.cookiejar
import http.server
import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request


class CallbackRejected(ValueError):
    pass


class GammaClient:
    def __init__(self, url, username, password):
        self.url = url.rstrip('/')
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.request('/api/login', {'username': username, 'password': password})

    def request(self, path, payload):
        request = urllib.request.Request(self.url + path, data=json.dumps(payload).encode(),
                                         headers={'Content-Type': 'application/json'})
        with self.opener.open(request, timeout=60) as response:
            return json.load(response)

    def finish_callback(self, callback):
        parsed = urllib.parse.urlsplit(callback)
        query = urllib.parse.parse_qs(parsed.query)
        if (parsed.path != '/auth/callback' or query.get('error')
                or len(query.get('state', [])) != 1 or len(query.get('code', [])) != 1):
            raise CallbackRejected('Missing or invalid sign-in response')
        state = query['state'][0]
        # Gamma checks the active attempt's state, expiry and account ownership.
        # A relay-created attempt and a later UI-created attempt are distinct;
        # validate against Gamma, never a stale state cached by the relay.
        active = self.request('/api/ai/oauth/chatgpt/status', {'state': state})
        if active.get('error'):
            raise CallbackRejected('This attempt is expired or belongs to another account')
        # Gamma validates state again and exchanges with its stored PKCE verifier.
        return self.request('/api/ai/oauth/chatgpt/complete', {
            'state': state, 'callback': callback, 'name': 'ChatGPT', 'models': '',
        })


def callback_handler(client, record):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Callback URLs contain credentials; never log them.

        def do_GET(self):
            path = urllib.parse.urlsplit(self.path).path
            if path == '/health':
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'ready')
                return
            if path != '/auth/callback':
                self.send_error(404)
                return
            try:
                client.finish_callback('http://localhost:1455' + self.path)
            except Exception:
                record('callback_rejected')
                code = 400
                body = ('<h1>Gamma could not complete this sign-in</h1>'
                        '<p>Return to Gamma and start a fresh ChatGPT sign-in from its connection form.</p>')
            else:
                record('connected', inference_verified=False)
                self.server.finished = True
                code = 200
                body = ('<h1>Gamma is connected to ChatGPT</h1><p>Return to '
                        f'<a href="{html.escape(client.url, quote=True)}">Gamma</a> and open your paper chat.</p>')
            self.send_response(code)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body.encode())
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials', type=Path, required=True,
                        help='Protected JSON file containing Gamma url, username and password')
    parser.add_argument('--status-file', type=Path)
    args = parser.parse_args()
    os.umask(0o077)

    def record(status, **fields):
        if args.status_file:
            args.status_file.write_text(json.dumps({'status': status, **fields}) + '\n')
            args.status_file.chmod(0o600)

    credentials = json.loads(args.credentials.read_text())
    client = GammaClient(credentials['url'], credentials['username'], credentials['password'])
    try:
        with http.server.HTTPServer(('127.0.0.1', 1455), callback_handler(client, record)) as server:
            server.timeout = 1
            server.finished = False
            record('waiting_for_gamma_ui_callback')
            deadline = time.monotonic() + 900
            while not server.finished and time.monotonic() < deadline:
                server.handle_request()
            if not server.finished:
                record('expired')
    finally:
        client.request('/api/logout', {})


if __name__ == '__main__':
    main()
