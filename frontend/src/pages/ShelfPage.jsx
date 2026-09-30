/** The Shelf: owns the bottle list and the functions that change it. */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api'
import AddBottleForm from '../components/AddBottleForm'
import BottleList from '../components/BottleList'
import ScanPanel from '../components/ScanPanel'

export default function ShelfPage() {
  const [ingredients, setIngredients] = useState([])
  const [bottles, setBottles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Fetch once after the first render.
  useEffect(() => {
    // Ignore responses that land after unmount.
    let cancelled = false

    async function load() {
      try {
        // Run both requests at once.
        const [ingredientRows, bottleRows] = await Promise.all([
          api.listIngredients(),
          api.listBottles(),
        ])
        if (cancelled) return
        setIngredients(ingredientRows)
        setBottles(bottleRows)
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  async function handleAdd(draft) {
    // Store the server's bottle, which has the id and timestamp.
    const created = await api.addBottle(draft)
    setBottles((current) => [created, ...current])
    setError(null)
    // Returned so a caller can say what was added ("✓ Added Campari").
    return created
  }

  async function handleDelete(id) {
    try {
      await api.deleteBottle(id)
      setBottles((current) => current.filter((bottle) => bottle.id !== id))
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1>The Shelf</h1>
          <p className="count">
            {loading ? 'Loading…' : `${bottles.length} bottles`}
          </p>
        </div>
        {!loading && bottles.length > 0 && (
          <Link to="/recipes" className="header-link">
            What can I make? →
          </Link>
        )}
      </header>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <ScanPanel ingredients={ingredients} onAdd={handleAdd} />

      <details className="manual-add">
        <summary>No barcode? Add by hand</summary>
        <AddBottleForm ingredients={ingredients} onAdd={handleAdd} />
      </details>

      <BottleList bottles={bottles} loading={loading} onDelete={handleDelete} />
    </>
  )
}
