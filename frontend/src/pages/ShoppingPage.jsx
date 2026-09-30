/** Shopping: which bottle would unlock the most drinks. */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api'
import RecipeCard from '../components/RecipeCard'
import RecipeSection from '../components/RecipeSection'
import ShoppingList from '../components/ShoppingList'

export default function ShoppingPage() {
  const [suggestions, setSuggestions] = useState(null)
  const [recipeIdByName, setRecipeIdByName] = useState({})
  const [oneShort, setOneShort] = useState([])
  const [furtherOff, setFurtherOff] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [shopping, recipeData] = await Promise.all([
          api.shoppingList(10),
          api.listRecipes(),
        ])
        if (cancelled) return
        setSuggestions(shopping)
        setOneShort(recipeData.recipes.filter((recipe) => recipe.status === 'one_short'))
        setFurtherOff(recipeData.recipes.filter((recipe) => recipe.status === 'not_tonight'))
        setRecipeIdByName(
          Object.fromEntries(recipeData.recipes.map((recipe) => [recipe.name, recipe.id])),
        )
      } catch (err) {
        if (!cancelled) setError(err.message)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Shopping</h1>
          <p className="count">
            One bottle each, ranked by how many new drinks it would unlock
          </p>
        </div>
      </header>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {!suggestions && !error && <p className="muted">Checking the shelf…</p>}

      {suggestions && suggestions.length === 0 && (
        <p className="muted shopping-empty">
          {oneShort.length === 0
            ? "Nothing is exactly one bottle away right now. Suggestions appear when a recipe is missing a single ingredient."
            : 'Nothing to suggest.'}{' '}
          <Link to="/recipes">See all recipes</Link>.
        </p>
      )}

      {suggestions && suggestions.length > 0 && (
        <ShoppingList suggestions={suggestions} recipeIdByName={recipeIdByName} />
      )}

      {suggestions && oneShort.length > 0 && (
        <RecipeSection
          title="One short"
          recipes={oneShort}
          empty="Nothing is exactly one ingredient away."
        />
      )}

      {suggestions && furtherOff.length > 0 && (
        <details className="recipe-section">
          <summary>
            <h2>Further off</h2>
            <span className="section-count">{furtherOff.length}</span>
          </summary>
          <ul className="recipe-grid">
            {furtherOff.map((recipe) => (
              <RecipeCard key={recipe.id} recipe={recipe} />
            ))}
          </ul>
        </details>
      )}
    </>
  )
}
