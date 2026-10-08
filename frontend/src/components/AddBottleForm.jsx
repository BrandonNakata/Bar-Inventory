/** Add a bottle: name and category, pre-filled after a barcode lookup. */

import { useId, useState } from 'react'

import { api } from '../api'
import CategoryPicker from './CategoryPicker'

export default function AddBottleForm({
  ingredients,
  onAdd,
  initialName = '',
  initialIngredientId = '',
  submitLabel = 'Add',
  placeholder = 'Carpano Antica Formula',
  onCancel,
}) {
  const [productName, setProductName] = useState(initialName)
  const [ingredientId, setIngredientId] = useState(initialIngredientId)
  const [suggestion, setSuggestion] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState(null)

  // useId keeps label ids unique when two forms are on screen.
  const id = useId()

  async function handleNameBlur() {
    const name = productName.trim()
    if (!name) return
    try {
      const guess = await api.suggestIngredient(name)
      setSuggestion(guess)
      // Only fill the category if the user hasn't picked one.
      if (guess.ingredient_id && !ingredientId) {
        setIngredientId(guess.ingredient_id)
      }
    } catch {
      // A failed suggestion is not worth interrupting anyone over.
      setSuggestion(null)
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()

    const name = productName.trim()
    if (!name || !ingredientId) {
      setFormError('Both a name and a category, please.')
      return
    }

    setSubmitting(true)
    setFormError(null)
    try {
      await onAdd({ product_name: name, ingredient_id: ingredientId })
      setProductName('')
      setIngredientId('')
      setSuggestion(null)
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="add-form" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor={`${id}-name`}>Bottle</label>
        <input
          id={`${id}-name`}
          type="text"
          value={productName}
          placeholder={placeholder}
          autoComplete="off"
          onChange={(event) => setProductName(event.target.value)}
          onBlur={handleNameBlur}
        />
      </div>

      <CategoryPicker
        ingredients={ingredients}
        value={ingredientId}
        onChange={setIngredientId}
        label="Category"
      />

      <div className="form-actions">
        <button type="submit" disabled={submitting}>
          {submitting ? 'Adding…' : submitLabel}
        </button>
        {onCancel && (
          <button type="button" className="ghost" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>

      {suggestion?.ingredient_id && (
        <p className="hint">
          Guessed <strong>{suggestion.ingredient_name}</strong> from the name.
          Change it if that's wrong.
        </p>
      )}
      {suggestion && !suggestion.ingredient_id && (
        <p className="hint">
          No guess for that one. Pick a category and it'll be remembered.
        </p>
      )}
      {formError && <p className="error">{formError}</p>}
    </form>
  )
}
