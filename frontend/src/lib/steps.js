/** Recipe step templates, ported from backend/app/steps.py. */

// {gin} or {gin:name}
export const TOKEN = /\{([a-z0-9-]+)(?::(name))?\}/g

const COUNT_UNIT = /^([\d /]+)\s+(leaves|leaf|sprigs?|slices?|wedges?|cubes?)$/
const OF_UNIT = /^[\d /]+\s+(dash|dashes|drop|drops|barspoons?|tsp|tbsp|pinch(es)?)$/

/** One ingredient line as a phrase: "2 dashes of Aromatic Bitters". */
export function phrase(name, amount) {
  let a = (amount ?? '').trim()
  if (!a || ['top', 'top up', 'fill', 'rinse'].includes(a)) return name
  if (a === 'splash') return `a splash of ${name}`
  if (a === 'pinch') return `a pinch of ${name}`
  if (a.endsWith(' float')) a = a.slice(0, -' float'.length)
  const count = a.match(COUNT_UNIT)
  if (count) return `${count[1]} ${name.toLowerCase()} ${count[2]}`
  if (OF_UNIT.test(a)) return `${a} of ${name}`
  return `${a} ${name}`
}

function fill(lines, names, id, nameOnly) {
  const line = lines.find((l) => l.ingredient_id === id)
  if (!line) return names?.get?.(id) ?? id.replaceAll('-', ' ')
  return nameOnly ? line.ingredient_name : phrase(line.ingredient_name, line.amount)
}

/** Every template with its placeholders filled in. Mirrors steps.render(). */
export function renderSteps(templates, lines, names) {
  return templates.map((step) =>
    step.replace(TOKEN, (_, id, nameOnly) => fill(lines, names, id, Boolean(nameOnly))),
  )
}

/** Split a step into text and placeholder segments for the editor. */
export function segments(template, lines, names) {
  const out = []
  let last = 0
  for (const match of template.matchAll(TOKEN)) {
    if (match.index > last) out.push({ text: template.slice(last, match.index) })
    out.push({
      text: fill(lines, names, match[1], Boolean(match[2])),
      id: match[1],
      known: lines.some((l) => l.ingredient_id === match[1]),
    })
    last = match.index + match[0].length
  }
  if (last < template.length) out.push({ text: template.slice(last) })
  return out
}

/** Every ingredient id a list of steps mentions. */
export function referencedIds(templates) {
  const ids = new Set()
  for (const step of templates) {
    for (const match of step.matchAll(TOKEN)) ids.add(match[1])
  }
  return ids
}

/** Swap one ingredient for another in every step. */
export function swapIngredient(templates, fromId, toId) {
  return templates.map((step) =>
    step.replace(TOKEN, (whole, id, nameOnly) =>
      id === fromId ? `{${toId}${nameOnly ? ':name' : ''}}` : whole,
    ),
  )
}

/** Remove an ingredient from the steps, leaving its plain name. */
export function dropIngredient(templates, id, name) {
  return templates.map((step) =>
    step.replace(TOKEN, (whole, tokenId) => (tokenId === id ? name : whole)),
  )
}
