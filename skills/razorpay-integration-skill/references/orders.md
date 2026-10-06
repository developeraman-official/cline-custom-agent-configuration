# Orders — one-time payments

The standard flow for a single charge (cart checkout, one-off purchase). Three steps:
**create order (server) → checkout (client) → verify signature (server)**.

## 1. Create the order (server)

Never let the client decide the amount. Compute it server-side from the cart/DB.

```ts
import Razorpay from 'razorpay'
const razorpay = new Razorpay({
  key_id: process.env.RAZORPAY_KEY_ID!,
  key_secret: process.env.RAZORPAY_KEY_SECRET!,   // server-only, never shipped to client
})

const amountPaise = computeTotalFromServer(cartId)  // integer paise
const order = await razorpay.orders.create({
  amount: amountPaise,
  currency: 'INR',
  receipt: `order_${yourOrderId}`,
  notes: { orderId: yourOrderId },
})
// return order.id + RAZORPAY_KEY_ID (public) to the client
```

## 2. Checkout (client)

Load `https://checkout.razorpay.com/v1/checkout.js` (a real `<script>`/`Script` tag — a missing
tag is the classic "Razorpay SDK not loaded" error). Open checkout with the order id:

```ts
const rzp = new (window as any).Razorpay({
  key: RAZORPAY_KEY_ID,            // public key id only
  order_id: order.id,
  amount: order.amount,
  currency: 'INR',
  handler: (resp) => {
    // resp: razorpay_payment_id, razorpay_order_id, razorpay_signature
    // POST these to your /verify endpoint. DO NOT trust this callback alone —
    // the webhook is the real source of truth.
  },
})
rzp.open()
```

## 3. Verify the signature (server) — the critical step

Mark the order paid **only** after this passes (or after the `payment.captured` webhook).

```ts
import crypto from 'crypto'

function verifyPaymentSignature(orderId: string, paymentId: string, signature: string): boolean {
  const expected = crypto
    .createHmac('sha256', process.env.RAZORPAY_KEY_SECRET!)   // NB: key secret, not webhook secret
    .update(`${orderId}|${paymentId}`)
    .digest('hex')
  const a = Buffer.from(expected); const b = Buffer.from(signature)
  return a.length === b.length && crypto.timingSafeEqual(a, b)
}

// in /verify:
if (!verifyPaymentSignature(razorpay_order_id, razorpay_payment_id, razorpay_signature)) {
  return json({ error: 'Invalid payment signature' }, 400)
}
// (optional but recommended) re-fetch the payment and assert amount/status match what you expect:
const payment = await razorpay.payments.fetch(razorpay_payment_id)
if (payment.status !== 'captured' || payment.amount !== expectedAmountPaise) { /* reject */ }
await db.orders.markPaid(yourOrderId, razorpay_payment_id)
```

## Gotchas
- **Two different HMAC keys:** payment-verify uses `RAZORPAY_KEY_SECRET` over `order_id|payment_id`;
  webhooks use `RAZORPAY_WEBHOOK_SECRET` over the raw body. Don't mix them.
- **Don't mark paid on order creation** or in the client handler — only after verification/webhook.
- **Amounts are integer paise.**
- The webhook (`payment.captured`) is your safety net when the client never returns.
