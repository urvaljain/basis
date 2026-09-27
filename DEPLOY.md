# Deploying Basis

Two services. Neither needs a database, a cache or an object store.

Measured: **49 MB RSS** with the corpus loaded and indexed, **6.5 s** to ingest 206 pages at
startup, **~1.5 ms** per search. It fits a free tier.

---

## Backend → Railway

The Dockerfile's build context is the **repository root**, not `backend/` — it copies both
`backend/app` and `data/`, because the corpus ships inside the image.

1. **railway.app → New Project → Deploy from GitHub repo → `urvaljain/basis`**
2. Railway reads **`railway.json` at the repository root** and builds `backend/Dockerfile`
   with the repo root as the build context.

   **Leave the root directory unset.** If Railway offers "Set root directory to `backend`",
   decline it — the Dockerfile copies `backend/app` *and* `data/`, so a `backend/` context
   cannot see the corpus. (An earlier version of this file put `railway.json` inside
   `backend/`, where Railway does not look for it; the build then fell back to Railpack and
   failed with "Railpack failed to prepare the build".)
3. Under **Settings → Networking**, click **Generate Domain**. Note the URL.
4. Under **Variables**, set:

   | Variable | Value |
   |---|---|
   | `ALLOWED_ORIGINS` | your Vercel production URL, e.g. `https://basis.vercel.app` |
   | `ALLOW_ORIGIN_REGEX` | `https://.*\.vercel\.app` — covers per-commit preview deploys |
   | `ANTHROPIC_API_KEY` | *optional.* Without it the API runs in extractive mode, which is a supported mode |

   `PORT` is supplied by Railway; the container reads it.

5. Confirm: `https://<your-railway-domain>/api/health` should return
   `{"ok": true, "corpus_loaded": true, "mode": "extractive", ...}`.

**Expect the first boot to take ~30 s** — image pull plus 6.5 s of corpus ingestion before
the port opens. The healthcheck timeout is set to 120 s to accommodate that.

---

## Frontend → Vercel

1. **vercel.com → Add New → Project → import `urvaljain/basis`**
2. Set **Root Directory** to `frontend`. Vercel detects Next.js from there.
3. Under **Environment Variables**, set `NEXT_PUBLIC_API_URL` to the Railway URL from above
   (no trailing slash).
4. Deploy.

`next.config.mjs` proxies `/api/*` to `NEXT_PUBLIC_API_URL`, so the browser sees one origin
and CORS is only a fallback rather than the primary path.

---

## Order matters

Deploy the **backend first**. The frontend needs its URL, and the backend needs the
frontend's origin for `ALLOWED_ORIGINS` — so the sequence is: deploy backend → generate
domain → deploy frontend with that URL → come back and set `ALLOWED_ORIGINS` to the Vercel
domain.

---

## After deploying

- `/api/health` — `corpus_loaded: true`, and `fixtures.count` should be 12
- `/demo` — runs from recorded provider responses, so it works even when Overpass is
  rate-limited
- `/corpus` — should report 206 pages, 73.8% coverage, 54 unreadable
- `/evaluation` — reads `data/eval/results.json`, which ships in the image. Re-run
  `python -m app.eval.harness --json data/eval/results.json` and redeploy to refresh it

## Known deployment caveats

- **Uploads are in-process memory** and do not survive a restart or scale beyond one replica.
  `numReplicas` is pinned to 1 for that reason, and because the corpus index is per-process.
- **Rendered page images are written to the container filesystem** and are lost on redeploy.
  They re-render on first request, so this costs latency once per page, not correctness.
- **Overpass rate-limits by IP.** On a shared platform that IP is shared. The recorded
  fixtures are what make the demo reliable regardless.
