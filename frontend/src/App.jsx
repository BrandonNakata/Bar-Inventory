/** Layout: navigation, demo badge and routes. */

import { Link, NavLink, Route, Routes } from 'react-router-dom'

import { isDemo } from './api'
import HiddenPage from './pages/HiddenPage'
import RecipeDetailPage from './pages/RecipeDetailPage'
import RecipeEditPage from './pages/RecipeEditPage'
import RecipesPage from './pages/RecipesPage'
import ShelfPage from './pages/ShelfPage'
import ShoppingPage from './pages/ShoppingPage'

export default function App() {
  return (
    <div className="app">
      {/* `end` so Shelf is only active on exactly /. */}
      <nav className="nav" aria-label="Main">
        <NavLink to="/" end>
          Shelf
        </NavLink>
        <NavLink to="/recipes">Recipes</NavLink>
        <NavLink to="/shopping">Shopping</NavLink>
      </nav>

      {isDemo && (
        <p className="demo-badge">
          Demo: changes live in this browser tab and reset on reload
        </p>
      )}

      <Routes>
        <Route path="/" element={<ShelfPage />} />
        <Route path="/recipes" element={<RecipesPage />} />
        {/* Fixed paths like /recipes/new outrank the :recipeId wildcard. */}
        <Route path="/recipes/new" element={<RecipeEditPage />} />
        <Route path="/recipes/hidden" element={<HiddenPage />} />
        <Route path="/recipes/:recipeId" element={<RecipeDetailPage />} />
        <Route path="/recipes/:recipeId/edit" element={<RecipeEditPage />} />
        <Route path="/shopping" element={<ShoppingPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </div>
  )
}

function NotFound() {
  return (
    <section>
      <h1>Nothing here</h1>
      <p className="muted">
        That page doesn't exist. <Link to="/">Back to the shelf</Link>.
      </p>
    </section>
  )
}
