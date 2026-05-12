# earthMockServer

`earthMockServer` is the FastAPI backend for the Earth Online prototype.
It currently provides:

- user register / login / JWT auth
- persona profile binding and storage
- notification + chat message event model
- random NPC push simulation
- event-triggered message creation

## Stack

- Python 3.11
- FastAPI
- SQLAlchemy
- PostgreSQL
- APScheduler

## Local development

### 1. Start PostgreSQL

```bash
docker compose up -d postgres
```

### 2. Prepare env

```bash
cp .env.example .env
```

If you run the app locally outside Docker, change `DATABASE_URL` in `.env`
from `postgres` to `localhost`.

### 3. Install dependencies

```bash
pip install -e .[dev]
```

### 4. Start server

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000/api/v1
```

## Docker deployment

This project can run as a complete Docker Compose stack with PostgreSQL and
the FastAPI app together.

### 1. Prepare env

```bash
cp .env.example .env
```

Before deployment, update at least:

- `SECRET_KEY`
- `CORS_ORIGINS`
- `DATABASE_URL` if you change database credentials

Inside Docker, the database host is `postgres`, not `localhost`.

### 2. Build and start

```bash
docker compose up -d --build
```

### 3. Check status

```bash
docker compose ps
docker compose logs -f app
```

### 4. API address

By default, the backend is exposed on:

```text
http://YOUR_SERVER_IP:3002/api/v1
```

Health check:

```text
http://YOUR_SERVER_IP:3002/api/v1/health
```

### 5. Stop services

```bash
docker compose down
```

If you also want to remove PostgreSQL data:

```bash
docker compose down -v
```

## Main endpoints

### Auth

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

### Persona

- `GET /api/v1/persona/me`
- `PUT /api/v1/persona/me`
- `PUT /api/v1/persona/bind`

### Messages

- `GET /api/v1/messages`
- `GET /api/v1/messages/poll`
- `GET /api/v1/messages/stream`
- `POST /api/v1/messages/trigger/random`
- `POST /api/v1/messages/trigger/event`
- `POST /api/v1/messages/{message_id}/read`
