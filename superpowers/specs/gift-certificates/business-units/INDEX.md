# Business Units: Gift Certificates

## Source

`superpowers/specs/gift-certificates/SPEC.md`

## Slug

`gift-certificates`

## Split Summary

The idea is split by business outcome: selling a gift certificate to the buyer, redeeming the certificate for the recipient, and maintaining operational control over one-time codes. Each unit owns a separate promise and can be planned without taking over another unit's business decision.

## Units

- `UNIT-1.md`: Buyer can purchase a 30-day gift certificate and receive a forwardable code.
- `UNIT-2.md`: Recipient can activate a valid certificate for exactly 30 days of access.
- `UNIT-3.md`: Business can control certificate validity, support cases, and abuse boundaries.

## Execution Order

UNIT-1 and UNIT-3 can be planned in parallel. UNIT-2 depends on the certificate rules from UNIT-3 and the existence of purchasable certificates from UNIT-1, but its user workflow is distinct.
