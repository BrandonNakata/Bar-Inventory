/** In-browser fake API for the Netlify demo: same functions, answered from memory. */

import {
  DEMO_ALIASES,
  DEMO_BOTTLES,
  DEMO_INGREDIENTS,
  DEMO_RECIPES,
} from './demoData'
import { normalizeBarcode } from '../lib/barcode'
import { MAKEABLE, ONE_SHORT, ancestorIds, judgeRecipes, shoppingList } from '../lib/matching'
import { referencedIds } from '../lib/steps'

const delay = (ms = 180) => new Promise((resolve) => setTimeout(resolve, ms))

// @__PURE__ lets the production build drop this module entirely.

// Copy so a reload starts clean.
let bottles = /* @__PURE__ */ DEMO_BOTTLES.map((bottle) => ({ ...bottle }))
let nextId = /* @__PURE__ */ Math.max(0, .../* @__PURE__ */ bottles.map((b) => b.id)) + 1

// Stands in for the barcode_product table; the demo has no online lookup.
const barcodeMemory = /* @__PURE__ */ new Map()

const nameOf = (id) => DEMO_INGREDIENTS.find((i) => i.id === id)?.name ?? null

// Clone on the way out so callers can't mutate the store.
const clone = (value) => JSON.parse(JSON.stringify(value))

// Copied like the bottles, so a reload resets edits.
let recipes = /* @__PURE__ */ clone(DEMO_RECIPES)

const judgeAll = () => judgeRecipes(recipes, DEMO_INGREDIENTS, bottles)

// What every guest-facing list shows: cocktails, nothing hidden.
const visibleCocktails = () =>
  judgeAll().filter((r) => r.kind === 'cocktail' && !r.hidden)

const byId = /* @__PURE__ */ new Map(/* @__PURE__ */ DEMO_INGREDIENTS.map((i) => [i.id, i]))
const fold = (text) => text.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
const escape = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** Mirrors recipe_store._clean() so validation errors match the real API. */
function cleanRecipe(data) {
  const name = (data.name ?? '').trim()
  if (!name) throw new Error('Give the drink a name.')
  const ingredients = (data.ingredients ?? []).map((line) => {
    if (!byId.has(line.ingredient_id)) {
      throw new Error(`Unknown ingredient '${line.ingredient_id}'.`)
    }
    return {
      ingredient_id: line.ingredient_id,
      amount: (line.amount ?? '').trim() || null,
      optional: Boolean(line.optional),
    }
  })
  if (ingredients.length === 0) throw new Error('Add at least one ingredient.')
  const ids = new Set(ingredients.map((l) => l.ingredient_id))
  if (ids.size !== ingredients.length) throw new Error('Each ingredient can only appear once.')
  const steps = (data.steps ?? []).map((s) => s.trim()).filter(Boolean)
  const dangling = [...referencedIds(steps)].filter((id) => !ids.has(id)).sort()
  if (dangling.length) {
    throw new Error(
      `A step mentions an ingredient that isn't in the recipe: ${dangling.join(', ')}. ` +
        'Add it to the ingredients or take it out of the step.',
    )
  }
  const text = (v) => (v ?? '').trim() || null
  return {
    name,
    kind: data.kind === 'shot' ? 'shot' : 'cocktail',
    glass: text(data.glass),
    method: text(data.method),
    garnish: text(data.garnish),
    instructions: text(data.instructions),
    steps,
    ingredients,
  }
}

const RESERVED = /* @__PURE__ */ new Set(['new', 'hidden', 'random', 'shopping-list', 'edit'])
const slugify = (text) => fold(text).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'recipe'

function findJudged(id) {
  const recipe = judgeAll().find((r) => r.id === id)
  if (!recipe) throw new Error(`No recipe '${id}'`)
  return recipe
}

export const demoApi = {
  // ---- inventory ----------------------------------------------------------

  async listIngredients() {
    await delay()
    return clone(DEMO_INGREDIENTS)
  },

  async listBottles() {
    await delay()
    return clone(bottles)
  },

  async addBottle(draft) {
    await delay()
    if (!nameOf(draft.ingredient_id)) {
      throw new Error(`Unknown ingredient '${draft.ingredient_id}'`)
    }
    // Same canonical form and same rejections as the server.
    const barcode = draft.barcode ? normalizeBarcode(draft.barcode) : null
    if (barcode) {
      barcodeMemory.set(barcode, {
        product_name: draft.product_name,
        ingredient_id: draft.ingredient_id,
      })
    }
    const bottle = {
      id: nextId++,
      product_name: draft.product_name,
      ingredient_id: draft.ingredient_id,
      ingredient_name: nameOf(draft.ingredient_id),
      barcode,
      added_at: new Date().toISOString().slice(0, 19).replace('T', ' '),
    }
    bottles = [bottle, ...bottles]
    return clone(bottle)
  },

  async deleteBottle(id) {
    await delay()
    const before = bottles.length
    bottles = bottles.filter((bottle) => bottle.id !== id)
    if (bottles.length === before) throw new Error(`No bottle ${id}`)
  },

  async suggestIngredient(productName) {
    await delay(80)
    // Mirrors taxonomy.suggest_ingredient().
    const haystack = fold(productName)
    const matches = new Map()
    for (const [alias, ingredientId] of Object.entries(DEMO_ALIASES)) {
      const folded = fold(alias)
      if (new RegExp(`(?<![a-z0-9])${escape(folded)}`).test(haystack)) {
        matches.set(ingredientId, Math.max(matches.get(ingredientId) ?? 0, folded.length))
      }
    }
    let bestId = null
    if (matches.size) {
      const chains = new Map([...matches.keys()].map((id) => [id, ancestorIds(id, byId)]))
      const redundant = new Set()
      for (const chain of chains.values()) {
        for (const ancestor of chain.slice(1)) if (matches.has(ancestor)) redundant.add(ancestor)
      }
      let candidates = [...matches.keys()].filter((id) => !redundant.has(id))
      if (!candidates.length) candidates = [...matches.keys()]
      const key = (id) => [matches.get(id), chains.get(id).length, id]
      bestId = candidates.reduce((best, id) => {
        const [a, b] = [key(id), key(best)]
        return a[0] > b[0] || (a[0] === b[0] && (a[1] > b[1] || (a[1] === b[1] && a[2] > b[2])))
          ? id
          : best
      })
    }
    return {
      product_name: productName,
      ingredient_id: bestId,
      ingredient_name: bestId ? nameOf(bestId) : null,
    }
  },

  async lookupBarcode(code) {
    await delay(300)
    const barcode = normalizeBarcode(code)
    const known = barcodeMemory.get(barcode)
    return clone({
      barcode,
      found: Boolean(known),
      product_name: known?.product_name ?? null,
      brand: null,
      source: known ? 'manual' : 'none',
      ingredient_id: known?.ingredient_id ?? null,
      ingredient_name: known ? nameOf(known.ingredient_id) : null,
      suggested_ingredient_id: null,
      suggested_ingredient_name: null,
      on_shelf: bottles.filter((bottle) => bottle.barcode === barcode),
      cached: Boolean(known),
      lookup_error: known
        ? null
        : 'This demo runs without a server, so online lookup is off.',
    })
  },

  // ---- recipes ------------------------------------------------------------

  async listRecipes({ kind = 'cocktail', hidden = 'exclude' } = {}) {
    await delay()
    const shown = judgeAll().filter(
      (r) =>
        (kind === 'all' || r.kind === kind) &&
        (hidden === 'include' || (hidden === 'only' ? r.hidden : !r.hidden)),
    )
    return clone({
      inventory_count: bottles.length,
      makeable_count: shown.filter((r) => r.status === MAKEABLE).length,
      one_short_count: shown.filter((r) => r.status === ONE_SHORT).length,
      recipes: shown,
    })
  },

  async getRecipe(id) {
    await delay()
    return clone(findJudged(id))
  },

  async randomRecipe() {
    await delay()
    const options = visibleCocktails().filter((r) => r.status === MAKEABLE)
    if (options.length === 0) {
      throw new Error('Nothing on the shelf makes a complete drink yet.')
    }
    return clone(options[Math.floor(Math.random() * options.length)])
  },

  async shoppingList(limit = 5) {
    await delay()
    return clone(shoppingList(visibleCocktails(), DEMO_INGREDIENTS, limit))
  },

  // ---- editing --------------------------------------------------------------

  async createRecipe(data) {
    await delay()
    const clean = cleanRecipe(data)
    const base = slugify(clean.name)
    let id = RESERVED.has(base) ? `${base}-2` : base
    for (let n = RESERVED.has(base) ? 3 : 2; recipes.some((r) => r.id === id); n++) id = `${base}-${n}`
    recipes = [...recipes, { ...clean, id, source: 'user', rank: 500, hidden: false, edited: false }]
    return clone(findJudged(id))
  },

  async updateRecipe(id, data) {
    await delay()
    const clean = cleanRecipe(data)
    const index = recipes.findIndex((r) => r.id === id)
    if (index === -1) throw new Error(`No recipe '${id}'`)
    recipes = recipes.map((r, i) => (i === index ? { ...r, ...clean, edited: true } : r))
    return clone(findJudged(id))
  },

  async setHidden(id, hidden) {
    await delay(80)
    if (!recipes.some((r) => r.id === id)) throw new Error(`No recipe '${id}'`)
    recipes = recipes.map((r) => (r.id === id ? { ...r, hidden } : r))
    return clone(findJudged(id))
  },
}
