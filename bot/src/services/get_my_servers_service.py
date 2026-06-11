from __future__ import annotations

from dataclasses import dataclass

import httpx

import config
from config import API_URL
from exceptions import APIError
from services.handle_error import log_service_error


@dataclass(kw_only=True, slots=True, frozen=True)
class ServerItem:
    location: str
    proxy_link: str


@dataclass(kw_only=True, slots=True, frozen=True)
class MyServersResponse:
    expired_date: str
    servers: list[ServerItem]


@dataclass(kw_only=True, slots=True, frozen=True)
class GetMyServersService:
    url: str = API_URL + "/api/v1/users/my-servers/"

    @log_service_error
    async def __call__(self, *, telegram_id: str) -> MyServersResponse:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.url,
                data={"username": telegram_id},
                headers={"Bot-Auth-Token": config.BOT_AUTH_TOKEN},
            )
            response.raise_for_status()
            data = response.json()
            return MyServersResponse(
                expired_date=data["expired_date"],
                servers=[ServerItem(**item) for item in data["servers"]],
            )
