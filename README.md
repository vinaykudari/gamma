<img alt="Gamma PDF — read papers, keep what you learn: a highlighted paper next to its outliner notes with a live-rendered equation" src="./docs/assets/branding/gamma-hero-light.svg" width="100%">

# Gamma PDF Annotator

**Organize papers and knowledge, in one place.** Self-hosted, multi-user, Logseq-inspired: read and annotate PDFs in your browser, keep the notes as a nested outliner, and link everything together.

[![Release](https://img.shields.io/github/v/release/tim4431/Gamma?filter=v%2A&style=flat&label=release&color=2563eb)](https://github.com/tim4431/Gamma/releases/latest)
[![GitHub stars](https://img.shields.io/github/stars/tim4431/Gamma?style=flat&logo=github&color=eab308)](https://github.com/tim4431/Gamma/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/tim4431/Gamma?style=flat&logo=github&color=8b5cf6)](https://github.com/tim4431/Gamma/forks)

<a href="https://apps.microsoft.com/detail/9N8WGWR2J2MV"><img src="https://get.microsoft.com/images/en-us%20dark.svg" alt="Download Gamma from the Microsoft Store" width="240"></a>
<a href="https://testflight.apple.com/join/nTmSHDx6"><img src="./docs/assets/badges/testflight-ipad.svg" alt="Get the Gamma iPad app beta on TestFlight" width="240"></a>
<a href="https://chromewebstore.google.com/detail/gamma-connector/njpeklephhndnpakmlaancinpnabcomn"><img src="./docs/assets/badges/chrome-web-store.png" alt="Get the Gamma Connector browser extension from the Chrome Web Store" width="218"></a>

**[Install](#install)** · **[User guide](./docs/user_guide/user_guide.md)** · [Try the demo](https://demo.gammapdf.com) · [Website](https://gammapdf.com) · [Releases](https://github.com/tim4431/Gamma/releases)

Every picture below is clickable and opens the matching part of the [user guide](./docs/user_guide/user_guide.md).

## Ask an AI about your papers

<a href="./docs/user_guide/user_guide.md#ai-chat"><img alt="Ctrl+drag panels c and d of a figure into the chat and ask what they show; the answer cites page 2 and a click jumps to the marked passage. Then click a highlighted sentence that cites refs 3–5 and ask to compare them: the assistant searches for the three papers, fetches them and answers in a table that cites the reference list" src="./docs/assets/demos/demo-native-agentic.webp" width="100%"></a>

- **Chat with the open paper** — ask about it, Ctrl+drag a figure or table into the question, paste pictures, dictate by voice, or attach the whole PDF so the model sees tables and plots. Answers cite pages; a click jumps the PDF to the passage. Use Anthropic or OpenAI models, or sign in with your ChatGPT subscription — no API key.
- **Mention a paper** — type `@` to attach a library page; its text stays in context for follow-ups.
- **Put the agent to work** — ask it to search your library or the web for papers, read and compare them, save the ones you want, rename pages, file and label them, many at once, or tidy up folders and labels. It asks before each change, many pages on one card (once, or for the whole chat; deleting a folder or a label asks every time), each tool step expands to show what it did, and it never deletes a page. What it changed is listed under its answer, and a note change, a rename, move or label change, or a deleted folder or label can be reverted from there — note changes one at a time or all at once.

<a href="./docs/user_guide/user_guide.md#the-library-agent"><img alt="Paste a lecture slide into the chat and ask for its equation under the block you are on: after the approval card, the formula lands rendered in the note" src="./docs/assets/demos/demo-agentic-notes.webp" width="100%"></a>

- **Write into your notes** — paste a slide or a screenshot into the chat and ask: the new block goes where your cursor is, math as KaTeX, once you approve the edit.

→ Guide: [AI chat](./docs/user_guide/user_guide.md#ai-chat) · [The library agent](./docs/user_guide/user_guide.md#the-library-agent)

## Read from any place

<a href="./docs/user_guide/user_guide.md#offline-copies"><img alt="One library on the lab server, open on a desktop, an iPad and a phone; a note typed from the iPad appears on every other device as the sync between them runs" src="./docs/assets/branding/gamma-anywhere-light.svg" width="100%"></a>

Your library lives on your server and opens from any browser: the office desktop, the iPad (with the Pencil), your phone. Reading position, open tabs and zoom follow your account from device to device.

- **Offline copy** — keep a full copy of a workspace on your laptop with the desktop app (one click on the workspace's *clone* chip) or on any second Gamma. Read and write it on the train; it syncs itself when the connection returns — edits merge block by block, and the rare conflict is shown on its block with both versions rather than lost.
- **Install it** — the [iPad app](https://testflight.apple.com/join/nTmSHDx6) (a TestFlight beta) or Safari → *Add to Home Screen* on the iPad, *Install Gamma* in Chrome or Edge, or the desktop app for Windows, macOS and Linux.

→ Guide: [Offline copies](./docs/user_guide/user_guide.md#offline-copies) · [Install as an app](./docs/user_guide/user_guide.md#install-as-an-app)

## Highlight, annotate and draw

<a href="./docs/user_guide/user_guide.md#draw-and-type-on-the-page"><img alt="Import a Notability note: the review lists the new page, and the paper opens with the pencil marks made on the iPad and their ink cards in the notes; then Gamma's pen circles a phrase and draws an arrow to a margin note" src="./docs/assets/demos/demo-ink-import.webp" width="100%"></a>

Open a paper by pasting any link — arXiv, DOI, or a publisher page; Gamma finds the PDF and falls back to a legal open-access copy when the DOI is paywalled — or drag the file in. Then:

- **Highlight** — select text or drag a box around a figure, pick a color, add a note. Each highlight becomes a block in your notes. Highlights already saved in the file by Acrobat, Preview or SumatraPDF come in as blocks too.
- **Draw** — with a stylus or the mouse: circle a claim, sketch an arrow, highlight freely. Lasso strokes to move, resize, rotate or recolor them; erase whole strokes or part of one. Ink is a note block linked to its place on the page. Notes from Notability come in with their handwriting as live ink you can keep writing on.
- **Type on the page** — the Text tool puts a text box on a PDF page or a notebook sheet, like Acrobat's, with Markdown and math inside. Boxes are notes too, and export as real text boxes in the annotated PDF.
- **Follow citations** — references in the PDF are clickable; a global **← Back** unwinds jumps across documents, and a cited arXiv/DOI paper is one click from your library.
- **Translate** — redraw a page in your language in place, figures untouched, or translate just a selected sentence. Microsoft's free service works with no setup; a chat model, Google or Youdao are one setting away.

→ Guide: [Highlight and annotate](./docs/user_guide/user_guide.md#highlight-and-annotate) · [Draw and type on the page](./docs/user_guide/user_guide.md#draw-and-type-on-the-page) · [Follow links and translate](./docs/user_guide/user_guide.md#follow-links-and-translate)

## Take notes

<a href="./docs/user_guide/user_guide.md#notes"><img alt="Type markdown, a page link and a live LaTeX equation, then /note drops a sheet of paper into the notes and a pen sketches the result on it" src="./docs/assets/demos/demo-notes.webp" width="100%"></a>

Highlights and free notes are the same kind of block, so a paper's notes and a plain page are edited the same way:

- **Outliner** — Enter for a new block, Tab / Shift+Tab to nest, drag to reorder, one undo history for the whole page.
- **Live preview, Obsidian-style** — markdown, `$…$` / `$$…$$` math, code fences, callouts, tables, Mermaid diagrams and SVG figures render in place while the block you're on stays raw. Math gets bracket-pair coloring, `\command` autocomplete, and Tab hops between `{}` arguments.
- **Pictures, tables and diagrams** — paste a screenshot and drag its edge to size it; tables are edited cell by cell, never as raw markdown; double-click a diagram to edit its source.
- **Pages to write on** — type `/note` and a sheet of paper opens among your notes; write on it with a stylus or the mouse, or show a page's sheets large as a notebook.
- **Link and embed** — `[[page]]` mentions, `/page` for a new page linked where you type, `![[block]]` embeds that edit the source in place, backlinks, and a "/" menu for everything else.

→ Guide: [Notes](./docs/user_guide/user_guide.md#notes)

## Link and organize

<a href="./docs/user_guide/user_guide.md#library"><img alt="Gamma fills metadata when a paper is downloaded, organizes papers with folders and labels, searches titles, notes and PDF text, and follows references to other papers with Back returning to the previous reading position" src="./docs/assets/branding/gamma-library-light.svg" width="100%"></a>

- **Labels and folders** — a label is a word you'll search for; a folder is a label that nests, for a topic or a talk. One paper can sit in several folders without a copy ([which to use](#labels-or-folders)).
- **Metadata** fills itself on open (arXiv → DOI → AI) and is editable; one click copies BibTeX or a slide-ready citation with real italics.

<a href="./docs/user_guide/user_guide.md#search"><img alt="In an open paper Ctrl+F finds a word and steps through its matches in the page, then Ctrl+P finds the quantum computing label and opens its papers" src="./docs/assets/demos/demo-search.webp" width="100%"></a>

- **Find in the paper** — in an open PDF, `Ctrl+F` counts the matches and Enter steps through them, marked in the page.
- **Jump anywhere** — `Ctrl+P` opens any page, folder or label as you type, typos forgiven; `Ctrl+Enter` there searches notes and PDFs, and `Ctrl+Shift+P` runs any command by name.
- **Search everything** — `Ctrl+F` searches notes, highlights and the full text of every PDF at once; narrow with label and folder chips. Matching is forgiving: "3000" finds "3,000-qubit" across a line break.

### Labels or folders?

Neither one copies a paper, and a paper can have as many labels and folders as you like. The difference is how you'll come back to it.

**A label is a word you'll search for.** A paper on PDH locking gets the label `pdh`. A paper from Vladan's lab on PGC cooling gets `vladan` and `pgc`. Labels are flat, so keep them short: a technique, an author, a lab, a keyword. Click one, or type it after `Ctrl+P`, to list every paper that has it.

**A folder is a label that nests, for a topic or a talk.** If you're studying quantum computing, make a folder **Quantum computing** with **Neutral atom**, **Superconducting qubits** and **Ion trap** inside it. A paper filed in Neutral atom shows *Quantum computing / Neutral atom* next to its labels. If you're giving group meetings, make **gm1**, then **gm2**. A paper you present at both sits in both folders, and it is still one paper with one set of notes. You can also use a folder as a whole: share it, export its bibliography, or ask the AI about every paper in it.

A simple test: if you'd type it into search, make it a label. If you'd open it and work through it, make it a folder.

Coming from Zotero? A folder is a collection and a label is a tag. Importing or exporting a Zotero library keeps them that way.

→ Guide: [Library](./docs/user_guide/user_guide.md#library) · [Labels or folders](./docs/user_guide/user_guide.md#labels-or-folders) · [Search](./docs/user_guide/user_guide.md#search) · [Metadata and citations](./docs/user_guide/user_guide.md#metadata-and-citations)

## Share and work together

<a href="./docs/user_guide/user_guide.md#workspaces"><img alt="Personal workspaces next to a shared research library where an owner and an editor type into two blocks of the same page at the same time and a viewer reads along" src="./docs/assets/branding/gamma-workspaces-light.svg" width="100%"></a>

- **Workspaces** — keep separate personal libraries, or collaborate in a shared library created by a server administrator: owners manage members, editors change pages, viewers read.
- **Share a page or a folder** — send a link to an annotated paper, or to a whole folder of them; invite people with view or edit rights, or open it to anyone with the link.

<a href="./docs/user_guide/user_guide.md#workspaces"><img alt="Three people on one page of a shared workspace: Maya types a question and Sam adds to the takeaway, each caret labeled with its writer's name, while the owner pastes a figure from the paper and drags it larger" src="./docs/assets/demos/demo-collab.webp" width="100%"></a>

- **Edit together** — changes and cursors appear live; edits to different blocks coexist, same-block edits merge.
- **Comments and an inbox** — comment on a note, a highlight or the whole page, @mention people, reply and resolve; viewers comment too. The bell gathers the mentions, replies, shares and invitations of every workspace and share you can open, and opens each one at its note with the thread showing.

→ Guide: [Share a page](./docs/user_guide/user_guide.md#share-a-page) · [Workspaces](./docs/user_guide/user_guide.md#workspaces) · [Comments and inbox](./docs/user_guide/user_guide.md#comments-and-inbox)

## Connect your research

<a href="./docs/user_guide/user_guide.md#assistants"><img alt="Gamma in the middle of an assistant prompt that mentions @Gamma and a paper, the Obsidian, Notion and Zotero import and export arrows, and the Gamma Connector saving a paper with the publisher sign-in kept per journal" src="./docs/assets/branding/gamma-connections-light.svg" width="100%"></a>

- **Assistants** — the [Gamma plugin for Codex and Claude Code](./plugins/gamma/) lets either assistant search, read and export your papers, notes and highlights, read-only, for a workspace you approve in the browser: *"@Gamma, in the Rydberg arrays paper, how is the blockade radius measured?"* Setup is one command copied from **Settings → AI → Integrations**; any other MCP client connects with the same URL.

<a href="./docs/user_guide/user_guide.md#gamma-connector"><img alt="On a Physical Review Letters article page, the Gamma Connector's toolbar badge has found the paper; its popup shows the title and authors, files it under Quantum/Neutral atoms with a label, saves it, and the PDF opens in Gamma with its folder and label" src="./docs/assets/demos/demo-connector.webp" width="100%"></a>

- **Gamma Connector** — the browser extension ([Chrome Web Store](https://chromewebstore.google.com/detail/gamma-connector/njpeklephhndnpakmlaancinpnabcomn) · [source](./extension/)) saves the paper you're reading in one click — PDF, metadata, folder, labels — from the arXiv / DOI / publisher tab, and clips links or selections into your notes. Its cookie button saves your **publisher sign-in per journal**, so the server can fetch that journal's PDFs on its own from then on.
- **Import** — Zotero libraries, Logseq exports and Notability notes with their annotations and handwriting; Obsidian vaults, Notion exports and Markdown folders as notes. **Export** — annotated PDF, Markdown, an Obsidian vault, a Logseq graph, a Zotero library, a Notability note, or a Gamma zip another Gamma can merge.

→ Guide: [Assistants](./docs/user_guide/user_guide.md#assistants) · [Gamma Connector](./docs/user_guide/user_guide.md#gamma-connector) · [Import and export](./docs/user_guide/user_guide.md#import-and-export) · [Backups and upgrades](./docs/user_guide/user_guide.md#backups-and-upgrades)

---

## Install

### Downloads

Get the Windows app from the [**Microsoft Store**](https://apps.microsoft.com/detail/9N8WGWR2J2MV), the iPad app from [**TestFlight**](https://testflight.apple.com/join/nTmSHDx6), or download standalone installers from [**GitHub Releases**](https://github.com/tim4431/Gamma/releases/latest).

- **Desktop app** (Windows installer, macOS dmg, Debian/Ubuntu deb) — a self-contained Gamma with local libraries on your disk, no Docker, Python or Node. It also opens any Gamma server you host (the NAS, a VPS) and keeps [offline copies](./docs/user_guide/user_guide.md#offline-copies) of its workspaces. Details: [desktop/](./desktop/). Builds are not notarized: Windows SmartScreen → *More info → Run anyway*; macOS says *Apple could not verify Gamma* on first launch → *System Settings → Privacy & Security → Open Anyway* (once); Linux: `sudo apt install ./Gamma-<version>-linux-amd64.deb`. Windows and Linux apps update themselves.
- **iPad app** (beta) — join on [**TestFlight**](https://testflight.apple.com/join/nTmSHDx6): install Apple's TestFlight app, then open the link on the iPad. It opens your servers with the Pencil captured natively, and keeps a workspace on the iPad itself, so it works with no connection. Details: [ipad/](./ipad/).
- **iPad, phone, any browser** — open your server and install it from the browser; see [Install as an app](./docs/user_guide/user_guide.md#install-as-an-app).
- **Gamma Connector** browser extension — from the [**Chrome Web Store**](https://chromewebstore.google.com/detail/gamma-connector/njpeklephhndnpakmlaancinpnabcomn) for Chrome, Edge and other Chromium browsers; it updates itself. Or take `gamma-connector-<version>.zip` from the [GitHub release](https://github.com/tim4431/Gamma/releases/latest), unzip it, then `chrome://extensions` → *Developer mode* → *Load unpacked*.
- **Server** — the Docker image below, built from `main` on every merge.

### Quickstart

```bash
docker run -d --name gamma -p 9001:9001 -v gamma-data:/data ghcr.io/tim4431/gamma:latest
```

Open <http://localhost:9001> and log in as `admin` — a fresh instance seeds the account itself and prints its password once to the log (`docker logs gamma`). No environment variables needed.

### Docker Compose (recommended)

Copy the template (the real file is gitignored, so local tweaks never land in commits) and start:

```bash
cp docker-compose.yml.example docker-compose.yml
docker compose up -d
```

Open <http://localhost:9001> and log in with the seeded `admin` password from `docker logs gamma` (printed once on first start). Accounts, notes and uploaded PDFs live under the container's `/data` volume and survive upgrades. Behind a reverse proxy, set `FORWARDED_ALLOW_IPS` to the proxy (the template shows how), or every visitor shares the proxy's rate limits.

Upgrades: the template runs [Watchtower](https://containrrr.dev/watchtower/) beside Gamma, which pulls each new image and restarts the container; Gamma then upgrades its data directory as it starts, and each workspace as it is first opened, after snapshotting the databases. Remove that service to update by hand (`docker compose pull && docker compose up -d`). A very old data directory may need one intermediate release first; if so, the server shows a page at its usual address saying exactly which image to run once, and nothing is changed until you do ([how upgrades work](./docs/dev/migrations.md)).

Backups: a workspace exports as one zip from Settings → Workspaces, and snapshots live in Settings → Backups. Administrators snapshot the whole instance from Settings → Server (restore those with the server stopped: `manage.py backups --restore`) and can keep off-site copies of the databases and uploaded files in an S3-compatible bucket (Settings → Backups → *Off-site copies*). See [Backups and upgrades](./docs/user_guide/user_guide.md#backups-and-upgrades) and the [backup internals](./docs/dev/workspaces.md#export-and-backups). If you bind-mount `/data` to a host folder, set `PUID`/`PGID` to your user's ids (`id -u` / `id -g`) so the files belong to you instead of root.

Users are managed in the app: sign in with an admin account → Settings → Users (create/delete accounts, reset passwords, grant or revoke the admin privilege — admin is a flag, not a special name). The CLI equivalent still works:

```bash
docker exec gamma python manage.py create-user alice her-password
docker exec gamma python manage.py set-admin alice on
docker exec gamma python manage.py list-users
```

For assistants (Codex, Claude Code) signing in to a remotely hosted Gamma, an administrator confirms the **Public server URL** once in Settings → Server; it applies immediately, without environment variables or a restart.

<details>
<summary><b>Run from source (development)</b></summary>

Requires Python 3.11+ and Node 18+.

**Backend**

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py create-user admin yourpassword
python manage.py set-admin admin on                 # admin privilege → GUI user management
python manage.py setup                              # seeds the guest account
uvicorn app:app --host 127.0.0.1 --port 9001
```

**Frontend**

```bash
cd frontend
npm install
npm run dev        # :5173, proxies /api → :9001
```

Frontend source is grouped by function (`editor/`, `pdf/`, `settings/`, and
others), with startup/session code in `app/` and reused code in `shared/`.
See the [frontend source map](./frontend/src/README.md) for file locations and
naming conventions, and the [developer guide](./docs/dev/README.md) for
architecture, shared rules, and topic documentation.

**Tests**

For local changes, run tests for the affected modules and their direct consumers;
see the [test selection policy](docs/dev/debugging.md#local-changes-test-the-affected-modules)
for targeted backend, frontend, and browser commands. The commands below run
full suites, which also run in PR CI.

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest tests -q
```

In-process API tests against a throwaway data dir — auth, the block tree, metadata/BibTeX, PDF-annotation import, full-text search, sync, and export.

Frontend checks, from `frontend/`: `npm test` for module tests, `npm run build`
for the production bundle, and `npm run e2e` for the browser suite against an
isolated backend (requires backend dependencies and Playwright Chromium).

**Production without Docker** — build the frontend and let the backend serve it:

```bash
cd frontend && npm run build
cd ../backend
GAMMA_STATIC_DIR=../frontend/dist uvicorn app:app --host 127.0.0.1 --port 9001
```

Put a TLS-terminating reverse proxy (Caddy, nginx) in front of 9001 for a domain. If you use HTTP/3, consider limiting Caddy to `protocols h1 h2` — a Chrome QUIC bug can make large PDFs crawl. A proxy's request-body limit (Cloudflare's 100 MB, nginx's `client_max_body_size`) does not cap your PDFs: a file past 32 MiB goes up in parts of that size, so the proxy only has to allow that much per request. Gamma itself caps no file's size, only an account's total storage when an admin sets a quota (Settings → Server). An upload a proxy does refuse says so in its error instead of looking like Gamma's refusal. Gamma's login throttle counts per client address, which it takes from the proxy's `X-Forwarded-For` only when the proxy's own address is in `FORWARDED_ALLOW_IPS` (below). Behind a proxy, set it to the proxy's address, or in Docker to the subnet of the compose network the proxy container shares with Gamma (pin that subnet in the compose file). Otherwise every visitor shares the proxy's rate-limit bucket. The build ships Brotli and gzip copies of its assets. The backend serves them itself, and a proxy that serves `dist` directly can too ([serving the build](docs/dev/debugging.md#serving-the-build)).

</details>

<details>
<summary><b>Environment variables</b></summary>

| Variable | Required | Default | Description |
|---|---|---|---|
| `GAMMA_DATA_DIR` | No | `data/` at the repo root (`/data` in Docker) | Where `users.db` and the per-workspace data live |
| `GAMMA_STATIC_DIR` | No | unset (`/app/static` in Docker) | Built frontend to serve as SPA; unset = API only |
| `GAMMA_PORT` | No | `9001` | Listen port (Docker entrypoint only) |
| `FORWARDED_ALLOW_IPS` | Behind a reverse proxy | `127.0.0.1` (Docker too) | Addresses of reverse proxies whose `X-Forwarded-For` / `-Proto` headers are believed (uvicorn's setting; comma list, networks allowed, `*` for any — only when nothing but the proxy can reach the port). Rate limits key on the client address this yields: behind a proxy that is not listed, every visitor shares the proxy's |
| `GAMMA_ADMIN_USER` / `GAMMA_ADMIN_PASSWORD` | No | `admin` / random, printed to the log once | Overrides the account a **fresh** instance seeds itself at startup (only while no real accounts exist; never touched afterwards). Admins manage users from the GUI (Settings → Users) |
| `GAMMA_AI_ANTHROPIC_BASE_URL` | No | `https://api.anthropic.com` | Default Anthropic-protocol endpoint, e.g. `https://api.deepseek.com/anthropic` |
| `GAMMA_AI_OPENAI_BASE_URL` | No | `https://api.openai.com` | Default OpenAI-compatible endpoint |
| `GAMMA_SEARXNG_URL` | No | unset | A SearXNG instance (JSON format enabled) that the assistant's web search uses for accounts without a search service of their own; it may be on the private network |
| `GAMMA_OPENALEX_API_KEY` | No | unset | An OpenAlex key for accounts without their own: ten times the keyless daily budget for scholarly search, and no pauses under load |

AI is configured in the app, not the environment: each user adds provider entries under Settings → AI → Connections (pick the API format — Anthropic Messages or OpenAI Chat Completions — then a key, plus optional label, base URL, and model list), or connects a ChatGPT Plus/Pro subscription with *Sign in with ChatGPT* — OAuth, no key at all. Keys are stored server-side per user and never sent back to the browser. The base-URL variables above only change the per-protocol defaults shown in that dialog.

Custom endpoints can explicitly select **No authentication** instead of supplying a dummy API key. See [custom APIs and local models](./docs/user_guide/user_guide.md#custom-apis-and-local-models) for supported formats, model selection, and the distinction between browser, server and container localhost.

</details>

<details>
<summary><b>Docker image</b></summary>

Published to GitHub Container Registry on every push to `main` (`latest`) and on version tags (`v1.2.3` → `1.2.3`, `1.2`), for `linux/amd64` and `linux/arm64`:

```
ghcr.io/tim4431/gamma
```

Multi-stage build: a Node stage compiles the frontend, the final Python image runs FastAPI serving both the API and the SPA on port 9001. See [Dockerfile](./Dockerfile) and [.github/workflows/docker.yml](./.github/workflows/docker.yml).

</details>

## License

Gamma is licensed under the [GNU Affero General Public License v3.0 only](LICENSE)
(`AGPL-3.0-only`). Third-party components and assets retain their respective licenses.
