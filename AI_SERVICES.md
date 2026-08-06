# Connecting to AI Design Services (MCP servers)

This project now has connections configured for five AI / design services. They are configured
as opencode MCP servers in [`opencode.json`](./opencode.json), with API-key credentials kept in
the gitignored **[`.env`](./.env)** file (template: [`.env.example`](./.env.example)).

## Summary table

| Service | MCP endpoint | MCP type | Auth | Server name |
|---------|--------------|----------|------|-------------|
| Recraft AI | `https://mcp.recraft.ai/mcp` | remote | OAuth (browser) | `recraft` |
| Ideogram | `https://mcp.ideogram.ai/mcp` | remote | OAuth (browser) | `ideogram` |
| Canva | `https://mcp.canva.com/mcp` | remote | OAuth (browser) | `canva` |
| Freepik AI (Magnific) | `https://mcp.magnific.com` | remote | OAuth (browser) | `freepik` |
| Vectorizer.ai (Kittl Vectorizer) | (none official) | local stdio | API Basic (Id + Secret) | `vectorizer-ai` |

## How to activate

1. **Restart opencode** — config is only read at startup.
2. Confirm the servers loaded: `opencode mcp list`
3. On first use of a remote OAuth server, opencode opens a browser window for you to sign in.
   You can also trigger the flow manually:
   ```bash
   opencode mcp auth recraft
   opencode mcp auth ideogram
   opencode mcp auth canva
   opencode mcp auth freepik
   ```
   Tokens are stored securely in `~/.local/share/opencode/mcp-auth.json`.

Then use the server by name in a prompt, e.g. `use the recraft tools to generate a mascot icon`.

## Where to get credentials

- **Recraft AI** — https://www.recraft.ai/profile/api
  Buy API units first, then generate an API key. (For the browser-OAuth MCP server you only
  need a Recraft account; the API key is for the REST / local-server path.)
- **Ideogram** — https://developer.ideogram.ai/manage-api  (REST key sent in the `Api-Key` header).
- **Canva** — https://www.canva.com/developer/  register an app for the Connect API
  (Client ID + Secret). The OAuth MCP server uses CIMD, so no manual key is required to sign in.
- **Freepik / Magnific** — https://www.magnific.com/user/api-keys (API keys are gated to
  Business/Enterprise plans; the OAuth MCP server works on any account).
- **Vectorizer.AI** (the engine behind Kittl's Vectorizer) — https://vectorizer.ai/api
  gives an **API ID** (username) and **API Secret** (password) for HTTP Basic auth.

## Web access tokens (without MCP)

If you prefer plain REST keys over MCP servers:

- **Vectorizer.AI**: `python3 vectorizer_client.py logo.png -o out.svg` — zero-dependency
  (Python standard library only), reads `VECTORIZER_API_ID` / `VECTORIZER_API_SECRET` from `.env`.
- **Recraft / Ideogram / Freepik**: send `Authorization: Bearer <KEY>` (or the `Api-Key`
  header for Ideogram) against their public REST APIs.

## Troubleshooting

- The `vectorizer-ai` local MCP entry is **disabled by default** because it needs `uv` and a
  cloned repo (`git clone https://github.com/agentic-ai-forge/vectorizer-ai-mcp`). Until that
  is set up, use `vectorizer_client.py` instead. To enable it: set `VECTORIZER_MCP_DIR` in
  `.env`, install `uv`, and switch `"enabled": true` in `opencode.json`.
- Remote OAuth servers add tools/context to every session, and usage is billed against that
  service's own subscription credits.
- Never commit `.env` — it is already in `.gitignore`.