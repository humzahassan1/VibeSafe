# Deploy VibeSafe API to Railway

The landing page at `vibe-safe-pt7v.vercel.app` needs a live FastAPI backend.
Static Vercel hosting returns **405** for `POST /api/*` — those routes must hit Railway.

## One-time setup

### 1. Create Railway project

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select `humzahassan1/VibeSafe`
3. Railway reads `railway.toml` and builds with `Dockerfile.api`

### 2. Set environment variables (Railway → Variables)

| Variable | Value |
|----------|--------|
| `VIBESAFE_SECRET_KEY` | random 32+ char string |
| `VIBESAFE_CORS_ORIGINS` | `https://vibe-safe-pt7v.vercel.app` |
| `VIBESAFE_DATABASE_URL` | `sqlite:////tmp/vibesafe.db` (ephemeral, fine for demo) |

Optional: `GITHUB_TOKEN` for private repo scans.

### 3. Copy the public URL

Railway → your service → **Settings** → **Networking** → **Generate Domain**

Example: `https://vibesafe-api-production.up.railway.app`

Verify: `curl https://YOUR-URL/health` → `{"status":"ok",...}`

### 4. Point Vercel landing at the API

Vercel → `vibe-safe-pt7v` project → **Settings** → **Environment Variables**:

```
VITE_API_URL = https://YOUR-RAILWAY-URL.up.railway.app
```

Redeploy the landing (Deployments → Redeploy).

### 5. Test the scan page

Open `https://vibe-safe-pt7v.vercel.app/scan` and run a scan on a public GitHub repo.

## API endpoints used by `/scan`

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /api/demo/scan` | None | Zip upload, Tier 1+2 |
| `POST /api/demo/scan/github` | None | GitHub repo, Tier 1+2 |
| `GET /health` | None | Health check |

Authenticated endpoints (`/api/scans`, etc.) require signup — not used by the public demo.

## CLI deploy (alternative)

```bash
curl -fsSL https://railway.com/install.sh | sh
railway login
railway link          # link to your project
railway up --detach
```

## GitHub Actions auto-deploy

Add `RAILWAY_TOKEN` to GitHub repo secrets. Pushes to `main` that touch API code
trigger `.github/workflows/railway-api.yml`.

Get token: Railway → Account Settings → Tokens.

## Local dev

```bash
# Terminal 1
uvicorn saas.app:app --reload

# Terminal 2
cd landing && npm run dev
# /scan proxies /api → localhost:8000 via vite.config.ts
```
