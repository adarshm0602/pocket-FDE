"""Private, hidden-input Gemini setup. Run in a user-facing terminal, not a chat tool."""
import getpass
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx
from dotenv import set_key
from pocketfd.llm import LLMError, extract_json
from web.provider import LOCAL_ENV, PROVIDERS, Provider


def clean_key(raw):
    """Normalize common paste artifacts. Returns (key, None) or ("", reason) without echoing input."""
    key = raw.replace("\x1b[200~", "").replace("\x1b[201~", "").strip()
    if key.startswith("GEMINI_API_KEY="):
        key = key.removeprefix("GEMINI_API_KEY=").strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in "'\"":
        key = key[1:-1].strip()
    if not key:
        return "", "No key was received. Paste with Cmd+V (or right-click → Paste), then press Enter."
    if any(c.isspace() for c in key):
        return "", "The pasted text contains spaces or line breaks. Copy only the key itself."
    if any(ord(c) < 32 or ord(c) == 127 for c in key):
        return "", "The pasted text contains terminal control characters. Try pasting again."
    if not re.fullmatch(r"[A-Za-z0-9_.\-]{20,512}", key):
        return "", "The pasted text has unexpected characters or length for an API key."
    return key, None


def verify(key):
    preferred = PROVIDERS["gemini"]["model"]
    # Query the user's account for available model IDs before choosing one.
    response = httpx.get(PROVIDERS["gemini"]["url"] + "/models",
                         headers={"x-goog-api-key": key}, timeout=20)
    if response.status_code != 200:
        messages = {400: "Gemini rejected this key. Check it and try again.",
                    401: "Gemini rejected this key. Check it and try again.",
                    403: "This key does not have permission to use the Gemini API.",
                    429: "The Gemini account's rate limit was reached. Try again shortly."}
        raise LLMError(messages.get(response.status_code, f"Gemini connection failed (HTTP {response.status_code})."))
    models = {m["name"].removeprefix("models/") for m in response.json().get("models", [])
              if "generateContent" in m.get("supportedGenerationMethods", [])}
    choices = [preferred, "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
    # Listed models can still be retired for new projects, so also try other text Flash models on the account.
    skip = ("image", "tts", "audio", "live", "embedding", "robotics", "computer-use")
    discovered = sorted((m for m in models if "flash" in m and not any(s in m for s in skip)), reverse=True)
    discovered.sort(key=lambda m: "lite" in m)  # Prefer full Flash models; lite ones give thinner triage answers.
    available = [m for m in dict.fromkeys(choices + discovered) if m in models][:8]
    if not available:
        raise LLMError("No supported Flash model was found for this key. Use Model settings to choose an available model.")
    # The key is already accepted; if one model is overloaded or unavailable, try the next Flash model.
    print(f"Testing {len(available)} Flash model(s) available to this key…")
    for model in available:
        try:
            result = Provider("gemini", model, key).complete('Return JSON only: {"ok": true}', "Verify the connection by returning valid JSON.")
        except LLMError as exc:
            # LLMError text is our fixed status message; provider bodies and the key are never included.
            print(f"  {model}: {exc}")
            continue
        if extract_json(result.text).get("ok") is True:
            return model
        print(f"  {model}: did not return the expected JSON.")
    raise LLMError(f"None of the {len(available)} Flash models on this key completed a test request (see reasons above).")


def save(key, model):
    if LOCAL_ENV.is_symlink():
        raise OSError("Settings path is a symbolic link")
    if not LOCAL_ENV.exists():
        fd = os.open(LOCAL_ENV, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    os.chmod(LOCAL_ENV, 0o600)
    set_key(LOCAL_ENV, "GEMINI_API_KEY", key)
    set_key(LOCAL_ENV, "LLM_PROVIDER", "gemini")
    set_key(LOCAL_ENV, "LLM_MODEL", model)
    os.chmod(LOCAL_ENV, 0o600)


def main():
    if not sys.stdin.isatty():
        print("Open this setup in Terminal so your API key can be entered with hidden input.")
        return 1
    print("Pocket FDE — private Gemini connection\n")
    print("Paste your Gemini API key below, then press Enter.")
    print("The input is hidden: no characters will appear as you paste.")
    print("A small test request will verify the connection before saving locally.\n")
    try:
        key, problem = clean_key(getpass.getpass("Gemini API key (hidden): "))
        if problem:
            print("\n" + problem + "\nNothing was saved. Run this setup again.")
            return 1
        print("\nVerifying Gemini access…")
        model = verify(key)
        save(key, model)
        key = ""
        print(f"\nConnected successfully with {model}.")
        print("Your key is saved in a private, Git-ignored local settings file.")
        print("Refresh Pocket FDE at http://127.0.0.1:8000 and analyze a case.")
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\nSetup cancelled. Nothing was saved.")
        return 1
    except LLMError as exc:
        print("\n" + str(exc) + "\nNo new settings were saved.")
        return 1
    except Exception:
        # Never print exceptions, HTTP bodies, local configuration, or the key.
        print("\nConnection or saving failed. Nothing was printed from your credentials. Try again.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
