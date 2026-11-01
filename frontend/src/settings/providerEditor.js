// The AI connect dialog's state (useProviderEditor) and the helpers its
// forms in SettingsAi.jsx and the chat's setup card share. A module of its
// own because App holds the account's editor from startup, while the
// Settings dialog and the chat are fetched on first use
// (docs/dev/frontend-refactor.md, "Lazy boundaries").
import React from "react";
import { API, apiJson } from "../shared/lib/utils";
import { friendlyApiError } from "../library/libraryUtils";
import { GlobeIcon, KeyIcon, UserIcon } from "../shared/ui/Icons";
import { T, t } from "../shared/i18n/i18n.js";

// A provider's model list as stored: comma-separated names.
export const modelList = (raw) => (raw || "").split(",").map((name) => name.trim()).filter(Boolean);

// Who may use a shared entry (gamma/ai_settings.py "access"): every account,
// every account and the guests too, or the accounts named — what a new
// shared entry starts with, and the few words a Server section row says.
export const DEFAULT_ACCESS = { who: "everyone", users: [], guests: false };

export function accessSummary(access) {
  const a = access || DEFAULT_ACCESS;
  if (a.who !== "selected") return a.guests ? t("every account and guests") : t("every account");
  const names = a.users || [];
  if (!names.length) return t("no account yet — administrators only");
  return names.length <= 3 ? names.join(", ") : t("{names} and {n} more", { names: names.slice(0, 2).join(", "), n: names.length - 2 });
}

// The ways to connect an AI service, as tiles: each protocol the server
// offers (sign-in first, then the API-key ones in the server's order), then
// "Other" for the named services and a custom endpoint. The chat's setup
// card and the connect dialog both draw from it; `long` gives the card's
// fuller hints. A tile's value is a protocol id or "other".
const SERVICE_TILES = {
  chatgpt: { label: t("ChatGPT"), hint: t("Subscription sign-in"), long: t("Sign in with your subscription. No API key.") },
  anthropic: { label: t("Anthropic"), hint: t("API key"), long: t("Claude models, with an API key") },
  openai: { label: t("OpenAI API"), hint: t("API key"), long: t("GPT models, with an API key") },
};

// The plan labels and notes of the server's named services
// (gamma/ai_protocols/services.py), named here so the catalog has them; the
// menus and hints translate them as they render.
export const SERVICE_WORDING = [
  T("API key"), T("API key (China)"), T("Coding plan subscription"), T("Coding plan subscription (China)"),
  T("Alibaba's terms allow the Coding Plan only inside coding tools such as Qwen Code, and other use may get the plan suspended."),
];

// The named services by vendor, in the server's order: the Other tile's
// Service menu lists the groups, and a group of several presets gets a Plan
// menu of them.
export function serviceGroups(services) {
  const groups = [];
  for (const service of services || []) {
    const name = service.group || service.label;
    const group = groups.find((item) => item.name === name);
    if (group) group.services.push(service);
    else groups.push({ name, services: [service] });
  }
  return groups;
}

export function aiServiceTiles(info, { long = false, only = null } = {}) {
  const protocols = [...(info?.protocols || [])]
    .sort((a, b) => Number(b.auth === "oauth") - Number(a.auth === "oauth"))
    .filter((p) => !only || only(p));
  const tiles = protocols.map((p) => {
    const known = SERVICE_TILES[p.id];
    const oauth = p.auth === "oauth";
    return {
      value: p.id,
      label: known?.label || p.label,
      hint: known ? (long ? known.long : known.hint) : oauth ? t("Subscription sign-in") : t("API key"),
      Icon: oauth ? UserIcon : KeyIcon,
    };
  });
  const keyProtocol = (info?.protocols || []).find((p) => p.auth !== "oauth");
  if (keyProtocol && (!only || only(keyProtocol))) {
    const names = serviceGroups(info?.services).map((group) => group.name).join(", ");
    tiles.push({
      value: "other",
      label: long ? t("Other service") : t("Other"),
      hint: long
        ? (names ? t("{services} or any OpenAI-compatible endpoint", { services: names }) : t("Any OpenAI-compatible endpoint"))
        : (names ? t("{services}, custom URL", { services: names }) : t("Custom URL")),
      Icon: GlobeIcon,
    });
  }
  return tiles;
}

// The page runs at a loopback address, so this browser shares the server's
// machine and the server can catch the sign-in's localhost redirect itself.
export const onThisMachine = () => /^(localhost|127(\.\d+){3}|\[::1\])$/.test(window.location.hostname);

// A sign-in's redirect address as copied from the address bar (of the sign-in
// `state` when one is given).
export function signInAddress(text, state = "") {
  try {
    const url = new URL(text);
    return url.pathname === "/auth/callback" && !!url.searchParams.get("code")
      && (!state || url.searchParams.get("state") === state);
  } catch {
    return false;
  }
}

// A form's sign-in fields once it is connected, or before a new start.
const SIGN_IN_CLEARED = { oauthState: "", oauthCallback: "", oauthLocal: false, oauthDevice: null, oauthWaitError: "" };

// The connect dialog's state, one path for both provider lists: the
// account's own (App: `base` /api/ai/providers, sign-in at
// /api/ai/oauth/chatgpt) and Settings → Server's shared entries
// (/api/admin/ai-providers, sign-in at `${base}/chatgpt`). ProviderForm's
// `value` contract over the REST collection `base` (POST adds, PUT/DELETE
// `${base}/<id>`, each answering with the list; a ChatGPT sign-in goes
// through `${signIn}/start`, `status` while the server may catch it, and
// `complete`). The model picker lists live through /api/ai/model-catalog,
// which takes a saved entry's id (a shared one from an admin).
// `onSaved()` hears every change `run` saved (the account refreshes its
// model list and login check, the Server section says so);
// `onConnected(entry, form)` hears a connection this dialog just made, once
// it is saved with its models — both lists test it right away. `shared`
// (the Server section) gives every form an `access` — who may use the
// entry — that is saved with it.
export function useProviderEditor({ info, setInfo, base, signIn = `${base}/chatgpt`, onSaved, onConnected, shared = false }) {
  const [form, setForm] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const [catalog, setCatalog] = React.useState(null); // null | {loading} | {models} | {error}
  const [customModel, setCustomModel] = React.useState(""); // free-form entry next to the picker
  const catalogRequest = React.useRef(0);
  const protocolOf = (id) => info?.protocols?.find((p) => p.id === id);
  // Sign-in protocols (ChatGPT OAuth) have no key/base-URL fields — the
  // server marks them with auth: "oauth" in the protocols payload.
  const isOauth = (id) => protocolOf(id)?.auth === "oauth";
  const stored = form?.id ? info?.providers?.find((p) => p.id === form.id) : null;
  // What the live list is for; `oauthConnectedAt` re-lists after a
  // reconnect that keeps the entry's id.
  const target = JSON.stringify([form?.id, form?.protocol, form?.api_key, form?.no_auth, form?.base_url, form?.oauthConnectedAt]);
  const targetRef = React.useRef(target);
  targetRef.current = target;
  const formModels = modelList(form?.models);

  // API protocols list live from the provider (the typed key, or the stored
  // one when editing); a ChatGPT sign-in lists through the entry's token.
  async function loadModelCatalog() {
    if (!form) return;
    const request = ++catalogRequest.current;
    const at = target;
    setCatalog({ loading: true });
    try {
      const d = await apiJson(`${API}/ai/model-catalog`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider_id: form.id || "", protocol: form.protocol,
          api_key: form.api_key.trim(), no_auth: !!form.no_auth, base_url: form.base_url.trim() }),
      });
      if (request === catalogRequest.current && at === targetRef.current) setCatalog({ models: d.models || [] });
    } catch (err) {
      if (request === catalogRequest.current && at === targetRef.current) setCatalog({ error: friendlyApiError(err) });
    }
  }
  // A sign-in that isn't connected yet can't list models: its list comes
  // from the signed-in account, so the fetch waits for Connect.
  const oauthPending = !!form && isOauth(form.protocol) && !stored?.oauth_connected;
  // Credential edits are debounced, and a stale answer is dropped.
  React.useEffect(() => {
    setCatalog(null);
    const ready = form && (isOauth(form.protocol) ? stored?.oauth_connected : form.no_auth ? form.base_url?.trim() : form.api_key?.trim() || stored?.key_hint);
    if (!ready) return;
    const timer = setTimeout(loadModelCatalog, 500);
    return () => { clearTimeout(timer); catalogRequest.current++; };
  }, [target, stored?.oauth_connected]); // eslint-disable-line react-hooks/exhaustive-deps
  React.useEffect(() => { setCustomModel(""); }, [form?.id, form?.protocol]);

  // "Open ChatGPT sign-in": the OAuth page in a new tab. The server listens
  // for its localhost:1455 redirect when this browser shares its machine
  // (`oauthLocal`), and otherwise offers a device code (`oauthDevice`); either
  // way the form asks `${signIn}/status` until the server has the sign-in.
  // Elsewhere the redirect page fails to load and its address is pasted.
  async function startChatGPTAuth() {
    setError("");
    try {
      const d = await apiJson(`${signIn}/start`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ local: onThisMachine(), device: true }),
      });
      setForm((f) => (f ? { ...f, ...SIGN_IN_CLEARED, oauthState: d.state, oauthLocal: !!d.local, oauthDevice: d.device || null } : f));
      window.open(d.auth_url, "_blank", "noopener");
    } catch (err) {
      setError(err.message);
    }
  }

  // The form and list as they are now, for the waits below.
  const latest = React.useRef({});
  latest.current = { form, info };
  const completing = React.useRef("");

  // Finish the sign-in (or a reconnect) with the pasted address, or with ""
  // once the server has it. The form stays open on the entry so its models
  // can be picked from the account's live list — unless the chat's setup
  // card opened it and the sign-in already brought models.
  async function connectSignIn(callback = "") {
    const f = latest.current.form;
    if (!f?.oauthState) { setError(t("Hit “Open ChatGPT sign-in” first, then paste the URL it ends on.")); return; }
    if (completing.current === f.oauthState) return;
    completing.current = f.oauthState;
    let made = null;
    try {
      await run(async () => {
        const next = await apiJson(`${signIn}/complete`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ state: f.oauthState, callback, provider_id: f.id || "", name: f.name.trim(), models: f.models.trim() }),
        });
        const connected = f.id ? next.providers.find((p) => p.id === f.id)
          : next.providers.find((p) => !(latest.current.info?.providers || []).some((old) => old.id === p.id));
        if (connected && f.fromChat && modelList(connected.models).length) made = connected;
        else if (connected) {
          setForm((current) => current?.oauthState === f.oauthState
            ? { ...current, ...SIGN_IN_CLEARED, id: connected.id, models: connected.models || "",
                oauthConnectedAt: Date.now(), fresh: current.fresh || !f.id }
            : current);
        }
        return next;
      });
    } finally {
      completing.current = "";
    }
    if (made) onConnected?.(made, f);
  }

  // While the server may catch the sign-in itself, ask every few seconds
  // (a device code is polled with OpenAI on these calls, at its own pace).
  const watching = form && isOauth(form.protocol) && form.oauthState && (form.oauthLocal || form.oauthDevice)
    && !form.oauthWaitError ? form.oauthState : "";
  React.useEffect(() => {
    if (!watching) return undefined;
    let stopped = false;
    let timer = 0;
    const ask = async () => {
      try {
        const s = await apiJson(`${signIn}/status`, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ state: watching }),
        });
        if (stopped) return;
        if (s.ready) { connectSignIn(""); return; }
        if (s.error) { setForm((f) => (f?.oauthState === watching ? { ...f, oauthWaitError: s.error } : f)); return; }
      } catch {}
      if (!stopped) timer = setTimeout(ask, 2500);
    };
    timer = setTimeout(ask, 2500);
    return () => { stopped = true; clearTimeout(timer); };
  }, [watching]); // eslint-disable-line react-hooks/exhaustive-deps

  // Back from the sign-in tab with its address copied: where the browser
  // lets a page read the clipboard (Chromium, asking once), connect with it.
  const pasting = form && isOauth(form.protocol) && form.oauthState && !form.oauthLocal ? form.oauthState : "";
  React.useEffect(() => {
    if (!pasting || !navigator.clipboard?.readText || !navigator.permissions?.query) return undefined;
    let tried = "";
    const onFocus = async () => {
      try {
        if ((await navigator.permissions.query({ name: "clipboard-read" })).state === "denied") return;
        const text = (await navigator.clipboard.readText()).trim();
        if (text === tried || !signInAddress(text, pasting)) return;
        tried = text;
        setForm((f) => (f?.oauthState === pasting ? { ...f, oauthCallback: text } : f));
        connectSignIn(text);
      } catch {}
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [pasting]); // eslint-disable-line react-hooks/exhaustive-deps

  // One change to the list (a save here, a delete from the row): busy while
  // it runs, the list it answers with kept, the form closed on request.
  async function run(call, closeForm = false) {
    setBusy(true);
    setError("");
    try {
      setInfo(await call());
      if (closeForm) setForm(null);
      onSaved?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    const f = form;
    if (!f) return;
    const oauth = isOauth(f.protocol);
    const callback = oauth ? (f.oauthCallback || "").trim() : "";
    // A typed callback completes the sign-in (or a reconnect).
    if (callback) { await connectSignIn(callback); return; }
    if (oauth && !f.id) {
      setError(f.oauthState ? t("Finish the sign-in first, or paste the address it ended on.") : t("Open ChatGPT sign-in first."));
      return;
    }
    if (!oauth && f.no_auth && !f.base_url.trim()) { setError(t("Enter a base URL for a connection without authentication.")); return; }
    if (!oauth && !f.no_auth && !f.id && !f.api_key.trim()) { setError(t("An API key is required.")); return; }
    // A plain field edit (name/models — plus key/base URL for key entries).
    // A connection made in this dialog (`fresh` survives the sign-in step,
    // which keeps the form open on the new entry) is handed on once saved.
    let made = null;
    await run(async () => {
      const next = await apiJson(`${base}${f.id ? `/${encodeURIComponent(f.id)}` : ""}`, {
        method: f.id ? "PUT" : "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ protocol: f.protocol, name: f.name.trim(), base_url: f.base_url.trim(), models: f.models.trim(),
          ...(!oauth ? { no_auth: !!f.no_auth } : {}),
          test_model: (f.test_model || "").trim(), ...(f.api_key.trim() ? { api_key: f.api_key.trim() } : {}),
          ...(f.access ? { access: f.access } : {}) }),
      });
      made = f.id ? (f.fresh ? next.providers.find((p) => p.id === f.id) : null)
        : next.providers.find((p) => !(info?.providers || []).some((old) => old.id === p.id));
      return next;
    }, true);
    if (made) onConnected?.(made, f);
  }

  // A new connection's form, set to `service`: a protocol id, or "other"
  // (the first named service, else a custom endpoint). Without one it starts
  // on the first tile, the subscription sign-in. `list` stands in for `info`
  // when the form opens right as the list lands; `fromChat` marks the chat's
  // setup card as the opener.
  function startAdd(service = "", { list = info, fromChat = false } = {}) {
    setError("");
    const protocols = list?.protocols || [];
    const preset = service === "other" ? list?.services?.[0] : null;
    const protocol = preset?.protocol
      || (service === "other" ? protocols.find((p) => p.auth !== "oauth")?.id : service)
      || "";
    setForm({
      id: "", protocol: protocols.some((p) => p.id === protocol) ? protocol : (protocols.find((p) => p.auth === "oauth") || protocols[0])?.id || "chatgpt",
      name: "", api_key: "", no_auth: false, base_url: preset?.base_url || "", models: "", test_model: "",
      ...(service === "other" && !preset ? { custom: true } : {}),
      ...(fromChat ? { fromChat: true } : {}),
      ...(shared ? { access: DEFAULT_ACCESS } : {}),
    });
  }

  return {
    aiKeysForm: form,
    setAiKeysForm: setForm,
    aiKeysInfo: info,
    aiKeysBusy: busy,
    aiKeysError: error,
    setAiKeysError: setError,
    aiModelCatalog: catalog,
    formOauthPending: oauthPending,
    formModels,
    availModels: (catalog?.models || []).filter((m) => !formModels.includes(m)),
    customModel,
    setCustomModel,
    aiProtocolOf: protocolOf,
    isOauthProto: isOauth,
    startChatGPTAuth,
    connectSignIn,
    loadModelCatalog,
    addCatalogModel: (m) => m && setForm((f) => {
      if (!f) return f;
      const cur = modelList(f.models);
      return cur.includes(m) ? f : { ...f, models: [...cur, m].join(", ") };
    }),
    removeModel: (m) => setForm((f) => f ? { ...f, models: modelList(f.models).filter((x) => x !== m).join(", ") } : f),
    submitAiProvider: submit,
    run,
    startAdd,
    startEdit: (p) => {
      setError("");
      setForm({ id: p.id, protocol: p.protocol, name: p.name || "", api_key: "", base_url: p.base_url || "", models: p.models || "",
        no_auth: !!p.no_auth, test_model: p.test_model || "", ...(shared ? { access: p.access || DEFAULT_ACCESS } : {}) });
    },
    close: () => { setForm(null); setError(""); },
  };
}
