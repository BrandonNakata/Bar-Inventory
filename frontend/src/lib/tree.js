/** Orders the flat ingredient list into tree order. */

const ROOT = Symbol('root')

/**
 * @param {{id: string, name: string, parent_id: string|null}[]} ingredients
 * @returns {{id: string, name: string, parent_id: string|null, depth: number}[]}
 *   the same rows, in tree order, each tagged with how deep it sits
 */
export function orderByTree(ingredients) {
  // Bucket nodes under their parents in one pass.
  const childrenOf = new Map()
  for (const ingredient of ingredients) {
    const key = ingredient.parent_id ?? ROOT
    if (!childrenOf.has(key)) childrenOf.set(key, [])
    childrenOf.get(key).push(ingredient)
  }
  for (const siblings of childrenOf.values()) {
    siblings.sort((a, b) => a.name.localeCompare(b.name))
  }

  const ordered = []
  const walk = (key, depth) => {
    for (const ingredient of childrenOf.get(key) ?? []) {
      ordered.push({ ...ingredient, depth })
      walk(ingredient.id, depth + 1)
    }
  }
  walk(ROOT, 0)
  return ordered
}

/** Non-breaking spaces, because a <option> collapses ordinary leading spaces. */
export function indent(depth) {
  return '  '.repeat(depth)
}
