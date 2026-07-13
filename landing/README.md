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

The repo root `vercel.json` builds this app automatically. Connect the GitHub repo
in Vercel — no extra settings needed. Vercel will run `npm install` and `npm run build`
inside `landing/` and serve `landing/dist`.

> **Note:** The Python scanner and FastAPI SaaS (`saas/app.py`) are separate from this
> static landing page. Do not point Vercel at the FastAPI entrypoint unless you intend
> to deploy the SaaS API as a serverless backend.
