# Refunds

Two distinct mechanisms — pick by how the payment was made:

- **Plain payment** → refund the payment: `razorpay.payments.refund(paymentId, { amount })`.
- **Route (split) payment** → **reverse the transfer**: `POST /v1/transfers/:id/reversals`.
  Razorpay auto-refunds the buyer and pulls the money back from the seller's transfer. See
  `references/route.md` §4.

All amounts in **paise**. Partial refunds: pass a smaller `amount`.

## Create a refund (plain payment)

```ts
const refund = await razorpay.payments.refund(paymentId, {
  amount: amountPaise,                 // omit for full refund
  notes: { orderId, reason },
  speed: 'normal',                     // or 'optimum'
})
// store refund.id + status ('pending' | 'processed' | 'failed')
```

## ⚠️ Refunds can fail — build a retry path

A refund can come back `failed` (transient gateway/bank issues). Don't treat "created" as "done".
Track attempts and retry with a cron, capped.

```ts
// refunds table: id, payment_id, amount, status, retry_count, last_retry_at, max_retries=3
// every few hours:
for (const r of failedRefundsUnderMaxRetries) {
  try {
    const res = await razorpay.payments.refund(r.payment_id, { amount: r.amount })
    await db.refunds.update(r.id, { status: res.status, retry_count: r.retry_count + 1, last_retry_at: now })
  } catch (e) {
    await db.refunds.update(r.id, { retry_count: r.retry_count + 1, last_retry_at: now })
    // after max_retries, flag for manual review — alert an admin
  }
}
```

## Reconcile via webhook

Wire `refund.processed` / `refund.failed` (`references/webhooks.md`) to set the final status
idempotently. The webhook is authoritative over your optimistic "pending".

## Knock-on state to keep consistent
- **Seller balance:** on a Route reversal, debit the seller's ledger by their share.
- **Parent order status:** only mark the *order* `refunded` when **all** of its
  shipments/sub-orders are refunded/cancelled — otherwise it's `partially_refunded`.
- **Idempotency:** key everything on `refund.id`; the webhook may arrive before *or* after your
  API response.

## Gotchas
- Route payment → **reverse the transfer**, don't `payments.refund` (the money is with the seller, not you).
- Always implement retry; a one-shot refund call is not reliable.
- Reconcile final status from the webhook, not the create call.
