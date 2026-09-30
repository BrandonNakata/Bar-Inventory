/** Recipe matching in JS, used only by the demo build. Mirrors backend/app/recipes.py. */

import { renderSteps } from './steps.js'

export const MAKEABLE = 'makeable'
export const ONE_SHORT = 'one_short'
export const NOT_TONIGHT = 'not_tonight'

const BUCKET_ORDER = { [MAKEABLE]: 0, [ONE_SHORT]: 1, [NOT_TONIGHT]: 2 }

// Code-point order to match Python and SQLite sorting.
const byCodePoint = (a, b) => (a < b ? -1 : a > b ? 1 : 0)

/** Walk parent pointers upward: ['sweet-vermouth', 'vermouth', 'fortified-wine'] */
export function ancestorIds(ingredientId, byId) {
  const chain = []
  let current = byId.get(ingredientId)
  // Length guard in case the data ever has a cycle.
  while (current && chain.length < 64) {
    chain.push(current.id)
    current = current.parent_id ? byId.get(current.parent_id) : undefined
  }
  return chain
}

/** Every requirement the shelf can meet. Mirrors satisfiable_ids(). */
export function satisfiableIds(ingredients, bottles) {
  const byId = new Map(ingredients.map((ingredient) => [ingredient.id, ingredient]))
  const start = new Set(bottles.map((bottle) => bottle.ingredient_id))
  for (const ingredient of ingredients) {
    if (ingredient.assumed_on_hand) start.add(ingredient.id)
  }

  const available = new Set()
  for (const id of start) {
    for (const ancestor of ancestorIds(id, byId)) available.add(ancestor)
  }
  return available
}

/** Mark lines have or missing and set each status. Mirrors load_recipes(). */
export function judgeRecipes(recipes, ingredients, bottles) {
  const available = satisfiableIds(ingredients, bottles)
  const nameOf = new Map(ingredients.map((ingredient) => [ingredient.id, ingredient.name]))
  const byId = new Map(ingredients.map((ingredient) => [ingredient.id, ingredient]))

  const judged = recipes.map((recipe) => {
    const lines = recipe.ingredients.map((line) => ({
      ingredient_id: line.ingredient_id,
      ingredient_name: nameOf.get(line.ingredient_id) ?? line.ingredient_id,
      amount: line.amount ?? null,
      optional: Boolean(line.optional),
      note: line.note ?? null,
      have: available.has(line.ingredient_id),
    }))

    const missing = lines.filter((line) => !line.have && !line.optional)
    const status =
      missing.length === 0 ? MAKEABLE : missing.length === 1 ? ONE_SHORT : NOT_TONIGHT

    const template = recipe.steps ?? []
    return {
      id: recipe.id,
      name: recipe.name,
      kind: recipe.kind ?? 'cocktail',
      glass: recipe.glass ?? null,
      method: recipe.method ?? null,
      garnish: recipe.garnish ?? null,
      instructions: recipe.instructions ?? null,
      steps: renderSteps(template, lines, nameOf),
      steps_template: template,
      source: recipe.source ?? 'curated',
      rank: recipe.rank ?? 3000,
      base: baseFamily(lines, byId),
      hidden: Boolean(recipe.hidden),
      edited: Boolean(recipe.edited),
      ingredients: lines,
      missing,
      status,
    }
  })

  // Makeable first, then most common, then A to Z.
  judged.sort(
    (a, b) =>
      BUCKET_ORDER[a.status] - BUCKET_ORDER[b.status] ||
      a.rank - b.rank ||
      byCodePoint(a.name.toLowerCase(), b.name.toLowerCase()),
  )
  return judged
}

// Mirrors taxonomy.FAMILIES: the iPad's spirit chips.
const FAMILIES = [
  ['gin', ['gin']],
  ['rum', ['rum', 'flavored-rum', 'cachaca']],
  ['tequila', ['tequila', 'mezcal']],
  ['vodka', ['vodka', 'flavored-vodka', 'grain-alcohol']],
  ['whiskey', ['whiskey', 'flavored-whiskey']],
]

/** '1 1/2 oz' -> 1.5; anything that isn't ounces -> 0. Mirrors recipes._oz(). */
function ounces(amount) {
  const m = (amount ?? '').trim().match(/^(\d+)?\s*(?:(\d+)\/(\d+))?\s*oz(?: float)?$/)
  if (!m || !(m[1] || m[2])) return 0
  return Number(m[1] ?? 0) + (m[2] ? Number(m[2]) / Number(m[3]) : 0)
}

/** The spirit line with the biggest pour decides the chip. Mirrors base_family(). */
function baseFamily(lines, byId) {
  let best = null
  let bestOz = -1
  for (const line of lines) {
    const chain = ancestorIds(line.ingredient_id, byId)
    if (!chain.includes('spirit')) continue
    const oz = ounces(line.amount)
    if (oz > bestOz) {
      best = chain
      bestOz = oz
    }
  }
  if (!best) return 'other'
  for (const [family, roots] of FAMILIES) {
    if (roots.some((root) => best.includes(root))) return family
  }
  return 'other'
}

/** Which single bottle unlocks the most drinks. Mirrors shopping_list(). */
export function shoppingList(judged, ingredients, limit = 5) {
  const byId = new Map(ingredients.map((ingredient) => [ingredient.id, ingredient]))
  const oneShort = judged.filter((recipe) => recipe.status === ONE_SHORT)
  const candidates = new Set(oneShort.map((recipe) => recipe.missing[0].ingredient_id))

  const suggestions = [...candidates].map((candidate) => {
    const covers = new Set(ancestorIds(candidate, byId))
    const unlocked = oneShort.filter((recipe) => covers.has(recipe.missing[0].ingredient_id))
    return {
      ingredient_id: candidate,
      ingredient_name: byId.get(candidate)?.name ?? candidate,
      unlocks: unlocked.length,
      recipes: unlocked.map((recipe) => recipe.name),
    }
  })

  suggestions.sort(
    (a, b) => b.unlocks - a.unlocks || byCodePoint(a.ingredient_name, b.ingredient_name),
  )
  return suggestions.slice(0, limit)
}
