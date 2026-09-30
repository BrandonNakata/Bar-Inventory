/** Camera barcode scanner; the scan loop lives in lib/cameraScan.js. */

import { useEffect, useRef, useState } from 'react'

import { explainCameraError, startScanning } from '../lib/cameraScan'

// UPC-E is left out: its check digit needs expansion to 12 digits first.
const FORMATS = ['ean_13', 'ean_8', 'upc_a']

async function loadDetector() {
  const { BarcodeDetector } = await import('barcode-detector/ponyfill')
  return new BarcodeDetector({ formats: FORMATS })
}

export default function CameraScanner({ onDetected, onClose }) {
  const videoRef = useRef(null)
  const [status, setStatus] = useState('starting') // starting | scanning | error
  const [error, setError] = useState(null)

  // Keep the latest onDetected in a ref so the effect runs once and the camera isn't restarted.
  const onDetectedRef = useRef(onDetected)
  useEffect(() => {
    onDetectedRef.current = onDetected
  })

  useEffect(() => {
    const stop = startScanning({
      video: videoRef.current,
      mediaDevices: navigator.mediaDevices,
      isSecureContext: window.isSecureContext,
      loadDetector,
      onReady: () => setStatus('scanning'),
      onDetected: (code) => {
        navigator.vibrate?.(60) // a buzz on Android; iOS ignores it
        onDetectedRef.current(code)
      },
      onError: (err) => {
        setError(explainCameraError(err))
        setStatus('error')
      },
    })
    // Stops the camera whenever the scanner unmounts.
    return stop
  }, [])

  return (
    <div className="camera">
      <div className="camera-frame">
        {/* playsInline keeps iPhones from going fullscreen; muted allows autoplay. */}
        <video ref={videoRef} playsInline muted autoPlay />
        {status === 'scanning' && <div className="camera-reticle" aria-hidden="true" />}
        {status === 'starting' && <p className="camera-status">Starting camera…</p>}
      </div>

      {status === 'scanning' && (
        <p className="muted camera-hint">
          Fit the barcode inside the box. It reads on its own.
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <button type="button" className="ghost" onClick={onClose}>
        Close camera
      </button>
    </div>
  )
}
