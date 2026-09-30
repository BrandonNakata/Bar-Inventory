/** Add by barcode: type or scan a code, look it up, confirm. */

import { useId, useState } from 'react'

import { api } from '../api'
import AddBottleForm from './AddBottleForm'
import CameraScanner from './CameraScanner'

const SOURCE_LABEL = {
  openfoodfacts: 'Open Food Facts',
  upcitemdb: 'UPCitemdb',
  manual: 'your own records',
}

export default function ScanPanel({ ingredients, onAdd }) {
  const [code, setCode] = useState('')
  const [looking, setLooking] = useState(false)
  const [result, setResult] = useState(null)
  const [addingAnother, setAddingAnother] = useState(false)
  const [error, setError] = useState(null)
  const [added, setAdded] = useState(null)
  const [cameraOpen, setCameraOpen] = useState(false)
  const id = useId()

  // Camera access needs a secure context (HTTPS or localhost).
  const cameraPossible =
    typeof window !== 'undefined' &&
    window.isSecureContext &&
    Boolean(navigator.mediaDevices?.getUserMedia)

  // One lookup, two ways in: the form's button, and the camera.
  async function runLookup(value) {
    setLooking(true)
    setError(null)
    setResult(null)
    setAdded(null)
    setAddingAnother(false)
    try {
      setResult(await api.lookupBarcode(value))
    } catch (err) {
      setError(err.message)
    } finally {
      setLooking(false)
    }
  }

  function lookUp(event) {
    event.preventDefault()
    runLookup(code)
  }

  function handleScanned(scanned) {
    setCameraOpen(false)
    setCode(scanned)
    runLookup(scanned)
  }

  function reset() {
    setResult(null)
    setCode('')
    setError(null)
    setAddingAnother(false)
  }

  // The barcode travels with the bottle so the server remembers the confirmed category.
  async function addWithBarcode(draft) {
    const created = await onAdd({ ...draft, barcode: result.barcode })
    setAdded(created.product_name)
    reset()
  }

  async function addAnother() {
    const existing = result.on_shelf[0]
    setAddingAnother(true)
    try {
      await addWithBarcode({
        product_name: existing.product_name,
        ingredient_id: existing.ingredient_id,
      })
    } catch (err) {
      setError(err.message)
      setAddingAnother(false)
    }
  }

  return (
    <section className="scan-panel">
      <h2>Add by barcode</h2>

      <form className="scan-form" onSubmit={lookUp}>
        <label htmlFor={`${id}-code`} className="sr-only">
          Barcode
        </label>
        {/* type="text" keeps leading zeros; inputMode brings up the number pad. */}
        <input
          id={`${id}-code`}
          type="text"
          inputMode="numeric"
          autoComplete="off"
          placeholder="Barcode digits, e.g. 0 36000 29145 2"
          value={code}
          onChange={(event) => setCode(event.target.value)}
        />
        <button type="submit" disabled={looking || !code.trim()}>
          {looking ? 'Looking up…' : 'Look up'}
        </button>
      </form>

      {!cameraOpen && (
        <div className="camera-launch">
          <button
            type="button"
            className="ghost"
            onClick={() => {
              setError(null)
              setResult(null)
              setAdded(null)
              setCameraOpen(true)
            }}
            disabled={!cameraPossible || looking}
          >
            Scan with camera
          </button>
          {!cameraPossible && (
            <span className="muted camera-note">
              Camera needs HTTPS. On your phone, use <code>npm run dev:phone</code>.
            </span>
          )}
        </div>
      )}

      {/* Unmounting the scanner stops the camera. */}
      {cameraOpen && (
        <CameraScanner onDetected={handleScanned} onClose={() => setCameraOpen(false)} />
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {added && !result && (
        <p className="scan-added" role="status">
          ✓ Added <strong>{added}</strong>. Next one?
        </p>
      )}

      {result && result.on_shelf.length > 0 && (
        <div className="scan-result">
          <p>
            <strong>Already on your shelf:</strong> {result.on_shelf[0].product_name}
            {result.on_shelf.length > 1 && ` (×${result.on_shelf.length})`}
          </p>
          <div className="form-actions">
            <button type="button" onClick={addAnother} disabled={addingAnother}>
              {addingAnother ? 'Adding…' : 'Add another bottle'}
            </button>
            <button type="button" className="ghost" onClick={reset}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {result && result.on_shelf.length === 0 && (
        <div className="scan-result">
          <p className="scan-headline">{headline(result)}</p>
          {/* key resets the form for each new barcode. */}
          <AddBottleForm
            key={result.barcode}
            ingredients={ingredients}
            initialName={result.product_name ?? ''}
            initialIngredientId={result.ingredient_id ?? result.suggested_ingredient_id ?? ''}
            submitLabel="Add to shelf"
            onAdd={addWithBarcode}
            onCancel={reset}
          />
        </div>
      )}
    </section>
  )
}

/** One sentence explaining where the pre-filled answer came from. */
function headline(result) {
  if (result.ingredient_id) {
    return "Seen this one before, so everything's filled in."
  }
  if (result.found) {
    const guess = result.suggested_ingredient_name
      ? ` Category guessed as ${result.suggested_ingredient_name}.`
      : ' Pick a category.'
    return `Found in ${SOURCE_LABEL[result.source] ?? result.source}.${guess} Check it and add.`
  }
  if (result.lookup_error) {
    return `${result.lookup_error} Type the name and it'll be remembered for this barcode.`
  }
  return "No database knows this one. Type the name once and it'll be remembered."
}
