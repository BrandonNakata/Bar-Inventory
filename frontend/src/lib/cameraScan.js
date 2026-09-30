/** Camera scan loop with no React, so it can be tested with fakes. */

import { normalizeBarcode } from './barcode.js'
import { createConfirmer } from './scanning.js'

export function startScanning({
  video,               // the <video> element to show the stream in
  mediaDevices,        // navigator.mediaDevices
  isSecureContext,     // window.isSecureContext
  loadDetector,        // async () => an object with detect(video) -> [{ rawValue }]
  onReady = () => {},  // camera + reader are up; frames are being read
  onDetected,          // (code) => void, called at most once
  onError,             // (err) => void; err.name says what kind
  intervalMs = 150,
  confirmations = 2,
}) {
  let stream = null
  let timer = null
  let stopped = false
  const confirm = createConfirmer(confirmations)

  function stopCamera() {
    stream?.getTracks().forEach((track) => track.stop())
    stream = null
  }

  function stop() {
    stopped = true
    clearTimeout(timer)
    stopCamera()
  }

  async function tick(detector) {
    if (stopped) return
    try {
      // readyState 2+ means a frame is actually available to read.
      if (video.readyState >= 2) {
        const results = await detector.detect(video)
        if (stopped) return
        for (const result of results) {
          let code
          try {
            // Drop misreads that fail the check digit.
            code = normalizeBarcode(result.rawValue)
          } catch {
            continue
          }
          const confirmed = confirm(code)
          if (confirmed) {
            stop()
            onDetected(confirmed)
            return
          }
        }
      }
    } catch {
      // One unreadable frame isn't worth giving up over.
    }
    timer = setTimeout(() => tick(detector), intervalMs)
  }

  async function start() {
    try {
      if (!isSecureContext) throw named('InsecureContext')
      if (!mediaDevices?.getUserMedia) throw named('NoCameraApi')

      // Prefer the rear camera, but accept any.
      stream = await mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } },
        audio: false,
      })

      // stop() may run while the permission prompt is open; release the stream.
      if (stopped) {
        stopCamera()
        return
      }

      video.srcObject = stream
      await video.play()

      const detector = await loadDetector()
      if (stopped) {
        stopCamera()
        return
      }

      onReady()
      tick(detector)
    } catch (err) {
      stopCamera()
      if (!stopped) onError(err)
    }
  }

  start()
  return stop
}

function named(name) {
  return Object.assign(new Error(name), { name })
}

/** Turn a camera error into something a person can act on. */
export function explainCameraError(err) {
  switch (err?.name) {
    case 'InsecureContext':
      return 'The camera only works over HTTPS. Open the https:// address instead: port 8443 on the Pi, or run `npm run dev:phone` in development.'
    case 'NoCameraApi':
      return "This browser doesn't give websites camera access."
    case 'NotAllowedError':
      return "Camera permission was denied. Allow it in the browser's site settings, then try again."
    case 'NotFoundError':
    case 'OverconstrainedError':
      return 'No camera found on this device.'
    case 'NotReadableError':
      return 'The camera is busy. Another app or tab is probably using it.'
    default:
      return `Couldn't start the barcode reader${err?.message ? `: ${err.message}` : '.'}`
  }
}
