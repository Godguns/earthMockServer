from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import settings


class DifyChatError(RuntimeError):
    pass


class DifyChatService:
    @staticmethod
    def send_blocking_message(
        *,
        api_key: str,
        query: str,
        inputs: dict[str, Any],
        user_identifier: str,
        conversation_id: str | None = None,
        workflow_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "query": query,
            "inputs": inputs,
            "response_mode": "blocking",
            "user": user_identifier,
            "auto_generate_name": False,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if workflow_id:
            payload["workflow_id"] = workflow_id

        try:
            with httpx.Client(timeout=settings.dify_timeout_seconds) as client:
                response = client.post(
                    f"{settings.dify_base_url.rstrip('/')}/chat-messages",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise DifyChatError(
                f"Dify request failed with status {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.HTTPError as exc:
            raise DifyChatError(f"Dify request failed: {exc}") from exc

        data = response.json()
        return {
            "task_id": data.get("task_id"),
            "message_id": data.get("message_id") or data.get("id"),
            "conversation_id": data.get("conversation_id"),
            "answer": data.get("answer", ""),
            "metadata": data.get("metadata") or {},
            "raw": data,
        }

    @staticmethod
    def parse_json_answer(answer: str) -> dict[str, Any]:
        normalized = (answer or "").strip()
        if not normalized:
            raise DifyChatError("Dify answer was empty.")

        try:
            return json.loads(normalized)
        except json.JSONDecodeError:
            pass

        if normalized.startswith("```"):
            parts = normalized.split("```")
            for part in parts:
                candidate = part.strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                if not candidate:
                    continue
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue

        raise DifyChatError("Dify answer was not valid JSON.")
