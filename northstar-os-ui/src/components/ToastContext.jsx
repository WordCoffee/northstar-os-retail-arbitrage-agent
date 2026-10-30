/**
 * Compat shim (work order UI-20, item 19).
 *
 * The old provider pattern is superseded by the module bus, because nothing in
 * the app ever mounted TOAST_PROVIDER and a notification system that only works
 * inside one tree is not a notification system. Both names are kept so any
 * existing import keeps compiling; new code should call `toast` directly.
 */
import { useSyncExternalStore } from 'react'
import { toast as busToast, dismiss, subscribe, getToasts } from '../lib/toastBus.js'

export const toast = busToast

export function useToast() {
  const toasts = useSyncExternalStore(subscribe, getToasts, getToasts)
  return { toasts, toast: busToast, dismiss }
}

/** Retained for imports; it no longer needs to wrap anything. */
export function TOAST_PROVIDER({ children }) {
  return children
}

export default { useToast, toast, TOAST_PROVIDER }
