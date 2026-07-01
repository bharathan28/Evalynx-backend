# Evalynx Interview Assessment Platform — Backend

Django REST Framework backend for the AI-powered video interview assessment platform.

---

## Architecture

```
backend/
├── config/                  # Django project config (settings, urls, wsgi)
│   └── exceptions.py        # Global DRF exception handler
│
├── apps/                    # Django apps (thin views → service layer)
│   ├── authentication/      # JWT auth, custom User model
│   ├── profiles/            # Resume upload, AI parsing, profile storage
│   ├── interviews/          # Session management, question flow, answer processing
│   └── analytics/           # Aggregated result computation, history
│
├── services/                # Pure business logic, fully decoupled from Django
│   ├── ai/
│   │   ├── resume_parser.py         # OpenAI call #1 — resume → structured JSON
│   │   ├── question_generator.py    # OpenAI call #2 — generate interview questions
│   │   └── technical_evaluator.py  # OpenAI call #3 — evaluate candidate answer
│   ├── processors/
│   │   ├── speech_to_text.py   # Whisper API — video → transcript
│   │   ├── grammar_checker.py  # LanguageTool (local) — grammar score
│   │   ├── filler_detector.py  # Pure Python — filler word count
│   │   └── confidence_score.py # Algorithm-based — confidence + communication
│   └── prompts/             # Versioned prompt templates
│       ├── resume_prompt.txt
│       ├── question_prompt.txt
│       └── evaluation_prompt.txt
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## API Reference

All endpoints are prefixed with `/api/v1/`.

### Authentication

| Method | Endpoint              | Auth Required | Description                        |
|--------|-----------------------|---------------|------------------------------------|
| POST   | `/auth/register/`     | No            | Register + receive JWT pair        |
| POST   | `/auth/login/`        | No            | Login — returns access + refresh   |
| POST   | `/auth/logout/`       | Yes           | Blacklist refresh token            |
| POST   | `/auth/token/refresh/`| No            | Exchange refresh for new access    |
| GET    | `/auth/me/`           | Yes           | Current user details               |

### Profile

| Method | Endpoint              | Auth Required | Description                        |
|--------|-----------------------|---------------|------------------------------------|
| POST   | `/resume/upload/`     | Yes           | Upload PDF → parse → store profile |
| GET    | `/profile/`           | Yes           | Retrieve structured profile        |

### Interview

| Method | Endpoint                    | Auth Required | Description                          |
|--------|-----------------------------|---------------|--------------------------------------|
| POST   | `/interview/start/`         | Yes           | Create session + generate questions  |
| GET    | `/interview/question/`      | Yes           | Retrieve specific question           |
| POST   | `/interview/submit-answer/` | Yes           | Submit video → full processing       |
| POST   | `/interview/cancel/`        | Yes           | Cancel + generate partial report     |
| GET    | `/interview/result/`        | Yes           | Retrieve analytics result            |
| GET    | `/interview/<id>/`          | Yes           | Full interview detail + all answers  |

### History

| Method | Endpoint      | Auth Required | Description               |
|--------|---------------|---------------|---------------------------|
| GET    | `/history/`   | Yes           | All past interview results|

---

## Quick Start

### Option A — Docker (Recommended)

```bash
cp .env.example .env
# Fill in DJANGO_SECRET_KEY, OPENAI_API_KEY, and DB_PASSWORD

docker-compose up --build
```

The API will be available at `http://localhost:8000`.

### Option B — Local

**Requirements:** Python 3.11+, PostgreSQL, ffmpeg

```bash
# 1. Create and activate virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 4. Create PostgreSQL database
createdb interview_platform

# 5. Run migrations
python manage.py migrate

# 6. Start development server
python manage.py runserver
```

---

## Environment Variables

| Variable                        | Required | Description                              |
|---------------------------------|----------|------------------------------------------|
| `DJANGO_SECRET_KEY`             | Yes      | Django secret key (generate a strong one)|
| `DEBUG`                         | No       | `True` for development                   |
| `ALLOWED_HOSTS`                 | No       | Comma-separated hostnames                |
| `DB_NAME`                       | Yes      | PostgreSQL database name                 |
| `DB_USER`                       | Yes      | PostgreSQL user                          |
| `DB_PASSWORD`                   | Yes      | PostgreSQL password                      |
| `DB_HOST`                       | No       | Default: `localhost`                     |
| `DB_PORT`                       | No       | Default: `5432`                          |
| `OPENAI_API_KEY`                | Yes      | OpenAI API key                           |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` | No  | Default: `15`                            |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS`   | No  | Default: `7`                             |
| `CORS_ALLOWED_ORIGINS`          | No       | Default: `http://localhost:3000`         |

---

## AI Cost Strategy

The platform uses only **3 OpenAI API calls** per interview answer:

| Task                    | Service           | Type         |
|-------------------------|-------------------|--------------|
| Resume parsing          | GPT-4o-mini       | One-time     |
| Question generation     | GPT-4o-mini       | Per interview|
| Technical evaluation    | GPT-4o-mini       | Per answer   |
| Audio transcription     | Whisper API       | Per answer   |
| Grammar checking        | LanguageTool (local) | Free      |
| Filler detection        | Pure Python       | Free         |
| Confidence scoring      | Algorithm         | Free         |

Estimated cost per interview (10 questions): **~$0.05–0.15** at GPT-4o-mini rates.

---

## Data Privacy

- Uploaded PDF resumes are deleted **immediately** after text extraction.
- Recorded video files are deleted **immediately** after audio transcription.
- Only structured extracted data is stored in the database.
- No raw files are ever persisted to disk beyond the processing window.
