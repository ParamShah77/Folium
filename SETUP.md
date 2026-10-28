# Folium: first-time setup (Windows, no Docker)

This gets a fresh Windows laptop to a running app. For the daily commands and the demo walkthrough see `DEMO.md`; for how everything works see `FOLIUM_MASTER.md`.

## What you need

| | Version | Notes |
|---|---|---|
| Python | 3.13 | Not 3.11 or 3.12: `dowhy` caps scipy below 3.13, which would change the scipy the model artefacts were built with |
| Node.js | 22 or newer | For the frontend |
| PostgreSQL | 18 | Installed as a Windows service; listens on 5432 |
| Memurai (Redis for Windows) | Developer edition | Free. Installed as a service; listens on 6379 |

Both services start automatically after installing. No Docker is involved.

## 1. Python environment

The ML libraries are large (about 2.5 GB), so put the virtual environment on a drive with room. This project uses `D:\FolioEnv`:

```powershell
py -3.13 -m venv D:\FolioEnv\venv313
$env:PIP_CACHE_DIR = "D:\FolioEnv\pip-cache"
D:\FolioEnv\venv313\Scripts\python.exe -m pip install --upgrade pip
D:\FolioEnv\venv313\Scripts\python.exe -m pip install -r backend\requirements.txt -r backend\requirements-ml.txt
```

Confirm the pinned versions, the model files and a few known predictions:

```powershell
D:\FolioEnv\venv313\Scripts\python.exe scripts\verify_ml_env.py
```

If you use a different location, replace `D:\FolioEnv\venv313` in the commands in these documents.

## 2. Database roles and database

Open `psql` as the `postgres` superuser:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost
```

```sql
CREATE ROLE finai LOGIN SUPERUSER PASSWORD 'choose-a-password';
CREATE DATABASE finai OWNER finai;
```

`finai` is the **owner**: it runs migrations and creates the tables. The app itself never connects as `finai`. Migration `0007` creates a separate least-privilege role, **`app_user`**, which the app uses so that row-level security is enforced (a superuser would silently bypass it).

Use only letters and digits in these passwords, or URL-encode them, because they go inside connection URLs.

## 3. Configuration (`.env`)

```powershell
D:\FolioEnv\venv313\Scripts\python.exe scripts\generate_dev_keys.py
```

This creates `.env` from `.env.example` (if it doesn't exist) and fills in the login-token key pair and the encryption key. Then set the database lines:

```
DATABASE_URL=postgresql://app_user:<APP_PASSWORD>@localhost:5432/finai
APP_DB_PASSWORD=<APP_PASSWORD>
ALEMBIC_DATABASE_URL=postgresql://finai:<FINAI_PASSWORD>@localhost:5432/finai
REDIS_URL=redis://localhost:6379/0
```

`<APP_PASSWORD>` is any password you choose now (migration `0007` creates `app_user` with it), and it must be identical in `DATABASE_URL` and `APP_DB_PASSWORD`. `.env` is git-ignored and never leaves your machine.

Every command that needs these values runs through `scripts\with_env.py`, which loads `.env` into that one command, so secrets are never typed into a shell.

## 4. Create the tables

```powershell
D:\FolioEnv\venv313\Scripts\python.exe scripts\with_env.py -m alembic -c backend\db\migrations\alembic.ini upgrade head
```

Run it again after pulling new code; it applies only what's missing.

## 5. Frontend packages

```powershell
npm --prefix frontend install
```

## 6. Demo data (optional)

```powershell
D:\FolioEnv\venv313\Scripts\python.exe scripts\with_env.py scripts\seed_demo.py
```

Creates two demo accounts with full portfolios and real analyses. The credentials are in `DEMO.md`.

## 7. Run

```powershell
D:\FolioEnv\venv313\Scripts\python.exe scripts\with_env.py -m uvicorn backend.main:app --port 8000 --reload
```

```powershell
npm --prefix frontend run dev
```

Open **http://localhost:3000**. If that port is taken by another app, stop it or run the frontend with `$env:PORT=3001`.

## 8. Test

| What | Command | Needs |
|---|---|---|
| Models, data and explainer | `D:\FolioEnv\venv313\Scripts\python.exe -m pytest tests` | the venv |
| Backend without a database | `D:\FolioEnv\venv313\Scripts\python.exe -m pytest backend\tests\unit` | the venv |
| Backend, full (about 10 minutes) | `D:\FolioEnv\venv313\Scripts\python.exe scripts\with_env.py -m pytest backend\tests` | PostgreSQL + Memurai |
| Frontend | `npm --prefix frontend test` | Node |

The full backend run creates and migrates its own `finai_test` database (and uses Redis database 15), so it never touches your data.

## Optional services

### Email

With no `RESEND_API_KEY` and `ENV=development`, sign-up and password-reset emails go to an in-app **development inbox** (`/dev/mailbox`) instead of being sent. To send real mail, add a Resend key and sender to `.env`; the inbox disappears.

### AI rewording of explanations

Off by default (`EXPLAINER_LLM=off`); the explanations are complete without it. To try it, get a free Gemini key at https://aistudio.google.com/apikey and set `EXPLAINER_LLM=on` and `GEMINI_API_KEY=` in `.env`. The model may only reword: any reply that changes a number is discarded. `scripts\check_llm_polish.py` tests it live.

### Google sign-in

Works end to end in the web app: "Continue with Google" on the log-in and sign-up pages, then back into the app. A new account is asked for its investor profile first.

1. In https://console.cloud.google.com create a project, then **APIs & Services → OAuth consent screen**: External, add yourself under **Test users**, default scopes (`openid`, `email`, `profile`).
2. **Credentials → Create credentials → OAuth client ID → Web application**, with the authorised redirect URI exactly `http://localhost:3000/v1/auth/google/callback`. This is the web app's address: the request goes through its `/v1` proxy to the backend. An existing client set up with `http://localhost:8000/...` needs this address added.
3. Put the client id and secret in `.env` as `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`. Leave `GOOGLE_OAUTH_REDIRECT_URI` empty locally: it defaults to `{FRONTEND_URL}/v1/auth/google/callback`.
4. The "Continue with Google" button then appears on the sign-in pages. While the credentials are empty the button is hidden.

If the web app runs on another port (because 3000 is taken), Google sign-in only works once `FRONTEND_URL` and the registered redirect URI use that port too. Google's "Error 400: redirect_uri_mismatch" means the address in step 2 doesn't match.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| "Can't reach the server" in the app | The backend isn't running, or isn't on port 8000 |
| Login fails with a database password error | `DATABASE_URL`'s password differs from `APP_DB_PASSWORD` |
| Migration says `ALEMBIC_DATABASE_URL` is not set | Run it through `scripts\with_env.py` |
| An analysis fails immediately | Run `scripts\verify_ml_env.py`: a missing ML library or model file is reported by name |
| Port 3000 or 8000 already in use | Stop the other app, or choose another port |
| Login or live progress misbehaves | Memurai isn't running (sessions and the live progress both use it) |
| Changed a model or the causal results | Restart the backend; both are cached in memory |
