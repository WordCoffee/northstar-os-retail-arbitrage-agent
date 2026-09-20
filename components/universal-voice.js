/**
 * Universal Voice Integration - Auto-attaches to all text inputs and textareas
 * 
 * Works with Northstar OS dynamic views - hooks into NS.mount/NS.onMount
 * to attach voice buttons when views become visible.
 *
 * Usage:
 *   <script type="module" src="/components/universal-voice.js"></script>
 *
 * Or with options:
 *   <script type="module">
 *     import { initUniversalVoice } from '/components/universal-voice.js';
 *     initUniversalVoice({ serverUrl: 'https://voice.your-domain.com' });
 *   </script>
 */

import { attachVoiceToChats } from './chat-voice.js';

// Default selectors for text inputs that should get voice
const TEXT_INPUT_SELECTORS = [
  'input[type="text"]',
  'input[type="search"]',
  'input[type="email"]',
  'input[type="url"]',
  'input[type="tel"]',
  'textarea',
  '[contenteditable="true"]',
  '.chat-input',
  '.message-input',
  '.search-input',
  '[data-voice-input]'
];

// Inputs to exclude (passwords, hidden, etc.)
const EXCLUDE_SELECTORS = [
  'input[type="password"]',
  'input[type="hidden"]',
  'input[type="checkbox"]',
  'input[type="radio"]',
  'input[type="range"]',
  'input[type="color"]',
  'input[type="file"]',
  'input[type="submit"]',
  'input[type="button"]',
  'input[type="reset"]',
  'input[type="number"]',
  'input[type="date"]',
  'input[type="time"]',
  'input[type="datetime-local"]',
  'input[type="month"]',
  'input[type="week"]',
  // Note: [readonly] removed - text inputs with readonly can still get voice
  // Use .no-voice class to explicitly opt out
  '[disabled]',
  '.no-voice',
  '[data-no-voice]'
];

let mutationObserver = null;
let mountedViews = new Set();
let pendingOptions = null;

/**
 * Find and attach voice to inputs in a specific root element
 */
function attachVoiceToInputsInRoot(root, options) {
  const {
    serverUrl = null,
    excludeSelectors = [],
    includeSelectors = [],
    onTranscribed = null,
    onError = null
  } = options;

  // D4-F5: never default to a localhost voice server. When no server URL is
  // configured, do not attach voice (feature stays disabled, honest no-op).
  if (!serverUrl) return;

  const allExclude = [...EXCLUDE_SELECTORS, ...excludeSelectors];
  const allInclude = [...TEXT_INPUT_SELECTORS, ...includeSelectors];

  // Find all matching inputs within root
  const inputs = root.querySelectorAll(allInclude.join(', '));
  
  const validInputs = Array.from(inputs).filter(input => {
    return !allExclude.some(sel => input.matches(sel));
  });

  if (validInputs.length === 0) return [];

  const widgets = [];
  validInputs.forEach(input => {
    if (input.dataset.voiceAttached === 'true') return;
    
    let container = input.closest('.voice-input-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'voice-input-container';
      container.style.display = 'inline-flex';
      container.style.alignItems = 'center';
      container.style.gap = '8px';
      container.style.width = '100%';
      
      input.parentNode.insertBefore(container, input);
      container.appendChild(input);
    }

    try {
      const widget = attachVoiceToChats(container, {
        serverUrl,
        onTranscribed: (text) => {
          const event = new Event('input', { bubbles: true });
          input.dispatchEvent(event);
          if (onTranscribed) onTranscribed(text, input);
        },
        onError: (err) => {
          if (onError) onError(err, input);
        }
      });
      
      if (widget && widget.length > 0) {
        widgets.push(...widget);
        input.dataset.voiceAttached = 'true';
      }
    } catch (e) {
      console.warn('[UniversalVoice] Failed to attach to input:', e);
    }
  });

  return widgets;
}

/**
 * Initialize universal voice on a specific view
 */
function initView(viewElement, options) {
  if (!viewElement) return [];
  
  const viewId = viewElement.id;
  if (mountedViews.has(viewId)) return [];
  mountedViews.add(viewId);
  
  console.log(`[UniversalVoice] Initializing voice for view: ${viewId}`);
  return attachVoiceToInputsInRoot(viewElement, options);
}

/**
 * Initialize universal voice on all currently visible views
 */
function initAllVisibleViews(options) {
  const views = document.querySelectorAll('.view[aria-hidden="false"], .view.active');
  let allWidgets = [];
  views.forEach(view => {
    allWidgets.push(...initView(view, options));
  });
  return allWidgets;
}

/**
 * Main initialization function
 */
export function initUniversalVoice(options = {}) {
  pendingOptions = options;
  
  // Initial scan for visible views
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      setTimeout(() => initAllVisibleViews(options), 100);
      setupObservers(options);
    });
  } else {
    setTimeout(() => initAllVisibleViews(options), 100);
    setupObservers(options);
  }
}

/**
 * Set up observers for dynamic content
 */
function setupObservers(options) {
  // 1. Hook into Northstar OS view system
  if (window.NS && window.NS.onMount) {
    const originalOnMount = window.NS.onMount;
    window.NS.onMount = function(route) {
      if (originalOnMount) originalOnMount(route);
      
      // Initialize voice for the newly mounted view
      setTimeout(() => {
        const viewEl = document.getElementById('view-' + route);
        if (viewEl) initView(viewEl, options);
      }, 50);
    };
  }

  // 2. Listen for hash changes (fallback)
  window.addEventListener('hashchange', () => {
    setTimeout(() => initAllVisibleViews(options), 100);
  });

  // 3. MutationObserver for dynamically added inputs
  if (!mutationObserver) {
    mutationObserver = new MutationObserver((mutations) => {
      let shouldCheck = false;
      for (const mutation of mutations) {
        if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
          shouldCheck = true;
          break;
        }
      }
      if (shouldCheck) {
        setTimeout(() => initAllVisibleViews(options), 50);
      }
    });
    
    mutationObserver.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  // 4. Handle the global search input specifically (always visible)
  const globalSearch = document.getElementById('global-search');
  if (globalSearch && !globalSearch.dataset.voiceAttached) {
    attachVoiceToInputsInRoot(globalSearch.parentElement, options);
  }
}

// Export for manual use
export { TEXT_INPUT_SELECTORS, EXCLUDE_SELECTORS, initView, initAllVisibleViews };