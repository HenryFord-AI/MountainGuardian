"""
MountainGuardian v1.0 – DeepSeekProvider (the single real v1.0 provider).

Frozen design references:
  - 03_...AI_Agent_Architecture_v1.0.md §4 (deepseek-flash), §5, §6, §20–23
  - 06_...Engineering_Deployment_Spec_v1.0.md §16 (env naming), §17 (secret
    contract: the application reads ONLY os.environ["DEEPSEEK_API_KEY"] and
    never integrates Bitwarden), §21–24, §27 (live tests are opt-in)

Protocol: OpenAI-compatible chat completions at
    {base_url}/chat/completions        (default https://api.deepseek.com)
Structured output via response_format={"type": "json_object"}.
Multimodal via OpenAI-style image_url content parts (capability interface;
the Remote Sensing Agent workflow is NOT part of G01).

Retry / repair policy (bounded, doc 06 §24):
    network / 429 / 5xx : max_retries (default 2)
    schema repair       : max_schema_repairs (default 1)
No recursive self-healing. Total HTTP attempts are hard-capped.

Secrets: the API key is read from os.environ at call time, never stored in
the object, never logged, never included in exceptions or audit records.
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import time
from pathlib import Path
from typing import Any, Optional

import requests

from providers.base_provider import (
    ModelProvider,
    ModelRequest,
    ModelResult,
    ProviderError,
    ProviderErrorCategory,
    ProviderHealth,
    ProviderStatus,
    extract_json_block,
    find_outermost_json,
    monotonic_ms,
    sanitize_text,
    validate_json_schema,
)

logger = logging.getLogger(__name__)

#: Hard cap on total HTTP chat attempts for one generate call:
#: (1 initial + max_retries) * (1 initial generation + max_schema_repairs)
_REPAIR_INSTRUCTION = (
    "Your previous response failed structural validation. Errors:\n"
    "{errors}\n"
    "Return ONLY the corrected valid JSON object conforming to the required "
    "schema. Fix the structure only; do not change the factual content, and "
    "do not wrap the JSON in markdown fences."
)


class DeepSeekProvider(ModelProvider):
    """DeepSeek API provider (OpenAI-compatible), model `deepseek-flash`.

    Non-secret configuration may come from the environment (doc 06 §16):
        DEEPSEEK_MODEL     (default "deepseek-flash")
        DEEPSEEK_BASE_URL  (default "https://api.deepseek.com")
    The secret comes ONLY from:
        os.environ["DEEPSEEK_API_KEY"]   (read at call time)
    """

    provider_name = "deepseek"
    API_KEY_ENV = "DEEPSEEK_API_KEY"
    DEFAULT_MODEL_ID = "deepseek-flash"
    DEFAULT_BASE_URL = "https://api.deepseek.com"
    DEFAULT_TIMEOUT = 30.0          # seconds; explicit timeout required (doc 06 §23)
    DEFAULT_MAX_RETRIES = 2         # bounded network retries (doc 06 §24: max 1–2)
    DEFAULT_MAX_SCHEMA_REPAIRS = 1  # exactly one bounded repair (doc 03 §21)
    HEALTH_TTL_SECONDS = 60.0       # cache so refreshes never hammer the API
    MAX_ERROR_MESSAGE_LEN = 300

    #: v1.0 capability flags (doc 03 §6)
    capabilities = {
        "structured_output": True,
        "multimodal": True,
    }

    def __init__(
        self,
        model_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_schema_repairs: int = DEFAULT_MAX_SCHEMA_REPAIRS,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        health_ttl_seconds: float = HEALTH_TTL_SECONDS,
        session: Optional[requests.Session] = None,
    ):
        self.model_id = (model_id or os.getenv("DEEPSEEK_MODEL")
                         or self.DEFAULT_MODEL_ID)
        self.base_url = (base_url or os.getenv("DEEPSEEK_BASE_URL")
                         or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = float(timeout)
        self.max_retries = int(max_retries)
        self.max_schema_repairs = int(max_schema_repairs)
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)
        self.health_ttl_seconds = float(health_ttl_seconds)
        self._session = session if session is not None else requests.Session()
        self._health_cache: Optional[ProviderHealth] = None
        self._health_cached_at: float = 0.0

    # The object never stores the secret – only the env var NAME.
    def __repr__(self) -> str:
        return (f"DeepSeekProvider(model_id={self.model_id!r}, "
                f"base_url={self.base_url!r}, "
                f"api_key_env={self.API_KEY_ENV!r})")

    # ─── Secret access (never stored, never logged) ───────────────────────────
    def _api_key(self) -> str:
        return os.environ.get(self.API_KEY_ENV, "")

    def _sanitize(self, text: Any) -> str:
        """Scrub the current key value (if any) from outgoing error text."""
        return sanitize_text(str(text), secrets=(self._api_key(),))[: 4000]

    # ─── HTTP layer ────────────────────────────────────────────────────────────
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key()}",
            "Content-Type": "application/json",
        }

    def _classify_http_error(self, resp: requests.Response) -> ProviderError:
        """Map a non-2xx HTTP response to a sanitized ProviderError."""
        status = resp.status_code
        detail = ""
        try:
            body = resp.json()
            detail = str(body.get("error", {}).get("message", "")) \
                or str(body)[:200]
        except Exception:
            detail = (resp.text or "")[:200]
        detail = self._sanitize(detail)[: self.MAX_ERROR_MESSAGE_LEN]

        if status in (401, 403):
            return ProviderError(ProviderErrorCategory.AUTH_ERROR,
                                 f"DeepSeek authentication failed (HTTP {status}): {detail}",
                                 http_status=status, retryable=False)
        if status == 429:
            return ProviderError(ProviderErrorCategory.RATE_LIMIT,
                                 f"DeepSeek rate limit (HTTP 429): {detail}",
                                 http_status=status, retryable=True)
        if 500 <= status <= 599:
            return ProviderError(ProviderErrorCategory.SERVICE_UNAVAILABLE,
                                 f"DeepSeek service unavailable (HTTP {status}): {detail}",
                                 http_status=status, retryable=True)
        return ProviderError(ProviderErrorCategory.INVALID_RESPONSE,
                             f"DeepSeek request rejected (HTTP {status}): {detail}",
                             http_status=status, retryable=False)

    def _chat_completion(
        self,
        messages: list,
        json_mode: bool,
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> tuple:
        """One bounded HTTP chat-completions attempt.

        Returns (content_text, usage_dict, http_status, provider_response_id).
        Raises ProviderError (sanitized) on any failure.
        """
        if not self._api_key():
            raise ProviderError(
                ProviderErrorCategory.AUTH_ERROR,
                f"{self.API_KEY_ENV} environment variable is not set; "
                "cannot call the real DeepSeek API.",
                retryable=False,
            )

        payload: dict = {
            "model": self.model_id,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        url = f"{self.base_url}/chat/completions"
        try:
            resp = self._session.post(
                url, headers=self._headers(), json=payload,
                timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            raise ProviderError(
                ProviderErrorCategory.TIMEOUT,
                self._sanitize(f"DeepSeek request timed out after {self.timeout}s: {exc}"),
                retryable=True) from None
        except requests.exceptions.ConnectionError as exc:
            raise ProviderError(
                ProviderErrorCategory.SERVICE_UNAVAILABLE,
                self._sanitize(f"DeepSeek connection failed: {exc}")[: self.MAX_ERROR_MESSAGE_LEN],
                retryable=True) from None
        except requests.exceptions.RequestException as exc:
            raise ProviderError(
                ProviderErrorCategory.UNKNOWN_PROVIDER_ERROR,
                self._sanitize(f"DeepSeek request error: {exc}")[: self.MAX_ERROR_MESSAGE_LEN],
                retryable=False) from None
        except ProviderError:
            raise
        except Exception as exc:  # defensive: never crash the caller
            raise ProviderError(
                ProviderErrorCategory.UNKNOWN_PROVIDER_ERROR,
                self._sanitize(
                    f"Unexpected DeepSeek transport failure: {exc!r}")[: self.MAX_ERROR_MESSAGE_LEN],
                retryable=False) from None

        if resp.status_code != 200:
            raise self._classify_http_error(resp)

        try:
            body = resp.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise ProviderError(
                ProviderErrorCategory.INVALID_RESPONSE,
                "DeepSeek returned a non-JSON response body.",
                http_status=resp.status_code, retryable=True) from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                ProviderErrorCategory.INVALID_RESPONSE,
                "DeepSeek response missing choices[0].message.content.",
                http_status=resp.status_code, retryable=True) from exc

        if not content or not str(content).strip():
            # Known transient DeepSeek behavior: occasionally empty content.
            raise ProviderError(
                ProviderErrorCategory.INVALID_RESPONSE,
                "DeepSeek returned empty content.",
                http_status=resp.status_code, retryable=True)

        usage = body.get("usage") or {}
        return str(content), usage, resp.status_code, body.get("id")

    # ─── Structured generation pipeline ───────────────────────────────────────
    def _system_prompt_for(self, request: ModelRequest) -> str:
        parts = [request.system_prompt.strip()] if request.system_prompt.strip() else []
        parts.append(
            "You must respond with a single valid JSON object and nothing "
            "else. Do not use markdown fences.")
        if request.schema:
            parts.append("The JSON must conform to this schema:\n"
                         + json.dumps(request.schema, ensure_ascii=False))
        return "\n\n".join(parts)

    def _parse_and_validate(self, text: str,
                            request: ModelRequest) -> tuple:
        """JSON parse → schema validation → scientific/output validation hook.

        Returns (data_or_None, errors_list, parse_failed_bool).
        """
        candidate = extract_json_block(text)
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            sliced = find_outermost_json(candidate)
            if sliced is None:
                return None, ["output is not valid JSON"], True
            try:
                data = json.loads(sliced)
            except (json.JSONDecodeError, ValueError):
                return None, ["output is not valid JSON"], True

        if not isinstance(data, dict):
            return None, ["top-level JSON value must be an object"], True

        errors = validate_json_schema(data, request.schema) if request.schema else []
        if not errors and request.output_validator is not None:
            try:
                hook_errors = request.output_validator(data)
            except Exception as exc:  # defensive: broken hook must not crash
                hook_errors = [f"output_validator raised: {exc!r}"]
            if hook_errors:
                errors.extend(str(e) for e in hook_errors)
        return data, errors, False

    def _failure_result(self, request: ModelRequest, *,
                        category: ProviderErrorCategory, message: str,
                        status_override: Optional[ProviderStatus],
                        start: float, retry_count: int, repair_count: int,
                        usage: dict, http_status: Optional[int],
                        raw_text: str,
                        provider_response_id: Optional[str]) -> ModelResult:
        has_fallback = request.fallback_data is not None
        if status_override is not None:
            status = status_override
        elif has_fallback:
            status = ProviderStatus.FALLBACK_ACTIVE
        elif category in (ProviderErrorCategory.AUTH_ERROR,
                          ProviderErrorCategory.TIMEOUT,
                          ProviderErrorCategory.SERVICE_UNAVAILABLE):
            status = ProviderStatus.OFFLINE
        else:
            status = ProviderStatus.DEGRADED

        sanitized = self._sanitize(message)[: self.MAX_ERROR_MESSAGE_LEN]
        logger.warning(
            "[DeepSeekProvider] generation failed | request=%s run=%s "
            "category=%s fallback=%s detail=%s",
            request.request_id, request.run_id, category.value,
            has_fallback, sanitized)

        return ModelResult(
            success=False,
            data=request.fallback_data if has_fallback else None,
            raw_text=raw_text,
            status=status,
            fallback_used=has_fallback,
            error_category=category,
            error_message=sanitized,
            provider=self.provider_name,
            model_id=self.model_id,
            request_id=request.request_id,
            run_id=request.run_id,
            provider_response_id=provider_response_id,
            latency_ms=monotonic_ms(start),
            retry_count=retry_count,
            repair_count=repair_count,
            http_status=http_status,
            token_usage=dict(usage),
        )

    def _generate(self, request: ModelRequest, messages: list,
                  json_mode: bool) -> ModelResult:
        """Shared bounded generate loop for text and multimodal requests.

        Total HTTP attempts are hard-capped at
        (1 + max_retries) * (1 + max_schema_repairs); the loop can never run
        unbounded (doc 03 §21, doc 06 §24).
        """
        start = time.monotonic()
        max_attempts = (1 + self.max_retries) * (1 + self.max_schema_repairs)
        attempts = 0
        retry_count = 0
        repair_count = 0
        usage_total = {"prompt_tokens": 0, "completion_tokens": 0,
                       "total_tokens": 0}
        http_status: Optional[int] = None
        raw_text = ""
        provider_response_id: Optional[str] = None
        work_messages = list(messages)

        while attempts < max_attempts:
            attempts += 1
            try:
                raw_text, usage, http_status, provider_response_id = \
                    self._chat_completion(
                        work_messages, json_mode,
                        request.temperature, request.max_tokens)
                for k in usage_total:
                    usage_total[k] += int(usage.get(k) or 0)
            except ProviderError as exc:
                if exc.retryable and retry_count < self.max_retries:
                    retry_count += 1
                    time.sleep(min(0.5 * (2 ** (retry_count - 1)), 4.0))
                    continue
                return self._failure_result(
                    request, category=exc.category, message=str(exc),
                    status_override=None, start=start,
                    retry_count=retry_count, repair_count=repair_count,
                    usage=usage_total, http_status=exc.http_status,
                    raw_text=raw_text,
                    provider_response_id=provider_response_id)

            data, errors, parse_failed = self._parse_and_validate(
                raw_text, request)
            if not errors:
                degraded = (retry_count > 0 or repair_count > 0)
                return ModelResult(
                    success=True,
                    data=data,
                    raw_text=raw_text,
                    status=(ProviderStatus.DEGRADED if degraded
                            else ProviderStatus.CONNECTED),
                    fallback_used=False,
                    provider=self.provider_name,
                    model_id=self.model_id,
                    request_id=request.request_id,
                    run_id=request.run_id,
                    provider_response_id=provider_response_id,
                    latency_ms=monotonic_ms(start),
                    retry_count=retry_count,
                    repair_count=repair_count,
                    http_status=http_status,
                    token_usage=usage_total,
                )

            # One bounded structural repair attempt (doc 03 §21)
            if repair_count < self.max_schema_repairs:
                repair_count += 1
                work_messages = work_messages + [
                    {"role": "assistant", "content": raw_text},
                    {"role": "user",
                     "content": _REPAIR_INSTRUCTION.format(
                         errors="\n".join(f"- {e}" for e in errors[:20]))},
                ]
                continue

            category = (ProviderErrorCategory.INVALID_RESPONSE
                        if parse_failed
                        else ProviderErrorCategory.SCHEMA_ERROR)
            return self._failure_result(
                request, category=category,
                message="Model output failed validation after one bounded "
                        f"repair: {'; '.join(errors[:10])}",
                status_override=None, start=start,
                retry_count=retry_count, repair_count=repair_count,
                usage=usage_total, http_status=http_status,
                raw_text=raw_text,
                provider_response_id=provider_response_id)

        # Defensive: hard cap reached (should not happen with the loop math).
        return self._failure_result(
            request, category=ProviderErrorCategory.UNKNOWN_PROVIDER_ERROR,
            message="Provider attempt budget exhausted.",
            status_override=None, start=start, retry_count=retry_count,
            repair_count=repair_count, usage=usage_total,
            http_status=http_status, raw_text=raw_text,
            provider_response_id=provider_response_id)

    def generate_structured(self, request: ModelRequest) -> ModelResult:
        messages = [
            {"role": "system", "content": self._system_prompt_for(request)},
            {"role": "user", "content": request.user_prompt},
        ]
        return self._generate(request, messages, json_mode=True)

    # ─── Multimodal capability interface (G01 §4.D – interface only) ──────────
    @staticmethod
    def _image_part(image: Any) -> dict:
        """Build an OpenAI-compatible image_url content part.

        Accepts: http(s) URL string, local file path string/Path, or raw
        bytes. Supported formats per DeepSeek docs: JPEG, PNG, GIF, WebP.
        """
        if isinstance(image, (bytes, bytearray)):
            b64 = base64.b64encode(bytes(image)).decode("ascii")
            return {"type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        s = str(image)
        if s.startswith(("http://", "https://", "data:")):
            return {"type": "image_url", "image_url": {"url": s}}
        path = Path(s)
        if path.is_file():
            mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
            b64 = base64.b64encode(path.read_bytes()).decode("ascii")
            return {"type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"}}
        raise ProviderError(
            ProviderErrorCategory.INVALID_RESPONSE,
            "Unsupported image input: not a URL, existing file path, "
            "or bytes.",
            retryable=False)

    def generate_multimodal(self, request: ModelRequest,
                            images: Optional[list] = None) -> ModelResult:
        if not self.capabilities.get("multimodal"):
            return self._failure_result(
                request, category=ProviderErrorCategory.INVALID_RESPONSE,
                message="Provider does not support multimodal input.",
                status_override=ProviderStatus.DEGRADED,
                start=time.monotonic(), retry_count=0, repair_count=0,
                usage={}, http_status=None, raw_text="",
                provider_response_id=None)

        content: list = [{"type": "text", "text": request.user_prompt}]
        try:
            for image in (images or []):
                content.append(self._image_part(image))
        except ProviderError as exc:
            return self._failure_result(
                request, category=exc.category, message=str(exc),
                status_override=ProviderStatus.DEGRADED,
                start=time.monotonic(), retry_count=0, repair_count=0,
                usage={}, http_status=None, raw_text="",
                provider_response_id=None)

        messages = [
            {"role": "system", "content": self._system_prompt_for(request)},
            {"role": "user", "content": content},
        ]
        return self._generate(request, messages, json_mode=True)

    # ─── Health check (doc 03 §23: cheap, cached, no token spend) ─────────────
    def health_check(self, force: bool = False) -> ProviderHealth:
        now = time.monotonic()
        if (not force and self._health_cache is not None
                and (now - self._health_cached_at) < self.health_ttl_seconds):
            return self._health_cache

        health = self._probe_health()
        self._health_cache = health
        self._health_cached_at = time.monotonic()
        return health

    def _probe_health(self) -> ProviderHealth:
        if not self._api_key():
            return ProviderHealth(
                status=ProviderStatus.OFFLINE, model_id=self.model_id,
                detail=f"{self.API_KEY_ENV} not set – real model unavailable; "
                       "deterministic fallback applies.")
        start = time.monotonic()
        try:
            resp = self._session.get(
                f"{self.base_url}/models", headers=self._headers(),
                timeout=min(self.timeout, 10.0))
        except requests.exceptions.RequestException as exc:
            return ProviderHealth(
                status=ProviderStatus.OFFLINE, model_id=self.model_id,
                detail=self._sanitize(
                    f"DeepSeek endpoint unreachable: {exc!r}")[: self.MAX_ERROR_MESSAGE_LEN],
                latency_ms=monotonic_ms(start))

        latency = monotonic_ms(start)
        if resp.status_code in (401, 403):
            return ProviderHealth(
                status=ProviderStatus.OFFLINE, model_id=self.model_id,
                detail=f"Authentication rejected (HTTP {resp.status_code}).",
                latency_ms=latency)
        if resp.status_code == 429:
            return ProviderHealth(
                status=ProviderStatus.DEGRADED, model_id=self.model_id,
                detail="Rate limited (HTTP 429).", latency_ms=latency)
        if resp.status_code != 200:
            return ProviderHealth(
                status=ProviderStatus.DEGRADED, model_id=self.model_id,
                detail=f"Unexpected HTTP {resp.status_code} from /models.",
                latency_ms=latency)

        try:
            listed = {m.get("id") for m in resp.json().get("data", [])}
        except Exception:
            listed = set()
        if listed and self.model_id not in listed:
            return ProviderHealth(
                status=ProviderStatus.DEGRADED, model_id=self.model_id,
                detail="Endpoint reachable, but configured model_id not "
                       "listed by /models.",
                latency_ms=latency)
        return ProviderHealth(
            status=ProviderStatus.CONNECTED, model_id=self.model_id,
            detail="DeepSeek endpoint reachable; model available.",
            latency_ms=latency)
