# WhatsApp AI

A WhatsApp shopping assistant for a Mumbai-based luxury fashion designer, built on FastAPI + Twilio WhatsApp + Gemini 2.5 Flash + ChromaDB (RAG over the product catalog). Built by Kalpavriksha AI Solutions as a capability showcase.

---

## Local development

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Fill in GEMINI_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM,
# and set ADMIN_USER / ADMIN_PASS to your own values.
```
Get a Gemini API key: https://aistudio.google.com/app/apikey

For local testing you can set `TWILIO_VALIDATE_SIGNATURE=false` in `.env`, since your local
requests won't carry a real Twilio signature. **Never disable it in production.**

### 3. Run the server
```bash
uvicorn main:app --reload --port 8000
```
Health check: http://localhost:8000/

### 4. Expose with ngrok (local only)
```bash
ngrok http 8000
```
Copy the HTTPS URL — e.g. `https://abc123.ngrok-free.app`

### 5. Point the Twilio Sandbox at it
1. Go to https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
2. Set **"When a message comes in"** to `https://<your-url>/webhook`, method `POST`, and save.

### 6. Test
Text `join <your-sandbox-code>` to the Twilio sandbox number, then send a message. You should get a reply within a few seconds.

---

## Deploying it publicly (Railway)

The local setup above only runs while your laptop is on and ngrok is open — not suitable for a public LinkedIn demo. Deploying to a small always-on host fixes that.

### 1. Push this project to a GitHub repo
Make sure `.env` is **not** committed (it's already in `.gitignore`). Only `.env.example` should go in.

### 2. Create a Railway project
1. https://railway.app → New Project → Deploy from GitHub repo → select this repo.
2. Railway will detect the `Procfile` and use it as the start command automatically.
3. Under **Variables**, add everything from `.env.example` with your real values:
   `GEMINI_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`,
   `ADMIN_USER`, `ADMIN_PASS`, `TWILIO_VALIDATE_SIGNATURE=true`, `RATE_LIMIT_PER_HOUR`.
4. Deploy. Railway gives you a permanent HTTPS URL like `https://your-app.up.railway.app`.

### 3. Point Twilio at the Railway URL
Same as local step 5, but use `https://your-app.up.railway.app/webhook` instead of the ngrok URL. This URL never changes on redeploys, so you only do this once.

### 4. Verify
- `https://your-app.up.railway.app/` should return the health check JSON.
- `https://your-app.up.railway.app/admin` should prompt for the `ADMIN_USER`/`ADMIN_PASS` you set.
- Send a WhatsApp message to the sandbox number and confirm you get a reply.

### On the ChromaDB data
`chroma_db/` is **not** committed in this version — the catalog content and collection name were just changed, so the old pre-built vectors are stale. Before your first deploy (and any time you edit `data/catalog.txt`), run:
```bash
python ingest.py
```
locally with a real `GEMINI_API_KEY` in `.env`, then commit the freshly generated `chroma_db/` folder and push. Skipping this step means the bot will run but `retrieve()` will always return empty context — it'll reply, just without any real product knowledge.

### Troubleshooting signature validation
If real Twilio messages start getting `403 Invalid Twilio signature` after deploying, it's almost always the proxy/scheme mismatch (Railway terminates HTTPS in front of your app). The `Procfile` already passes `--proxy-headers --forwarded-allow-ips='*'` to handle this — if it still fails, temporarily set `TWILIO_VALIDATE_SIGNATURE=false` to confirm the rest of the flow works, then re-enable and check Railway's logs for the URL your app is validating against.

---

## Going from Sandbox to a real WhatsApp Business number

The Sandbox is fine for a LinkedIn demo and client pitches (testers just text a join code once), but a client who wants to actually run this needs Twilio's WhatsApp Business API onboarding, which involves Meta business verification and can take from a few days to a few weeks. It's worth starting that process for a serious prospect early, since it's calendar time, not engineering time — the code here doesn't change when you switch to a real number, only `TWILIO_WHATSAPP_FROM` in your env vars.

---

## Security notes

- `/admin` and `/send` require HTTP basic auth (`ADMIN_USER` / `ADMIN_PASS`). Don't skip setting these — without `ADMIN_PASS`, both routes refuse all requests.
- `/webhook` verifies Twilio's request signature, so only genuine Twilio traffic gets processed.
- Inbound messages are rate-limited per WhatsApp number (`RATE_LIMIT_PER_HOUR`, default 20/hour) to cap what a single abusive sender can cost you in Gemini calls.
- **Rotate your Gemini and Twilio credentials before deploying** if they were ever in a `.env` file that left your machine (e.g. in a zip, a shared repo, or a chat) — treat any key that's been shared as compromised.

---

## Project structure
```
├── main.py           # FastAPI app: webhook, /send, /admin, auth, rate limiting
├── rag.py             # ChromaDB retrieval over the catalog
├── ingest.py          # One-time/occasional script to (re)build chroma_db from data/
├── twilio_client.py   # Outbound WhatsApp sending
├── admin.html          # Admin UI served at /admin
├── data/catalog.txt   # Source catalog text used for RAG
├── chroma_db/          # Generated by ingest.py — not committed until you run it (see above)
├── Procfile            # Railway/Heroku-style start command
├── requirements.txt
├── .env.example        # Copy to .env locally; set the same vars in Railway
└── .env                 # Never commit this
```
