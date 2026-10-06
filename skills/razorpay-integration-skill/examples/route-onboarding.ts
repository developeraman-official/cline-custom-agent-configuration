/**
 * Razorpay Route — linked-account onboarding service.
 * Mirrors references/route.md + references/kyc.md. Generic — adapt `db`.
 *
 * Flow: create account -> stakeholder -> request product (route) -> configure
 * settlement + accept T&C -> account activates (track via webhooks).
 *
 * The Node SDK has no typed v2 methods, so we call the raw HTTP client:
 *   (razorpay as any).api.post({ version: 'v2', url, data })
 * Pass `version` separately; the SDK prepends `/{version}` to the url.
 */
import Razorpay from 'razorpay'

const razorpay = new Razorpay({
  key_id: process.env.RAZORPAY_KEY_ID!,
  key_secret: process.env.RAZORPAY_KEY_SECRET!,
})
const api = (razorpay as any).api

export type AccountStatus =
  | 'not_started' | 'created' | 'needs_clarification'
  | 'under_review' | 'activated' | 'suspended' | 'rejected'

export interface OnboardingInput {
  email: string
  phone: string
  legalBusinessName: string
  businessType: 'individual' | 'proprietorship' | 'company' | 'partnership'
  panNumber: string         // validate ^[A-Z]{5}[0-9]{4}[A-Z]$ before calling
  panName: string           // person's name on the PAN
  bank: { accountNumber: string; ifscCode: string; beneficiaryName: string } // IFSC ^[A-Z]{4}0[A-Z0-9]{6}$
  address?: { street1?: string; street2?: string; city?: string; state?: string; postalCode?: string }
}

const isIndividualLike = (t: string) => t === 'individual' || t === 'proprietorship'

/** Runs the whole chain. Returns the acc_ id to store as your lookup key. */
export async function onboardLinkedAccount(input: OnboardingInput): Promise<{ accountId: string }> {
  // 1) Linked account. Company PAN goes on legal_info; individual/proprietor PAN does NOT.
  const accountPayload: Record<string, any> = {
    email: input.email,
    phone: input.phone,
    type: 'route',
    legal_business_name: input.legalBusinessName,
    business_type: input.businessType,
    contact_name: input.legalBusinessName,
    profile: {
      category: 'ecommerce',
      subcategory: 'ecommerce_marketplace',
      addresses: {
        registered: {
          street1: input.address?.street1 || 'N/A',
          street2: input.address?.street2 || 'NA',
          city: input.address?.city || 'N/A',
          state: input.address?.state || 'N/A',
          postal_code: input.address?.postalCode || '000000',
          country: 'IN',
        },
      },
    },
  }
  if (!isIndividualLike(input.businessType)) {
    accountPayload.legal_info = { pan: input.panNumber }
  }
  const account = await api.post({ version: 'v2', url: '/accounts', data: accountPayload })
  const accountId: string = account.id // 'acc_...'

  // 2) Stakeholder. Individual/proprietor PAN belongs HERE (kyc.pan), not on the account.
  await api.post({
    version: 'v2',
    url: `/accounts/${accountId}/stakeholders`,
    data: {
      name: input.panName,
      email: input.email,
      phone: { primary: input.phone },
      ...(isIndividualLike(input.businessType) ? { kyc: { pan: input.panNumber } } : {}),
    },
  })

  // 3) Request the route product.
  const product = await api.post({
    version: 'v2',
    url: `/accounts/${accountId}/products`,
    data: { product_name: 'route' }, // do NOT send requested_at — Razorpay rejects it
  })

  // 4) Configure settlement (bank) + accept T&C -> moves toward activation.
  await api.patch({
    version: 'v2',
    url: `/accounts/${accountId}/products/${product.id}`,
    data: {
      settlements: {
        account_number: input.bank.accountNumber,
        ifsc_code: input.bank.ifscCode,
        beneficiary_name: input.bank.beneficiaryName,
      },
      tnc_accepted: true,
    },
  })

  // Persist accountId + status; the rest of the lifecycle arrives via webhooks.
  return { accountId }
}

// --- status-downgrade guard (use in polling; webhooks are authoritative) ---
const STATUS_PRIORITY: Record<string, number> = {
  not_started: 0, created: 1, under_review: 2,
  needs_clarification: 3, activated: 4, suspended: 5, rejected: 5,
}
export function isStatusDowngrade(current: string, next: string): boolean {
  if (next === 'needs_clarification' || next === 'suspended'
      || next === 'rejected' || next === 'activated') return false
  return (STATUS_PRIORITY[next] ?? 0) < (STATUS_PRIORITY[current] ?? 0)
}

/** Poll Razorpay for the live status, applying the downgrade guard. */
export async function syncAccountStatus(accountId: string, currentStatus: string): Promise<AccountStatus | null> {
  const res = await api.get({ version: 'v2', url: `/accounts/${accountId}` })
  const next = res.status as AccountStatus
  if (isStatusDowngrade(currentStatus, next)) return null // ignore stale read
  return next
}

// --- transfers (split / hold / release / reverse) ---
export async function releaseTransfer(transferId: string) {
  return api.patch({ url: `/transfers/${transferId}`, data: { on_hold: 0 } })
}
export async function reverseTransfer(transferId: string, amountPaise: number) {
  return api.post({ url: `/transfers/${transferId}/reversals`, data: { amount: amountPaise } })
}
