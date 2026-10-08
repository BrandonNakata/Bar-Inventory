/** Layout: the spruce rail (navigation, scan shortcut, demo note) and the routes. */

import { useEffect, useState } from 'react'
import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom'

import { api, isDemo } from './api'
import Icon from './components/Icon'
import HiddenPage from './pages/HiddenPage'
import RecipeDetailPage from './pages/RecipeDetailPage'
import RecipeEditPage from './pages/RecipeEditPage'
import RecipesPage from './pages/RecipesPage'
import ShelfPage from './pages/ShelfPage'
import ShoppingPage from './pages/ShoppingPage'

// Counts for the rail. Refetched on navigation and whenever the shelf changes.
function useCounts() {
  const { pathname } = useLocation()
  const [counts, setCounts] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [bottles, recipes, shopping] = await Promise.all([
          api.listBottles(),
          api.listRecipes(),
          api.shoppingList(10),
        ])
        if (!cancelled) {
          setCounts({ shelf: bottles.length, recipes: recipes.makeable_count, shopping: shopping.length })
        }
      } catch {
        // The rail just shows no numbers; each page reports its own errors.
      }
    }
    load()
    window.addEventListener('bar:changed', load)
    return () => {
      cancelled = true
      window.removeEventListener('bar:changed', load)
    }
  }, [pathname])

  return counts
}

export default function App() {
  const counts = useCounts()
  const n = (key) => counts && <span className="nav-count">{counts[key]}</span>

  return (
    <div className="app">
      <aside className="rail">
        <Link to="/" className="brand">
          <b>Bar Inventory</b>
          <span>Brandon's home bar</span>
        </Link>

        {/* `end` so Shelf is only active on exactly /. */}
        <nav className="nav" aria-label="Main">
          <NavLink to="/" end>
            <Icon name="shelf" />
            Shelf
            {n('shelf')}
          </NavLink>
          <NavLink to="/recipes">
            <Icon name="glass" />
            Recipes
            {n('recipes')}
          </NavLink>
          <NavLink to="/shopping">
            <Icon name="list" />
            Shopping
            {n('shopping')}
          </NavLink>
        </nav>

        <div className="rail-foot">
          {/* The Shelf page reads this state and focuses the barcode field. */}
          <Link to="/" state={{ scan: Date.now() }} className="rail-scan">
            <Icon name="scan" />
            Scan a bottle
          </Link>
          {isDemo && (
            <p className="demo-badge">Demo: changes live in this tab and reset on reload</p>
          )}
        </div>
      </aside>

      <main className="work">
        {isDemo && (
          <p className="demo-inline">Demo: changes live in this tab and reset on reload</p>
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
      </main>
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
