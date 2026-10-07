# Hosted demo and durable storage

The Vercel project is **pocket-fde**, owned by **adarsh's projects** (`adarshs-projects-f822047a`). Its root directory is `pocket-fde/`. The public production URL is [https://pocket-fde-adarsh.vercel.app](https://pocket-fde-adarsh.vercel.app). Verification evidence is recorded in [the release verification](../../submission/release-verification.md).

## What is deployed

FastAPI serves the existing browser workspace and both retrieval modes. The build installs the pinned Python 3.12 dependencies from `uv.lock` and downloads the pinned MiniLM model into `.models/`. Linux builds use CPU-only PyTorch. The model is bundled in the function, and runtime loading is offline. This requires Vercel's large-functions option because the current bundle is slightly above the standard Python size limit. See [FastAPI hosting](https://vercel.com/docs/frameworks/backend/fastapi) and [large functions](https://vercel.com/docs/functions/configuring-functions/large-functions).

Private Vercel Blob stores completed analyses as immutable JSON snapshots. Each browser has its own encrypted workspace cookie; another browser cannot read those snapshots through the application. The store is outside the function filesystem, so records survive deployments and server restarts. Drafts and the current result also survive refresh through browser storage. The demo has no user accounts or cross-device history recovery. Second Brain learning is shared separately among unlocked demo users.

The original reviewed knowledge lives in Git and is bundled with the release. Successful analyses also automatically draft provisional shared learnings for explicit human review. Only approved notes enter either search mode; the combined corpus carries a fingerprint. Pending and rejected notes stay excluded from retrieval. There is no automatic approval of learning.

## Secrets and access

The **Second Brain** workspace stores shared web submissions and review decisions using the same private Blob token under `second-brain-v1/`. They persist independently of the deployed code; approval refreshes both search indexes without a redeployment. This does not change private incident history. A separate `POCKET_FDE_BRAIN_NAMESPACE` is recommended for isolated staging checks; never run synthetic approval tests against the live namespace. Existing Git-based knowledge continues to be bundled with the app. See [the browser workflow](README.md#second-brain-in-the-browser) for review and access boundaries.

Set these in Vercel's production and preview environments:

- `GEMINI_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`: reasoning-model connection.
- `LLM_FALLBACK_MODEL`: optional Gemini fallback used only for primary quota limits or temporary provider errors. The release uses `gemini-3.5-flash` with `gemini-flash-lite-latest` as fallback. Responses and measured call records identify the actual model(s) used. Visitor-selected models have no automatic fallback.
- `POCKET_FDE_SESSION_KEY`: a stable Fernet key for encrypted session and workspace cookies. Keep the same key across releases to preserve access to saved history.
- `POCKET_FDE_ACCESS_CODE`: shared demo access code. Required before model calls, connection tests, private history or shared Second Brain access.
- `BLOB_READ_WRITE_TOKEN`: supplied by the connected **pocket-fde-workspaces** private store in Mumbai (`bom1`).
- `VERCEL_SUPPORT_LARGE_FUNCTIONS=1`, `TOKENIZERS_PARALLELISM=false`, `OMP_NUM_THREADS=1`.

API and signing keys are Vercel secrets, never browser-visible configuration. Optional visitor-supplied model keys are encrypted in HttpOnly, Secure cookies for up to eight hours, and never included in saved analyses. Claude Code is a local-only provider.

The shared access code is a capstone-demo gate, not a substitute for account authentication in a real multi-tenant product. Public visitors may inspect the synthetic sources without using the paid model. Model requests have a per-browser 15-second cooldown and a shared 50-request daily budget. Reservations use private create-only storage slots and survive independent function instances. An analysis can include one repair call. Failed provider requests consume their reservation. Budget/storage failures stop further model calls.

Do not upload `.env*`, `.venv/`, `personal-notes/`, private access files or credentials. The deployment ignore file excludes them, and the release upload was checked for the configured Gemini key. Keep the private local access notes outside Git.

## Release process

1. Run the backend/API tests and check the current UI. Verify both search modes against the same corpus.
2. Confirm the exact team and project with `vercel project inspect --non-interactive` in the repository root.
3. Inspect the upload with `vercel deploy --dry --json`; check that private files are excluded.
4. Stage production using `vercel deploy --prod --skip-domain` with the explicit team/project.
5. Use authenticated `vercel curl` for protected deployment URLs. Check static assets, both source-inspection routes, access gating, live model output, private saves and isolation between browsers.
6. Promote that production deployment with `vercel promote DEPLOYMENT_URL`. Verify the actual production alias anonymously and in a browser.

Do not disable preview Deployment Protection to test a build. Keep a known-good deployment ID so a failed release can be rolled back. Model-default changes require a new deployment; local `web/.env` changes take effect on the next request.

## Recovery and limitations

A successful model result is returned even if its history save or learning capture fails; the UI displays the failure and retains it in browser storage. Learning capture can be retried from a private saved analysis without another model call. Copy the analysis before clearing browser data. Clearing workspace cookies removes the browser's access to its saved snapshots; rotating the signing key has the same effect. Results from older knowledge revisions are marked so they can be analyzed again.

Provider quotas and overloads are external conditions. The UI reports them instead of showing a fabricated result. The application provides suggested investigations; it does not modify customer systems or confirm that a suggested cause is true. A real production release would need account authentication, retention/deletion policies, operational monitoring and real participant validation.
