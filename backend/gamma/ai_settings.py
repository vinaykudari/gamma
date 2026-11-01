"""AI provider entries (GUI-managed API keys): each account's own, and the
server's shared ones.

Users manage a LIST of provider entries (Settings → AI → Connections), each:
  {"id", "name", "protocol": a key of ai_protocols.PROTOCOLS, "api_key" (or
   "oauth" tokens for a sign-in protocol), "base_url": "" = protocol default,
   "models": "a, b" = comma list ("" = none offered yet), "test_model",
   "created_at"}

Entries live in users.db `user_prefs` under the account-wide reserved
`ai-settings` key, which the generic /api/prefs endpoints refuse to serve: the
only read path is the masked GET /api/ai/settings (last 4 characters, never
the key itself). There is no env key.

Admins may add SHARED entries (Settings → Server → Shared AI provider,
/api/admin/ai-providers*): the same shape — an API key, or a ChatGPT
sign-in made through /api/admin/ai-providers/chatgpt/* — ids namespaced
``server:<id>`` so they never collide with an account's, each with an
``access`` saying who may use it ({"who": "everyone" | "selected", "users":
[account ids], "guests": bool}). They live in the users.db `settings` KV
under `ai_providers` as
{"providers": [...], "allowance": {"accounts": N, "guests": N}},
each api_key and each sign-in's tokens Fernet-encrypted with the data
directory's key (the cloud client secret's scheme); a shared sign-in's
tokens are refreshed under that entry's own lock and written back to the
KV. ai_runtime() offers an account the entries whose access admits it,
after its own (shared_access). The allowance meters them per account over
a rolling 24 hours (tokens, 0 = unlimited; guests and other accounts each
have their own limit): ai_runtime() reports it and marks the shared
provider confs so ai_client.open_ai refuses a call once it is used up
(docs/dev/guests.md).
"""

import json
import re
import secrets
import sqlite3
import threading
import time

from cryptography.fernet import InvalidToken
from fastapi import HTTPException

from . import ai_protocols, ai_usage
from .chatgpt_oauth import RefreshUnavailable
from .db import connect_users_db, get_pref, page_now, set_pref, update_pref
from .logbuf import log
from .publisher_sessions import cipher
from .server_settings import _get_raw, _set_raw

AI_SETTINGS_PREF_KEY = "ai-settings"

MAX_KEY_LEN = 512
MAX_URL_LEN = 300
MAX_MODELS_LEN = 1000
MAX_NAME_LEN = 60
MAX_PROVIDERS = 20


def _entries_of(value) -> list:
    entries = value.get("providers") if isinstance(value, dict) else None
    return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


def load_provider_entries(user_id: str) -> list:
    return _entries_of(get_pref(user_id, AI_SETTINGS_PREF_KEY)[0])


def save_provider_entries(user_id: str, entries: list):
    """Replace the whole list. Edits go through update_provider_entries."""
    set_pref(user_id, AI_SETTINGS_PREF_KEY, {"providers": entries})


def update_provider_entries(user_id: str, change) -> list:
    """Read-modify-write the account's entries in one transaction
    (db.update_pref): ``change(entries)`` edits the list in place and may
    raise to abort. A list read before a slow call (a sign-in's token
    exchange) is never saved back over a change made meanwhile. Returns the
    saved list."""
    def apply(value):
        entries = _entries_of(value)
        change(entries)
        return {"providers": entries}
    return update_pref(user_id, AI_SETTINGS_PREF_KEY, apply)["providers"]


def new_provider_id() -> str:
    return secrets.token_urlsafe(6)


# --- validation, shared by /api/ai/providers* and /api/admin/ai-providers* ----

def is_oauth_protocol(protocol) -> bool:
    """Sign-in protocols (ChatGPT) hold OAuth tokens instead of an API key."""
    proto = ai_protocols.PROTOCOLS.get(protocol)
    return bool(proto) and proto.auth == "oauth"


def apply_provider_fields(entry: dict, fields) -> None:
    """Validate + copy the editable fields of a provider entry in place.
    ``fields`` has ``name``, ``api_key``, ``base_url``, ``models`` and
    ``test_model`` attributes (the request model); None leaves a field."""
    oauth_entry = is_oauth_protocol(entry.get("protocol"))
    if fields.name is not None:
        entry["name"] = str(fields.name).strip()[:MAX_NAME_LEN]
    # OAuth secrets and endpoints are owned by the sign-in flow. In
    # particular, accepting an arbitrary base URL here would let a crafted API
    # request redirect the bearer token on the next model or usage call.
    if fields.api_key and not oauth_entry:  # never clears; delete the entry to drop a key
        key = str(fields.api_key).strip()
        if not key or len(key) > MAX_KEY_LEN or any(c.isspace() for c in key):
            raise HTTPException(status_code=400, detail="invalid API key")
        entry["api_key"] = key
    if fields.base_url is not None and not oauth_entry:
        url = str(fields.base_url).strip().rstrip("/")
        if (url and not re.match(r"^https?://", url)) or len(url) > MAX_URL_LEN:
            raise HTTPException(status_code=400, detail="base URL must start with http(s)://")
        entry["base_url"] = url
    if not oauth_entry:
        no_auth = getattr(fields, "no_auth", None)
        if no_auth is not None:
            entry["no_auth"] = no_auth
        if entry.get("no_auth") is True:
            if not entry.get("base_url"):
                raise HTTPException(status_code=400, detail="a base URL is required without authentication")
            # Switching to keyless mode forgets the previous credential.
            entry["api_key"] = ""
        elif no_auth is False and not entry.get("api_key"):
            raise HTTPException(status_code=400, detail="API key required")
    if fields.models is not None:
        models = str(fields.models).strip()
        if len(models) > MAX_MODELS_LEN:
            raise HTTPException(status_code=400, detail="model list too long")
        entry["models"] = models
    if fields.test_model is not None:
        test_model = str(fields.test_model).strip()
        if len(test_model) > 100:
            raise HTTPException(status_code=400, detail="test model name too long")
        entry["test_model"] = test_model


def new_key_entry(fields, entry_id: str) -> dict:
    """A new API-key entry from an add request (``fields.protocol`` plus the
    editable fields); 400 on a sign-in or unknown protocol or a missing key."""
    if fields.protocol not in ai_protocols.PROTOCOLS or is_oauth_protocol(fields.protocol):
        raise HTTPException(status_code=400, detail="unknown protocol")
    if not (fields.api_key or "").strip() and not getattr(fields, "no_auth", False):
        raise HTTPException(status_code=400, detail="API key required")
    entry = {"id": entry_id, "protocol": fields.protocol,
             "name": "", "api_key": "", "base_url": "", "models": "",
             "created_at": page_now()}
    apply_provider_fields(entry, fields)
    return entry


def update_entry(entry: dict, fields) -> None:
    """Apply an edit request to a saved entry. A protocol change never
    crosses the key/OAuth boundary: it is refused outright rather than
    ignored, so the other fields of such a request (reset for the new
    service) don't land on the old entry."""
    if fields.protocol and fields.protocol != entry.get("protocol"):
        if fields.protocol not in ai_protocols.PROTOCOLS:
            raise HTTPException(status_code=400, detail="unknown protocol")
        if is_oauth_protocol(fields.protocol) != is_oauth_protocol(entry.get("protocol")):
            raise HTTPException(status_code=400,
                                detail="a sign-in connection and an API-key connection can't be "
                                       "switched into each other — add a new connection instead")
        entry["protocol"] = fields.protocol
    apply_provider_fields(entry, fields)


def mask_entry(entry: dict, hint: bool = True) -> dict:
    """What the browser may see of an entry: never the key or the tokens.
    ``hint`` = the key's last 4 characters (off for a shared entry shown to
    someone who is not an admin)."""
    key = (entry.get("api_key") or "").strip()
    oauth = entry.get("oauth") if isinstance(entry.get("oauth"), dict) else {}
    return {
        "id": entry.get("id") or "",
        "name": (entry.get("name") or "").strip(),
        "label": provider_label(entry),  # name, else the service / protocol label
        "protocol": entry.get("protocol") or "",
        # Enough to recognize the key, never enough to use it.
        "key_hint": (f"…{key[-4:]}" if len(key) >= 12 else ("set" if key else "")) if hint else "",
        "no_auth": not is_oauth_protocol(entry.get("protocol")) and entry.get("no_auth") is True,
        "base_url": (entry.get("base_url") or "").strip(),
        "models": (entry.get("models") or "").strip(),
        "test_model": (entry.get("test_model") or "").strip(),
        "created_at": entry.get("created_at") or "",
        # ChatGPT sign-in entries: connection status + account label only,
        # never the tokens themselves.
        "oauth_connected": bool(oauth.get("access_token")),
        # The signed-in account's e-mail: like the key hint, not for someone
        # who sees a shared sign-in without being an admin.
        "account": (oauth.get("email") or "") if hint else "",
    }


def protocol_choices() -> dict:
    """What the settings form offers: the protocols (auth "oauth" = sign-in
    entries, no API key field) and the named services."""
    protocols = [{"id": pid, "label": proto.label, "default_base_url": proto.base_url, "auth": proto.auth,
                  "key_placeholder": proto.key_placeholder, "key_url": proto.key_url}
                 for pid, proto in ai_protocols.PROTOCOLS.items()]
    return {"protocols": protocols, "services": ai_protocols.SERVICES}


# --- the server's shared entries ----------------------------------------------

SERVER_AI_KEY = "ai_providers"  # the users.db `settings` KV key
SERVER_ID_PREFIX = ai_usage.SHARED_PREFIX  # "server:"
# The shared allowance's ceiling (tokens per account per 24 h): far beyond
# any real day, low enough to stay a sane integer everywhere.
ALLOWANCE_MAX = 1_000_000_000
_server_lock = threading.Lock()

# Who may use a shared entry, its ``access``: {"who": "everyone" |
# "selected", "users": [account ids], "guests": bool}. "everyone" is every
# account, the guest accounts too when ``guests`` is on; "selected" is the
# listed accounts alone (a guest is never one, and the list is kept only
# under "selected"). An administrator always has access: the Server
# section tests, lists the models of and asks usage of every shared entry
# through the admin's own runtime.
ACCESS_WHO = ("everyone", "selected")
MAX_ACCESS_USERS = 500


def default_access(guests: bool = False) -> dict:
    return {"who": "everyone", "users": [], "guests": bool(guests)}


def _clean_access(value, legacy_guests: bool = False) -> dict:
    """A stored access object as a clean one. An entry without one was
    written when access was one server-wide guest switch: it takes that
    switch's value, so an upgrade changes nobody's access."""
    if not isinstance(value, dict):
        return default_access(legacy_guests)
    who = value.get("who") if value.get("who") in ACCESS_WHO else "everyone"
    users = value.get("users") if isinstance(value.get("users"), list) else []
    users = [u for u in users if isinstance(u, str) and u][:MAX_ACCESS_USERS] if who == "selected" else []
    return {"who": who, "users": users, "guests": who == "everyone" and value.get("guests") is True}


def is_server_id(provider_id) -> bool:
    return str(provider_id or "").startswith(SERVER_ID_PREFIX)


def own_entries(user_id: str) -> list:
    """The account's own entries (a ``server:`` id is never one of them)."""
    return [e for e in load_provider_entries(user_id) if not is_server_id(e.get("id"))] if user_id else []


def new_server_provider_id() -> str:
    return SERVER_ID_PREFIX + new_provider_id()


def _allowance_limit(value) -> int:
    """A stored allowance number as a clean limit (anything odd reads as 0 =
    unlimited — never as a lock-out)."""
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return min(max(value, 0), ALLOWANCE_MAX)


def load_server_ai() -> dict:
    """The shared entries with their keys decrypted, each with its
    ``access``, and the allowance: {"providers": [...], "allowance":
    {"accounts": int, "guests": int}} (tokens per account per 24 h, 0 =
    unlimited). A key or a sign-in that no longer decrypts (the data
    directory's key changed) reads as none, with a warning."""
    try:
        value = json.loads(_get_raw(SERVER_AI_KEY) or "{}")
    except ValueError:
        value = {}
    if not isinstance(value, dict):
        value = {}
    entries = value.get("providers") if isinstance(value.get("providers"), list) else []
    # Written before access was per entry: the one guest switch of that time.
    legacy_guests = value.get("guests") is True
    out = []
    for e in entries:
        if not isinstance(e, dict) or not is_server_id(e.get("id")):
            continue
        e = dict(e)
        e["access"] = _clean_access(e.get("access"), legacy_guests)
        stored = e.get("api_key") or ""
        try:
            e["api_key"] = cipher().decrypt(stored.encode("ascii")).decode("utf-8") if stored else ""
        except (InvalidToken, ValueError):
            log.warning(f"shared AI provider {e.get('id')}: the stored key cannot be decrypted (key changed?)")
            e["api_key"] = ""
        sealed = e.pop("oauth", None)
        if isinstance(sealed, str) and sealed:
            try:
                oauth = json.loads(cipher().decrypt(sealed.encode("ascii")).decode("utf-8"))
                if isinstance(oauth, dict):
                    e["oauth"] = oauth
            except (InvalidToken, ValueError):
                log.warning(f"shared AI provider {e.get('id')}: the stored sign-in cannot be decrypted (key changed?)")
        out.append(e)
    allowance = value.get("allowance") if isinstance(value.get("allowance"), dict) else {}
    return {"providers": out,
            "allowance": {k: _allowance_limit(allowance.get(k)) for k in ("accounts", "guests")}}


def _sealed(entry: dict) -> dict:
    """A shared entry as stored: the key and the sign-in's tokens encrypted,
    the access a clean object."""
    out = {**entry, "api_key": cipher().encrypt(entry["api_key"].encode("utf-8")).decode("ascii")
           if entry.get("api_key") else "", "access": _clean_access(entry.get("access"))}
    oauth = entry.get("oauth")
    if isinstance(oauth, dict) and oauth:
        out["oauth"] = cipher().encrypt(json.dumps(oauth).encode("utf-8")).decode("ascii")
    else:
        out.pop("oauth", None)
    return out


def save_server_ai(config: dict) -> None:
    providers = [_sealed(e) for e in config.get("providers") or []]
    allowance = config.get("allowance") if isinstance(config.get("allowance"), dict) else {}
    _set_raw(SERVER_AI_KEY, json.dumps({
        "providers": providers,
        "allowance": {k: _allowance_limit(allowance.get(k)) for k in ("accounts", "guests")}}))


def validated_allowance(value) -> dict:
    """The allowance part of an admin request — {"accounts"?: N, "guests"?:
    N}, either key or both — checked: whole token counts from 0 (unlimited)
    to ALLOWANCE_MAX. 400 on anything else."""
    if not isinstance(value, dict) or set(value) - {"accounts", "guests"}:
        raise HTTPException(status_code=400, detail='allowance takes "accounts" and "guests"')
    for v in value.values():
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= ALLOWANCE_MAX:
            raise HTTPException(status_code=400,
                                detail=f"allowance must be a whole number of tokens from 0 to {ALLOWANCE_MAX}")
    return dict(value)


def validated_access(value) -> dict:
    """The access part of an admin request — {"who": "everyone" |
    "selected", "users"?: [usernames], "guests"?: bool} — checked and in
    its stored shape (the usernames as account ids). 400 on anything else,
    a username that is no account's or a guest's included. Under
    "everyone" the list is dropped, under "selected" the guest flag."""
    if not isinstance(value, dict) or set(value) - {"who", "users", "guests"}:
        raise HTTPException(status_code=400, detail='access takes "who", "users" and "guests"')
    who = value.get("who", "everyone")
    if who not in ACCESS_WHO:
        raise HTTPException(status_code=400, detail='access.who is "everyone" or "selected"')
    guests = value.get("guests", False)
    if not isinstance(guests, bool):
        raise HTTPException(status_code=400, detail="access.guests is true or false")
    names = value.get("users", [])
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise HTTPException(status_code=400, detail="access.users is a list of usernames")
    if who == "everyone":
        return default_access(guests)
    names = list(dict.fromkeys(n.strip() for n in names if n.strip()))
    if len(names) > MAX_ACCESS_USERS:
        raise HTTPException(status_code=400, detail=f"at most {MAX_ACCESS_USERS} accounts can be named")
    ids = []
    with connect_users_db() as conn:
        for name in names:
            row = conn.execute("SELECT id, is_guest FROM users WHERE username = ?", (name,)).fetchone()
            if not row:
                raise HTTPException(status_code=400, detail=f"no account is named {name}")
            if row[1]:
                raise HTTPException(status_code=400,
                                    detail=f"{name} is a guest account — guests are admitted by the guest switch")
            ids.append(row[0])
    return {"who": "selected", "users": ids, "guests": False}


def access_view(entry: dict, names: dict) -> dict:
    """An entry's access as the admin's form shows it: the listed accounts
    by username (``names`` = db.account_names of them; a deleted account is
    left out)."""
    access = _clean_access(entry.get("access"))
    return {**access, "users": [names[u] for u in access["users"] if u in names]}


def edit_server_ai(change) -> dict:
    """Read-modify-write the shared config under one lock: ``change(config)``
    mutates it in place (and may raise to abort). Returns the saved config."""
    with _server_lock:
        config = load_server_ai()
        change(config)
        save_server_ai(config)
        return config


def shared_access(user_id: str) -> tuple[list, int]:
    """The shared entries the account ``user_id`` (an id) may use, by each
    entry's access — every account under "everyone", a guest account only
    where ``guests`` is on, a listed account under "selected", an
    administrator always, an id that is no account never — and the
    allowance limit that applies to it (the guests' or the accounts', by
    the users row's ``is_guest``; 0 = unlimited)."""
    if not user_id:
        return [], 0
    config = load_server_ai()
    if not config["providers"]:
        return [], 0
    try:
        with connect_users_db() as conn:
            row = conn.execute("SELECT is_guest, is_admin FROM users WHERE id = ?", (user_id,)).fetchone()
    except sqlite3.Error:
        row = None
    if not row:
        return [], 0
    is_guest, is_admin = bool(row[0]), bool(row[1])
    limit = config["allowance"]["guests" if is_guest else "accounts"]
    if is_admin and not is_guest:
        return config["providers"], limit

    def admitted(entry: dict) -> bool:
        access = entry["access"]
        if access["who"] == "selected":
            return not is_guest and user_id in access["users"]
        return access["guests"] if is_guest else True
    return [e for e in config["providers"] if admitted(e)], limit




def _has_credential(entry: dict) -> bool:
    if is_oauth_protocol(entry.get("protocol")):
        oauth = entry.get("oauth")
        return isinstance(oauth, dict) and bool(oauth.get("access_token"))
    return bool((entry.get("api_key") or "").strip())


def server_entries_for(user_id: str) -> list:
    """The shared entries ``user_id`` may use (``shared_access``)."""
    return shared_access(user_id)[0]


def allowance_status(user_id: str, limit: int) -> dict:
    """What the account card, the pickers and the Usage pane show of the
    shared allowance: {"limit" (0 = unlimited), "used" (tokens through
    shared entries in the last 24 h), "exhausted"}."""
    used = ai_usage.shared_used(user_id)
    return {"limit": limit, "used": used, "exhausted": bool(limit) and used >= limit}


def shared_allowance(user_id: str) -> dict | None:
    """``allowance_status`` when a shared entry applies to ``user_id`` (one it
    can use: a key, or a connected sign-in; limit 0 when the admin set
    none), else None — the object ai_runtime() reports, without building
    the runtime."""
    entries, limit = shared_access(user_id)
    usable = any(ai_protocols.PROTOCOLS.get(e.get("protocol")) and _has_credential(e) for e in entries)
    return allowance_status(user_id, limit) if usable else None


def provider_label(entry: dict) -> str:
    """An entry's display name: its own, else the named service its endpoint
    is, else its protocol's label."""
    name = (entry.get("name") or "").strip()
    if name:
        return name
    service = ai_protocols.service_of(entry)
    if service:
        return service["label"]
    protocol = entry.get("protocol")
    proto = ai_protocols.PROTOCOLS.get(protocol)
    return proto.label if proto else protocol or ""


def entry_models(entry: dict) -> list:
    """The entry's model names. None picked = none offered: there is no
    built-in default (it would go stale); the settings form lists the
    provider's live models to pick from."""
    return [m.strip() for m in (entry.get("models") or "").split(",") if m.strip()]


# A refused sign-in token refresh isn't retried for this long: ai_runtime
# runs on every AI request, and retrying a dead grant each time would add a
# full round trip to the identity provider to chat/metadata/model calls.
REFRESH_BACKOFF_S = 300
# One that got no verdict (RefreshUnavailable: no connection, a 5xx) is
# retried sooner, since the grant is likely fine. Not much sooner: each try
# may hold a request for the token request's 30 s timeout.
REFRESH_RETRY_S = 60


def _backed_off(oauth: dict) -> bool:
    """Whether the sign-in's last refresh failed too recently to try again."""
    window = REFRESH_RETRY_S if oauth.get("refresh_unreachable") else REFRESH_BACKOFF_S
    return time.time() - (oauth.get("refresh_failed_at") or 0) <= window


# One refresh at a time per sign-in: per account for its own entries, per
# entry for a shared one (every account's requests refresh the same tokens).
# OpenAI rotates refresh tokens, so of two concurrent refreshes (the
# translator fires dozens of requests at once) the second fails — and its
# save must not overwrite the first one's fresh tokens.
_refresh_locks: dict = {}
_refresh_locks_guard = threading.Lock()


def _refresh_lock(key) -> threading.Lock:
    """``key``: an account id, or ``("server", <provider id>)`` for a
    shared sign-in (a tuple never equals an id)."""
    with _refresh_locks_guard:
        return _refresh_locks.setdefault(key, threading.Lock())


def _refresh_tokens(lock_key, read, write, flow, rejected: str = "") -> dict | None:
    """Refresh one sign-in's tokens through its protocol's OAuth ``flow``
    under ``lock_key``'s lock. ``read()`` gives the stored oauth dict fresh
    (so a refresh another request just did is reused, not repeated),
    ``write(oauth, expected)`` stores the result while the stored refresh
    token is still ``expected`` and returns the stored dict. ``rejected``:
    an access token the provider answered 401 to, refreshed although it
    does not look expired, unless the stored one is another by now or a
    refresh got it less than REFRESH_BACKOFF_S ago (``refreshed_at``): a
    provider refusing every token then costs one refresh per window, not
    one per check. Returns the current oauth dict."""
    with _refresh_lock(lock_key):
        oauth = read()
        if not oauth or not oauth.get("access_token"):
            return None
        if rejected:
            due = (oauth["access_token"] == rejected
                   and time.time() - (oauth.get("refreshed_at") or 0) > REFRESH_BACKOFF_S)
        else:
            due = flow.needs_refresh(oauth)
        if not due or _backed_off(oauth):
            return oauth
        expected = oauth.get("refresh_token")
        try:
            refreshed = flow.refresh(oauth)
        except RefreshUnavailable:
            # No verdict on the grant: keep the tokens, try again soon.
            return write({**oauth, "refresh_failed_at": int(time.time()), "refresh_unreachable": True}, expected)
        if not refreshed:
            # Refused: keep the stale token, so the call fails with a clear
            # upstream 401 and someone signs in again in Settings.
            oauth = {k: v for k, v in oauth.items() if k != "refresh_unreachable"}
            return write({**oauth, "refresh_failed_at": int(time.time())}, expected)
        refreshed = {**refreshed, "refreshed_at": int(time.time())}
        # OpenAI has spent the old refresh token: a lost save loses the grant.
        for attempt in range(3):
            try:
                return write(refreshed, expected)
            except sqlite3.OperationalError as e:
                if attempt == 2:
                    log.error(f"[ai] a refreshed sign-in could not be saved ({e}): the stored refresh "
                              "token is spent, so the sign-in will have to be made again")
        return refreshed


def _entry_oauth(entries: list, provider_id: str) -> dict | None:
    e = next((x for x in entries if x.get("id") == provider_id), None)
    return e.get("oauth") if e and isinstance(e.get("oauth"), dict) else None


def _swap_oauth(entries: list, provider_id: str, oauth: dict, expected) -> None:
    """Put ``oauth`` on the entry while its stored refresh token is still
    ``expected``, the one the refresh started from: a refresh, failed or
    late, never overwrites a sign-in made again meanwhile."""
    stored = _entry_oauth(entries, provider_id)
    if stored is not None and stored.get("refresh_token") == expected:
        next(e for e in entries if e.get("id") == provider_id)["oauth"] = oauth


def _refreshed_oauth(user_id: str, provider_id: str, flow, rejected: str = "") -> dict | None:
    """An account's own sign-in entry, refreshed under the account's lock
    and written back as only its tokens (an edit of the list meanwhile —
    another tab adding a key — stays)."""
    def write(oauth, expected):
        return _entry_oauth(update_provider_entries(
            user_id, lambda entries: _swap_oauth(entries, provider_id, oauth, expected)), provider_id)
    return _refresh_tokens(user_id, lambda: _entry_oauth(load_provider_entries(user_id), provider_id),
                           write, flow, rejected)


def _refreshed_server_oauth(provider_id: str, flow, rejected: str = "") -> dict | None:
    """A shared sign-in entry, refreshed under the entry's own lock and
    written back to the server's config (only its tokens: an admin's edit
    of the other fields meanwhile stays)."""
    def write(oauth, expected):
        return _entry_oauth(edit_server_ai(
            lambda config: _swap_oauth(config["providers"], provider_id, oauth, expected))["providers"], provider_id)
    return _refresh_tokens(("server", provider_id),
                           lambda: _entry_oauth(load_server_ai()["providers"], provider_id), write, flow, rejected)


def ai_runtime(user_id: str) -> dict:
    """The effective AI config for a request, built from the provider entries
    of the account ``user_id`` (an id) followed by the server's shared ones
    (``shared_access``):
    {"providers": {id: {api_key, base_url, protocol, name}},
    "models": [{"id": "<pid>:<model>", "provider": pid, "provider_name",
    "model", "native_pdf", "shared"}], "default": the first model — the
    account's own when it has one, else the server's — or None,
    "enabled": bool, "allowance": {"limit", "used", "exhausted"} or None}.

    ``allowance`` is None unless a shared entry made it into the runtime
    (limit 0 = unlimited). Under a limit every shared provider conf carries
    ``"allowance": {"user", "limit"}``, which ai_client.open_ai checks
    before each call. The shared models stay listed once it is used up; a
    refused call says why."""
    shared, limit = shared_access(user_id)
    providers, models = {}, []
    for e in own_entries(user_id) + shared:
        protocol = e.get("protocol")
        proto = ai_protocols.PROTOCOLS.get(protocol)
        pid = str(e.get("id") or "")
        if not proto or not pid or pid in providers:
            continue
        name = provider_label(e)
        conf = {
            "base_url": ((e.get("base_url") or "").strip() or proto.base_url).rstrip("/"),
            "protocol": protocol,
            "name": name,
        }
        if proto.auth == "oauth":
            # Sign-in entry: the bearer token comes from the sign-in and is
            # refreshed lazily here (persisted so other requests reuse it).
            oauth = e.get("oauth") if isinstance(e.get("oauth"), dict) else None
            if not oauth or not oauth.get("access_token"):
                continue
            if proto.oauth.needs_refresh(oauth) and not _backed_off(oauth):
                refreshed = (_refreshed_server_oauth(pid, proto.oauth) if is_server_id(pid)
                             else _refreshed_oauth(user_id, pid, proto.oauth))
                oauth = refreshed or oauth
            conf["api_key"] = oauth["access_token"]
            conf["account_id"] = oauth.get("account_id") or ""
            if oauth.get("refresh_unreachable") and proto.oauth.needs_refresh(oauth):
                # Due for renewal, and the identity provider could not be
                # reached: a 401 then says so, not "sign in again"
                # (ai_client.open_ai). The token may still work meanwhile.
                conf["refresh_unreachable"] = True
        else:
            key = (e.get("api_key") or "").strip()
            if not key and not (e.get("no_auth") is True and e.get("base_url")):
                continue
            conf["api_key"] = "" if e.get("no_auth") is True else key
        providers[pid] = conf
        for model in entry_models(e):
            mid = f"{pid}:{model}"
            if mid not in [m["id"] for m in models]:
                models.append({"id": mid, "provider": pid, "provider_name": name, "model": model,
                               # Whether the provider takes the PDF file itself
                               # (native document part); if not, the chat sends
                               # extracted text.
                               "native_pdf": proto.native_pdf,
                               "shared": is_server_id(pid)})
    allowance = None
    shared_ids = [pid for pid in providers if is_server_id(pid)]
    if shared_ids:
        # Reported whenever a shared entry applies (limit 0 = unlimited);
        # the transport only meters under a limit.
        allowance = allowance_status(user_id, limit)
        if limit:
            for pid in shared_ids:
                providers[pid]["allowance"] = {"user": user_id, "limit": limit}
    return {
        "user": user_id,  # whose config this is — the usage recorder's key
        "providers": providers,
        "models": models,
        "default": models[0] if models else None,
        "enabled": bool(models),
        "allowance": allowance,
    }


def clear_refresh_backoff(user_id: str, provider_id: str) -> None:
    """Forget a sign-in entry's failed refresh so the next ai_runtime()
    re-attempts the token refresh immediately (an explicit retry, e.g. the
    settings Test button). A ``server:<id>`` names a shared entry; the
    caller has checked the account may touch it."""
    def forget(entries):
        oauth = _entry_oauth(entries, provider_id)
        if oauth:
            oauth.pop("refresh_failed_at", None)
            oauth.pop("refresh_unreachable", None)

    if is_server_id(provider_id):
        with _refresh_lock(("server", provider_id)):
            oauth = _entry_oauth(load_server_ai()["providers"], provider_id)
            if oauth and "refresh_failed_at" in oauth:
                edit_server_ai(lambda config: forget(config["providers"]))
        return
    with _refresh_lock(user_id):
        oauth = _entry_oauth(load_provider_entries(user_id), provider_id)
        if oauth and "refresh_failed_at" in oauth:
            update_provider_entries(user_id, forget)


def renew_rejected(user_id: str, provider_id: str, rejected: str) -> str:
    """Renew a sign-in whose access token ``rejected`` the provider answered
    401 to although it did not look expired (a clock behind, a token
    revoked early). Under the refresh lock and within the backoff, like
    ai_runtime's renewal: of the requests the token was refused to, one
    refreshes and the others get its result. Returns the access token to
    try again with, "" when there is none (the grant was refused, a
    refusal is still backed off, or a refresh got the refused token only
    just now); raises RefreshUnavailable while the identity provider can't
    be reached. A shared entry's backoff is never reset here: that is an
    admin's."""
    shared = is_server_id(provider_id)
    entries = load_server_ai()["providers"] if shared else load_provider_entries(user_id)
    proto = ai_protocols.PROTOCOLS.get(next((e.get("protocol") for e in entries if e.get("id") == provider_id), None))
    if not rejected or not proto or proto.auth != "oauth":
        return ""
    oauth = (_refreshed_server_oauth(provider_id, proto.oauth, rejected) if shared
             else _refreshed_oauth(user_id, provider_id, proto.oauth, rejected)) or {}
    token = oauth.get("access_token") or ""
    if token and token != rejected:
        return token
    if oauth.get("refresh_unreachable"):
        raise RefreshUnavailable("the identity provider could not be reached to renew the sign-in")
    return ""


def require_ai_runtime(user_id: str) -> dict:
    """ai_runtime(), raising the standard 503 when no provider is usable."""
    rt = ai_runtime(user_id)
    if not rt["enabled"]:
        raise HTTPException(status_code=503,
                            detail="AI not configured (add a connection and pick its models in Settings → AI)")
    return rt


def transcriber_for(user_id: str, model_hint: str = "") -> tuple:
    """The connection the account's speech-to-text goes through, ``(protocol
    adapter, conf)``: dictation (``/ai/transcribe``) and a recording's
    transcript (gamma/recording.py). It needs an OpenAI credential, not chat
    models: an entry with none picked still transcribes. The entry that
    surely transcribes (Protocol.transcription: OpenAI itself) comes before
    one that may (a compatible server), the entry of ``model_hint`` (a
    model-registry id, the chat's model) first within each; the standard
    503 when none does."""
    rt = ai_runtime(user_id)
    # (A shared entry's ids have a colon of their own: "server:<id>:<model>".)
    hinted = rt["providers"].get(next((m["provider"] for m in rt["models"] if m["id"] == model_hint),
                                      (model_hint or "").split(":", 1)[0]))
    candidates = [(ai_protocols.of(c).transcription(c), c)
                  for c in ([hinted] if hinted else []) + list(rt["providers"].values())]
    best = max((rank for rank, _ in candidates), default=0)
    conf = next((c for rank, c in candidates if rank == best), None) if best else None
    if not conf:
        raise HTTPException(status_code=503,
                            detail="Voice input needs an OpenAI API key (Settings → AI → Connections) — "
                                   "Anthropic and ChatGPT sign-in connections don't offer transcription.")
    return ai_protocols.of(conf), conf


def resolve_model(runtime: dict, requested: str) -> dict:
    """The runtime entry a request's model names — its registry id
    (``<pid>:<model>``) or a bare model name — else the default."""
    for entry in runtime["models"]:
        if requested and requested in (entry["id"], entry["model"]):
            return entry
    return runtime["default"]
