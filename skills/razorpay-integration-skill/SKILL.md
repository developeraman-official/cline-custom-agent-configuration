---
name: razorpay-integration-skill
description: >-
  Implement or debug Razorpay payments in any stack — one-time Orders, Subscriptions,
  Route (marketplace payment splitting), linked-account KYC onboarding, webhooks (with
  HMAC signature verification + idempotency), refunds with retry, GST-compliant invoices,
  and PII encryption. Use when the task mentions Razorpay, Razorpay Route, linked accounts,
  payment splitting / marketplace payouts, transfers, KYC onboarding, payment webhooks,
  refunds, or "needs_clarification" / account activation errors. India-focused (PAN, IFSC,
  GST), framework-agnostic patterns.
---

# Razorpay Integration

Battle-tested patterns for integrating **Razorpay** — distilled from a production Indian
marketplace (Razorpay Route with per-seller payment splitting, linked-account KYC, the full
webhook surface, refunds, and GST invoicing). The value here is the **gotchas and recovery
procedures** that Razorpay's own docs don't spell out.

> These are **patterns + reference code**, not a drop-in library. Adapt them to your stack
> (the examples use generic TypeScript + a `db` adapter). All amounts are in **paise**
> (₹1 = 100 paise) unless noted.

> **Unofficial & independent** — not affiliated with or endorsed by Razorpay. "Razorpay®" is a
> trademark of Razorpay Software Private Limited, used nominatively. Verify against the official
> Razorpay docs.

## Decision tree — which Razorpay product do you need?

```
Are you charging a customer once (cart checkout, single payment)?
        └─ YES → Orders API                          → references/orders.md
Recurring billing (plans, subscriptions)?
        └─ YES → Subscriptions API                   → references/subscriptions.md
Splitting one payment across multiple payees
(marketplace: platform keeps a fee, sellers get the rest)?
        └─ YES → Route + Linked Accounts             → references/route.md
                 (sellers must be onboarded/KYC'd)   → references/kyc.md
```

Almost every integration also needs: **webhooks** (the backbone — never trust the
client callback alone), **refunds**, and **security** (signature verification + PII encryption).

## Integration checklist (in order)

1. **Setup** — set `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` (server-only;
   the *secret* must never reach the client). Load `checkout.js` on the client.
2. **Charge** — Orders / Subscriptions / Route per the decision tree.
3. **Verify** — confirm every payment **server-side** with an HMAC-SHA256 signature check.
   Never trust an amount or status sent by the browser.
4. **Webhooks** — wire them up as the *source of truth* (callbacks get lost). Verify the
   signature on the **raw** body; make handlers **idempotent**.
5. **Refunds** — implement creation + a **retry** path (refunds can fail transiently).
6. **Security** — encrypt any PII you store (PAN, bank); store only masked/last-4.
7. **Recovery** — keep the known-errors playbook handy (`references/recovery-playbook.md`).

## Reference index

| File | Covers | Read it when |
|------|--------|--------------|
| `references/orders.md` | One-time payments, create-order → checkout → **verify signature** | Cart checkout, single payments |
| `references/subscriptions.md` | Plans, subscribe, cancel, reconcile missed invoices | Recurring billing |
| `references/route.md` ⭐ | Linked accounts, **product config**, transfers (create/hold/release/reverse), **status-downgrade race** | Marketplace payment splitting |
| `references/kyc.md` | 2-step onboarding (PAN+address → bank+activate), **clarification-reason parsing**, resubmit | Onboarding payees / sellers |
| `references/webhooks.md` ⭐ | Signature verification, **the `acc_` prefix bug**, idempotency, serverless `await` | Any webhook handler |
| `references/refunds.md` | Create + API wrapper, **retry cron**, reversal-vs-refund | Refunds / cancellations |
| `references/invoices-gst.md` | India GST (CGST/SGST vs IGST), invoice PDF | Tax-compliant invoices |
| `references/security.md` | AES-256-GCM for PII, data minimization, secret handling | Storing PAN/bank |
| `references/recovery-playbook.md` ⭐ | Known Razorpay errors → the exact fix | Stuck/failed onboarding |

⭐ = the parts that are genuinely under-documented elsewhere.

## Top gotchas (the ones that cost real debugging time)

1. **Webhook account IDs:** `event.account_id` carries the `acc_` prefix; `payload.account.entity.id` does **not**. Use `event.account_id` for DB lookups, or you'll never find the record. (`references/webhooks.md`)
2. **Verify signatures on the *raw* body** — parse JSON only *after* verifying, and use a timing-safe compare.
3. **Don't set "paid"/"active" state before verifying the payment** — set it only after signature verification (or the webhook), never on order creation.
4. **Live-sync polling can downgrade status** — a stale Razorpay read can overwrite `needs_clarification` back to `created`. Guard with a status-priority check; treat webhooks as authoritative. (`references/route.md`)
5. **`await` async work in serverless** — fire-and-forget calls (push, cleanup) get killed when the function returns. Await them or use the platform's `waitUntil`.
6. **Individual/proprietor PAN goes on the *stakeholder*, not `legal_info.pan`** (which is company-PAN only). (`references/kyc.md`)
7. **Amounts are in paise**, integers. Never pass rupees to the API.
