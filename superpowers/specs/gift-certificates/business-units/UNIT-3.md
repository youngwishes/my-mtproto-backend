# UNIT-3: Certificate Control And Support

## Objective

Give the business enough control over certificates to keep the gift product reliable, supportable, and protected from obvious abuse.

## Scope

- Define certificate lifecycle states such as created, activated, and expired.
- Enforce one-time use.
- Enforce the 1-year pre-activation expiry window.
- Preserve enough purchase and activation context for support to answer basic questions.
- Keep certificate activation separate from free trial and referral program accounting.
- Make certificate purchases and activations distinguishable from regular subscription purchases.

## Out of Scope

- Public buyer dashboard for certificate status.
- Automated reminders for unused certificates.
- Refund workflow.
- Campaign promo codes or multi-use marketing codes.
- Recipient locking or identity verification before activation.

## Expected Output

Implementation planning should define the operational certificate rules, support-visible states, and the minimum reporting needed to distinguish bought, unused, activated, expired, and invalid certificates.

## Acceptance Criteria

- Support can determine whether a certificate was purchased, activated, unused, or expired.
- Expired certificates cannot be activated.
- Used certificates cannot be activated again.
- Certificate records remain auditable after activation.
- Certificate logic does not alter free trial or referral counters.

## Dependencies

None.
