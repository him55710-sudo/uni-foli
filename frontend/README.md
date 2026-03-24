# Polio Frontend

`frontend/` is the source of truth for the Polio web app.

The old AI Studio template framing is no longer the right mental model for this folder.

## Run

```powershell
npm install
npm run dev
```

## Build

```powershell
npm run build
```

## Environment

- Start from [`frontend/.env.example`](./.env.example).
- `VITE_API_URL` should point to the backend API, usually `http://localhost:8000`.
- Firebase variables are optional for local development.
- When Firebase config is absent, the app can fall back to local guest mode instead of crashing.

## Scope

Use this app for:

- auth and onboarding wiring
- diagnosis and drafting flows
- backend API integration
- evidence-safe UX around missing data

Do not treat this folder as a generated AI Studio export that should be regenerated from scratch.
