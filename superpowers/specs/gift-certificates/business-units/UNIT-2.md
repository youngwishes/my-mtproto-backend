# UNIT-2: Certificate Activation

## Objective

Allow any Telegram user who receives a valid certificate code to activate it for 30 days of BeatVault access.

## Scope

- Accept a certificate code in the bot.
- Activate only valid, unused, non-expired certificates.
- Extend an active subscription by 30 days when the recipient already has active access.
- Issue a new 30-day key when the recipient has no active subscription.
- Allow the original buyer to activate their own certificate if they choose.
- Give clear feedback for successful activation and rejected codes.

## Out of Scope

- Buying certificates.
- Referral rewards from certificate activation.
- Free trial state changes from certificate activation.
- Partial redemption, refunds, or transfer after activation.
- User-facing certificate management after activation.

## Expected Output

Implementation planning should define the activation journey, recipient-facing messages, and the business result of each activation state: extended subscription, new subscription, invalid code, used code, or expired code.

## Acceptance Criteria

- A valid unused certificate grants exactly 30 days of access.
- An active subscriber keeps their current remaining time and receives an additional 30 days.
- A user without active access receives a new 30-day subscription.
- The same certificate cannot be activated twice.
- Certificate activation does not mark the free trial as used and does not count as referral activation.

## Dependencies

Depends on UNIT-1 for purchased certificate creation and UNIT-3 for validity and one-time-use rules.
