/** A code counts only after it's read the same way `needed` times in a row. */

export function createConfirmer(needed = 2) {
  let last = null
  let count = 0

  return function confirm(value) {
    if (!value) return null
    if (value === last) {
      count += 1
    } else {
      last = value
      count = 1
    }
    if (count >= needed) {
      // Reset so the same code isn't "confirmed" again on the next frame.
      last = null
      count = 0
      return value
    }
    return null
  }
}
