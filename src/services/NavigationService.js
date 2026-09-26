// src/services/NavigationService.js
class NavigationService {
  constructor() {
    this.routes = {
      'hub': 'Operations Hub',
      'sourcescout': 'Prospector',
      'goldengoose': 'Golden Goose',
      'listingforge': 'OfferChisel',
      'socialpulse': 'The Town Crier',
      'adpilot': 'The Auctioneer',
      'autothink': 'AutothinK',
      'thewatch': 'The Watch',
      'rankledger': 'RankLedger',
      'rivalboard': 'The Rival Board',
      'account': 'Account',
      'ledger': 'The Ledger'
    };
    
    this.currentRoute = 'hub';
    this.routeHistory = [];
    this.listeners = [];
  }
  
  /**
   * Navigate to a specific route
   * @param {string} route - The route to navigate to
   * @param {Object} [options] - Navigation options
   * @param {boolean} [options.replace] - Replace current history instead of pushing
   * @param {boolean} [optionssilent] - Don't trigger navigation events
   */
  navigateTo(route, options = {}) {
    if (!this.routes[route]) {
      console.error(`Route ${route} not found`);
      this.notifyListeners('error', { route, message: `Route ${route} not found` });
      return false;
    }
    
    const { replace = false, silent = false } = options;
    
    this.currentRoute = route;
    this.routeHistory.push(route);
    
    // Update URL
    if (replace) {
      window.history.replaceState({}, '', `#/northstar-os/${route}`);
    } else {
      window.history.pushState({}, '', `#/northstar-os/${route}`);
    }
    
    // Load content
    this.loadContent(route);
    
    // Update active navigation
    this.updateActiveNavigation(route);
    
    // Notify listeners
    if (!silent) {
      this.notifyListeners('navigate', { route, routeName: this.routes[route] });
    }
    
    return true;
  }
  
  /**
   * Navigate back in history
   */
  navigateBack() {
    if (this.routeHistory.length > 1) {
      this.routeHistory.pop(); // Remove current route
      const previousRoute = this.routeHistory[this.routeHistory.length - 1];
      this.navigateTo(previousRoute, { replace: true });
      return true;
    }
    return false;
  }
  
  /**
   * Get current route
   * @returns {string}
   */
  getCurrentRoute() {
    return this.currentRoute;
  }
  
  /**
   * Get route name
   * @param {string} route - The route identifier
   * @returns {string}
   */
  getRouteName(route) {
    return this.routes[route] || route;
  }
  
  /**
   * Load content for a specific route
   * @param {string} route - The route to load content for
   */
  loadContent(route) {
    // This would typically load the actual content
    // For now, we'll just log the action
    console.log(`Loading content for route: ${route}`);
    
    // Dispatch custom event for content loading
    const event = new CustomEvent('routeContentLoad', {
      detail: { route }
    });
    document.dispatchEvent(event);
  }
  
  /**
   * Update active navigation state
   * @param {string} route - The active route
   */
  updateActiveNavigation(route) {
    // Remove active class from all nav items
    document.querySelectorAll('.nav-item').forEach(item => {
      item.classList.remove('active');
    });
    
    // Add active class to current route
    const activeItem = document.querySelector(`.nav-item[data-route="${route}"]`);
    if (activeItem) {
      activeItem.classList.add('active');
    }
  }
  
  /**
   * Register a navigation listener
   * @param {Function} callback - The callback function
   * @param {string} [eventType] - The event type to listen for
   */
  addListener(callback, eventType = 'navigate') {
    if (!this.listeners[eventType]) {
      this.listeners[eventType] = [];
    }
    this.listeners[eventType].push(callback);
  }
  
  /**
   * Remove a navigation listener
   * @param {Function} callback - The callback function to remove
   * @param {string} [eventType] - The event type
   */
  removeListener(callback, eventType = 'navigate') {
    if (this.listeners[eventType]) {
      this.listeners[eventType] = this.listeners[eventType].filter(listener => listener !== callback);
    }
  }
  
  /**
   * Notify all listeners of an event
   * @param {string} eventType - The event type
   * @param {Object} data - The event data
   */
  notifyListeners(eventType, data) {
    if (this.listeners[eventType]) {
      this.listeners[eventType].forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error('Error in navigation listener:', error);
        }
      });
    }
  }
  
  /**
   * Handle popstate events (browser back/forward)
   */
  handlePopState() {
    const route = this.getCurrentRouteFromUrl();
    if (route && route !== this.currentRoute) {
      this.navigateTo(route, { silent: true });
    }
  }
  
  /**
   * Get current route from URL
   * @returns {string}
   */
  getCurrentRouteFromUrl() {
    const hash = window.location.hash;
    if (hash) {
      const match = hash.match(/#\/northstar-os\/(.+)/);
      return match ? match[1] : 'hub';
    }
    return 'hub';
  }
  
  /**
   * Initialize navigation service
   */
  init() {
    // Handle initial route
    const initialRoute = this.getCurrentRouteFromUrl();
    this.navigateTo(initialRoute, { silent: true });
    
    // Handle popstate events
    window.addEventListener('popstate', () => this.handlePopState());
    
    // Handle hash changes
    window.addEventListener('hashchange', () => this.handlePopState());
  }
}

// Export singleton instance
export const navigationService = new NavigationService();

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  navigationService.init();
});