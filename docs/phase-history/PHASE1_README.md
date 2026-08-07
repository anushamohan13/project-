# PocketPilot — Phase 1

PocketPilot is a production-oriented starter for an AI-assisted personal financial planning application. This repository implements a runnable first vertical slice instead of placing illustrative pseudocode in a single file.

## What is implemented

- React Native with Expo, JavaScript/JSX, and `mobile/App.jsx`
- Apple-oriented interface structure with system light/dark mode
- FastAPI, Pydantic, SQLAlchemy, SQLite development database, and PostgreSQL Docker profile
- Development-safe sign-in plus JWT access/refresh tokens
- Profile, residence, planning currency, balance, and savings preferences
- Multiple income streams and weekly/fortnightly/monthly payment schedules
- Weekly activities with priorities and cost data
- Deterministic `Decimal`-based budgeting engine
- Recommended allocation chart, exact-total validation, confirmation, and immutable version number
- Smart Wishlist contribution calculation
- Widget snapshot API
- Native SwiftUI/WidgetKit source for Home Screen and Lock Screen widgets
- Local Expo native module that writes confirmed snapshots into the shared App Group and reloads WidgetKit timelines
- Mock financial assistant that uses saved application data and creates a non-applied proposal for emergency shortfalls
- Unit and API tests, including cross-user isolation

## Important limitations and assumptions

1. Google OAuth requires platform credentials and redirect configuration. Phase 1 includes a development sign-in endpoint; the authentication boundary is already isolated for replacement with Google OAuth.
2. Currency conversion is intentionally rejected when currencies differ. A trusted rate-provider interface must be connected before cross-currency calculations are enabled.
3. The AI provider defaults to a deterministic development implementation. Provider API keys never belong in React Native or WidgetKit code.
4. Expo cannot create a WidgetKit extension using only JavaScript. The Swift files under `ios-widget/` must be added to a native iOS widget target after running Expo prebuild.
5. The current UI demonstrates the complete core loop but does not yet include every screen listed in the full product specification.

## Repository structure

```text
financial-planner-phase1/
├── mobile/
│   ├── App.jsx
│   ├── app.json
│   ├── package.json
│   └── src/
│       ├── api/
│       ├── components/
│       ├── screens/
│       ├── store/
│       └── theme/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── agents/
│   │   └── main.py
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── ios-widget/
├── docker-compose.yml
└── README.md
```

## Backend setup

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Optionally load demo data with `python -m app.seed`.

Open the generated API documentation at `http://127.0.0.1:8000/docs`.

Run tests:

```bash
cd backend
pytest -q
ruff check .
```

PostgreSQL option:

```bash
docker compose up
```

## Mobile setup

```bash
cd mobile
npm install
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api npm run ios
```

For a physical iPhone, replace `127.0.0.1` with the development computer's LAN address and ensure the API is reachable on the network.

## WidgetKit integration

WidgetKit cannot be implemented purely in Python or `App.jsx`. It is a native iOS extension written in Swift and SwiftUI.

1. From `mobile/`, run `npx expo prebuild --platform ios`.
2. Open the generated `.xcworkspace` in Xcode.
3. Add a **Widget Extension** target named `FinanceWidget` and disable configuration intent unless required.
4. Replace the target's generated Swift files with the files from `ios-widget/`.
5. Add the App Group `group.com.example.pocketpilot` to both the main application target and widget extension.
6. Keep the same App Group identifier in `mobile/app.json`, backend `.env`, and `SharedBudgetData.swift`.
7. The included local Expo module at `mobile/modules/budget-widget/` writes the authenticated `/api/widget/snapshot` response into shared `UserDefaults(suiteName:)` and reloads WidgetKit timelines.
8. Build a native development client with `npx expo run:ios`; Expo Go cannot load this custom module.
9. Build on an iOS 17+ simulator/device for accessory Lock Screen widget support.

The backend snapshot endpoint is implemented. A production implementation should sign and minimise widget payloads, avoid credentials in shared defaults, and expose only display-safe aggregate values.

## Implemented API routes

- `POST /api/auth/dev-login`
- `POST /api/auth/refresh`
- `GET|PUT /api/profile`
- `GET|POST /api/income-streams`
- `PUT|DELETE /api/income-streams/{id}`
- `GET|POST /api/activities`
- `PUT|DELETE /api/activities/{id}`
- `POST /api/budgets/calculate`
- `POST /api/budgets/confirm`
- `GET /api/budgets/latest`
- `GET|POST /api/wishlist`
- `GET /api/widget/snapshot`
- `POST /api/chat/messages`

## Next implementation phases

Phase 2 should add Google OAuth, Alembic revisions, complete CRUD for all entities, transaction tracking, custom categories, allocation editing sliders, historical plan comparison, email/push jobs, the native snapshot bridge, and a provider-independent tool-calling AI orchestration layer with confirmation and reversal endpoints.
