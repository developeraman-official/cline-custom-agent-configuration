# GST-compliant invoices (India)

If you issue tax invoices in India, the GST split depends on whether the supply is **intra-state**
or **inter-state**, decided by comparing the **supplier's** state with the **place of supply**
(usually the buyer's / recipient's state), via the 2-digit **GST state code**.

```
supplier_state_code === place_of_supply_state_code
   ├─ YES → intra-state → CGST (½ rate) + SGST (½ rate)
   └─ NO  → inter-state → IGST (full rate)
```

For an 18% rate: intra-state = **CGST 9% + SGST 9%**; inter-state = **IGST 18%**. The total tax is
the same; the *split* and the line items on the invoice differ.

```ts
// GST state codes: '29' = Karnataka, '27' = Maharashtra, '07' = Delhi, ... (36 states/UTs)
function calculateGstSplit(baseAmount: number, ratePct: number, supplierCode: string, placeCode: string) {
  const tax = round2(baseAmount * ratePct / 100)
  if (supplierCode === placeCode) {
    const half = round2(tax / 2)
    return { type: 'intra', cgst: half, sgst: half, igst: 0, total: tax }
  }
  return { type: 'inter', cgst: 0, sgst: 0, igst: tax, total: tax }
}
```

## Storing it
- Persist the split on the invoice (e.g. a `gst_split` JSON: `{ type, cgst, sgst, igst }`) so the
  PDF and any re-render are deterministic.
- **Legacy fallback:** invoices created before you tracked the split should render a flat
  "GST @ <rate>%" line rather than crashing — branch on whether `gst_split` exists.

## Invoice PDF
- Generate from a single HTML template → PDF (server-side). Keep one template; render buyer,
  seller, and admin variants from the same source to avoid drift.
- Include: invoice number, dates, supplier GSTIN + state, place of supply, line items, the
  CGST/SGST **or** IGST lines, and the total. Sequential, immutable invoice numbers.

## Gotchas
- The split is decided by **place of supply vs supplier state**, not by amount.
- Round each component to 2 decimals; make sure `cgst + sgst` (or `igst`) reconciles to the total.
- Keep invoice numbers sequential and never reuse them.
