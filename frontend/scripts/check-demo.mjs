/** Checks that the demo's JS matching agrees with the Python backend. Run: npm run check:demo */

import {
  DEMO_EXPECTED,
  DEMO_EXPECTED_BARCODES,
  DEMO_INGREDIENTS,
  DEMO_RECIPES,
} from '../src/api/demoData.js'
import { normalizeBarcode } from '../src/lib/barcode.js'
import { judgeRecipes, shoppingList } from '../src/lib/matching.js'

let failures = 0

function check(label, got, want) {
  const a = JSON.stringify(got)
  const b = JSON.stringify(want)
  if (a === b) {
    console.log(`  ok    ${label}`)
  } else {
    failures += 1
    console.log(`  FAIL  ${label}\n          js:     ${a}\n          python: ${b}`)
  }
}

for (const [name, expected] of Object.entries(DEMO_EXPECTED)) {
  console.log(`\nshelf "${name}" (${expected.shelf.length} bottles)`)

  const bottles = expected.shelf.map((ingredient_id) => ({ ingredient_id }))
  // Python verdicts cover visible cocktails only, so filter the same way.
  const judged = judgeRecipes(DEMO_RECIPES, DEMO_INGREDIENTS, bottles).filter(
    (r) => r.kind === 'cocktail' && !r.hidden,
  )

  check('same recipes in the same order', judged.map((r) => r.id), expected.order)
  check(
    'same status for every recipe',
    Object.fromEntries(judged.map((r) => [r.id, r.status])),
    expected.status,
  )
  check(
    'same missing ingredients for every recipe',
    Object.fromEntries(judged.map((r) => [r.id, r.missing.map((l) => l.ingredient_id)])),
    expected.missing,
  )
  check('same shopping list', shoppingList(judged, DEMO_INGREDIENTS, 5), expected.shopping)
  if (expected.steps) {
    check(
      'same rendered steps for every recipe',
      Object.fromEntries(judged.map((r) => [r.id, r.steps])),
      expected.steps,
    )
    check(
      'same spirit chip for every recipe',
      Object.fromEntries(judged.map((r) => [r.id, r.base])),
      expected.base,
    )
  }
}

console.log('\nbarcode normalisation')
for (const expected of DEMO_EXPECTED_BARCODES) {
  let got
  try {
    got = { input: expected.input, ok: normalizeBarcode(expected.input) }
  } catch (err) {
    got = { input: expected.input, error: err.message }
  }
  check(`"${expected.input}"`, got, expected)
}

console.log()
if (failures) {
  console.log(`${failures} check(s) failed -- the demo disagrees with the real app.`)
  process.exit(1)
}
console.log('all good -- the demo and the backend agree')
