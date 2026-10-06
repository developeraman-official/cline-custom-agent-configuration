# Subscriptions — recurring billing

For recurring plans. The shape mirrors Orders (create → checkout → verify) but the **webhook is
even more important**, because charges recur server-side long after the user is gone.

## Setup

1. Create **Plans** in the Razorpay Dashboard (or API) — one per price/interval. Store the
   `plan_id`s (resolve your internal plan slug → Razorpay `plan_id`).
2. Create a **Subscription** for the customer against a plan.

```ts
const sub = await razorpay.subscriptions.create({
  plan_id: razorpayPlanId,
  customer_notify: 1,
  total_count: 12,                 // number of billing cycles
  notes: { sellerId },
})
// open checkout with subscription_id (instead of order_id)
```

## Verify the first payment

Same HMAC pattern as Orders, but the signed string is `payment_id|subscription_id`:

```ts
const expected = crypto.createHmac('sha256', process.env.RAZORPAY_KEY_SECRET!)
  .update(`${razorpay_payment_id}|${razorpay_subscription_id}`).digest('hex')
// timing-safe compare vs razorpay_signature
```

> **Don't mark the plan active on subscription *creation*.** Set active state only after the
> payment is verified (or the `subscription.activated` / `subscription.charged` webhook). Otherwise
> users appear subscribed without paying.

## Webhook events to handle

| Event | Do |
|-------|----|
| `subscription.activated` | mark active |
| `subscription.charged` | record the invoice/payment for that cycle (idempotent upsert by payment id) |
| `subscription.halted` | payment failing repeatedly — flag the account |
| `subscription.cancelled` | mark cancelled (respect cancel-at-cycle-end if used) |

## Cancel / upgrade / downgrade

- Cancel: `razorpay.subscriptions.cancel(subId, cancelAtCycleEnd)` — pass `true` to let the
  current paid period run out.
- Upgrades/downgrades are usually modeled as cancel + new subscription, or via plan change at
  cycle boundary; keep the *effective date* logic in your own code.

## ⚠️ Reconciliation — recover invoices missed by failed webhooks

Webhooks **do** occasionally fail to deliver (your endpoint was down, a deploy, a timeout). If you
rely on `subscription.charged` to create invoice records, you'll silently miss some. Add a periodic
**reconciliation job**:

```ts
// daily cron
for (const sub of activeSubscriptions) {
  const invoices = await razorpay.invoices.all({ subscription_id: sub.razorpay_subscription_id })
  for (const inv of invoices.items) {
    // upsert by inv.id — creates any invoice the webhook missed, no duplicates
    await db.invoices.upsertByRazorpayId(inv.id, mapInvoice(inv))
  }
}
```

This makes your billing records **self-healing** regardless of webhook reliability.

## Feature-flagging subscriptions off

If you later move to a free/no-subscription model, gate the whole surface behind a flag
(`SUBSCRIPTIONS_ENABLED`) rather than ripping code out — return `404` from the subscription routes
when off, and keep the code as dormant, reversible infrastructure.

## Gotchas
- Verify with `payment_id|subscription_id` (note the order differs from Orders' `order_id|payment_id`).
- Reconcile; never assume every `charged` webhook arrived.
- Activate on payment, not on creation.
