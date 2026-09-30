/** Category picker: type to filter, or tap a family chip. */

import { useEffect, useId, useMemo, useState } from 'react'

import { MORE_FAMILIES, PRIMARY_FAMILIES, searchCategories, withFamilies } from '../lib/families'

const MAX_RESULTS = 40

export default function CategoryPicker({ ingredients, value, onChange, label = 'Category' }) {
  const id = useId()
  const [open, setOpen] = useState(!value)
  const [query, setQuery] = useState('')
  const [family, setFamily] = useState(null)
  const [showMore, setShowMore] = useState(false)

  // Tagging walks the whole tree, so only redo it when the list changes.
  const tagged = useMemo(() => withFamilies(ingredients), [ingredients])

  // The value can also change from outside (name guess, form reset).
  useEffect(() => {
    setOpen(!value)
  }, [value])
  const selected = tagged.find((row) => row.id === value)

  const results = searchCategories(tagged, query, family?.key)
  const shown = results.slice(0, MAX_RESULTS)

  function choose(row) {
    onChange(row.id)
    setOpen(false)
    setQuery('')
  }

  function toggleFamily(f) {
    setFamily((current) => (current?.key === f.key ? null : f))
  }

  // Folded: one line with the choice. This is the state most forms end in.
  if (!open && selected) {
    return (
      <div className="field picker">
        <span className="picker-label">{label}</span>
        <div className="picker-chosen">
          <span>
            <strong>{selected.name}</strong>
            {selected.family && <span className="muted"> · {selected.family.label}</span>}
          </span>
          <button type="button" className="ghost" onClick={() => setOpen(true)}>
            Change
          </button>
        </div>
      </div>
    )
  }

  const chip = (f) => (
    <button
      key={f.key}
      type="button"
      className={`chip ${family?.key === f.key ? 'chip-on' : ''}`}
      aria-pressed={family?.key === f.key}
      onClick={() => toggleFamily(f)}
    >
      {f.label}
    </button>
  )

  return (
    <div className="field picker">
      <label htmlFor={`${id}-search`}>{label}</label>
      <input
        id={`${id}-search`}
        type="search"
        value={query}
        placeholder={family ? `Search ${family.label.toLowerCase()}…` : 'Type to search, e.g. blanco'}
        autoComplete="off"
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={(event) => {
          // Enter picks the top result instead of submitting the form.
          if (event.key === 'Enter') {
            event.preventDefault()
            if (shown.length > 0) choose(shown[0])
          }
        }}
      />

      <div className="chips" role="group" aria-label="Families">
        {PRIMARY_FAMILIES.map(chip)}
        {showMore && MORE_FAMILIES.map(chip)}
        <button type="button" className="chip chip-more" onClick={() => setShowMore((s) => !s)}>
          {showMore ? 'Fewer' : 'More…'}
        </button>
      </div>

      {shown.length > 0 && (
        <ul className="picker-results">
          {shown.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                className={`picker-result ${row.id === value ? 'is-selected' : ''}`}
                // Indent by depth only when browsing a family.
                style={!query && family ? { paddingLeft: `${0.75 + row.relDepth * 0.9}rem` } : undefined}
                onClick={() => choose(row)}
              >
                <span>{row.name}</span>
                {query && row.family && <span className="muted">{row.family.label}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}

      {results.length > MAX_RESULTS && (
        <p className="hint">
          {results.length - MAX_RESULTS} more. Keep typing to narrow it down.
        </p>
      )}
      {query && results.length === 0 && (
        <p className="hint">Nothing called that{family ? ` under ${family.label}` : ''}.</p>
      )}
      {!query && !family && (
        <p className="hint">Pick a family, or start typing.</p>
      )}
      {selected && (
        <button type="button" className="ghost picker-cancel" onClick={() => setOpen(false)}>
          Keep {selected.name}
        </button>
      )}
    </div>
  )
}
