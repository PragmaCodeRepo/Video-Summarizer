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

## SharePoint video folder import

The configured folder import uses Microsoft Graph app-only access. The folder is pinned by its drive and item IDs in the backend environment; the browser never receives the Microsoft app credential. The importer recursively finds MP4, MOV, and WEBM files, skips already-indexed items in the signed-in user's library, and saves each summary and transcript as it completes.

1. In Microsoft Entra, rotate the client secret that was used for setup and grant the registered application read access to the target folder (or its dedicated site/library). Microsoft Graph app-only access requires admin consent and an explicit resource grant when using a selected permission.
2. Set `MS_GRAPH_TENANT_ID`, `MS_GRAPH_CLIENT_ID`, `MS_GRAPH_CLIENT_SECRET`, `MS_GRAPH_DRIVE_ID`, `MS_GRAPH_FOLDER_ITEM_ID`, and `MS_GRAPH_FOLDER_NAME` in `backend/.env` or the deployment's secret store. The tenant, app, drive, and folder IDs from the supplied setup guide are prefilled in the local `.env` and `.env.example`; enter only the newly rotated secret in the backend environment. Do not commit `.env` or place the secret in frontend variables.
3. Apply migrations: `python manage.py migrate`.
4. Start one import worker alongside Django: `python manage.py process_sharepoint_imports`. Keep a single worker process for this SQLite-backed POC. The worker polls the database queue and continues processing even after the browser closes.
5. Sign in, then click **Analyze folder videos** in the SharePoint folder panel. The dashboard polls job progress and refreshes the library when processing completes. Use `python manage.py process_sharepoint_imports --once` to drain one queued import and exit.

### Keep the production worker running (Ubuntu / EC2)

The Django web service only queues SharePoint imports. Run one separate worker process on the same backend host, with access to the same SQLite database, `.env`, and video storage. Without it, imports remain at **Queued · waiting for the SharePoint worker**.

The example unit at `deploy/video-sharepoint-worker.service` uses the backend checkout path previously shown in the Nginx configuration. Confirm the checkout contains `manage.py`, `.env`, and `venv/bin/python` before installing it; update `WorkingDirectory` and `ExecStart` if your paths differ.

```bash
sudo cp deploy/video-sharepoint-worker.service /etc/systemd/system/video-sharepoint-worker.service
sudo systemctl daemon-reload
sudo systemctl enable --now video-sharepoint-worker
sudo systemctl status video-sharepoint-worker --no-pager
sudo journalctl -u video-sharepoint-worker -f
```

After restarting the worker, an import already waiting in the production queue should start automatically. The worker loads the Microsoft Graph and OpenAI configuration from `backend/.env`; do not copy either secret into the frontend or the unit file.

Only MP4, MOV, and WEBM are imported, with a 500 MB per-video cap. The Graph `/content` redirect's short-lived download URL is used only in memory and is never saved or logged. For a multi-process production deployment, move this queue from SQLite to a dedicated task broker/database and run the worker under a service manager.
