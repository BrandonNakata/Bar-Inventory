/** Barcode validation, ported from backend/app/barcode.py for the demo build. */

/** Weight digits 3,1,3,1... from the right; the check digit tops up to ×10. */
export function gtinCheckDigit(body) {
  let total = 0
  const digits = [...body].reverse()
  digits.forEach((digit, i) => {
    total += Number(digit) * (i % 2 === 0 ? 3 : 1)
  })
  return (10 - (total % 10)) % 10
}

/** Clean and validate; returns the canonical form or throws with a readable message. */
export function normalizeBarcode(raw) {
  let digits = (raw ?? '').replace(/[\s-]/g, '')
  if (!digits) throw new Error('Enter a barcode.')
  if (!/^\d+$/.test(digits)) throw new Error('A barcode is digits only.')
  if (![8, 12, 13, 14].includes(digits.length)) {
    throw new Error(
      `Barcodes are 8, 12, 13 or 14 digits long; that one is ${digits.length}.`,
    )
  }
  if (gtinCheckDigit(digits.slice(0, -1)) !== Number(digits.at(-1))) {
    throw new Error("That barcode's check digit doesn't add up; probably a typo.")
  }
  if (digits.length === 12) digits = '0' + digits
  else if (digits.length === 14 && digits.startsWith('0')) digits = digits.slice(1)
  return digits
}
