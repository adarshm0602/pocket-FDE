"""Provider abstraction. Swap the model with LLM_PROVIDER / LLM_MODEL env vars."""
import json
import os
import subprocess
import time
from dataclasses import dataclass


@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    provider: str


class LLMError(RuntimeError):
    pass


def _est(s: str) -> int:
    return max(1, len(s) // 4)


def _claude_cli(prompt: str, system: str, model: str) -> LLMResult:
    # Uses the local Claude Code login; no API key. A custom system prompt and no tools
    # keeps the overhead small and the call a pure text completion.
    cmd = ["claude", "-p", "--output-format", "json", "--tools", "", "--model", model,
           "--system-prompt", system or "You are a precise assistant."]
    t0 = time.time()
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=180)
    if p.returncode != 0:
        raise LLMError(f"claude cli failed: {p.stderr[:300] or p.stdout[:300]}")
    d = json.loads(p.stdout)
    if d.get("is_error"):
        raise LLMError(str(d.get("result"))[:300])
    u = d.get("usage", {})
    inp = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
    return LLMResult(d["result"], inp, u.get("output_tokens", 0), time.time() - t0, f"claude_cli:{model}")


def _ollama(prompt: str, system: str, model: str) -> LLMResult:
    import urllib.request
    body = json.dumps({"model": model, "prompt": prompt, "system": system, "stream": False}).encode()
    req = urllib.request.Request("http://localhost:11434/api/generate", body, {"Content-Type": "application/json"})
    t0 = time.time()
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=120).read())
    except Exception as e:  # connection refused etc.
        raise LLMError(f"ollama unavailable: {e}")
    return LLMResult(d["response"], d.get("prompt_eval_count", _est(prompt)), d.get("eval_count", 0),
                     time.time() - t0, f"ollama:{model}")


_MOCK_HANDLER = None


def set_mock_handler(fn):
    """Tests install fn(prompt, system) -> str."""
    global _MOCK_HANDLER
    _MOCK_HANDLER = fn


def _mock(prompt: str, system: str) -> LLMResult:
    text = _MOCK_HANDLER(prompt, system) if _MOCK_HANDLER else "{}"
    return LLMResult(text, _est(prompt + system), _est(text), 0.0, "mock")


def complete(prompt: str, system: str = "", tier: str = "frontier", model: str = None) -> LLMResult:
    provider = os.getenv("LLM_PROVIDER", "claude_cli")
    if provider == "mock":
        return _mock(prompt, system)
    if tier == "local":
        return _ollama(prompt, system, os.getenv("LOCAL_MODEL", "gemma3:1b"))
    if provider == "ollama":
        return _ollama(prompt, system, os.getenv("LLM_MODEL", "gemma3:1b"))
    return _claude_cli(prompt, system, model or os.getenv("LLM_MODEL", "sonnet"))


def extract_json(text: str):
    """Parse the first JSON object/array in an LLM reply (tolerates code fences)."""
    s = text.strip()
    if "```" in s:
        parts = s.split("```")
        s = max(parts[1::2], key=len, default=s)
        if s.startswith("json"):
            s = s[4:]
    for open_c, close_c in (("{", "}"), ("[", "]")):
        i, j = s.find(open_c), s.rfind(close_c)
        if i != -1 and j > i:
            try:
                return json.loads(s[i:j + 1])
            except json.JSONDecodeError:
                continue
    raise LLMError(f"no JSON in reply: {text[:200]}")
