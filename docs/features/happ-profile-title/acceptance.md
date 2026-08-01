# HApp Profile Title Acceptance

- **Verdict:** accepted
- **Scope revision:** 1
- **Reviewed range:** `1bda808..dd72dcf`
- **Reviewed head:** `dd72dcff320d8dd5b961e17539d5bea92014acfe`
- **Reviewed plan item:** HPT-001

## Product outcome

The existing successful public `GET /api/v1/vpn/subscriptions/<token>/` response
now supplies HApp with the exact profile name `mtprotokeys.ru` in the
`profile-title` HTTP header. The subscription URL and Base64 configuration
payload remain unchanged.

## Requirement traceability

| Requirement | Implementation / contract | Test and observed result | Status |
| --- | --- | --- | --- |
| BR-001 — a valid VPN-subscription response communicates HApp title `mtprotokeys.ru` | `VPNSubscriptionView.get` sets `response["profile-title"] = "mtprotokeys.ru"`; `docs/CONTRACTS.md` documents the public GET contract | The existing public happy-path API test received `200 OK` and asserts the exact header. Targeted subscription suite passed: 5 tests. | passed |
| AC-001 — `200 OK` from `GET /api/v1/vpn/subscriptions/<token>/` contains `profile-title: mtprotokeys.ru` | The header is added after constructing the successful `HttpResponse` and before its return. | `test_active_subscription_returns_happ_profiles_without_bot_authentication` asserts `response["profile-title"] == "mtprotokeys.ru"`; it passed. | passed |
| AC-002 — title addition changes neither payload nor current subscription URL | The exact existing decoded Base64 payload assertion was retained unchanged; the feature range contains no URL-routing or URL-generation changes. | The same happy-path test passed its exact decoded VLESS/Hysteria payload assertion. Targeted suite passed: 5 tests; full suite passed: 367 tests. | passed |

## Non-goals and scope check

The exact feature range changes the public contract documentation, the approved
feature artifacts, one response-header line, and one matching test assertion.
It contains no changes to routes or URL generation, DNS, TLS,
`subscription-userinfo`, payload formatting, VPN nodes/profiles, deploy files,
settings, environment, or administrative configuration. The title is a fixed
literal, so no configurable-title surface was introduced.

No blocking in-scope findings, scope-change requests, or follow-ups were found.

## Evidence

- Batch review evidence for exact head `dd72dcf`: BR-001, AC-001, and AC-002
  passed; no blocking, scope, or follow-up findings; verdict `approved`.
- Independent verification: `make test ARGS="apps.vpn.tests.test_subscription_view"`
  passed (5 tests) and `make test` passed (367 tests), with the repository
  `.venv` on `PATH`.
- `docker compose -f docker-compose.yml config --quiet` and
  `git diff --check 1bda808..dd72dcf` completed successfully.
