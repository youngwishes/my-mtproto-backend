from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from src.exceptions import APIError


@dataclass(kw_only=True, slots=True, frozen=True)
class BackendClient:
    """Thin HTTP client over the Django backend REST API.

    Centralises base URL, the ``Bot-Auth-Token`` header, error parsing and
    JSON decoding so domain clients stay free of httpx boilerplate.
    """

    base_url: str
    auth_token: str

    async def post(
        self,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        telegram_id: str | int | None = None,
        expect_json: bool = True,
    ) -> dict[str, Any]:
        return await self._request(
            "POST", path, data=data, telegram_id=telegram_id, expect_json=expect_json
        )

    async def get(
        self,
        path: str,
        *,
        telegram_id: str | int | None = None,
    ) -> dict[str, Any]:
        return await self._request("GET", path, data=None, telegram_id=telegram_id)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None,
        telegram_id: str | int | None,
        expect_json: bool = True,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method,
                    url,
                    data=data,
                    headers={"Bot-Auth-Token": self.auth_token},
                )
                response.raise_for_status()
                return response.json() if expect_json else {}
        except Exception as exc:
            raise APIError(
                telegram_id=telegram_id,
                request_url=url,
                error=str(exc),
                message=self._extract_error_message(exc),
            )

    @staticmethod
    def _extract_error_message(exc: Exception) -> str | None:
        response = getattr(exc, "response", None)
        if response is None:
            return None
        try:
            return response.json().get("error")
        except Exception:
            return None
