# VLESS cross-repository release checklist

This checklist is the tracked protocol, not release evidence. Store no secrets,
node addresses, raw subscription URLs, or mutable branch/image references here.
Fill the evidence in the PR or release report only after every SHA is final.

## Compatibility matrix

| Backend consumer | Agent provider | Contract | Snapshot schema | Result |
|---|---|---|---|---|
| reviewed VLESS backend SHA | reviewed and test-deployed agent SHA | v1 | 1.0 | compatible |
| any backend | agent with unknown contract major | other | any | incompatible; no mutation or sales |
| v1 backend | agent with unknown schema major | v1 | other | incompatible; no mutation or sales |

Contract v1 accepts at most 5,000 entries and 1,048,576 canonical JSON bytes per
node. Lower operational capacity may block a node, but an agent must never accept
above those maxima. Changing these maxima or canonical hash semantics requires a
new contract major.

## Immutable release evidence

- `BACKEND_SHA=<40-character reviewed commit SHA>`
- `AGENT_SHA=<40-character reviewed and test-deployed commit SHA>`
- `CONTRACT_MAJOR=<v1>`
- `SCHEMA_MAJOR=<1>`
- `XRAY_VERSION=<pinned semantic version>`
- `XRAY_IMAGE_DIGEST=<sha256 digest>`
- `CONTRACT_TEST_RESULTS=<commands and pass/fail results>`
- `ROLLBACK_BACKEND_SHA=<reviewed compatible commit SHA>`
- `ROLLBACK_AGENT_SHA=<reviewed compatible and schema-safe commit SHA>`

The evidence must also record the compatibility decision, agent test-deploy
health, empty and non-empty exact-snapshot tests, stale/conflict/overflow tests,
restart recovery, rollback rehearsal, and controlled Android/iOS import and
connection smoke results. Verify that both SHAs and the Xray digest are immutable
and match the deployed artifacts.

## Required order and gates

Complete these gates in order for one exact compatible SHA pair:

1. Agent PR and review — contract/provider/runtime tests pass on the exact agent SHA.
2. Agent test deploy — deploy that SHA and pinned Xray digest; complete recovery and rollback rehearsal.
3. Backend integration and PR — integrate only against the reviewed, test-deployed agent evidence.
4. Controlled smoke — with sales off, verify health, empty/non-empty snapshots, import, connection, receipt recovery, reissue, and refund behavior.
5. Explicit production permission — request permission naming both exact SHAs; permission applies only to this pair.

The backend MUST NOT send `PUT /api/v1/snapshot` before the agent SHA is reviewed and test-deployed.
The operator MUST NOT enable VPN sales without a verified compatible backend/agent SHA pair.
Agent-first deployment does not authorize backend deploy, sales enablement, merge,
or production mutation. Every repository requires its own PR review.

## Rollback gates

1. Turn new sales off first. Sales off must not stop an accepted paid receipt,
   subscription serving, recovery, or reconcile.
2. Select the recorded compatible backend and agent rollback SHAs. Preserve the
   durable snapshot before an agent downgrade and verify schema compatibility.
3. Do not roll back expand migrations. Verify existing paid receipts and current
   reconcile continue before completing the rollback.
4. A pre-VLESS backend is not a valid rollback target after the first accepted paid receipt.
   If no compatible code rollback exists, retain the current runtime with sales
   off and prepare a reviewed forward fix.

Rollback never disables already-paid access or discards a receipt. A new release
pair or changed tracked artifact invalidates prior evidence and needs a new review,
test deploy, controlled smoke, and explicit production permission.
