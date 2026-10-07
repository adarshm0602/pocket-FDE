# Pocket FDE application guide

The web workspace serves the core triage pipeline with Keyword and Hybrid search, connected model reasoning, private saved analyses and a shared Second Brain. See the [root quick start](../../README.md#run-locally), [project report](../../PROJECT_REPORT.md) and [deployment guide](DEPLOYMENT.md).

## Investigate an incident

Select a case or choose **+** for a custom issue. Enter its title, symptoms, version and available evidence. Unknown-version cases can inspect sources, but analysis requires v1, v2 or v3. Editing a selected case sends the edited facts. Hidden case answers and resolution fields are excluded from the investigation payload.

Choose a search mode. **Inspect sources** makes no model call. **Analyze incident** returns an owner hypothesis, diagnostic questions, logs and their availability, version caveats, proposed next step, source references and handover. Confirm the evidence before applying a suggestion. Switching modes clears the previous result so its provenance stays clear.

| Mode | Method |
|---|---|
| Keyword search | Existing BM25 + TF-IDF ranking |
| Hybrid search | BM25 + normalized local MiniLM passage similarity, fused by reciprocal rank |

Both modes search the same approved knowledge and enforce the same review/version rules. The bundled corpus has 96 sources; human-approved web learning extends it. Unknown-scope notes retain explicit caveats. Corpus fingerprints identify the knowledge revision used by an analysis.

Hybrid setup runs from the repository root:

```sh
PYTHONPATH=pocket-fde .venv/bin/python -m web.hybrid
```

It downloads the pinned `all-MiniLM-L6-v2` model once. Local queries use the cache at `~/.cache/pocket-fde/embeddings`; hosted builds bundle the model under `.models/`. Missing or failed model loading produces a setup error rather than silent fallback. Embeddings consume no reasoning-provider tokens.

## Connect a model

Use **Model settings** for Gemini, Groq, xAI or local Claude Code. The connection check makes one small model call. Model IDs are editable. The deployed release uses Gemini Flash and discloses any configured Lite fallback used during quota or temporary errors.

For private terminal input:

```sh
.venv/bin/python pocket-fde/web/connect_gemini.py
```

Setup saves local defaults in ignored `web/.env` with private permissions. They take effect on the next request. Browser-session settings take precedence until disconnected. Local session keys remain in server memory for eight hours; hosted keys use encrypted HttpOnly, Secure cookies for the same period. Keys are excluded from responses, browser draft storage and saved analyses. Claude Code requires local authentication and is unavailable in the hosted app.

Alternatively, copy the root `.env.example` to a git-ignored `.env` and privately set the provider key. Do not commit credentials. [Deployment configuration](DEPLOYMENT.md#secrets-and-access) explains the separate hosted environment.

## Second Brain in the browser

Completed analyses automatically create provisional learnings in **Needs review**, reusing measured output without another model call. **View learning** opens the matching entry. Drafts mark causes and fixes as unverified, include questions and source references, and omit raw incident descriptions and supplied logs. Recognized identifiers and credentials are masked; human review must still check confidential free text.

The same incident facts reuse the existing draft and preserve its approval/rejection. New evidence, version or context creates a new draft. Failed analyses and source inspection create none. If capture fails, the analysis is retained; **Retry saving learning** uses a private saved snapshot without another model request.

Browse the reviewed library, search by title/content/source ID and filter version scope. **Add learning** is an optional manual entry. A reviewer provides a name and notes; approval also requires evidence/version confirmation. Pending/rejected entries never enter either search mode. Approved entries refresh both indexes without redeployment, while historical analyses keep their original revision. Review decisions cannot be overwritten; propose a new learning for a correction.

Web learning is shared among users with demo access. Names are entered by users, not verified identities; there is no separate reviewer role. Submissions and decisions use `second-brain-v1/` in private Blob or local data storage. The demo limits the collection to 200 submissions. `POCKET_FDE_BRAIN_NAMESPACE` isolates staging checks; keep the production namespace stable. Local test notes are not copied to cloud storage.

The optional [local Markdown capture tool](../../.claude/skills/capture-learning/SKILL.md) is a separate workflow. Its reviewed files become bundled knowledge when included in a code release.

## Saved work and access

Drafts, selected mode and current result survive refresh through browser storage. Model keys are excluded. Per-case drafts retain the 20 most recently edited cases.

Successful analyses also create immutable private snapshots. **Saved analyses** lists the browser workspace's 20 most recent records. Local storage defaults to `~/.local/share/pocket-fde`; deployment uses private Vercel Blob. The encrypted workspace cookie preserves access across server instances and releases. Clearing cookies loses that browser's history access; there is no account-based recovery or cross-device sync.

A failed save preserves the successful result and displays the failure. Copy valuable results as a backup. Older corpus revisions are identified. Shared Second Brain storage is separate from private history.

The hosted code gates analysis, connection tests, history and Second Brain. Anonymous source inspection uses only the original synthetic corpus. Hosted model requests have a 15-second browser cooldown and 50 daily reservations; failed attempts consume reservations, and unavailable budget storage stops further paid calls.

## Tests and developer evaluations

```sh
.venv/bin/python -m pytest pocket-fde/tests pocket-fde/web/tests -q
```

The suite has 104 checks. Controlled provider tests validate behavior, not live model quality. The pipeline targets 3–6 diagnostic questions and allows one measured repair for malformed/incomplete replies or grounding failures. Persistent gaps are flagged, with no fabricated fallback questions.

Use `web/evaluate_baseline.py` for development cases against a running local server, or `web.evaluate_variants` for repeated variations. These call the connected provider and record actual usage and failures; hidden answers remain offline. Generated runs are excluded from Git by default. See [retained evidence and reproducibility notes](evaluation/README.md).

Internal API retrieval IDs remain `surya` (Keyword) and `hybrid` for compatibility.
