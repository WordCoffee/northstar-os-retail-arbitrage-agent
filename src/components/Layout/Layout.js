// src/components/Layout/Layout.js
class Layout {
  constructor() {
    this.currentRoute = 'hub';
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
    
    this.init();
  }
  
  init() {
    this.setupEventListeners();
    this.loadInitialContent();
    this.setupThemeToggle();
    this.setupNavigation();
    this.setupActionDock();
    this.setupPaperclipAssistant();
  }
  
  setupEventListeners() {
    // Global search
    const globalSearch = document.getElementById('globalSearch');
    if (globalSearch) {
      globalSearch.addEventListener('input', (e) => this.handleGlobalSearch(e));
      globalSearch.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          this.handleGlobalSearchSubmit(e.target.value);
        }
      });
    }
    
    // AI controls
    const aiEngine = document.getElementById('aiEngine');
    const aiTier = document.getElementById('aiTier');
    if (aiEngine) aiEngine.addEventListener('change', (e) => this.handleAIEngineChange(e));
    if (aiTier) aiTier.addEventListener('change', (e) => this.handleAITierChange(e));
    
    // Account button
    const accountBtn = document.getElementById('accountBtn');
    if (accountBtn) accountBtn.addEventListener('click', () => this.handleAccountClick());
  }
  
  setupNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const navGroupHeaders = document.querySelectorAll('.nav-group-header');
    
    // Setup nav group headers (dropdowns)
    navGroupHeaders.forEach(header => {
      header.addEventListener('click', () => {
        const group = header.dataset.group;
        const items = header.nextElementSibling;
        
        // Toggle dropdown
        items.style.display = items.style.display === 'none' ? 'block' : 'none';
        
        // Update header state
        header.classList.toggle('expanded');
      });
    });
    
    // Setup nav items (navigation)
    navItems.forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const route = item.dataset.route;
        this.navigateTo(route);
      });
    });
  }
  
  setupActionDock() {
    const dockItems = document.querySelectorAll('.dock-item');
    dockItems.forEach(item => {
      item.addEventListener('click', (e) => {
        const action = item.dataset.action;
        this.handleActionDockClick(action);
      });
    });
  }
  
  setupThemeToggle() {
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', () => this.toggleTheme());
    }
  }
  
  setupPaperclipAssistant() {
    const paperclipAssistant = document.getElementById('paperclipAssistant');
    if (paperclipAssistant) {
      // Show/hide assistant on click
      paperclipAssistant.addEventListener('click', () => {
        const content = paperclipAssistant.querySelector('.assistant-content');
        content.style.display = content.style.display === 'none' ? 'block' : 'none';
      });
    }
  }
  
  loadInitialContent() {
    this.loadContent('hub');
  }
  
  navigateTo(route) {
    if (!this.routes[route]) {
      console.error(`Route ${route} not found`);
      return;
    }
    
    this.currentRoute = route;
    this.loadContent(route);
    
    // Update URL
    window.history.pushState({}, '', `#/northstar-os/${route}`);
    
    // Update active nav item
    this.updateActiveNavItems(route);
    
    // Show success message
    this.showAlert(`Navigated to ${this.routes[route]}`, 'success');
  }
  
  loadContent(route) {
    const mainContent = document.getElementById('mainContent');
    if (!mainContent) return;
    
    // Clear previous content
    mainContent.innerHTML = '';
    
    // Load appropriate content based on route
    switch (route) {
      case 'hub':
        mainContent.innerHTML = this.getOperationsHubContent();
        break;
      case 'sourcescout':
        mainContent.innerHTML = this.getProspectorContent();
        break;
      case 'goldengoose':
        mainContent.innerHTML = this.getGoldenGooseContent();
        break;
      case 'listingforge':
        mainContent.innerHTML = this.getOfferChiselContent();
        break;
      case 'socialpulse':
        mainContent.innerHTML = this.getTownCrierContent();
        break;
      case 'adpilot':
        mainContent.innerHTML = this.getAuctioneerContent();
        break;
      case 'autothink':
        mainContent.innerHTML = this.getAutothinKContent();
        break;
      case 'thewatch':
        mainContent.innerHTML = this.getTheWatchContent();
        break;
      case 'rankledger':
        mainContent.innerHTML = this.getRankLedgerContent();
        break;
      case 'rivalboard':
        mainContent.innerHTML = this.getRivalBoardContent();
        break;
      case 'account':
        mainContent.innerHTML = this.getAccountContent();
        break;
      case 'ledger':
        mainContent.innerHTML = this.getLedgerContent();
        break;
      default:
        mainContent.innerHTML = this.getDefaultContent();
    }
  }
  
  getOperationsHubContent() {
    return `
      <div class="glass-card">
        <h2 class="glow-text">Operations Hub</h2>
        <p class="text-gray">Portfolio overview · suite shell · demo</p>
        
        <div class="dashboard-metrics">
          <div class="metric-card">
            <h3>Total Profit</h3>
            <p class="success-green">$11,483.22</p>
            <p class="text-gray">portfolio, 90 days (demo)</p>
          </div>
          
          <div class="metric-card">
            <h3>BSR Health</h3>
            <p>3 / 10 assets</p>
            <p class="text-gray">stable or improving (demo)</p>
          </div>
          
          <div class="metric-card">
            <h3>Open Gates</h3>
            <p>"8"</p>
            <p class="text-gray">authorization required</p>
          </div>
          
          <div class="metric-card">
            <h3>Live Warehouse</h3>
            <p>173 items</p>
            <p class="text-gray">stocked · 173 fresh · 3 live pulls</p>
          </div>
        </div>
        
        <div class="alpha-command-deck">
          <h3 class="glow-text">Alpha Command Deck</h3>
          <p class="text-gray">engines · gates · caps · launch checks</p>
        </div>
        
        <div class="recent-activity">
          <h3>Recent Activity</h3>
          <div class="activity-list">
            <div class="activity-item">
              <span class="activity-icon">🔍</span>
              <span>Prospector</span>
              <span class="activity-time">2h ago</span>
            </div>
            <div class="activity-item">
              <span class="activity-icon">⚙️</span>
              <span>Golden Goose</span>
              <span class="activity-time">5h ago</span>
            </div>
            <div class="activity-item">
              <span class="activity-icon">✍️</span>
              <span>OfferChisel</span>
              <span class="activity-time">1d ago</span>
            </div>
            <div class="activity-item">
              <span class="activity-icon">📱</span>
              <span>The Town Crier</span>
              <span class="activity-time">2d ago</span>
            </div>
          </div>
        </div>
        
        <div class="quick-actions">
          <h3>Quick Actions</h3>
          <div class="actions-grid">
            <button class="glass-button" data-action="scan">Scan products</button>
            <button class="glass-button" data-action="generate">Generate listing</button>
            <button class="glass-button" data-action="review">Review ad performance</button>
            <button class="glass-button" data-action="create">Create post</button>
          </div>
        </div>
        
        <div class="service-cards">
          <div class="service-card">
            <h4>Prospector</h4>
            <p>Product sourcing, margin calc, velocity analysis, Kirkland-to-Amazon arbitrage detection.</p>
            <span class="demo-badge">demo</span>
          </div>
          
          <div class="service-card">
            <h4>OfferChisel</h4>
            <p>Title/bullet/description rewrites, A+ content, SEO, compliance screening, Rufus readiness.</p>
            <span class="demo-badge">demo</span>
          </div>
          
          <div class="service-card">
            <h4>The Auctioneer</h4>
            <p>PPC bid optimization, ACoS management, keyword harvesting, placement analysis, negatives.</p>
            <span class="demo-badge">demo</span>
          </div>
          
          <div class="service-card">
            <h4>The Town Crier</h4>
            <p>Post generation, scheduling copy, brand-voice content, creator outreach.</p>
            <span class="demo-badge">demo</span>
          </div>
        </div>
      </div>
    `;
  }
  
  getProspectorContent() {
    return `
      <div class="glass-card">
        <h2 class="glow-text">Prospector</h2>
        <p class="text-gray">Retail Arbitrage Agent</p>
        
        <div class="prospector-content">
          <div class="search-section">
            <h3>Product Search</h3>
            <div class="search-form">
              <input type="text" placeholder="Enter product name or SKU..." class="glass-input">
              <button class="glass-button primary">Search</button>
            </div>
          </div>
          
          <div class="results-section">
            <h3>Search Results</h3>
            <div class="results-table">
              <div class="table-header">
                <div>Product</div>
                <div>Amazon Price</div>
                <div>Costco Price</div>
                <div>Margin</div>
                <div>BSR</div>
                <div>Actions</div>
              </div>
              <div class="table-body">
                <!-- Results will be populated dynamically -->
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }
  
  getGoldenGooseContent() {
    return `
      <div class="glass-card">
        <h2 class="glow-text">Golden Goose</h2>
        <p class="text-gray">Deal Finder Agent</p>
        
        <div class="golden-goose-content">
          <div class="filters-section">
            <h3>Filters</h3>
            <div class="filter-form">
              <select class="glass-select">
                <option>Price Range</option>
              </select>
              <select class="glass-select">
                <option>Margin Range</option>
              </select>
              <select class="glass-select">
                <option>BSR Range</option>
              </select>
              <button class="glass-button primary">Apply Filters</button>
            </div>
          </div>
          
          <div class="deals-section">
            <h3>Qualified Deals</h3>
            <div class="deals-grid">
              <!-- Deals will be populated dynamically -->
            </div>
          </div>
        </div>
      </div>
    `;
  }
  
  getOfferChiselContent() {
    return `
      <div class="glass-card">
        <h2 class="glow-text">OfferChisel</h2>
        <p class="text-gray">Listing Optimizer Agent</p>
        
        <div class="offer-chisel-content">
          <div class="listing-section">
            <h3>Create Listing</h3>
            <div class="listing-form">
              <input type="text" placeholder="Product Title" class="glass-input">
              <textarea placeholder="Product Description" class="glass-textarea"></textarea>
              <input type="text" placeholder="Bullet Points" class="glass-input">
              <button class="glass-button primary">Generate Listing</button>
            </div>
          </div>
          
          <div class="templates-section">
            <h3>Listing Templates</h3>
            <div class="templates-grid">
              <!-- Templates will be populated dynamically -->
            </div>
          </div>
        </div>
      </div>
    `;
  }
  
  getTownCrierContent() {
    return `
      <div class="glass-card">
        <h2 class="glow-text">The Town Crier</h2>
        <p class="text-gray">Social Media Agent</p>
        
        <div class="town-crier-content">
          <div class="social-section">
            <h3>Social Posts</h3>
            <div class="post-form">
              <textarea placeholder="Create your post..." class="glass-textarea"></textarea>
              <div class="post-actions">
                <select class="glass-select">
                  <option>Platform</option>
                </select>
                <button class="glass-button primary">Schedule Post</button>
              </div>
            </div>
          </div>
          
          <div class="schedule-section">
            <h3>Scheduled Posts</h3>
            <div class="schedule-grid">
              <!-- Scheduled posts will be populated dynamically -->
            </div>
          </div>
        </div>
      </div>
    `;
  }
  
  getAuctioneerContent() {
    return `
      <div class="glass-card">
        <h2 class="glow-text">The Auctioneer</h2>
        <p class="text-gray">Amazon Ads Agent</p>
        
        <div class="auctioneer-content">
          <div class="campaign-section">
            <h3>Campaign Management</h3>
            <div class="campaign-form">
              <input type="text" placeholder="Campaign Name" class="glass-input">
              <select class="glass-select">
                <option>Budget</option>
              </select>
              <button class="glass-button primary">Create Campaign</button>
            </div>
          </div>
          
          <div class="performance-section">
            <h3>Performance Metrics</h3>
            <div class="metrics-grid">
              <!-- Metrics will be populated dynamically -->
            </div>
          </div>
        </div>
      </div>
    `;
  }
  
  getAutothinKContent() {
    return `
      <div class="glass-card">
        <h2 class="glow-text">AutothinK</h2>
        <p class="text-gray">AI Decision Engine</p>
        
        <div class="autothink-content">
          <div class="engine-section">
            <h3>Engine Status</h3>
            <div class="engine-status">
              <div class="status-card">
                <h4>Engine Health</h4>
                <p class="success-green">Running</p>
              </div>
              <div class="status-card">
                <h4>Active Agents</h4>
                <p>5</p>
              </div>
              <div class="status-card">
                <h4>Processing Speed</h4>
                <p>2.3s avg</p>
              </div>
            </div>
          </div>
          
          <div class="tasks-section">
            <h3>Active Tasks</h3>
            <div class="tasks-grid">
              <!-- Tasks will be populated dynamically -->
            </div>
          </div>
        </div>
      </div>
    `;
  }
  
  getTheWatchContent() {
    return `
      <div class="glass-card">
        <h2 class="glow-text">The Watch</h2>
        <p class="text-gray">Monitoring Agent</p>
        
        <div class="thewatch-content">
          <div class="monitoring-section">
            <h3>Market Watch</h3>
            <div class="watch-grid">
              <!-- Watch items will be populated dynamically -->
            </div>
          </div>
        </div>
      </div>
    `;
  }
  
  getRankLedgerContent() {
    return `
      <div class="glass-card">
        <h2 class="glow-text">RankLedger</h2>
        <p class="text-gray">Rank Tracking Agent</p>
        
        <div class="rankledger-content">
          <div class="ranking-section">
            <h3>Product Rankings</h3>
            <div class="ranking-grid">
              <!-- Rankings will be populated dynamically -->
            </div>
          </div>
        </div>
      </div>
    `;
  }
  
  getRivalBoardContent() {
    return `
      <div class="glass-card">
        <h2 class="glow-text">The Rival Board</h2>
        <p class="text-gray">Competitor Analysis</p>
        
        <div class="rivalboard-content">
          <div class="analysis-section">
            <h3>Competitor Analysis</h3>
            <div class="analysis-grid">
              <!-- Analysis will be populated dynamically -->
            </div>
          </div>
        </div>
      </div>
    `;
  }
  
  getAccountContent() {
    return `
      <div class="glass-card">
        <h2 class="glow-text">Account</h2>
        <p class="text-gray">User Account & Settings</p>
        
        <div class="account-content">
          <div class="profile-section">
            <h3>Profile</h3>
            <div class="profile-form">
              <input type="text" placeholder="Name" class="glass-input">
              <input type="email" placeholder="Email" class="glass-input">
              <button class="glass-button primary">Save Changes</button>
            </div>
          </div>
          
          <div class="plans-section">
            <h3>Subscription Plans</h3>
            <div class="plans-grid">
              <!-- Plans will be populated dynamically -->
            </div>
          </div>
        </div>
      </div>
    `;
  }
  
  getLedgerContent() {
    return `
      <div class="glass-card">
        <h2 class="glow-text">The Ledger</h2>
        <p class="text-gray">Financial Tracking</p>
        
        <div class="ledger-content">
          <div class="transactions-section">
            <h3>Recent Transactions</h3>
            <div class="transactions-grid">
              <!-- Transactions will be populated dynamically -->
            </div>
          </div>
        </div>
      </div>
    `;
  }
  
  getDefaultContent() {
    return `
      <div class="glass-card">
        <h2 class="glow-text">Welcome to Northstar OS</h2>
        <p class="text-gray">Select a service from the sidebar to get started.</p>
      </div>
    `;
  }
  
  updateActiveNavItems(route) {
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
  
  handleGlobalSearch(e) {
    // Handle search input
    console.log('Global search:', e.target.value);
  }
  
  handleGlobalSearchSubmit(value) {
    console.log('Global search submitted:', value);
    this.showAlert(`Searching for: ${value}`, 'info');
  }
  
  handleAIEngineChange(e) {
    console.log('AI Engine changed:', e.target.value);
    this.showAlert(`AI Engine: ${e.target.value}`, 'info');
  }
  
  handleAITierChange(e) {
    console.log('AI Tier changed:', e.target.value);
    this.showAlert(`AI Tier: ${e.target.value}`, 'info');
  }
  
  handleAccountClick() {
    this.navigateTo('account');
  }
  
  handleActionDockClick(action) {
    console.log('Action dock clicked:', action);
    this.showAlert(`Action: ${action}`, 'info');
    
    // Map actions to routes
    const actionRoutes = {
      'scan': 'sourcescout',
      'generate': 'listingforge',
      'review': 'adpilot',
      'create': 'socialpulse',
      'settings': 'account'
    };
    
    if (actionRoutes[action]) {
      this.navigateTo(actionRoutes[action]);
    }
  }
  
  toggleTheme() {
    console.log('Theme toggled');
    this.showAlert('Theme toggle clicked', 'info');
  }
  
  showAlert(message, type = 'info') {
    const alert = document.createElement('div');
    alert.className = `glass-alert ${type}`;
    alert.innerHTML = `
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      <span>${message}</span>
    `;
    
    document.body.appendChild(alert);
    
    // Remove alert after 3 seconds
    setTimeout(() => {
      alert.remove();
    }, 3000);
  }
}

// Initialize the layout when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  new Layout();
});