/** Tests the camera loop with a fake camera and reader. Run: npm run check:camera */

import { explainCameraError, startScanning } from '../src/lib/cameraScan.js'

let failures = 0
function check(label, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want)
  if (!ok) failures += 1
  console.log(
    ok
      ? `  ok    ${label}`
      : `  FAIL  ${label}\n          got:  ${JSON.stringify(got)}\n          want: ${JSON.stringify(want)}`,
  )
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function deferred() {
  let resolve, reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

/** A camera whose permission prompt resolves when the test says so. */
function fakeCamera() {
  const track = { stopped: false, stop() { this.stopped = true } }
  const stream = { getTracks: () => [track] }
  const permission = deferred()
  const mediaDevices = {
    calls: 0,
    getUserMedia() {
      this.calls += 1
      return permission.promise
    },
  }
  return { track, stream, permission, mediaDevices, grant: () => permission.resolve(stream) }
}

function fakeVideo({ ready = true, playFails = false } = {}) {
  return {
    readyState: ready ? 4 : 0,
    srcObject: null,
    async play() {
      if (playFails) throw Object.assign(new Error('play blocked'), { name: 'NotAllowedError' })
    },
  }
}

/** A reader that returns the scripted frames in order, then nothing. */
function fakeReader(frames) {
  const reader = {
    calls: 0,
    async detect() {
      reader.calls += 1
      const frame = frames.shift()
      if (frame instanceof Error) throw frame
      return (frame ?? []).map((rawValue) => ({ rawValue }))
    },
  }
  return reader
}

function run(overrides) {
  const events = { ready: 0, detected: [], errors: [] }
  const stop = startScanning({
    isSecureContext: true,
    intervalMs: 1,
    onReady: () => (events.ready += 1),
    onDetected: (code) => events.detected.push(code),
    onError: (err) => events.errors.push(err.name),
    ...overrides,
  })
  return { stop, events }
}

console.log('\nthe happy path')
{
  const cam = fakeCamera()
  const reader = fakeReader([['036000291452'], ['036000291452']])
  const { events } = run({ video: fakeVideo(), mediaDevices: cam.mediaDevices, loadDetector: async () => reader })
  cam.grant()
  await sleep(40)
  check('a code seen twice is reported, normalised', events.detected, ['0036000291452'])
  check('...exactly once', events.detected.length, 1)
  check('the reader was declared ready', events.ready, 1)
  check('camera is OFF after a detection', cam.track.stopped, true)
  const callsAtDetection = reader.calls
  await sleep(20)
  check('...and no more frames are read after it', reader.calls, callsAtDetection)
}

console.log('\nclosing while the permission prompt is still up')
{
  const cam = fakeCamera()
  const video = fakeVideo()
  // A reader that never loads: the camera must stop the moment the late stream arrives.
  const neverLoads = () => new Promise(() => {})
  const { stop, events } = run({ video, mediaDevices: cam.mediaDevices, loadDetector: neverLoads })
  stop()              // user closes the scanner...
  cam.grant()         // ...then taps "Allow" on a prompt that was still open
  await sleep(20)
  check('the late stream is stopped immediately -- camera OFF', cam.track.stopped, true)
  check('...without ever being attached to the video', video.srcObject, null)
  check('nothing is reported as ready', events.ready, 0)
  check('no error is shown for a scanner that is already gone', events.errors, [])
}

console.log('\nclosing while the reader is still loading')
{
  const cam = fakeCamera()
  const loading = deferred()
  const { stop, events } = run({ video: fakeVideo(), mediaDevices: cam.mediaDevices, loadDetector: () => loading.promise })
  cam.grant()
  await sleep(10)
  stop()
  loading.resolve(fakeReader([['036000291452'], ['036000291452']]))
  await sleep(20)
  check('camera OFF', cam.track.stopped, true)
  check('never declared ready', events.ready, 0)
  check('never detects anything', events.detected, [])
}

console.log('\nclosing mid-scan')
{
  const cam = fakeCamera()
  const reader = fakeReader([])        // frames with nothing in them, forever
  const { stop, events } = run({ video: fakeVideo(), mediaDevices: cam.mediaDevices, loadDetector: async () => reader })
  cam.grant()
  await sleep(30)
  check('it was reading frames', reader.calls > 3, true)
  stop()
  const callsAtStop = reader.calls
  await sleep(30)
  check('camera OFF', cam.track.stopped, true)
  check('the loop really stopped -- no frames read after stop()', reader.calls <= callsAtStop + 1, true)
  check('nothing detected', events.detected, [])
}

console.log('\nerrors, each turned into words')
{
  const cam = fakeCamera()
  const { events } = run({ video: fakeVideo(), mediaDevices: cam.mediaDevices, loadDetector: async () => fakeReader([]) })
  cam.permission.reject(Object.assign(new Error('denied'), { name: 'NotAllowedError' }))
  await sleep(10)
  check('permission denied is reported', events.errors, ['NotAllowedError'])
  check('...as advice, not a stack trace', explainCameraError({ name: 'NotAllowedError' }).startsWith('Camera permission was denied'), true)
}
{
  const cam = fakeCamera()
  const { events } = run({ isSecureContext: false, video: fakeVideo(), mediaDevices: cam.mediaDevices, loadDetector: async () => fakeReader([]) })
  await sleep(10)
  check('plain HTTP is refused before asking for the camera', [events.errors, cam.mediaDevices.calls], [['InsecureContext'], 0])
  check('...and the message says what to run', explainCameraError({ name: 'InsecureContext' }).includes('npm run dev:phone'), true)
}
{
  const { events } = run({ video: fakeVideo(), mediaDevices: undefined, loadDetector: async () => fakeReader([]) })
  await sleep(10)
  check('a browser with no camera API says so', events.errors, ['NoCameraApi'])
}
{
  const cam = fakeCamera()
  const { events } = run({ video: fakeVideo({ playFails: true }), mediaDevices: cam.mediaDevices, loadDetector: async () => fakeReader([]) })
  cam.grant()
  await sleep(10)
  check('if the video will not play: error reported AND camera OFF', [events.errors, cam.track.stopped], [['NotAllowedError'], true])
}
{
  const cam = fakeCamera()
  const { events } = run({ video: fakeVideo(), mediaDevices: cam.mediaDevices, loadDetector: async () => { throw new Error('WASM download failed') } })
  cam.grant()
  await sleep(10)
  check('if the reader fails to load: camera OFF', cam.track.stopped, true)
  check('...with the reason passed along', explainCameraError(new Error('WASM download failed')), "Couldn't start the barcode reader: WASM download failed")
}

console.log('\nwhat counts as a read')
{
  const cam = fakeCamera()
  const reader = fakeReader([
    new Error('bad frame'),   // the reader chokes on one frame
    ['036000291453'],         // a misread: wrong check digit
    ['036000291453'],         // ...twice
    ['4006381333931'],
    [],                       // a frame with nothing in it
    ['4006381333931'],
  ])
  const { events } = run({ video: fakeVideo(), mediaDevices: cam.mediaDevices, loadDetector: async () => reader })
  cam.grant()
  await sleep(40)
  check('a frame that throws does not stop scanning', reader.calls >= 6, true)
  check('a repeated misread is never accepted; the real code is', events.detected, ['4006381333931'])
}
{
  const cam = fakeCamera()
  const reader = fakeReader([['4006381333931'], ['4006381333931']])
  const video = fakeVideo({ ready: false })
  const { stop } = run({ video, mediaDevices: cam.mediaDevices, loadDetector: async () => reader })
  cam.grant()
  await sleep(20)
  check('no frames are read before the video has one to give', reader.calls, 0)
  stop()
}

console.log()
if (failures) {
  console.log(`${failures} check(s) failed`)
  process.exit(1)
}
console.log('all good -- every way out turns the camera off')
