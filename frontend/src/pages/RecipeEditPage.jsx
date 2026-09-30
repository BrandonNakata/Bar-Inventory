/** Create or edit a recipe: /recipes/new or /recipes/:recipeId/edit. */

import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { api } from '../api'
import CategoryPicker from '../components/CategoryPicker'
import StepsEditor from '../components/StepsEditor'
import { dropIngredient, swapIngredient } from '../lib/steps'

const METHODS = ['shaken', 'stirred', 'built', 'blended', 'layered', 'bomb']
const GLASSES = [
  'coupe', 'rocks', 'highball', 'collins', 'flute', 'wine glass', 'copper mug',
  'mug', 'hurricane', 'julep cup', 'shot', 'pint', 'snifter', 'tiki mug',
]

function blank(kind) {
  return {
    name: '',
    kind: kind === 'shot' ? 'shot' : 'cocktail',
    glass: kind === 'shot' ? 'shot' : '',
    method: '',
    garnish: '',
    instructions: '',
    steps: [],
    ingredients: [],
  }
}

/** A recipe from the API -> the editable draft. */
function toDraft(recipe) {
  return {
    name: recipe.name,
    kind: recipe.kind,
    glass: recipe.glass ?? '',
    method: recipe.method ?? '',
    garnish: recipe.garnish ?? '',
    instructions: recipe.instructions ?? '',
    steps: recipe.steps_template,
    ingredients: recipe.ingredients.map((line) => ({
      ingredient_id: line.ingredient_id,
      amount: line.amount ?? '',
      optional: line.optional,
    })),
  }
}

export default function RecipeEditPage() {
  const { recipeId } = useParams() // undefined on /recipes/new
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const [ingredients, setIngredients] = useState([])
  const [draft, setDraft] = useState(recipeId ? null : blank(searchParams.get('kind')))
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let cancelled = false
    Promise.all([api.listIngredients(), recipeId ? api.getRecipe(recipeId) : null])
      .then(([rows, recipe]) => {
        if (cancelled) return
        setIngredients(rows)
        if (recipe) setDraft(toDraft(recipe))
      })
      .catch((err) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [recipeId])

  if (!draft) return error ? <p className="error">{error}</p> : <p className="muted">Loading…</p>

  const nameOf = (id) => ingredients.find((i) => i.id === id)?.name ?? id
  // What the steps preview renders against: the lines as they are right now.
  const previewLines = draft.ingredients
    .filter((line) => line.ingredient_id)
    .map((line) => ({ ...line, ingredient_name: nameOf(line.ingredient_id) }))

  const set = (field, value) => setDraft((d) => ({ ...d, [field]: value }))

  function setLine(index, patch) {
    setDraft((d) => {
      const before = d.ingredients[index]
      let steps = d.steps
      if (patch.ingredient_id && before.ingredient_id && patch.ingredient_id !== before.ingredient_id) {
        steps = swapIngredient(steps, before.ingredient_id, patch.ingredient_id)
      }
      const lines = d.ingredients.map((line, i) => (i === index ? { ...line, ...patch } : line))
      return { ...d, ingredients: lines, steps }
    })
  }

  function addLine() {
    setDraft((d) => ({
      ...d,
      ingredients: [...d.ingredients, { ingredient_id: '', amount: '', optional: false }],
    }))
  }

  function removeLine(index) {
    setDraft((d) => {
      const gone = d.ingredients[index]
      return {
        ...d,
        ingredients: d.ingredients.filter((_, i) => i !== index),
        steps: gone.ingredient_id
          ? dropIngredient(d.steps, gone.ingredient_id, nameOf(gone.ingredient_id))
          : d.steps,
      }
    })
  }

  async function save(event) {
    event.preventDefault()
    setError(null)
    const payload = {
      ...draft,
      ingredients: draft.ingredients
        .filter((line) => line.ingredient_id)
        .map((line) => ({ ...line, amount: line.amount.trim() || null })),
      steps: draft.steps.filter((step) => step.trim()),
    }
    if (payload.ingredients.length === 0) {
      setError('Add at least one ingredient.')
      return
    }
    setSaving(true)
    try {
      const saved = recipeId
        ? await api.updateRecipe(recipeId, payload)
        : await api.createRecipe(payload)
      navigate(`/recipes/${saved.id}`)
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
  }

  return (
    <form className="recipe-edit" onSubmit={save}>
      <Link to={recipeId ? `/recipes/${recipeId}` : '/recipes'} className="back">
        ← Cancel
      </Link>
      <h1>{recipeId ? `Edit ${draft.name || 'recipe'}` : `New ${draft.kind}`}</h1>

      <section className="edit-block">
        <div className="field">
          <label htmlFor="edit-name">Name</label>
          <input id="edit-name" value={draft.name} onChange={(e) => set('name', e.target.value)} required />
        </div>
        <div className="edit-row">
          <div className="field">
            <label htmlFor="edit-kind">Kind</label>
            <select id="edit-kind" value={draft.kind} onChange={(e) => set('kind', e.target.value)}>
              <option value="cocktail">Cocktail</option>
              <option value="shot">Shot</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="edit-method">Method</label>
            <select id="edit-method" value={draft.method} onChange={(e) => set('method', e.target.value)}>
              <option value="">—</option>
              {METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="edit-glass">Glass</label>
            <select id="edit-glass" value={draft.glass} onChange={(e) => set('glass', e.target.value)}>
              <option value="">—</option>
              {/* Keep a glass that isn't in the list (from a dataset) selectable. */}
              {[...new Set([...GLASSES, draft.glass].filter(Boolean))].map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </div>
        </div>
      </section>

      <section className="edit-block">
        <h2>Ingredients</h2>
        {draft.ingredients.map((line, index) => (
          <div key={index} className="edit-line">
            <CategoryPicker
              ingredients={ingredients}
              value={line.ingredient_id}
              onChange={(id) => setLine(index, { ingredient_id: id })}
              label={`Ingredient ${index + 1}`}
            />
            <div className="edit-line-row">
              <div className="field">
                <label htmlFor={`amount-${index}`}>Amount</label>
                <input
                  id={`amount-${index}`}
                  value={line.amount}
                  placeholder="1 1/2 oz, 2 dashes, top"
                  onChange={(e) => setLine(index, { amount: e.target.value })}
                />
              </div>
              <label className="check">
                <input
                  type="checkbox"
                  checked={line.optional}
                  onChange={(e) => setLine(index, { optional: e.target.checked })}
                />
                Optional
              </label>
              <button type="button" className="ghost danger" onClick={() => removeLine(index)}>
                Remove
              </button>
            </div>
          </div>
        ))}
        <button type="button" className="ghost" onClick={addLine}>
          + Add ingredient
        </button>
      </section>

      <section className="edit-block">
        <h2>Steps</h2>
        <StepsEditor steps={draft.steps} lines={previewLines} onChange={(steps) => set('steps', steps)} />
      </section>

      <section className="edit-block">
        <div className="field">
          <label htmlFor="edit-garnish">Garnish</label>
          <input id="edit-garnish" value={draft.garnish} placeholder="lime wheel"
            onChange={(e) => set('garnish', e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="edit-summary">One-line summary (shown on cards)</label>
          <input id="edit-summary" value={draft.instructions}
            placeholder="Shake with ice and strain into a chilled coupe."
            onChange={(e) => set('instructions', e.target.value)} />
        </div>
      </section>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="form-actions">
        <button type="submit" disabled={saving}>
          {saving ? 'Saving…' : recipeId ? 'Save changes' : 'Create'}
        </button>
      </div>
    </form>
  )
}
