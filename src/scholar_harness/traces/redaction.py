from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

DEFAULT_SECRET_MARKERS = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "token",
        "password",
        "secret",
        "cookie",
        "credential",
    }
)


class TraceSanitizer:
    def __init__(
        self,
        *,
        secret_markers: frozenset[str] = DEFAULT_SECRET_MARKERS,
        max_payload_bytes: int = 256 * 1024,
        preview_bytes: int = 32 * 1024,
    ) -> None:
        self.secret_markers = secret_markers
        self.max_payload_bytes = max_payload_bytes
        self.preview_bytes = preview_bytes

    def prepare(self, value: Any) -> dict[str, Any]:
        redacted = self._redact(value)
        if not isinstance(redacted, dict):
            redacted = {"value": redacted}
        encoded = self.dumps(redacted).encode("utf-8")
        if len(encoded) <= self.max_payload_bytes:
            return redacted
        return {
            "truncated": True,
            "original_bytes": len(encoded),
            "preview": encoded[: self.preview_bytes].decode("utf-8", errors="ignore"),
        }

    @staticmethod
    def dumps(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

    def _redact(self, value: Any) -> Any:
        if isinstance(value, BaseModel):
            return self._redact(value.model_dump(mode="json"))
        if isinstance(value, Mapping):
            result = {}
            for key, item in value.items():
                key_text = str(key)
                if self._is_secret_key(key_text):
                    result[key_text] = "[REDACTED]"
                else:
                    result[key_text] = self._redact(item)
            return result
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [self._redact(item) for item in value]
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value

    def _is_secret_key(self, key: str) -> bool:
        snake_case = re.sub(r"(?<!^)(?=[A-Z])", "_", key).casefold().replace("-", "_")
        return any(
            snake_case == marker or snake_case.endswith(f"_{marker}")
            for marker in self.secret_markers
        )
