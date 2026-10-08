/**
 * The shelf as a shadow board: bottles sit in family rows, and anything missing
 * waits in the navy "Not on the shelf" row underneath, ranked by drinks it unlocks.
 */

import Icon from './Icon'

export default function ShelfBoard({
  rows,
  missing,
  loading,
  query,
  totalBottles,
  showMissing,
  onToggleMissing,
  onFinish,
  onRestock,
  busyId,
  landedId,
}) {
  return (
    <section className="board" aria-label="Shelf">
      {loading ? (
        <p className="board-note">Reading the shelf…</p>
      ) : rows.length === 0 ? (
        <p className="board-note board-empty">
          {totalBottles === 0
            ? 'Nothing on the shelf yet. Scan a bottle and it gets a home here.'
            : `No bottles on the shelf match “${query}”.`}
        </p>
      ) : (
        rows.map((row) => (
          <div className="board-row" key={row.key}>
            <h2 className="board-label">{row.label}</h2>
            <ul className="slots">
              {row.bottles.map((bottle) => (
                <li key={bottle.id}>
                  <button
                    type="button"
                    className={`slot${landedId === bottle.id ? ' slot-landed' : ''}`}
                    onClick={() => onFinish(bottle)}
                    disabled={busyId === bottle.id}
                    aria-label={`${bottle.product_name}, ${bottle.ingredient_name}. Mark finished`}
                  >
                    <Icon name="bottle" className="icon slot-icon" />
                    <span className="slot-text">
                      <b>{bottle.product_name}</b>
                      <span>{bottle.ingredient_name}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))
      )}

      {!loading && (
        <div className="missing" id="missing-row" tabIndex={-1}>
          <div className="missing-head">
            <h2>
              Not on the shelf <b>{missing.length}</b>
            </h2>
            <button
              type="button"
              role="switch"
              aria-checked={showMissing}
              className="switch"
              onClick={onToggleMissing}
            >
              <span className="switch-track" aria-hidden="true" />
              Show empty homes
            </button>
          </div>

          {showMissing &&
            (missing.length === 0 ? (
              <p className="board-note">
                Nothing missing. No drink is waiting on a single bottle right now.
              </p>
            ) : (
              <ul className="slots slots-missing">
                {missing.map((item) => (
                  <li key={item.key}>
                    <button
                      type="button"
                      className="slot slot-out"
                      onClick={() => onRestock(item)}
                      disabled={busyId === item.key}
                      aria-label={`${item.name}, not on the shelf. ${item.action}`}
                    >
                      <span className="slot-text">
                        <b>{item.name}</b>
                        <span>{item.detail}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ))}

          <p className="board-note">
            Tap a bottle when it's finished and it drops down here. Tap an empty home when you
            buy it and it goes back to its shelf.
          </p>
        </div>
      )}
    </section>
  )
}
