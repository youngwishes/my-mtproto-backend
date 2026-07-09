# Gift Certificates

## Decision

pursue

## Status

Fixed

## Slug

gift-certificates

## Problem

MTPRoto Keys users can buy or extend only their own subscription. They have no simple way to pay for 30 days of access as a gift for a friend or relative without sharing their own account or coordinating payment manually.

## Target User

Primary user: an existing or new MTPRoto Keys user who wants to buy 30 days of MTProto proxy access for another Telegram user.

Recipient: a friend or relative who receives a certificate code and activates it in the Telegram bot.

## Proposed Solution

Add one-time gift certificates for 30 days of MTPRoto Keys subscription. A user buys a certificate in the bot for rubles via YuKassa or for Telegram Stars, receives a code in the format `KEY-XXXX-XXXX`, and can forward it to another person. The recipient activates the code in the bot: if they already have an active subscription, it is extended by 30 days; otherwise a new key is issued for 30 days.

## Scope

- Certificate purchase in the Telegram bot as a separate product from buying or extending the buyer's own subscription.
- Payment support for both rubles and Telegram Stars.
- One-time certificate code generation after successful payment.
- Code format `KEY-XXXX-XXXX`.
- Certificate activation by any Telegram user, including the buyer.
- Activation extends an active subscription by 30 days or creates a new 30-day key.
- Certificate expires if not activated within 1 year from purchase.
- Certificate activation does not affect free trial usage or referral activation.

## Out of Scope

- Variable certificate durations.
- Multi-use promo codes.
- Discounts or percentage coupons.
- Restricting a certificate to a specific recipient.
- User-facing certificate status cabinet.
- Gift card images or rich visual certificate templates.
- Referral attribution from certificate activation.

## Success Criteria

- Users can buy a certificate without changing their own subscription.
- Buyers receive a clear one-time code that can be forwarded outside the bot.
- Recipients can activate a valid code and receive exactly 30 days of access.
- Used, expired, or unknown codes are rejected with understandable bot feedback.
- Support can distinguish certificate purchases and activations from regular subscription purchases.

## Open Questions

- Should the ruble and Stars prices always mirror the regular 30-day subscription prices, or can they diverge later?
- Should the buyer receive a reminder if the certificate remains unused near expiry?
- Should admin tooling expose certificate status in the first implementation pass or only through raw operational support views?

## Next Step

Split the fixed idea into independent business units before implementation planning.
