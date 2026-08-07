# Open PocketPilot in VS Code

This folder contains real, runnable source files. Do not paste `ALL_CODE.txt` into one editor file.

## macOS or Linux

1. Install Python 3.12+, Node.js 20+, npm, Git, and VS Code.
2. Unzip the project.
3. Open Terminal in the unzipped folder.
4. Run:

```bash
code pocketpilot.code-workspace
```

If the `code` command is unavailable, open VS Code and select **File → Open Workspace from File**, then choose `pocketpilot.code-workspace`.

5. In VS Code, select **Terminal → Run Task → Setup: Backend**.
6. Run **Terminal → Run Task → Setup: Mobile**.
7. Start the backend with **Run and Debug → Backend: FastAPI (debug)**.
8. Start the app with **Terminal → Run Task → Mobile: Start Expo**.

Equivalent one-command setup:

```bash
./scripts/setup-macos-linux.sh
```

## Windows

Open PowerShell in the unzipped folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1
code .\pocketpilot.code-workspace
```

## Main code locations

- Mobile application entry: `mobile/App.jsx`
- Mobile screens: `mobile/src/screens/`
- Mobile API client: `mobile/src/api/client.js`
- Backend entry: `backend/app/main.py`
- Backend API routes: `backend/app/api/`
- Budgeting engine: `backend/app/services/budgeting.py`
- AI orchestration: `backend/app/agents/`
- Database entities: `backend/app/models/entities.py`
- Migrations: `backend/migrations/versions/`
- iOS WidgetKit code: `ios-widget/`

## Local URLs

- FastAPI: `http://127.0.0.1:8000`
- Swagger documentation: `http://127.0.0.1:8000/docs`
- Expo: displayed in the VS Code terminal after `npm start`

## Environment files

The setup process copies:

- `backend/.env.example` to `backend/.env`
- `mobile/.env.example` to `mobile/.env`

Add real Google OAuth, AI-provider, email, and push credentials only to the `.env` files. Do not commit those files to GitHub.
