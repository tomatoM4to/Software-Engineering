"""
[Issue #4] LLM 클라이언트 — Anthropic API 비동기 호출
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-4-5"
DEFAULT_MAX_TOKENS = 1024
REQUEST_TIMEOUT = 30.0


# JSON 파싱


def _extract_json(text: str) -> dict[str, Any]:
    """LLM 응답에서 ```json ... ``` 또는 순수 JSON 블록 추출."""
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        raw = m.group(1).strip()
    else:
        m2 = re.search(r"\{.*\}", text, re.DOTALL)
        if not m2:
            raise ValueError(
                f"LLM 응답에서 JSON을 찾을 수 없습니다. 응답: {text[:200]}"
            )
        raw = m2.group(0).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 파싱 실패: {exc} | 원본: {raw[:300]}") from exc


def _validate_json(data: dict[str, Any]) -> dict[str, Any]:
    """필수 필드 검증 및 잘못된 값 교정."""
    pos = str(data.get("position", "HOLD")).upper()
    if pos not in ("BUY", "SELL", "HOLD"):
        logger.warning("[LLMClient] 잘못된 position '%s' → HOLD 교정", pos)
        pos = "HOLD"
    data["position"] = pos

    try:
        conf = max(1, min(10, int(data.get("confidence", 5))))
    except (TypeError, ValueError):
        conf = 5
    data["confidence"] = conf

    data.setdefault("chart_basis", "차트 근거 없음")
    data.setdefault("key_signals", [])
    data.setdefault("risk_factors", [])

    for k in ("key_signals", "risk_factors"):
        if not isinstance(data[k], list):
            data[k] = [str(data[k])]

    for k in ("target_price", "stop_loss"):
        v = data.get(k)
        if v is not None:
            try:
                iv = int(float(str(v)))
                data[k] = iv if iv > 0 else None
            except (TypeError, ValueError):
                data[k] = None

    return data


# 동기 HTTP 호출 (requests)


def _call_anthropic_sync(
    *,
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    model: str,
    max_tokens: int,
    persona_label: str,
) -> tuple[dict[str, Any], str, float]:
    """
    requests 로 Anthropic API 동기 호출.
    asyncio.to_thread() 로 감싸서 이벤트 루프를 블로킹하지 않음.
    """
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_API_VERSION,
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    t0 = time.perf_counter()
    logger.info("[%s agent] LLM 호출 시작 (model=%s)", persona_label, model)

    try:
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"[{persona_label} agent] Anthropic API 호출 실패: {exc}"
        ) from exc

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info("[%s agent] 응답 수신 %.1f ms", persona_label, elapsed_ms)

    resp_data = resp.json()
    raw_text = "".join(
        b.get("text", "")
        for b in resp_data.get("content", [])
        if b.get("type") == "text"
    )

    if not raw_text.strip():
        raise ValueError(f"[{persona_label} agent] LLM 빈 응답")

    parsed = _extract_json(raw_text)
    validated = _validate_json(parsed)

    logger.info(
        "[%s agent] 결정: %s (확신도: %d)",
        persona_label,
        validated["position"],
        validated["confidence"],
    )
    return validated, raw_text, elapsed_ms


# 비동기 래퍼


async def call_llm_async(
    *,
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    persona_label: str = "unknown",
) -> tuple[dict[str, Any], str, float]:
    return await asyncio.to_thread(
        _call_anthropic_sync,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
        persona_label=persona_label,
    )
