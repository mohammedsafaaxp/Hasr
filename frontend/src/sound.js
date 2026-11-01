let ctx = null

function tone(freq, duration, delay = 0) {
  try {
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.frequency.value = freq
    osc.type = 'square'
    gain.gain.value = 0.05
    osc.connect(gain)
    gain.connect(ctx.destination)
    const start = ctx.currentTime + delay
    osc.start(start)
    osc.stop(start + duration)
  } catch (e) {
    /* no audio on this device */
  }
}

function vibrate(pattern) {
  if (navigator.vibrate) navigator.vibrate(pattern)
}

// Three sounds a worker can tell apart without looking:
// success = one short high beep, warning = two mid beeps, error = one long low buzz.
export function feedbackSuccess() {
  tone(1320, 0.07)
  vibrate(40)
}

export function feedbackWarning() {
  tone(660, 0.1)
  tone(660, 0.1, 0.16)
  vibrate([60, 80, 60])
}

export function feedbackError() {
  tone(180, 0.45)
  vibrate([250, 100, 250])
}
