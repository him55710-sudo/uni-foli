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
- Local guest mode is auto-enabled only during local development.
- In a non-dev environment, guest mode stays off unless `VITE_ALLOW_GUEST_MODE=true` is set explicitly.

## Firebase Console Checklist

For the current `.env`, the frontend expects the Firebase project `folia-e206f`.

1. Authentication -> Sign-in method
   Enable `Google`.
   Optional: enable `Anonymous` if you want Firebase-backed guest sessions instead of the local fallback.
2. Authentication -> Settings -> Authorized domains
   Add `localhost`.
   Add `127.0.0.1`.
3. Firestore Database
   Create the database in `Native mode`.
   Publish rules from [`firestore.rules`](./firestore.rules) if you plan to use Firestore-backed profile or document flows.
4. Project settings -> Service accounts
   Generate a new private key JSON for the same Firebase project.
   Save it at `backend/storage/runtime/firebase-service-account.json` so the backend can verify Firebase ID tokens.

If Google login shows `auth/unauthorized-domain`, the domain list is missing `localhost` or `127.0.0.1`.
If it shows `auth/configuration-not-found`, Google login is not enabled in Firebase Authentication.

## University Catalog Import

The target-university and target-major inputs support Korean initial-consonant search.
To load a real university/major catalog from an Excel file:

```powershell
python .\scripts\import_education_catalog_xlsx.py "C:\path\to\universities.xlsx"
```

The script writes [`frontend/src/data/education-catalog.generated.json`](./src/data/education-catalog.generated.json).
Until you import a real file, the fields still allow manual input so onboarding does not fail.

## Scope

Use this app for:

- auth and onboarding wiring
- diagnosis and drafting flows
- backend API integration
- evidence-safe UX around missing data

Do not treat this folder as a generated AI Studio export that should be regenerated from scratch.
