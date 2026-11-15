# DUCMANH AI — Connection Center Technical Specification

Version: 1.0  
Status: Architecture proposal — not a claim that integrations are connected.

## 1. Goals and non-goals

Connection Center is the single control plane for AI providers, external apps, developer tools, and plugins. It must keep the current Zalo webhook and Gemini reply path working while allowing providers to be added independently.

This document defines architecture and implementation order. It does not create OAuth applications, grant provider permissions, or claim any integration is live. Each provider remains `not_connected` until credentials are configured and a real health check or OAuth callback succeeds.

## 2. Current repository baseline

The current service is a Flask application on Render. It already has:
- Zalo webhook handling and asynchronous message replies.
- Gemini as the active model provider.
- `GET /api/connections` and `GET /api/plugins` starter endpoints.
- File Studio protected by `STUDIO_API_KEY`.
- A starter VS Code extension directory.

Current limitations to address:
- `connections.py` is an environment-variable presence check, not an authentication manager.
- Provider credentials are not stored per user and there is no OAuth callback flow.
- There is no persistent database, plugin installation lifecycle, permission model, or audit-log store.
- The VS Code folder is only a scaffold; Render cannot access local workspace files.
- The bot's message path currently calls Gemini directly rather than a provider-neutral AI gateway.

## 3. High-level architecture

Clients:
- Zalo Bot: chat interface and commands.
- Connection Center Web UI: connect, inspect, configure, and disconnect integrations.
- DUCMANH AI VS Code extension: local workspace bridge, user-approved file context, diffs, and explicit file writes.

Backend modules:
1. API layer — authenticated REST endpoints and Zalo webhook.
2. Authentication Manager — OAuth authorization code + PKCE where supported, signed state, token refresh, API-key onboarding, revoke/disconnect.
3. Integration Manager — provider registry, connection lifecycle, capability checks, health checks.
4. Credential Vault — encrypted credentials, key versioning, rotation, redaction.
5. AI Gateway — common request/response contract and provider adapters.
6. Plugin Manager — manifests, versions, permissions, install/enable/disable lifecycle.
7. Audit Logger — security-relevant events without secrets or message contents by default.
8. Database — users, connections, encrypted credentials, plugin installs, grants, audit events.

## 4. Provider catalog

All entries begin as `not_connected` unless an actual verified connection exists.

| Group | Provider | Authentication / integration | Initial capability |
|---|---|---|---|
| AI Models | Gemini | Google AI API key; OAuth only if a later Google account flow requires it | Chat, multimodal |
| AI Models | OpenAI | API key | Chat, coding, tools where supported |
| AI Models | Claude | Anthropic API key | Chat, analysis, coding |
| AI Models | DeepSeek | API key | Chat, coding, reasoning |
| AI Models | OpenRouter | API key | Multi-model gateway |
| Design | Canva | Canva Connect OAuth | Authorized design workflows only |
| Design | Image Generation | Provider-specific API key/OAuth | Image generation where provider permits |
| Design | Figma | OAuth or personal access token according to current API | Read/design metadata within granted scopes |
| Video | Sora | No generic public connection assumed; enable only when an official supported API/account flow is available | Provider-dependent |
| Development | VS Code | DUCMANH AI extension + device/session pairing | Local, consent-based workspace context |
| Development | GitHub | GitHub App or OAuth; minimum repository permissions | Repository operations explicitly authorized |
| Development | GitLab | OAuth or access token | Repository operations explicitly authorized |
| Development | Render | Render API key | Service/deploy metadata and permitted operations |
| Development | Replit | Official supported integration only | Capability-dependent |
| Productivity | Google Drive | Google OAuth | File operations within granted scopes |
| Productivity | Google Docs | Google OAuth | Document operations within granted scopes |
| Productivity | Google Sheets | Google OAuth | Spreadsheet operations within granted scopes |
| Productivity | Notion | Notion OAuth / integration token | Pages and databases within granted access |
| Productivity | Dropbox | OAuth | File operations within granted scopes |

Do not show a provider as connected merely because an environment variable exists. Use states: `not_connected`, `pending_authorization`, `connected`, `degraded`, `expired`, `revocation_pending`, and `disconnected`.

## 5. API contract

All endpoints except public health and the Zalo webhook require authenticated user/session or a service-to-service credential.

### Connection Center
- `GET /api/v1/connections` — safe metadata only: provider, display name, status, granted scopes, last health check, capabilities. Never return secrets or access/refresh tokens.
- `POST /api/v1/connections/{provider}/begin` — start OAuth or return API-key setup instructions.
- `POST /api/v1/connections/{provider}/credentials` — submit a provider key over TLS; validate, encrypt, and never echo it.
- `GET /api/v1/connections/{provider}/callback` — validate one-time OAuth state, exchange code server-side, encrypt tokens.
- `POST /api/v1/connections/{provider}/disconnect` — revoke remotely when supported, then delete local credential material and mark disconnected.
- `POST /api/v1/connections/{provider}/health-check` — perform a minimal non-destructive provider check.

### AI Gateway
- `GET /api/v1/models` — list only models enabled by configured providers.
- `POST /api/v1/ai/chat` — provider-neutral chat request with model, messages, optional safe tool declarations, and bounded output.
- `POST /api/v1/ai/route` — optional task-based routing (chat, coding, analysis); user-selected default always takes precedence.
- Provider adapters normalize timeout, rate-limit, authentication, and unavailable errors. Do not silently switch providers if doing so would violate user choice or data-handling expectations.

### Plugins
- `GET /api/v1/plugins` — catalog and compatibility metadata.
- `GET /api/v1/plugins/{id}` — manifest, permissions, version, and status.
- `POST /api/v1/plugins/{id}/install` — install after explicit user consent.
- `POST /api/v1/plugins/{id}/enable` and `/disable`.
- `DELETE /api/v1/plugins/{id}` — uninstall and revoke grants.

### Audit
- `GET /api/v1/audit-events` — owner/admin only, paginated and filtered; never include secret values.

Existing `/api/connections` and `/api/plugins` should remain as backwards-compatible aliases during migration.

## 6. Authentication and credential security

- Use HTTPS only. OAuth flows must use signed, short-lived, one-time `state`; use PKCE where supported; validate redirect URI exactly.
- Never put provider keys in Zalo messages, browser local storage, extension settings, Git, logs, exception text, or API responses.
- For API-key onboarding, accept the key only over TLS, validate with a minimal provider request, encrypt before persistence, and discard plaintext from application memory as soon as practical.
- Store encrypted credentials in the database using authenticated encryption (e.g. AES-256-GCM) with a master key supplied through a dedicated secret-management mechanism. Keep key version and nonce; support rotation. Do not store the encryption master key beside ciphertext.
- Use per-user/per-connection data isolation. Restrict database access to the backend service account.
- Redact Authorization headers, tokens, OAuth codes, API keys, and sensitive request bodies from logs.
- Disconnect must disable use immediately, attempt provider-side revocation where supported, delete local token material, and record a metadata-only audit event.
- Apply rate limits, CSRF protection to browser sessions, request-size limits, strict CORS, and security headers.
- Treat provider responses, plugin manifests, repository files, and model output as untrusted data.

## 7. VS Code Connector

The extension is the only component allowed to read a user's local workspace. Render must never attempt to browse a user's device.

Pairing:
1. User installs DUCMANH AI Connector for VS Code.
2. Extension opens a DUCMANH AI pairing page or device-code flow.
3. User signs in and approves the device/session.
4. Backend issues a short-lived, revocable, scoped extension token.
5. Extension stores the token using VS Code SecretStorage, not plaintext settings.

Workspace behavior:
- Ask the user before reading files; show included paths and exclusions.
- Respect `.gitignore` plus built-in exclusions for secrets, credentials, build outputs, and large/binary files.
- Send only selected file snippets/context required for the current task.
- For edits, show a unified diff and require explicit user approval before writing.
- New-file creation also requires approval.
- Never run terminal commands, scripts, or generated code automatically.
- Revoke extension sessions from Connection Center.

Planned commands: Ask DUCMANH AI, Explain Selection, Analyze Diagnostics, Propose Fix, Review Diff, Create File, Connect GitHub.

## 8. Plugin Marketplace

Each plugin must have a signed/verified manifest containing:
- `id`, `name`, `version`, `description`, `publisher`, `entrypoint`, `minimum_api_version`.
- Required provider connections and declared capabilities.
- Explicit permission scopes (e.g. `drive.files.read`, `github.repo.read`, `github.repo.write`).
- Data categories accessed, external network destinations, and uninstall/revoke behavior.

Marketplace rules:
- Installation and each elevated permission require explicit consent.
- Default to least privilege and read-only scopes.
- Version pinning, compatibility checks, publisher verification, and audit events are required.
- No arbitrary Python/JavaScript execution inside the Flask web process. Third-party plugins should use a restricted, isolated execution model only after a separate security review.
- Users can disable/uninstall plugins and revoke their grants.

## 9. Database model (initial)

Recommended PostgreSQL tables:
- `users`: account identity and status.
- `connections`: user_id, provider_id, status, scopes, created_at, updated_at, last_health_check.
- `encrypted_credentials`: connection_id, ciphertext, nonce, key_version, expires_at.
- `plugin_catalog`: plugin_id, version, manifest, publisher_status.
- `plugin_installs`: user_id, plugin_id, version, enabled, granted_scopes.
- `extension_sessions`: user_id, device_id, token_hash, scopes, expires_at, revoked_at.
- `audit_events`: actor, event_type, provider/plugin, timestamp, outcome, safe metadata.

Do not store raw extension bearer tokens; store only a one-way token hash. Add indexes and retention policies for audit events.

## 10. AI Gateway design

Define one internal interface for all adapters: `generate(messages, model, options) -> normalized response`. Each adapter owns its provider URL, authentication header, model mapping, timeout, and error normalization.

Initial rollout:
1. Wrap the existing Gemini SDK call in a Gemini adapter without changing webhook behavior.
2. Add OpenAI, Claude, DeepSeek, and OpenRouter adapters behind feature flags.
3. Add a user-selected default model.
4. Add optional task routing only after users can inspect and override the selected provider.
5. Add bounded retries only for transient errors; enforce request timeout and output limits.

## 11. Implementation phases and acceptance criteria

### Phase 0 — Architecture and inventory
- This specification reviewed and provider catalog agreed.
- Existing Zalo webhook and Gemini response path remain unchanged.
- No provider is falsely labeled connected.

### Phase 1 — Backend foundation
- Add PostgreSQL schema/migrations, authenticated owner/admin sessions, credential encryption, audit logging, and provider registry.
- API tests prove secrets never appear in status responses or logs.
- Add migration-safe compatibility endpoints.

### Phase 2 — AI Gateway
- Move Gemini behind an adapter and prove existing Zalo messages still receive replies.
- Add providers one at a time, with missing/invalid key, timeout, rate-limit, and success tests.

### Phase 3 — First OAuth integration
- Choose one provider (Canva or Google Drive) and configure its developer console application, exact redirect URI, scopes, and consent screen.
- Verify connect, refresh, health check, disconnect, and remote revocation behavior.

### Phase 4 — Connection Center UI and Marketplace
- Add searchable provider catalog, state labels, connect/disconnect, granted scopes, health checks, plugin install/disable/uninstall, and audit view.
- UI must distinguish planned, configured, and verified-connected.

### Phase 5 — VS Code Connector
- Implement pairing, SecretStorage, user-selected workspace context, diagnostics, proposed diffs, and approval-gated writes.
- Test token expiry/revocation and workspace exclusion rules.

### Phase 6 — Additional integrations
- Add GitHub/GitLab/Render, Canva/Figma, Google Docs/Sheets/Drive, Notion, Dropbox, image providers, and other supported integrations incrementally.
- Add Sora/Replit only when an official supported API/integration is available and verified.

## 12. Decisions and prerequisites before production

- Choose account model: single owner initially or multi-user accounts.
- Provision PostgreSQL before per-user credential storage; the current service has no persistent database configured.
- Configure a master encryption key through Render secrets before accepting credentials.
- Register OAuth applications and provide client IDs/secrets via Render environment variables.
- Define the Connection Center web UI host and allowed origins.
- Keep Render free-tier sleep/latency constraints in mind; do not promise real-time availability from a sleeping service.
- Keep the existing Gemini key and Zalo token out of source control; rotate any credential that has been exposed.

## 13. Explicit non-claims

A catalog entry is not an integration. A configured key is not necessarily a healthy connection. An OAuth button is not authorization until consent and callback validation succeed. Sora, Replit, Canva, VS Code, and all other providers must be marked according to actual supported APIs and verified permissions, not aspirational features.
