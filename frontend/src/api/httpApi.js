/** API client for the FastAPI backend. */

// Blank in development (Vite proxies /api); set when the API is on another origin.
const BASE = import.meta.env.VITE_API_BASE ?? ''

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  // fetch only rejects on network errors, so check response.ok.
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      if (body.detail) {
        // FastAPI 422 errors put a list here; flatten it to text.
        detail = Array.isArray(body.detail)
          ? body.detail.map((d) => d.msg).join('; ')
          : body.detail
      }
    } catch {
      // response wasn't JSON; the status line is all we have
    }
    throw new Error(detail)
  }

  // 204 has no body; .json() would throw.
  if (response.status === 204) return undefined
  return response.json()
}

export const httpApi = {
  // ---- inventory ----------------------------------------------------------

  listIngredients() {
    return request('/api/ingredients')
  },

  listBottles() {
    return request('/api/bottles')
  },

  addBottle(draft) {
    return request('/api/bottles', {
      method: 'POST',
      body: JSON.stringify(draft),
    })
  },

  deleteBottle(id) {
    return request(`/api/bottles/${id}`, { method: 'DELETE' })
  },

  suggestIngredient(productName) {
    // Encode names like "Maker's Mark" for the query string.
    return request(
      `/api/ingredients/suggest?product_name=${encodeURIComponent(productName)}`,
    )
  },

  lookupBarcode(code) {
    // May call Open Food Facts or UPCitemdb, so a first lookup can take a few seconds.
    return request(`/api/barcodes/${encodeURIComponent(code.trim())}`)
  },

  // ---- recipes ------------------------------------------------------------

  // kind: 'cocktail' | 'shot' | 'all'; hidden: 'exclude' | 'include' | 'only'
  listRecipes({ kind = 'cocktail', hidden = 'exclude' } = {}) {
    return request(`/api/recipes?kind=${kind}&hidden=${hidden}`)
  },

  getRecipe(id) {
    return request(`/api/recipes/${encodeURIComponent(id)}`)
  },

  randomRecipe() {
    // no-store: a random pick must not come from the browser cache.
    return request('/api/recipes/random', { cache: 'no-store' })
  },

  shoppingList(limit = 5) {
    return request(`/api/recipes/shopping-list?limit=${limit}`)
  },

  // ---- editing (the phone's editor) --------------------------------------

  createRecipe(recipe) {
    return request('/api/recipes', { method: 'POST', body: JSON.stringify(recipe) })
  },

  // PUT replaces the whole recipe.
  updateRecipe(id, recipe) {
    return request(`/api/recipes/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(recipe),
    })
  },

  // PATCH changes only the hidden flag.
  setHidden(id, hidden) {
    return request(`/api/recipes/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({ hidden }),
    })
  },
}
