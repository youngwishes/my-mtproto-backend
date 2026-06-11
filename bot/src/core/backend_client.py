from __future__ import annotations

from dataclasses import dataclass
from typing import final

import httpx

from core import config
from core.exceptions import APIError


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class BackendClient:
    async def post(self, *, path: str, telegram_id: str, data: dict) -> dict:
        url = config.API_URL + path
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    data=data,
                    headers={"Bot-Auth-Token": config.BOT_AUTH_TOKEN},
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                body = exc.response.json()
            except Exception:
                raise APIError(telegram_id=telegram_id, request_url=url, error=str(exc))
            raise APIError(
                telegram_id=telegram_id,
                request_url=url,
                error=str(exc),
                message=body.get("error"),
            )
        except httpx.RequestError as exc:
            raise APIError(telegram_id=telegram_id, request_url=url, error=str(exc))
        return response.json()

    async def get(
        self,
        *,
        path: str,
        telegram_id: str | None = None,
        params: dict | None = None,
    ) -> dict:
        url = config.API_URL + path
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    params=params or {},
                    headers={"Bot-Auth-Token": config.BOT_AUTH_TOKEN},
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                body = exc.response.json()
            except Exception:
                raise APIError(
                    telegram_id=telegram_id or "unknown",
                    request_url=url,
                    error=str(exc),
                )
            raise APIError(
                telegram_id=telegram_id or "unknown",
                request_url=url,
                error=str(exc),
                message=body.get("error"),
            )
        except httpx.RequestError as exc:
            raise APIError(
                telegram_id=telegram_id or "unknown",
                request_url=url,
                error=str(exc),
            )
        return response.json()
