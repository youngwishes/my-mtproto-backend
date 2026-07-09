# UNIT-1: Certificate Purchase

## Objective

Allow a user to buy a 30-day MTPRoto Keys gift certificate in the Telegram bot and receive a one-time code they can forward to another person.

## Scope

- Separate the gift certificate purchase from the regular "buy or extend my subscription" purchase.
- Support payment in rubles via YuKassa and in Telegram Stars.
- Promise the buyer a 30-day certificate, not an immediate extension of their own subscription.
- Deliver the certificate code after successful payment in the format `KEY-XXXX-XXXX`.
- Provide buyer-facing copy that makes forwarding the code natural and clear.

## Out of Scope

- Activating the certificate for the recipient.
- Restricting the certificate to a specific recipient.
- Showing a certificate history or status cabinet to the buyer.
- Supporting durations other than 30 days.
- Supporting discounts, bundles, or multi-certificate checkout.

## Expected Output

Implementation planning should define the purchase flow, payment confirmation behavior, buyer-facing bot messages, and the business record that proves a certificate was purchased rather than a regular subscription.

## Acceptance Criteria

- A buyer can choose to buy a gift certificate without extending their own subscription.
- The buyer can pay with either supported payment method.
- A successful payment produces exactly one one-time certificate code.
- The bot message clearly tells the buyer that the code can be forwarded.
- Failed or cancelled payment does not create a usable certificate.

## Dependencies

Depends on UNIT-3 for shared certificate validity rules and support visibility.
