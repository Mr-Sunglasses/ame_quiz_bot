## AME Telegram Quiz Bot

Production-ready Telegram quiz bot built with Python, aiogram, FastAPI (webhook optional), and SQLite (Postgres optional). Supports creating quizzes (single or bulk), deep-links, Telegram quiz polls, timing, scoring, and persistence.

### Features
- /newquiz conversational flow: title, description, single/bulk questions
- Robust parser for single and bulk formats (with references)
- Deep-link share: `https://t.me/<BOT_USERNAME>?start=quiz_<QUIZ_ID>`
- Quiz attempt via Telegram quiz polls with instant feedback
- Global duration timer, partial scoring if time expires
- SQLite by default; optional PostgreSQL
- Admin/creator controls; public/private quizzes; basic rate limiting
- Dockerfile and docker-compose provided
- Unit tests for parser

### Quickstart (Local)
1. Copy env and set values:
```bash
cp .env.example .env
# edit .env for BOT_TOKEN and BOT_USERNAME
```
2. Create venv and install deps:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
3. Run with long polling:
```bash
python -m src.main
```
4. In Telegram, open your bot and run `/start` then `/newquiz`.

### Docker
```bash
docker compose up --build
```

### Webhook (optional)
- Set `WEBHOOK_URL` in `.env` to your public HTTPS endpoint.
- The app will start FastAPI on `PORT` (default 8080) and register webhook.
- For local dev, use a tunnel (e.g., `cloudflared tunnel` or `ngrok`).

### Database
- Default: `sqlite+aiosqlite:///./data.db` file in project root.
- To use Postgres, set `DATABASE_URL` accordingly (see `.env.example`).
- Database tables are auto-created on startup via SQLAlchemy.

### Tests
```bash
pytest -q
```

### Demo Script
See `docs/demo_script.md` for example conversations and expected outputs.

### Files
- `src/` bot, parser, db models
- `tests/` unit tests for parser and flows

### Deployment notes
- Heroku/Railway: deploy container, set env vars, ensure webhook public URL
- VPS: run docker-compose, secure BOT_TOKEN, set up a service/cron for resilience
