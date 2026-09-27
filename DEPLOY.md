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
   | `ALLOWED_ORIGINS` | your Vercel production URL, e.g. `https://basis.vercel.app`. Optional — the frontend proxies server-side, so this only matters for direct API callers |
   | `ALLOW_ORIGIN_REGEX` | `https://.*\.vercel\.app` — optional, same reason |
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
3. Under **Environment Variables**, add **one** variable:

   | Key | Value |
   |---|---|
   | `API_ORIGIN` | your Railway URL, no trailing slash — e.g. `https://basis-production.up.railway.app` |

   Note it is `API_ORIGIN`, **not** `NEXT_PUBLIC_API_URL`. It is read by the Next.js server
   when proxying, so it is never exposed to the browser and never baked into the bundle.

   On the import screen, "Environment Variables" is a collapsed section below
   *Build and Output Settings*. If you have already deployed without it:
   **Project → Settings → Environment Variables → Add**, then
   **Deployments → ⋯ → Redeploy** on the newest deployment.

4. Deploy.

`next.config.mjs` rewrites `/api/*` to `API_ORIGIN` server-side, so the browser only ever
sees the Vercel origin. **CORS is therefore not load-bearing** — a wrong `ALLOWED_ORIGINS`
on Railway cannot break the deployed app. The API keeps its CORS config for anyone calling
it directly.

---

## Order matters

Deploy the **backend first** — the frontend needs its URL as `API_ORIGIN`.

The reverse dependency is now optional: because the frontend proxies server-side, you do
*not* have to come back and set `ALLOWED_ORIGINS` for the app to work. Set it only if you
want direct browser access to the API from another origin.

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
