# VibeSafe Landing Page

Dark single-page product landing for [VibeSafe](../README.md).

## Stack

- React 19 + Vite + TypeScript
- Tailwind CSS v4
- GSAP (ScrollTrigger, marquee)
- Framer Motion (scroll reveals)
- hls.js (background video)

## Development

```bash
cd landing
npm install
npm run dev
```

Open http://localhost:5173

### Live scan demo (`/scan`)

The scan page calls the FastAPI backend for Tier 1 + 2 analysis.

**Terminal 1 — API:**
```bash
cd ..  # repo root
pip install -e ".[saas]"
uvicorn saas.app:app --reload
```

**Terminal 2 — landing:**
```bash
npm run dev
```

Visit http://localhost:5173/scan — paste a GitHub URL or upload a zip.

For production, deploy the API separately and set `VITE_API_URL` in Vercel
(e.g. `https://your-api.railway.app`). Add your landing origin to
`VIBESAFE_CORS_ORIGINS` on the API.

## Production build

```bash
npm run build
npm run preview
```

Output is written to `landing/dist/`.

## Deploy on Vercel

See **[RAILWAY.md](../RAILWAY.md)** for deploying the FastAPI backend to Railway
(required for `/scan` to work in production).

In Vercel → **Project Settings → General → Root Directory**, set:

```
landing
```

Then redeploy. Vercel will only see the Vite app and will not try to deploy Python/FastAPI.

### Alternative (repo root)

The repo root `vercel.json` + `package.json` also build `landing/` as a static site.
If you still see a FastAPI entrypoint error, use the **Root Directory** setting above —
the Python scanner (`pyproject.toml`, `requirements.txt`) lives at the repo root and can
cause Vercel to mis-detect the project.

> **Note:** The FastAPI SaaS (`saas/app.py`) is a separate backend. Do not deploy it
> from this project unless you intend to run the API on Vercel serverless.
