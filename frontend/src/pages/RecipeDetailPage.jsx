/** One recipe with each line marked against the shelf, plus its steps. */

import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { api } from '../api'

const STATUS_LABEL = {
  makeable: 'You can make this',
  one_short: 'One ingredient short',
  not_tonight: 'Not tonight',
}

export default function RecipeDetailPage() {
  const { recipeId } = useParams()
  const navigate = useNavigate()

  const [recipe, setRecipe] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    setRecipe(null)
    setError(null)

    api
      .getRecipe(recipeId)
      .then((result) => {
        if (!cancelled) setRecipe(result)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })

    return () => {
      cancelled = true
    }
  }, [recipeId])

  async function pickAnother() {
    setBusy(true)
    try {
      const next = await api.randomRecipe()
      navigate(`/recipes/${next.id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function toggleHidden() {
    setBusy(true)
    try {
      // Redraw from the server's answer.
      setRecipe(await api.setHidden(recipe.id, !recipe.hidden))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (error && !recipe) {
    return (
      <>
        <Link to="/recipes" className="back">
          ← All recipes
        </Link>
        <p className="error" role="alert">
          {error}
        </p>
      </>
    )
  }

  if (!recipe) return <p className="muted">Loading…</p>

  return (
    <article className="recipe-detail">
      <Link to="/recipes" className="back">
        ← All recipes
      </Link>

      <header>
        <h1>{recipe.name}</h1>
        <p className={`status-pill status-${recipe.status}`}>
          {STATUS_LABEL[recipe.status]}
        </p>
        <p className="count">
          {[recipe.kind === 'shot' ? 'shot' : null, recipe.method, recipe.glass]
            .filter(Boolean)
            .join(' · ')}
          {recipe.hidden && ' · hidden'}
        </p>
      </header>

      <ul className="lines">
        {recipe.ingredients.map((line, index) => {
          const state = line.have ? 'have' : line.optional ? 'optional' : 'missing'
          return (
            // Index keys are fine: a recipe's lines don't reorder here.
            <li key={index} className={`line line-${state}`}>
              <span className="mark" aria-hidden="true">
                {state === 'have' ? '✓' : state === 'optional' ? '–' : '✗'}
              </span>
              <span className="amount">{line.amount}</span>
              <span className="ingredient">
                {line.ingredient_name}
                {line.optional && <em className="muted"> optional</em>}
                {/* The marks are decoration; screen readers get words. */}
                <span className="sr-only">
                  {state === 'have' ? ', on the shelf' : ', not on the shelf'}
                </span>
              </span>
            </li>
          )
        })}
      </ul>

      {recipe.garnish && (
        <p className="garnish">
          <span className="label">Garnish</span> {recipe.garnish}
        </p>
      )}

      {recipe.steps.length > 0 ? (
        <ol className="steps">
          {recipe.steps.map((step, index) => (
            <li key={index}>{step}</li>
          ))}
        </ol>
      ) : (
        recipe.instructions && <p className="instructions">{recipe.instructions}</p>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <div className="detail-actions">
        {recipe.kind === 'cocktail' && (
          <button type="button" className="ghost" onClick={pickAnother} disabled={busy}>
            Pick another
          </button>
        )}
        <Link to={`/recipes/${recipe.id}/edit`} className="button-link">
          Edit
        </Link>
        <button type="button" className="ghost" onClick={toggleHidden} disabled={busy}>
          {recipe.hidden ? 'Unhide' : 'Hide'}
        </button>
      </div>
      {recipe.edited && (
        <p className="hint">You've edited this one, so updates to the recipe library leave it alone.</p>
      )}
    </article>
  )
}
