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

## Production build

```bash
npm run build
npm run preview
```

Output is written to `landing/dist/`.

## Deploy on Vercel

### Recommended (most reliable)

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
