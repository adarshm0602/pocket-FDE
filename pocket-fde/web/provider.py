"""Request-scoped LLM adapters. API keys stay on the server, never in model prompts."""
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from dotenv import dotenv_values

import httpx

from pocketfd.llm import LLMError, LLMResult, _claude_cli

PROVIDERS = {
    "groq": {"label": "Groq", "model": "openai/gpt-oss-120b", "url": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY"},
    "gemini": {"label": "Gemini", "model": "gemini-3.5-flash", "url": "https://generativelanguage.googleapis.com/v1beta", "key_env": "GEMINI_API_KEY"},
    "xai": {"label": "Grok / xAI", "model": "grok-4.7", "url": "https://api.x.ai/v1", "key_env": "XAI_API_KEY"},
    "claude_cli": {"label": "Claude Code (local)", "model": "sonnet", "key_env": None},
}
LOCAL_ENV = Path(__file__).resolve().parent / ".env"
RETRYABLE_STATUS = {500, 502, 503, 504}
RETRY_DELAYS = (1.5, 4.0)


class ProviderHTTPError(LLMError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Provider:
    name: str
    model: str
    key: str = field(default="", repr=False)
    fallback_model: str = ""

    def complete(self, prompt, system="", tier="frontier"):
        started = time.monotonic()
        try:
            return self._complete(prompt, system, tier)
        except ProviderHTTPError as exc:
            if self.name != "gemini" or not self.fallback_model or self.fallback_model == self.model or exc.status not in RETRYABLE_STATUS | {429}:
                raise
            result = Provider(self.name, self.fallback_model, self.key)._complete(prompt, system, tier)
            return LLMResult(result.text, result.input_tokens, result.output_tokens,
                             time.monotonic() - started, result.provider)

    def _complete(self, prompt, system="", tier="frontier"):
        if self.name == "claude_cli":
            try:
                return _claude_cli(prompt, system, self.model)
            except subprocess.TimeoutExpired as exc:
                raise LLMError("Claude Code took too long to respond. Try again.") from exc
            except (OSError, ValueError, KeyError) as exc:
                raise LLMError("Claude Code could not complete this request. Check your local login.") from exc
        spec = PROVIDERS[self.name]
        if not self.key:
            raise LLMError("Add an API key in Model settings first.")
        if self.name == "gemini":
            url = spec["url"] + "/models/" + quote(self.model, safe="") + ":generateContent"
            headers = {"x-goog-api-key": self.key}
            config = {"responseMimeType": "application/json", "maxOutputTokens": 8192}
            if self.model.startswith("gemini-3"):
                config["thinkingConfig"] = {"thinkingLevel": "LOW"}
            body = {"systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": config}
        else:
            url = spec["url"] + "/chat/completions"
            headers = {"Authorization": "Bearer " + self.key}
            body = {"model": self.model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"}, "max_completion_tokens": 3500}
            if self.name == "groq" and self.model.startswith("openai/gpt-oss"):
                body["reasoning_effort"] = "low"
        start = time.monotonic()
        for attempt in range(len(RETRY_DELAYS) + 1):
            try:
                response = httpx.post(url, headers=headers, json=body, timeout=httpx.Timeout(90, connect=10))
            except httpx.TimeoutException as exc:
                raise LLMError("The model took too long to respond. Try again.") from exc
            except httpx.RequestError as exc:
                raise LLMError("Cannot reach the model provider. Check your connection and try again.") from exc
            # Overloaded/temporarily unavailable models (common on Gemini previews) usually recover in seconds.
            if response.status_code not in RETRYABLE_STATUS or attempt == len(RETRY_DELAYS):
                break
            time.sleep(RETRY_DELAYS[attempt])
        if response.status_code >= 400:
            messages = {
                400: "The provider rejected the key or model settings. Check both in Model settings.",
                401: "The provider rejected this API key. Check it in Model settings.",
                403: "This key does not have access to the selected model.",
                404: "The selected model was not found. Check the model ID.",
                429: "The provider's quota or rate limit was reached. Wait or check your account.",
                500: "The provider had an internal error. Try again shortly.",
                503: "The selected model is temporarily overloaded at the provider. Try again shortly or choose another model.",
                504: "The provider timed out. Try again shortly.",
            }
            # Provider bodies may echo request data or secrets; return only a safe status message.
            raise ProviderHTTPError(response.status_code, messages.get(response.status_code, f"The provider could not complete the request (HTTP {response.status_code})."))
        try:
            data = response.json()
            if self.name == "gemini":
                candidate = data["candidates"][0]
                if candidate.get("finishReason") == "MAX_TOKENS":
                    raise LLMError("The model response was cut short. Try a shorter issue description.")
                text = "".join(p.get("text", "") for p in candidate["content"]["parts"] if not p.get("thought"))
                if not text.strip():
                    raise ValueError("empty response")
                usage = data.get("usageMetadata", {})
                inp = int(usage.get("promptTokenCount", 0))
                output = int(usage["totalTokenCount"]) - inp if "totalTokenCount" in usage else int(usage.get("candidatesTokenCount", 0)) + int(usage.get("thoughtsTokenCount", 0))
                return LLMResult(text, inp, output, time.monotonic() - start, f"{self.name}:{self.model}")
            choice = data["choices"][0]
            text = choice["message"]["content"]
            if choice.get("finish_reason") == "length":
                raise LLMError("The model response was cut short. Try a shorter issue description.")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("empty response")
            usage = data.get("usage", {})
            return LLMResult(text, int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0)),
                             time.monotonic() - start, f"{self.name}:{self.model}")
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise LLMError("The provider returned an unreadable response. Try again.") from exc


def claude_logged_in():
    try:
        result = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True, timeout=8)
        import json
        return bool(json.loads(result.stdout).get("loggedIn"))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def default_provider():
    config = dict(os.environ)
    # Private terminal setup takes effect without a server restart.
    config.update({k: v for k, v in dotenv_values(LOCAL_ENV).items()
                   if k in {"LLM_PROVIDER", "LLM_MODEL", "LLM_FALLBACK_MODEL", "GEMINI_API_KEY"} and v is not None})
    requested = config.get("LLM_PROVIDER", "groq")
    name = requested if requested in PROVIDERS else "groq"
    spec = PROVIDERS[name]
    key = config.get(spec["key_env"], "") if spec["key_env"] else ""
    if not key and name == "groq":
        for alternative in ("gemini", "xai"):
            if config.get(PROVIDERS[alternative]["key_env"]):
                name, spec = alternative, PROVIDERS[alternative]
                key = config[spec["key_env"]]
                break
    return Provider(name, config.get("LLM_MODEL") or spec["model"], key,
                    config.get("LLM_FALLBACK_MODEL", "") if name == "gemini" else "")
