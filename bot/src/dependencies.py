"""Composition root: aggregates domain clients into a single container.

``build_dependencies`` is the single place where dependencies are wired. The
container is built once at startup and injected into handlers via aiogram's
contextual data (``dp["deps"]``), so handlers receive it as an argument instead
of importing global singletons.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from src.config import settings
from src.core.backend_client import BackendClient
from src.domains.free_trial import FreeTrialClient
from src.domains.links import LinksClient
from src.domains.payments import PaymentsClient
from src.domains.referrals import ReferralsClient


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class Dependencies:
    free_trial: FreeTrialClient
    links: LinksClient
    referrals: ReferralsClient
    payments: PaymentsClient


def build_dependencies() -> Dependencies:
    backend = BackendClient(
        base_url=settings.api_url, auth_token=settings.bot_auth_token
    )
    return Dependencies(
        free_trial=FreeTrialClient(backend=backend),
        links=LinksClient(backend=backend),
        referrals=ReferralsClient(backend=backend),
        payments=PaymentsClient(
            backend=backend, provider_token=settings.provider_token
        ),
    )
