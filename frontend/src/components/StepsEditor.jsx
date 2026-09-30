/** Edits recipe step templates, with placeholders drawn as chips. */

import { useRef, useState } from 'react'

import { segments } from '../lib/steps'

export default function StepsEditor({ steps, lines, onChange }) {
  const [editing, setEditing] = useState(null) // index being edited, or null
  const inputRef = useRef(null)

  function update(index, text) {
    onChange(steps.map((step, i) => (i === index ? text : step)))
  }

  function move(index, by) {
    const target = index + by
    if (target < 0 || target >= steps.length) return
    const next = [...steps]
    ;[next[index], next[target]] = [next[target], next[index]]
    onChange(next)
    if (editing === index) setEditing(target)
  }

  function remove(index) {
    onChange(steps.filter((_, i) => i !== index))
    setEditing(null)
  }

  function add() {
    onChange([...steps, ''])
    setEditing(steps.length)
  }

  // Insert the placeholder at the cursor.
  function insert(index, token) {
    const el = inputRef.current
    const text = steps[index]
    const at = el ? el.selectionStart : text.length
    const end = el ? el.selectionEnd : text.length
    const next = text.slice(0, at) + token + text.slice(end)
    update(index, next)
    // After React redraws, put the cursor just past what was inserted.
    requestAnimationFrame(() => {
      if (!inputRef.current) return
      inputRef.current.focus()
      inputRef.current.selectionStart = inputRef.current.selectionEnd = at + token.length
    })
  }

  return (
    <div className="steps-editor">
      <ol className="steps">
        {steps.map((step, index) => (
          <li key={index} className={editing === index ? 'step-editing' : ''}>
            {editing === index ? (
              <>
                <textarea
                  ref={inputRef}
                  value={step}
                  rows={2}
                  aria-label={`Step ${index + 1}`}
                  onChange={(event) => update(index, event.target.value.replace(/\n/g, ' '))}
                />
                <div className="chips insert-chips" aria-label="Insert an ingredient">
                  {lines.map((line) => (
                    <button
                      key={line.ingredient_id}
                      type="button"
                      className="chip"
                      onClick={() => insert(index, `{${line.ingredient_id}}`)}
                    >
                      + {line.ingredient_name}
                    </button>
                  ))}
                </div>
                <p className="step-preview">
                  <StepPreview step={step} lines={lines} />
                </p>
              </>
            ) : (
              <button type="button" className="step-view" onClick={() => setEditing(index)}>
                {step ? <StepPreview step={step} lines={lines} /> : <em className="muted">Empty step</em>}
              </button>
            )}
            <span className="step-tools">
              <button type="button" className="ghost" onClick={() => move(index, -1)} disabled={index === 0} aria-label="Move up">↑</button>
              <button type="button" className="ghost" onClick={() => move(index, 1)} disabled={index === steps.length - 1} aria-label="Move down">↓</button>
              {editing === index ? (
                <button type="button" className="ghost" onClick={() => setEditing(null)}>Done</button>
              ) : (
                <button type="button" className="ghost" onClick={() => setEditing(index)}>Edit</button>
              )}
              <button type="button" className="ghost danger" onClick={() => remove(index)} aria-label="Delete step">✕</button>
            </span>
          </li>
        ))}
      </ol>
      <button type="button" className="ghost" onClick={add}>
        + Add step
      </button>
      <p className="hint">
        Ingredient buttons insert the amount and name, so if you change an
        amount above, every step that uses it updates.
      </p>
    </div>
  )
}

function StepPreview({ step, lines }) {
  return segments(step, lines).map((part, i) =>
    part.id ? (
      <span key={i} className={`token ${part.known ? '' : 'token-missing'}`}>
        {part.text}
      </span>
    ) : (
      <span key={i}>{part.text}</span>
    ),
  )
}
