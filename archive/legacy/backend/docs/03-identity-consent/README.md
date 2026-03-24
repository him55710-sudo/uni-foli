# 03 Identity And Consent

The app handles minors and highly sensitive educational records.
Identity and consent cannot be an afterthought.

## Minimum requirements

- account creation with verified email or federated login
- age or school-stage capture
- guardian consent path when policy requires it
- explicit document-processing consent before upload
- per-file consent and retention tagging

## Backend responsibilities

- store consent events as append-only records
- bind each upload to a lawful processing basis
- prevent cross-user data leakage at query time
- support export and delete requests

## Recommended tables

- `users`
- `guardian_consents`
- `processing_consents`
- `sessions`
- `access_grants`
- `audit_events`

## Session rules

- short-lived access tokens
- refresh token rotation
- device and IP metadata for suspicious-session detection

## API boundaries

- `POST /auth/login`
- `POST /consents/processing`
- `POST /consents/guardian`
- `GET /me`
- `DELETE /me/data`

## Design decisions

- auth provider can be external, but consent logs must live in the primary database
- authorization must be resource-scoped, not just role-scoped
- "download my data" and "delete my data" must be first-class operations
