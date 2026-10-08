/** The Shelf: owns the bottle list, the missing row, and the functions that change them. */

import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { api } from '../api'
import AddBottleForm from '../components/AddBottleForm'
import Icon from '../components/Icon'
import RecipeCard from '../components/RecipeCard'
import ScanPanel from '../components/ScanPanel'
import ShelfBoard from '../components/ShelfBoard'
import { ALL_FAMILIES, fold, withFamilies } from '../lib/families'

const OTHER = { key: 'other', label: 'Other' }
const SHOW_MISSING_KEY = 'bar.showMissing'

function readShowMissing() {
  try {
    return localStorage.getItem(SHOW_MISSING_KEY) !== 'false'
  } catch {
    return true
  }
}

export default function ShelfPage() {
  const [ingredients, setIngredients] = useState([])
  const [bottles, setBottles] = useState([])
  const [suggestions, setSuggestions] = useState([])
  const [recipes, setRecipes] = useState(null)
  // Bottles finished this session, so they can go straight back on the shelf.
  const [finished, setFinished] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [family, setFamily] = useState('all')
  const [query, setQuery] = useState('')
  const [showMissing, setShowMissing] = useState(readShowMissing)
  const [restock, setRestock] = useState(null)
  const [manualOpen, setManualOpen] = useState(false)
  const [busyId, setBusyId] = useState(null)
  const [landedId, setLandedId] = useState(null)
  const manualRef = useRef(null)
  const location = useLocation()

  // Fetch once after the first render.
  useEffect(() => {
    // Ignore responses that land after unmount.
    let cancelled = false

    async function load() {
      try {
        // Run all three requests at once.
        const [ingredientRows, bottleRows, shopping, recipeData] = await Promise.all([
          api.listIngredients(),
          api.listBottles(),
          api.shoppingList(10),
          api.listRecipes(),
        ])
        if (cancelled) return
        setIngredients(ingredientRows)
        setBottles(bottleRows)
        setSuggestions(shopping)
        setRecipes(recipeData)
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  // Unlock counts and the side lists change whenever the shelf does.
  async function refreshSuggestions() {
    window.dispatchEvent(new Event('bar:changed'))
    try {
      const [shopping, recipeData] = await Promise.all([api.shoppingList(10), api.listRecipes()])
      setSuggestions(shopping)
      setRecipes(recipeData)
    } catch {
      // Stale suggestions are better than an error banner here.
    }
  }

  const familyOf = useMemo(() => {
    const map = new Map()
    for (const row of withFamilies(ingredients)) map.set(row.id, row.family ?? OTHER)
    return map
  }, [ingredients])
  const famFor = (ingredientId) => familyOf.get(ingredientId) ?? OTHER

  const q = fold(query.trim())
  const matches = (ingredientId, ...texts) =>
    (family === 'all' || famFor(ingredientId).key === family) &&
    (!q || texts.some((text) => text && fold(text).includes(q)))

  // Stocked bottles grouped into family rows, in the families' own order.
  const rows = useMemo(() => {
    const order = [...ALL_FAMILIES, OTHER]
    const groups = new Map()
    for (const bottle of bottles) {
      if (!matches(bottle.ingredient_id, bottle.product_name, bottle.ingredient_name)) continue
      const fam = famFor(bottle.ingredient_id)
      if (!groups.has(fam.key)) groups.set(fam.key, { ...fam, bottles: [] })
      groups.get(fam.key).bottles.push(bottle)
    }
    for (const group of groups.values()) {
      group.bottles.sort((a, b) => a.product_name.localeCompare(b.product_name))
    }
    return order.filter((fam) => groups.has(fam.key)).map((fam) => groups.get(fam.key))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bottles, familyOf, family, q])

  // Missing: what you just finished first, then what would unlock the most drinks.
  const missing = useMemo(() => {
    const finishedIds = new Set(finished.map((entry) => entry.draft.ingredient_id))
    const fromFinished = finished.map((entry) => ({
        key: `finished-${entry.id}`,
        kind: 'finished',
        entry,
        name: entry.draft.product_name,
        ingredientId: entry.draft.ingredient_id,
        detail: `${famFor(entry.draft.ingredient_id).label} · finished just now`,
        action: 'Put it back on the shelf',
    }))
    const fromSuggestions = suggestions
      .filter((s) => !finishedIds.has(s.ingredient_id))
      .map((s) => ({
        key: `suggest-${s.ingredient_id}`,
        kind: 'suggestion',
        suggestion: s,
        name: s.ingredient_name,
        ingredientId: s.ingredient_id,
        detail: `${famFor(s.ingredient_id).label} · +${s.unlocks} ${s.unlocks === 1 ? 'drink' : 'drinks'}`,
        action: 'Add a bottle of it',
      }))
    return [...fromFinished, ...fromSuggestions].filter((item) =>
      matches(item.ingredientId, item.name, item.detail),
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finished, suggestions, bottles, familyOf, family, q])

  // Chips only for families that have something on the board.
  const chipFamilies = useMemo(() => {
    const present = new Set([
      ...bottles.map((b) => famFor(b.ingredient_id).key),
      ...finished.map((e) => famFor(e.draft.ingredient_id).key),
      ...suggestions.map((s) => famFor(s.ingredient_id).key),
    ])
    return [...ALL_FAMILIES, OTHER].filter((fam) => present.has(fam.key))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bottles, finished, suggestions, familyOf])

  async function handleAdd(draft) {
    // Store the server's bottle, which has the id and timestamp.
    const created = await api.addBottle(draft)
    setBottles((current) => [created, ...current])
    setFinished((current) =>
      current.filter(
        (e) =>
          e.draft.ingredient_id !== draft.ingredient_id ||
          fold(e.draft.product_name) !== fold(draft.product_name),
      ),
    )
    setError(null)
    setRestock(null)
    setLandedId(created.id)
    refreshSuggestions()
    // Returned so a caller can say what was added ("Added Campari").
    return created
  }

  async function handleFinish(bottle) {
    setBusyId(bottle.id)
    try {
      await api.deleteBottle(bottle.id)
      setBottles((current) => current.filter((b) => b.id !== bottle.id))
      const entry = {
        id: bottle.id,
        draft: { product_name: bottle.product_name, ingredient_id: bottle.ingredient_id },
      }
      setFinished((current) => [entry, ...current])
      setNotice({ text: `${bottle.product_name} moved to Not on the shelf.`, entry })
      refreshSuggestions()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  async function putBack(entry) {
    setBusyId(`finished-${entry.id}`)
    try {
      const created = await handleAdd(entry.draft)
      setNotice({ text: `${created.product_name} is back on the shelf.` })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  function handleRestock(item) {
    if (item.kind === 'finished') {
      putBack(item.entry)
      return
    }
    // A category, not a bottle: ask for the bottle's name, category pre-picked.
    setRestock({ ingredientId: item.ingredientId, name: item.name })
    setManualOpen(true)
    requestAnimationFrame(() => {
      manualRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      manualRef.current?.querySelector('input')?.focus({ preventScroll: true })
    })
  }

  function jumpToMissing(event) {
    event.preventDefault()
    if (!showMissing) toggleMissing()
    const row = document.getElementById('missing-row')
    row?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    row?.focus({ preventScroll: true })
  }

  const oneShort = recipes?.recipes.filter((r) => r.status === 'one_short') ?? []
  const makeable = recipes?.recipes.filter((r) => r.status === 'makeable') ?? []

  function toggleMissing() {
    setShowMissing((current) => {
      try {
        localStorage.setItem(SHOW_MISSING_KEY, String(!current))
      } catch {
        // Private windows can refuse storage; the switch still works for this visit.
      }
      return !current
    })
  }

  // Clear the landing highlight once its animation has played.
  useEffect(() => {
    if (landedId == null) return
    const timer = setTimeout(() => setLandedId(null), 900)
    return () => clearTimeout(timer)
  }, [landedId])

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Shelf</h1>
          <p className="count">
            {loading ? (
              'Loading…'
            ) : (
              <>
                {bottles.length} {bottles.length === 1 ? 'bottle' : 'bottles'} on the shelf ·{' '}
                <a href="#missing-row" className="count-missing" onClick={jumpToMissing}>
                  <i aria-hidden="true" />
                  {missing.length} missing
                </a>
              </>
            )}
          </p>
        </div>
        <label className="search">
          <Icon name="search" />
          <span className="sr-only">Search the shelf</span>
          <input
            type="search"
            value={query}
            placeholder="Search bottles"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
      </header>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <ScanPanel ingredients={ingredients} onAdd={handleAdd} focusSignal={location.state?.scan} />

      <details
        className="manual-add"
        ref={manualRef}
        open={manualOpen}
        onToggle={(event) => setManualOpen(event.currentTarget.open)}
      >
        <summary>{restock ? `Restock ${restock.name}: name the bottle` : 'No barcode? Add by hand'}</summary>
        <AddBottleForm
          key={restock?.ingredientId ?? 'manual'}
          ingredients={ingredients}
          initialIngredientId={restock?.ingredientId ?? ''}
          submitLabel={restock ? 'Put on the shelf' : 'Add'}
          placeholder={restock ? 'Brand and bottle name' : undefined}
          onAdd={handleAdd}
          onCancel={restock ? () => setRestock(null) : undefined}
        />
      </details>

      {!loading && chipFamilies.length > 1 && (
        <div className="filters" role="group" aria-label="Filter by family">
          {[{ key: 'all', label: 'All' }, ...chipFamilies].map((fam) => (
            <button
              key={fam.key}
              type="button"
              className={`chip${family === fam.key ? ' chip-on' : ''}`}
              aria-pressed={family === fam.key}
              onClick={() => setFamily(fam.key)}
            >
              {fam.label}
            </button>
          ))}
        </div>
      )}

      {notice && (
        <div className="notice" role="status">
          <span>{notice.text}</span>
          {notice.entry && finished.includes(notice.entry) && (
            <button type="button" className="ghost" onClick={() => putBack(notice.entry)}>
              Undo
            </button>
          )}
          <button type="button" className="ghost" onClick={() => setNotice(null)}>
            Dismiss
          </button>
        </div>
      )}

      <div className="shelf-layout">
      <ShelfBoard
        rows={rows}
        missing={missing}
        loading={loading}
        query={query}
        totalBottles={bottles.length}
        showMissing={showMissing}
        onToggleMissing={toggleMissing}
        onFinish={handleFinish}
        onRestock={handleRestock}
        busyId={busyId}
        landedId={landedId}
      />

      {recipes && (
        <aside className="shelf-side" aria-label="Drinks">
          {oneShort.length > 0 && (
            <section className="side-panel">
              <h2>
                One bottle away <span className="section-count">{oneShort.length}</span>
              </h2>
              <ul className="side-list">
                {oneShort.slice(0, 5).map((recipe) => (
                  <RecipeCard key={recipe.id} recipe={recipe} />
                ))}
              </ul>
              {oneShort.length > 5 && (
                <Link to="/shopping" className="header-link">
                  See all {oneShort.length} drinks one bottle away
                </Link>
              )}
            </section>
          )}
          <section className="side-panel">
            <h2>
              Can make now <span className="section-count">{recipes.makeable_count}</span>
            </h2>
            {makeable.length === 0 ? (
              <p className="muted">Nothing yet. Add a bottle and drinks will show up here.</p>
            ) : (
              <ul className="side-list">
                {makeable.slice(0, 4).map((recipe) => (
                  <RecipeCard key={recipe.id} recipe={recipe} />
                ))}
              </ul>
            )}
            <Link to="/recipes" className="header-link">
              See all recipes
            </Link>
          </section>
        </aside>
      )}
      </div>
    </>
  )
}
