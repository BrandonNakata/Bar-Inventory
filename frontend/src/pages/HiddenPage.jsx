/** Recipes hidden from every list, with a way to restore them. */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api'

export default function HiddenPage() {
  const [recipes, setRecipes] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .listRecipes({ kind: 'all', hidden: 'only' })
      .then((data) => !cancelled && setRecipes(data.recipes))
      .catch((err) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [])

  async function unhide(id) {
    try {
      await api.setHidden(id, false)
      // Drop it from this list; the server has already put it back on the others.
      setRecipes((current) => current.filter((r) => r.id !== id))
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section>
      <Link to="/recipes" className="back">
        All recipes
      </Link>
      <h1>Hidden recipes</h1>
      {error && <p className="error">{error}</p>}
      {!recipes ? (
        <p className="muted">Loading…</p>
      ) : recipes.length === 0 ? (
        <p className="muted">Nothing hidden. Use Hide on any recipe to take it off the lists.</p>
      ) : (
        <ul className="bottle-list">
          {recipes.map((recipe) => (
            <li key={recipe.id} className="bottle">
              <span className="bottle-main">
                <Link to={`/recipes/${recipe.id}`} className="bottle-name">{recipe.name}</Link>
                <span className="bottle-category">{recipe.kind}</span>
              </span>
              <button type="button" className="ghost" onClick={() => unhide(recipe.id)}>
                Unhide
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
