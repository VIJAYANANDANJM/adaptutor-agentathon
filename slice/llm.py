"""
The one place a model is ever called.

Every architectural concern that touches a model call is enforced HERE, in one
function, rather than sprinkled across the agents:

    typed contracts   the reply is parsed into your schema, or repaired once
    bounded loops     the token fence is checked before the request goes out
    degradation       a named fallback model, a different provider family
    observability     one span per call, no-ops if tracing is not configured
"""
from __future__ import annotations

import json
import time
from typing import Any, Type

import httpx
from pydantic import BaseModel, ValidationError

from .budget import Budget
from .config import Settings

API = "https://openrouter.ai/api/v1"


class ModelError(RuntimeError):
    """Base for everything that can go wrong at the model boundary."""


class CapExhausted(ModelError):
    """This team's key has spent its cap. One team affected."""


class PoolExhausted(ModelError):
    """The shared account is out of credit. EVERY team is affected."""


class SchemaFailure(ModelError):
    """The model would not produce the agreed shape, even after a repair pass."""


class Truncated(ModelError):
    """The reply was cut off at max_tokens, mid-answer."""


def _classify_402(body: dict) -> ModelError:
    err = (body or {}).get("error", {}) or {}
    src = ((err.get("metadata") or {}).get("limit_source") or "").lower()
    msg = err.get("message", "") or json.dumps(body)[:300]
    if "key" in src:
        return CapExhausted(
            "Your team's API key has reached its spending cap.\n"
            "  -> Reduce SLICE_MAX_TOKENS, or ask the key desk for a top-up.\n"
            f"  (provider said: {msg})")
    return PoolExhausted(
        "The SHARED account is out of credit - this affects every team, not "
        "just yours.\n  -> Tell an organiser now. Do not wait.\n"
        f"  (provider said: {msg})")


def complete(
    *,
    settings: Settings,
    budget: Budget,
    messages: list[dict],
    schema: Type[BaseModel] | None = None,
    model: str | None = None,
    step: str = "call",
    timeout: float = 120.0,
) -> Any:
    """Call a model. Returns a parsed `schema` instance, or raw text if no
    schema was asked for.

    Raises CapExhausted / PoolExhausted / SchemaFailure / BudgetExceeded - all
    of which the runner handles explicitly.
    """
    budget.check_tokens()

    primary = model or settings.model
    attempts: list[tuple[str, str]] = [(primary, "primary")]
    if settings.fallback_model and settings.fallback_model != primary:
        attempts.append((settings.fallback_model, "fallback"))

    last_text = ""
    for mid, role in attempts:
        body = {
            "model": mid,
            "max_tokens": settings.max_tokens,
            "temperature": 0,
            "messages": messages,
        }
        if schema is not None:
            body["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {settings.api_key}",
            "HTTP-Referer": "https://github.com/VIJAYANANDANJM/adaptutor-agentathon",
            "X-Title": "AdaptTutor",
        }

        # Waiting / retry loop for rate-limits (429) or transient provider pauses (502, 503)
        max_retries = 3
        r = None
        for retry_idx in range(max_retries):
            try:
                r = httpx.post(f"{API}/chat/completions", json=body, timeout=timeout, headers=headers)
            except (httpx.RequestError, httpx.TimeoutException) as e:
                if retry_idx < max_retries - 1:
                    time.sleep(2 * (retry_idx + 1))
                    continue
                if role == "fallback":
                    raise ModelError(
                        f"Both models unreachable ({e}). Run "
                        "`python scripts/doctor.py` - this is usually the network "
                        "or a provider outage, not your code.") from e
                break

            if r is not None and r.status_code in (429, 500, 502, 503, 504):
                if retry_idx < max_retries - 1:
                    time.sleep(2 * (retry_idx + 1))
                    continue
                if role == "primary":
                    break
                raise ModelError(f"{mid} returned HTTP {r.status_code}: {r.text[:300]}")
            break

        if r is None:
            continue

        if r.status_code == 402:
            raise _classify_402(_safe_json(r))
        if r.status_code != 200:
            if role == "primary" and len(attempts) > 1:
                continue
            raise ModelError(f"{mid} returned HTTP {r.status_code}: {r.text[:300]}")

        data = r.json()
        used = (data.get("usage") or {}).get("total_tokens", 0)
        budget.record_tokens(used)
        choice = data["choices"][0]
        last_text = choice["message"]["content"] or ""

        if choice.get("finish_reason") == "length":
            if role == "primary" and len(attempts) > 1:
                continue
            raise Truncated(
                f"{mid} was cut off at max_tokens ({settings.max_tokens}) "
                "before finishing. This is not a prompt problem.\n"
                "  -> Raise SLICE_MAX_TOKENS, or ask the agent for a shorter "
                "answer (fewer items, shorter fields).")

        if schema is None:
            return last_text

        parsed = _parse(last_text, schema)
        if parsed is not None:
            return parsed

        repaired = _repair(settings, budget, messages, last_text, schema, mid, timeout)
        if repaired is not None:
            return repaired
        if role == "fallback":
            break

    raise SchemaFailure(
        f"No model produced valid {schema.__name__ if schema else 'output'} "
        f"after a repair pass. Last reply began: {last_text[:200]!r}")


def _safe_json(r: httpx.Response) -> dict:
    try:
        return r.json()
    except Exception:
        return {"error": {"message": r.text[:300]}}


def _strip_fence(text: str) -> str:
    t = (text or "").strip()
    # 1. Look for markdown code fence containing JSON
    if "```" in t:
        parts = t.split("```")
        for i in range(1, len(parts), 2):
            candidate = parts[i].strip()
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            if "{" in candidate and "}" in candidate:
                f = candidate.find("{")
                l = candidate.rfind("}")
                return candidate[f:l + 1].strip()

    # 2. Extract outermost JSON object { ... }
    first_brace = t.find("{")
    last_brace = t.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return t[first_brace:last_brace + 1].strip()

    return t


def _parse(text: str, schema: Type[BaseModel]):
    try:
        return schema.model_validate_json(_strip_fence(text))
    except (ValidationError, ValueError):
        return None


def _repair(settings, budget, messages, bad_text, schema, mid, timeout):
    budget.check_tokens()
    try:
        schema.model_validate_json(_strip_fence(bad_text))
    except Exception as e:
        why = str(e)[:600]
    else:
        return None
    fix = messages + [
        {"role": "assistant", "content": bad_text[:2000]},
        {"role": "user", "content":
            "That did not match the required schema.\n\n"
            f"Error:\n{why}\n\n"
            f"Required JSON schema:\n{json.dumps(schema.model_json_schema())}\n\n"
            "Reply with the corrected JSON object and nothing else."},
    ]
    try:
        r = httpx.post(f"{API}/chat/completions", timeout=timeout,
                       headers={"Authorization": f"Bearer {settings.api_key}"},
                       json={"model": mid, "max_tokens": settings.max_tokens,
                             "temperature": 0, "messages": fix,
                             "response_format": {"type": "json_object"}})
    except httpx.RequestError:
        return None
    if r.status_code == 402:
        raise _classify_402(_safe_json(r))
    if r.status_code != 200:
        return None
    data = r.json()
    budget.record_tokens((data.get("usage") or {}).get("total_tokens", 0))
    return _parse(data["choices"][0]["message"]["content"] or "", schema)
