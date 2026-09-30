/** Renders the shelf. */

export default function BottleList({ bottles, loading, onDelete }) {
  if (loading) {
    return <p className="muted">Reading the shelf…</p>
  }

  if (bottles.length === 0) {
    return (
      <p className="muted">
        Nothing here yet. Add a bottle above and it'll show up.
      </p>
    )
  }

  return (
    <ul className="bottle-list">
      {bottles.map((bottle) => (
        <li key={bottle.id} className="bottle">
          <div className="bottle-main">
            <span className="bottle-name">{bottle.product_name}</span>
            <span className="bottle-category">{bottle.ingredient_name}</span>
          </div>
          <button
            type="button"
            className="ghost"
            onClick={() => onDelete(bottle.id)}
            aria-label={`Remove ${bottle.product_name}`}
          >
            Remove
          </button>
        </li>
      ))}
    </ul>
  )
}
