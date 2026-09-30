/** Ranked bottles to buy and the drinks each unlocks. */

import { Link } from 'react-router-dom'

export default function ShoppingList({ suggestions, recipeIdByName = {} }) {
  return (
    <ol className="shopping-list">
      {suggestions.map((suggestion) => (
        <li key={suggestion.ingredient_id} className="shopping-item">
          <div className="shopping-head">
            <strong>{suggestion.ingredient_name}</strong>
            <span className="unlocks">
              +{suggestion.unlocks} {suggestion.unlocks === 1 ? 'drink' : 'drinks'}
            </span>
          </div>
          <ul className="unlocked-recipes">
            {suggestion.recipes.map((name) => {
              const id = recipeIdByName[name]
              return (
                <li key={name}>
                  {id ? <Link to={`/recipes/${id}`}>{name}</Link> : name}
                </li>
              )
            })}
          </ul>
        </li>
      ))}
    </ol>
  )
}
