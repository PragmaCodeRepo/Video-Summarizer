# Video Intelligence API

## Local development

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Set `OPENAI_API_KEY` in `.env` before analyzing transcripts or videos. Keep `.env` out of source control. For public deployments, use a unique `DJANGO_SECRET_KEY`, set `DJANGO_DEBUG=false`, use HTTPS, and configure the exact frontend origin in `CORS_ALLOWED_ORIGINS`.

## Accounts and authorization

- `POST /api/auth/register/` accepts `name`, `email`, and a password of at least 12 characters. Successful registration signs the user in.
- `POST /api/auth/login/` accepts `email` and `password`.
- `GET /api/auth/me/` returns the authenticated account.
- `POST /api/auth/logout/` revokes the current API token.
- Authenticated requests use `Authorization: Token <token>`.
- Every video is scoped to its owner. Videos created before owner accounts were added remain unassigned and are not included in a user's library.
- Registration and login are rate limited; AI analysis is limited to five requests per user per hour.

The health endpoint is public. Video, upload, transcription, analysis, and reanalysis endpoints require authentication.
