/** Families: groups categories into picker chips. */

import { orderByTree } from './tree'

export const PRIMARY_FAMILIES = [
  { key: 'rum', label: 'Rum', roots: ['rum', 'flavored-rum', 'cachaca'] },
  { key: 'tequila', label: 'Tequila', roots: ['tequila', 'mezcal'] },
  { key: 'whiskey', label: 'Whiskey', roots: ['whiskey', 'flavored-whiskey'] },
  { key: 'vodka', label: 'Vodka', roots: ['vodka', 'flavored-vodka', 'grain-alcohol'] },
  { key: 'gin', label: 'Gin', roots: ['gin'] },
  { key: 'liqueur', label: 'Liqueur', roots: ['liqueur'] },
]

export const MORE_FAMILIES = [
  { key: 'brandy', label: 'Brandy', roots: ['brandy', 'pisco'] },
  { key: 'spirits', label: 'Other spirits', roots: ['absinthe', 'aquavit', 'soju', 'spirit', 'flavored-spirit'] },
  { key: 'wine', label: 'Wine', roots: ['wine', 'fortified-wine'] },
  { key: 'beer', label: 'Beer & cider', roots: ['beer'] },
  { key: 'bitters', label: 'Bitters', roots: ['bitters'] },
  { key: 'mixer', label: 'Mixers', roots: ['mixer'] },
  { key: 'fresh', label: 'Fresh & pantry', roots: ['fresh', 'pantry'] },
]

export const ALL_FAMILIES = [...PRIMARY_FAMILIES, ...MORE_FAMILIES]

/** Lowercase and strip accents, so "creme" finds "Crème de Cassis". */
export function fold(text) {
  return text.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

/** Every category id at or below each root. */
function subtree(roots, childrenOf) {
  const out = new Set()
  const stack = [...roots]
  while (stack.length) {
    const id = stack.pop()
    if (out.has(id)) continue
    out.add(id)
    for (const child of childrenOf.get(id) ?? []) stack.push(child.id)
  }
  return out
}

/** Tag every category with its family, in tree order. */
export function withFamilies(ingredients) {
  const childrenOf = new Map()
  for (const ingredient of ingredients) {
    const key = ingredient.parent_id ?? null
    if (!childrenOf.has(key)) childrenOf.set(key, [])
    childrenOf.get(key).push(ingredient)
  }
  // Family, root index, and depth below the root (for ordering and indent).
  const familyOf = new Map()
  const rootIndex = new Map()
  for (const family of ALL_FAMILIES) {
    family.roots.forEach((root, index) => {
      for (const id of subtree([root], childrenOf)) {
        if (!familyOf.has(id)) {
          familyOf.set(id, family)
          rootIndex.set(id, index)
        }
      }
    })
  }
  const ordered = orderByTree(ingredients)
  const depthOf = new Map(ordered.map((row) => [row.id, row.depth]))
  return ordered
    .map((ingredient, position) => {
      const family = familyOf.get(ingredient.id) ?? null
      const root = family ? family.roots[rootIndex.get(ingredient.id)] : null
      return {
        ...ingredient,
        family,
        position,
        rootIndex: rootIndex.get(ingredient.id) ?? 0,
        relDepth: root ? ingredient.depth - (depthOf.get(root) ?? 0) : 0,
      }
    })
}

/** Picker results; names starting with the query come first. */
export function searchCategories(tagged, query, familyKey) {
  const q = fold(query.trim())
  let rows = familyKey ? tagged.filter((row) => row.family?.key === familyKey) : tagged
  if (!q) {
    if (!familyKey) return []
    // Browsing a family: roots in family order, subtrees underneath.
    return [...rows].sort((a, b) => a.rootIndex - b.rootIndex || a.position - b.position)
  }
  rows = rows.filter((row) => fold(row.name).includes(q))
  const starts = (row) => (fold(row.name).startsWith(q) ? 0 : 1)
  return [...rows].sort((a, b) => starts(a) - starts(b) || a.depth - b.depth || a.name.localeCompare(b.name))
}
