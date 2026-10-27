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

export function feedbackSuccess() {
  tone(1320, 0.08)
  vibrate(40)
}

export function feedbackError() {
  tone(220, 0.15)
  tone(180, 0.2, 0.18)
  vibrate([90, 60, 90])
}
