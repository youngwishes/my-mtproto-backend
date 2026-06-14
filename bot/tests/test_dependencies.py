from __future__ import annotations

from src.dependencies import Dependencies, build_dependencies
from src.domains.free_trial import FreeTrialClient
from src.domains.links import LinksClient
from src.domains.payments import PaymentsClient
from src.domains.referrals import ReferralsClient


def test_build_dependencies_wires_every_client():
    deps = build_dependencies()

    assert isinstance(deps, Dependencies)
    assert isinstance(deps.free_trial, FreeTrialClient)
    assert isinstance(deps.links, LinksClient)
    assert isinstance(deps.referrals, ReferralsClient)
    assert isinstance(deps.payments, PaymentsClient)


def test_build_dependencies_shares_a_single_backend():
    deps = build_dependencies()

    assert deps.links.backend is deps.free_trial.backend
    assert deps.referrals.backend is deps.payments.backend
    assert deps.links.backend is deps.payments.backend


def test_build_dependencies_reads_config():
    deps = build_dependencies()

    backend = deps.links.backend
    assert backend.base_url == "http://backend"
    assert backend.auth_token == "test-auth"
    assert deps.payments.provider_token == "test-provider"
