# YWAM AI Controller — setup

Three pieces, matching your three repos:

1. **`rode-addon/agent_api.py`** → drop into your `rode-main` (Tailoring) repo.
2. **`ywammut-addon/agent.js`** → drop into `YWAMMUT-main/routes/`.
3. **`orchestrator/`** → a brand-new small service, deployed as its own Railway app.

## 1. Tailoring app (rode)

- Copy `agent_api.py` into the root of your rode-main repo (next to `app.py`).
- In `app.py`, add near your other imports:
  ```python
  from agent_api import agent_bp
  app.register_blueprint(agent_bp)
  ```
- In Railway → your Tailoring service → Variables, add:
  `AGENT_API_KEY = <a long random string>`
- Redeploy. Test:
  ```bash
  curl -H "x-api-key: <that string>" https://ywamtailoring.up.railway.app/api/agent/students
  ```

## 2. YWAMMUT app

- Copy `agent.js` into `YWAMMUT-main/routes/`.
- In `server.js`, alongside the existing automation line, add:
  ```js
  const agentRoutes = require("./routes/agent");
  app.use(agentRoutes);
  ```
- In Railway → your YWAMMUT service → Variables, add:
  `AGENT_API_KEY = <a different long random string>`
- Redeploy. Test:
  ```bash
  curl -H "x-api-key: <that string>" https://ywammut.up.railway.app/api/agent/missionary
  ```

## 3. Orchestrator (new service)

- Push the `orchestrator/` folder as its own repo (or a subfolder Railway can point at).
- Create a **new** Railway service from it.
- Set these variables (see `.env.example`) — **three separate secrets, none shared**:
  - `GROQ_API_KEY` — your free key from console.groq.com/keys (this is the *only* AI-provider key)
  - `YWAMMUT_BASE_URL`, `YWAMMUT_API_KEY` — the `AGENT_API_KEY` you set in step 2 (a random string you invented, not an AI key)
  - `TAILORING_BASE_URL`, `TAILORING_API_KEY` — the `AGENT_API_KEY` you set in step 1 (a different random string)
- The `Procfile` runs the **Streamlit chat UI** (`streamlit_app.py`) by default — plain chat bot, nothing else on the page. Railway will use it automatically.
- Once deployed, **the Railway service's own URL is the chat UI** — open it in a browser.

If you'd rather have a JSON API instead of/alongside the chat page (e.g. to build your own frontend later, or wire it into Telegram), `main.py` (FastAPI) still works exactly the same way — just change the Procfile's command to `uvicorn main:app --host 0.0.0.0 --port $PORT` and it also serves a bare HTML chat page at `/`. Only one of the two `web:` commands runs at a time; pick whichever Procfile line you want live.

## Trying it end to end

Once all three are deployed, single prompts like these should work:

- "Register a new tailoring student named Priya, mobile 9876543210, course Tailoring Basics, batch A"
- "Mark student 12 present today"
- "Issue a certificate for student 12, course Tailoring Basics, started 2026-01-05"
- "Show me member M-014's loan and contribution history"
- "Create a ₹2000 loan for member M-014, due 2026-12-01"

The certificate tool returns the PDF as base64 in the orchestrator's JSON
response (`files` array) rather than dumping it into the chat model's
context — wire your frontend (web chat, Telegram bot, etc.) to save that
to a file and offer it as a download.

## Security notes

- Each app's `AGENT_API_KEY` should be a *different* long random string —
  generate with `openssl rand -hex 32`.
- These new endpoints skip each app's normal admin-session auth by design
  (an external agent process can't hold a browser session) — that's why
  the shared-secret key is the only thing standing between "anyone with
  the URL" and full read/write access. Keep the key out of client-side
  code, and rotate it if it ever leaks.
- The orchestrator itself has no auth on `/chat` in this scaffold — add
  your own (API key header, or put it behind your existing login) before
  exposing it beyond local testing.
"# connect-real-Agent-api" 
