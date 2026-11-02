// Scene event bus (U5).
//
// Workspaces say what they are doing; the scene reacts. The mapping is pure so
// the reaction is testable without a renderer, and an unknown event is ignored
// rather than guessed at.

export const SCENE_EVENTS = ['idle', 'working', 'done', 'error']

const MODES = {
  idle: 'calm',
  working: 'intense',
  done: 'flare',
  error: 'subdued',
}

export function modeForEvent(event) {
  return MODES[event] || 'calm'
}

export function createSceneBus() {
  const listeners = new Set()
  let last = 'idle'
  return {
    emit(event) {
      if (!SCENE_EVENTS.includes(event)) return false
      last = event
      for (const listener of [...listeners]) {
        try {
          listener(event, MODES[event])
        } catch { /* a scene listener must never break the workspace that emitted */ }
      }
      return true
    },
    subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    get last() { return last },
    get size() { return listeners.size },
  }
}

/** The app-wide bus. One scene listens; workspaces emit. */
export const sceneBus = createSceneBus()
