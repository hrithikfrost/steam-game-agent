# Steam Game AI Agent

MVP Telegram bot that recommends Steam games from onboarding answers, optional Steam profile data, RAWG metadata, deterministic scoring, and lightweight OpenAI-powered text/tag extraction.

## Features

- Telegram onboarding with `/start`
- Manual recommendations with `/recommend`
- Optional Steam profile import
- RAWG game search and local cache
- Rule-based hybrid recommendation scoring
- OpenAI usage limited to tag extraction and review-style pros/cons summaries
- Feedback buttons: interested, not interested, play now
- Daily recommendations via APScheduler
- FastAPI backend with health and manual scheduler endpoints
- PostgreSQL via SQLAlchemy async

## Stack

- Python 3.11
- FastAPI
- aiogram
- SQLAlchemy async + asyncpg
- PostgreSQL
- OpenAI API
- APScheduler
- httpx

## Quick Start

1. Copy environment:

```bash
cp .env.example .env
```

2. Fill tokens in `.env`:

- `TELEGRAM_BOT_TOKEN`
- `OPENAI_API_KEY`
- `STEAM_API_KEY`
- `RAWG_API_KEY`

3. Start dependencies:

```bash
docker compose up -d postgres
```

4. Install and run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

The FastAPI app runs on `http://localhost:8000`. The Telegram bot runs in polling mode in the same process.

## Project Layout

```text
app/
  bot/telegram_bot.py          Telegram command and onboarding handlers
  core/config.py               Settings
  db/session.py                Async database setup
  models/                      SQLAlchemy models
  repositories/                DB access helpers
  services/                    Steam, RAWG, OpenAI, recommendations, feedback
  scheduler/daily.py           Daily recommendation job
  main.py                      FastAPI entrypoint
```

## Notes

- The app uses `Base.metadata.create_all()` for MVP bootstrapping. Replace it with Alembic migrations before production.
- LLM calls are cached in PostgreSQL through `llm_cache`.
- Recommendation scoring is deterministic and does not depend on OpenAI.
- Steam pages are not scraped; only Steam Web API and Steam store links are used.
