# Pocket FDE

Pocket FDE is an incident-triage workspace built by **Surya and Adarsh**. It helps engineers investigate issues across teams, platform versions and tenant configurations using reviewed knowledge and a connected language model.

**[Open the live application](https://pocket-fde-adarsh.vercel.app/)** · [Project report](PROJECT_REPORT.md) · [Verified release](submission/release-verification.md)

The page and synthetic source inspection are public. Ask the project owners for the demo access code to run analyses, open private history or use Second Brain. API keys and access credentials are not included in this repository.

## What it does

- **Investigate incidents:** choose a library case or describe a custom issue. Get an owner hypothesis, diagnostic questions, relevant logs, version considerations, source references and a handover brief.
- **Compare retrieval:** Keyword search uses BM25 + TF-IDF; Hybrid search combines BM25 with local MiniLM embeddings. Both use the same reviewed corpus and triage rules.
- **Keep your work:** incident drafts survive refresh; completed analyses have private saved snapshots scoped to the browser workspace.
- **Build shared knowledge:** a completed analysis automatically drafts a provisional learning in Second Brain → Needs review. A person approves or rejects it. Only approved learning enters either search mode; manual Add learning is also available.

The platform and cases are fictional. Recommendations support investigation and require human verification; the application does not act on customer systems.

## Run locally

Use Python **3.12** and [uv](https://docs.astral.sh/uv/). From the repository root:

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r pocket-fde/web/requirements.txt
PYTHONPATH=pocket-fde .venv/bin/python -m web.hybrid
.venv/bin/python -m uvicorn web.app:app --app-dir pocket-fde --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. Hybrid setup downloads the pinned public embedding model once; queries then run locally on the server.

Connect Gemini through **Model settings**, or run the private terminal setup:

```sh
.venv/bin/python pocket-fde/web/connect_gemini.py
```

You can also use Groq, xAI, or locally authenticated Claude Code. Model settings are editable. See the [application guide](pocket-fde/web/README.md) for configuration and saved-work behavior. The root `.env.example` documents optional server defaults; never commit a populated `.env`.

## Verify

```sh
.venv/bin/python -m pytest pocket-fde/tests pocket-fde/web/tests -q
```

The current suite has **104 passing tests**. Live release checks cover both retrieval modes, Gemini analysis, private history, automatic capture, review persistence and mobile layout. These checks demonstrate the implemented mechanism; they do not establish real-world diagnostic accuracy or a human collaboration benefit.

## Repository

| Path | Purpose |
|---|---|
| `pocket-fde/web/` | FastAPI app, browser UI, providers, hybrid retrieval and storage |
| `pocket-fde/pocketfd/` | Core triage, retrieval, redaction, learning and handover logic |
| `pocket-fde/second-brain/` | Bundled reviewed cards and learning notes |
| `pocket-fde/world/`, `pocket-fde/repos/`, `pocket-fde/cases/` | Fictional platform definitions, simulator and case fixtures |
| `pocket-fde/docs/customer/` | Guides included in the retrieval corpus |
| `pocket-fde/tests/`, `pocket-fde/web/tests/` | Regression tests |
| `pocket-fde/eval/`, `pocket-fde/web/evaluation/` | Evaluation tools and retained verification evidence |
| `.claude/skills/capture-learning/` | Optional local learning capture and human review |
| `submission/` | Demo script, workflow description and release screenshots |

[Project report](PROJECT_REPORT.md) explains the architecture, evidence and limitations. [Deployment guide](pocket-fde/web/DEPLOYMENT.md) records the Vercel setup and release procedure. This public submission repository uses `main`. It contains the cleaned application from the original `dev-adarsh` branch at commit `5002b65`, with fresh publication history. The existing live application remains connected to its original deployment setup.
