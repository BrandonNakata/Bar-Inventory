/** The guest menu: makeable drinks first, everything else folded away. */

import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api } from '../api'
import RecipeCard from '../components/RecipeCard'
import { fold } from '../lib/families'

// Render 100 cards at a time.
const PAGE = 100

export default function RecipesPage() {
  const [kind, setKind] = useState('cocktail')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [picking, setPicking] = useState(false)
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(PAGE)

  const navigate = useNavigate()

  // [kind] in the dependency list: flipping Cocktails -> Shots refetches.
  useEffect(() => {
    let cancelled = false
    setData(null)

    async function load() {
      try {
        const recipeData = await api.listRecipes({ kind })
        if (!cancelled) setData(recipeData)
      } catch (err) {
        if (!cancelled) setError(err.message)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [kind])

  // A new search starts back at the first page.
  useEffect(() => setLimit(PAGE), [query, kind])

  // Memoized so the filter doesn't rerun on unrelated renders.
  const { menu, unavailable } = useMemo(() => {
    if (!data) return { menu: [], unavailable: [] }
    const q = fold(query.trim())
    const matches = (recipe) =>
      !q ||
      fold(recipe.name).includes(q) ||
      recipe.ingredients.some((line) => fold(line.ingredient_name).includes(q))
    const found = data.recipes.filter(matches)
    return {
      menu: found.filter((recipe) => recipe.status === 'makeable'),
      unavailable: found
        .filter((recipe) => recipe.status !== 'makeable')
        .sort((a, b) => a.rank - b.rank || a.name.localeCompare(b.name)),
    }
  }, [data, query])

  async function pickForMe() {
    setPicking(true)
    setError(null)
    try {
      const recipe = await api.randomRecipe()
      navigate(`/recipes/${recipe.id}`)
    } catch (err) {
      setError(err.message)
      setPicking(false)
    }
  }

  const noun = kind === 'shot' ? 'shot' : 'drink'

  return (
    <>
      <header className="page-header">
        <div>
          <h1>What I can make</h1>
          <p className="count">
            {data
              ? `${menu.length} ${menu.length === 1 ? noun : `${noun}s`}${query ? ' match' : ''}. Tap one for the recipe`
              : 'Checking the shelf…'}
          </p>
        </div>
        {kind === 'cocktail' && (
          <button
            type="button"
            onClick={pickForMe}
            disabled={picking || !data || data.makeable_count === 0}
          >
            {picking ? 'Choosing…' : 'Pick one for me'}
          </button>
        )}
      </header>

      <div className="recipe-tools">
        <div className="segmented" role="group" aria-label="Kind">
          {['cocktail', 'shot'].map((k) => (
            <button
              key={k}
              type="button"
              className={kind === k ? 'seg-on' : ''}
              aria-pressed={kind === k}
              onClick={() => setKind(k)}
            >
              {k === 'cocktail' ? 'Cocktails' : 'Shots'}
            </button>
          ))}
        </div>
        <input
          type="search"
          className="recipe-search"
          value={query}
          placeholder={`Search ${noun}s or ingredients`}
          aria-label="Search recipes"
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {data && menu.length === 0 && (
        <p className="muted menu-empty">
          {query
            ? `Nothing you can make matches "${query}".`
            : <>Nothing on the menu yet. Add bottles on the <Link to="/">Shelf</Link>.</>}{' '}
          Everything below can be browsed in the meantime.
        </p>
      )}
      {menu.length > 0 && (
        <section className="board menu-board" aria-label="On the menu">
          <ul className="recipe-grid menu-grid">
            {menu.map((recipe) => (
              <RecipeCard key={recipe.id} recipe={recipe} />
            ))}
          </ul>
        </section>
      )}

      {/* Collapsed so guests see the menu first; a search opens it. */}
      {unavailable.length > 0 && (
        <details className="recipe-section" open={Boolean(query)}>
          <summary>
            <h2>Not available</h2>
            <span className="section-count">{unavailable.length}</span>
          </summary>
          <ul className="recipe-grid unavailable-grid">
            {unavailable.slice(0, limit).map((recipe) => (
              <RecipeCard key={recipe.id} recipe={recipe} showMissing={false} />
            ))}
          </ul>
          {unavailable.length > limit && (
            <button type="button" className="ghost show-more" onClick={() => setLimit(limit + PAGE)}>
              Show {Math.min(PAGE, unavailable.length - limit)} more
              ({unavailable.length - limit} left)
            </button>
          )}
        </details>
      )}

      <footer className="recipe-owner">
        <Link to={`/recipes/new?kind=${kind}`} className="header-link">
          + New {noun}
        </Link>
        <Link to="/recipes/hidden" className="header-link">
          Hidden recipes
        </Link>
      </footer>
    </>
  )
}
