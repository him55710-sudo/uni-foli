# 12 Security And Compliance

This backend handles educational records and minor-related data.
Security design must be explicit.

## Threat model

- stolen session tokens
- file upload abuse
- prompt injection through uploaded or retrieved content
- cross-tenant data leaks
- over-retention of sensitive records

## Required controls

- signed upload URLs
- storage isolation by tenant scope
- row-level authorization in the data layer
- prompt-sanitization and source-trust filtering
- append-only audit log for sensitive actions

## Data classes

- public source material
- user-private uploads
- masked working text
- raw high-sensitivity text

Each class needs a different access rule and retention rule.

## Secrets and keys

- keep provider keys out of prompts and logs
- rotate secrets
- separate production and staging credentials

## Compliance posture

- document lawful basis and consent events
- support delete and export requests
- minimize stored raw data
- do not build features that require illegal or ambiguous data acquisition
