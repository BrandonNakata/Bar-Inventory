/** One recipe card, linking to its detail page. */

import { Link } from 'react-router-dom'

export default function RecipeCard({ recipe, showMissing = true }) {
  // Optional lines stay off the summary.
  const required = recipe.ingredients.filter((line) => !line.optional)

  return (
    <li className={`recipe-card status-${recipe.status}`}>
      <Link to={`/recipes/${recipe.id}`} className="recipe-link">
        <span className="recipe-name">{recipe.name}</span>
        <span className="recipe-meta">
          {[recipe.method, recipe.glass].filter(Boolean).join(' · ')}
        </span>
        <span className="recipe-lines">
          {required.map((line) => line.ingredient_name).join(', ')}
        </span>
        {showMissing && recipe.missing.length > 0 && (
          <span className="recipe-missing">
            Missing: {recipe.missing.map((line) => line.ingredient_name).join(', ')}
          </span>
        )}
      </Link>
    </li>
  )
}
