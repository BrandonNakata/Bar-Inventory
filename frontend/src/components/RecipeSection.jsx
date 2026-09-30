/** A titled group of recipe cards with a count and an empty state. */

import RecipeCard from './RecipeCard'

export default function RecipeSection({ title, recipes, empty }) {
  return (
    <section className="recipe-section">
      <div className="section-heading">
        <h2>{title}</h2>
        <span className="section-count">{recipes.length}</span>
      </div>
      {recipes.length === 0 ? (
        <p className="muted">{empty}</p>
      ) : (
        <ul className="recipe-grid">
          {recipes.map((recipe) => (
            <RecipeCard key={recipe.id} recipe={recipe} />
          ))}
        </ul>
      )}
    </section>
  )
}
