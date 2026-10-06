/**
 * One-time payment: create order (server) + verify signature (server).
 * Mirrors references/orders.md. Generic — adapt `db` and the Razorpay client.
 *
 * Two server endpoints:
 *   POST /api/payment/create-order  -> returns { orderId, keyId, amount }
 *   POST /api/payment/verify        -> verifies signature, marks order paid
 *
 * All amounts are integer PAISE (₹1 = 100 paise).
 */
import Razorpay from 'razorpay'
import crypto from 'crypto'

const razorpay = new Razorpay({
  key_id: process.env.RAZORPAY_KEY_ID!,
  key_secret: process.env.RAZORPAY_KEY_SECRET!, // server-only — never sent to the client
})

// --- placeholder data layer ---
declare const db: {
  orders: {
    computeTotalPaise(orderId: string): Promise<number>
    markPaid(orderId: string, paymentId: string): Promise<void>
  }
}

// 1) Create the order — amount comes from the SERVER, never the client.
export async function createOrder(yourOrderId: string) {
  const amount = await db.orders.computeTotalPaise(yourOrderId) // integer paise
  const order = await razorpay.orders.create({
    amount,
    currency: 'INR',
    receipt: `order_${yourOrderId}`,
    notes: { orderId: yourOrderId },
  })
  // Return only the public key id to the client (NOT the secret).
  return { orderId: order.id, keyId: process.env.RAZORPAY_KEY_ID!, amount: order.amount }
}

// 2) Verify the payment signature. Payment-verify signs `order_id|payment_id`
//    with the KEY SECRET (different from the webhook secret).
function verifyPaymentSignature(orderId: string, paymentId: string, signature: string): boolean {
  const expected = crypto
    .createHmac('sha256', process.env.RAZORPAY_KEY_SECRET!)
    .update(`${orderId}|${paymentId}`)
    .digest('hex')
  const a = Buffer.from(expected)
  const b = Buffer.from(signature)
  return a.length === b.length && crypto.timingSafeEqual(a, b)
}

export async function verifyPayment(input: {
  yourOrderId: string
  razorpay_order_id: string
  razorpay_payment_id: string
  razorpay_signature: string
}): Promise<{ ok: boolean; reason?: string }> {
  const { yourOrderId, razorpay_order_id, razorpay_payment_id, razorpay_signature } = input

  if (!verifyPaymentSignature(razorpay_order_id, razorpay_payment_id, razorpay_signature)) {
    return { ok: false, reason: 'invalid_signature' }
  }

  // Defense in depth: confirm the payment really is captured for the expected amount.
  const expectedAmount = await db.orders.computeTotalPaise(yourOrderId)
  const payment = await razorpay.payments.fetch(razorpay_payment_id)
  if (payment.status !== 'captured' || Number(payment.amount) !== expectedAmount) {
    return { ok: false, reason: 'amount_or_status_mismatch' }
  }

  // Only NOW mark it paid. (The payment.captured webhook is the backup path.)
  await db.orders.markPaid(yourOrderId, razorpay_payment_id)
  return { ok: true }
}
