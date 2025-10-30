# Agentspace Frontend

Next.js UI that streams responses from the Agentscope FastAPI layer via the Vercel AI SDK.

## Running locally

```bash
npm install
npm run dev
```

Create `.env.local` if required:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_SEASON_LABEL=2025/2026
```

Chat requests are proxied to the FastAPI backend (`/api/agent/chat`), which invokes the Agentscope agent and streams the response back to the UI.
