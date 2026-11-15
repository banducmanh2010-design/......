# DUCMANH AI Plugin Catalog

Plugins are explicit, least-privilege integrations. A catalog entry is not proof that a provider is connected.

## Initial providers
- Models: Gemini (active through existing bot), OpenAI, Claude, DeepSeek, OpenRouter.
- Design: Canva Connect, Figma, image-generation providers.
- Development: GitHub, Render, VS Code companion extension.
- Productivity: Google Drive, Docs, Sheets, Notion, Dropbox.

## Connection rules
1. API credentials are configured only as Render environment variables.
2. Never expose tokens in Zalo messages, API responses, logs, or Git.
3. OAuth providers require registered redirect URLs and user consent.
4. Mark a provider connected only after a real authorization/API health check.
5. Disconnect by revoking provider credentials and removing the corresponding Render secret.
6. Plugins must declare scopes and must not execute arbitrary generated code on the web worker.

## Planned VS Code companion
The VS Code extension connects to a DUCMANH AI endpoint configured by the user. Workspace file access is local and permission-based. The Render service cannot silently browse a user's computer.
