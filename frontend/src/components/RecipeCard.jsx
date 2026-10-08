/** One recipe card, linking to its detail page. Missing ingredients show as empty homes. */

import { Link } from 'react-router-dom'

export default function RecipeCard({ recipe, showMissing = true }) {
  // Optional lines stay off the summary.
  const required = recipe.ingredients.filter((line) => !line.optional)
  const missing = new Set(recipe.missing.map((line) => line.ingredient_name))

  return (
    <li className={`recipe-card status-${recipe.status}`}>
      <Link to={`/recipes/${recipe.id}`} className="recipe-link">
        <span className="recipe-head">
          <span className="recipe-name">{recipe.name}</span>
          <span className="recipe-meta">
            {[recipe.method, recipe.glass].filter(Boolean).join(' · ')}
          </span>
        </span>
        <span className="tags">
          {required.map((line) => {
            const out = showMissing && missing.has(line.ingredient_name)
            return (
              <span key={line.ingredient_name} className={`tag${out ? ' tag-out' : ''}`}>
                {line.ingredient_name}
                {out && <span className="sr-only"> (not on the shelf)</span>}
              </span>
            )
          })}
        </span>
      </Link>
    </li>
  )
}
