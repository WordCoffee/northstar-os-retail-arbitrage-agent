// src/tests/navigation-test.js
class NavigationTester {
  constructor() {
    this.navigationService = navigationService;
    this.testResults = [];
    this.totalTests = 0;
    this.passedTests = 0;
    this.failedTests = 0;
  }
  
  /**
   * Run all navigation tests
   */
  async runAllTests() {
    console.log('🚀 Starting Navigation Tests');
    console.log('==========================');
    
    this.totalTests = 0;
    this.passedTests = 0;
    this.failedTests = 0;
    
    // Test route existence
    await this.testRouteExistence();
    
    // Test navigation to each route
    await this.testRouteNavigation();
    
    // Test URL updates
    await this.testUrlUpdates();
    
    // Test history management
    await this.testHistoryManagement();
    
    // Test event listeners
    await this.testEventListeners();
    
    // Print results
    this.printTestResults();
  }
  
  /**
   * Test that all routes exist
   */
  async testRouteExistence() {
    console.log('\n📋 Testing Route Existence');
    console.log('------------------------');
    
    const routes = Object.keys(this.navigationService.routes);
    
    for (const route of routes) {
      this.totalTests++;
      
      try {
        const routeName = this.navigationService.getRouteName(route);
        console.log(`✅ Route exists: ${route} (${routeName})`);
        this.passedTests++;
      } catch (error) {
        console.log(`❌ Route missing: ${route}`);
        this.failedTests++;
        this.testResults.push({
          test: `Route Existence: ${route}`,
          status: 'FAILED',
          error: error.message
        });
      }
    }
  }
  
  /**
   * Test navigation to each route
   */
  async testRouteNavigation() {
    console.log('\n🧭 Testing Route Navigation');
    console.log('-------------------------');
    
    const routes = Object.keys(this.navigationService.routes);
    
    for (const route of routes) {
      this.totalTests++;
      
      try {
        // Navigate to route
        const success = this.navigationService.navigateTo(route, { silent: true });
        
        if (success) {
          console.log(`✅ Navigation successful: ${route}`);
          this.passedTests++;
        } else {
          console.log(`❌ Navigation failed: ${route}`);
          this.failedTests++;
          this.testResults.push({
            test: `Navigation: ${route}`,
            status: 'FAILED',
            error: 'Navigation returned false'
          });
        }
        
        // Wait a bit for any async operations
        await new Promise(resolve => setTimeout(resolve, 100));
        
        // Navigate back to hub
        this.navigationService.navigateTo('hub', { silent: true });
      } catch (error) {
        console.log(`❌ Navigation error: ${route}`);
        this.failedTests++;
        this.testResults.push({
          test: `Navigation: ${route}`,
          status: 'FAILED',
          error: error.message
        });
      }
    }
  }
  
  /**
   * Test URL updates
   */
  async testUrlUpdates() {
    console.log('\n🔗 Testing URL Updates');
    console.log('--------------------');
    
    const routes = ['hub', 'sourcescout', 'listingforge'];
    
    for (const route of routes) {
      this.totalTests++;
      
      try {
        // Navigate to route
        this.navigationService.navigateTo(route, { silent: true });
        
        // Check URL
        const currentUrl = window.location.hash;
        const expectedUrl = `#/northstar-os/${route}`;
        
        if (currentUrl === expectedUrl) {
          console.log(`✅ URL correct: ${expectedUrl}`);
          this.passedTests++;
        } else {
          console.log(`❌ URL mismatch: expected ${expectedUrl}, got ${currentUrl}`);
          this.failedTests++;
          this.testResults.push({
            test: `URL Update: ${route}`,
            status: 'FAILED',
            error: `URL mismatch: expected ${expectedUrl}, got ${currentUrl}`
          });
        }
        
        // Navigate back to hub
        this.navigationService.navigateTo('hub', { silent: true });
      } catch (error) {
        console.log(`❌ URL test error: ${route}`);
        this.failedTests++;
        this.testResults.push({
          test: `URL Update: ${route}`,
          status: 'FAILED',
          error: error.message
        });
      }
    }
  }
  
  /**
   * Test history management
   */
  async testHistoryManagement() {
    console.log('\n📜 Testing History Management');
    console.log('--------------------------');
    
    this.totalTests++;
    
    try {
      // Navigate to a route
      this.navigationService.navigateTo('sourcescout', { silent: true });
      
      // Navigate to another route
      this.navigationService.navigateTo('listingforge', { silent: true });
      
      // Navigate back
      const success = this.navigationService.navigateBack();
      
      if (success) {
        console.log('✅ History navigation successful');
        this.passedTests++;
      } else {
        console.log('❌ History navigation failed');
        this.failedTests++;
        this.testResults.push({
          test: 'History Management',
          status: 'FAILED',
          error: 'navigateBack returned false'
        });
      }
    } catch (error) {
      console.log('❌ History test error');
      this.failedTests++;
      this.testResults.push({
        test: 'History Management',
        status: 'FAILED',
        error: error.message
      });
    }
  }
  
  /**
   * Test event listeners
   */
  async testEventListeners() {
    console.log('\n🎧 Testing Event Listeners');
    console.log('-----------------------');
    
    this.totalTests++;
    
    try {
      // Add test listener
      const testListener = (data) => {
        console.log('✅ Navigation event received:', data);
      };
      
      this.navigationService.addListener(testListener, 'navigate');
      
      // Trigger navigation
      this.navigationService.navigateTo('hub', { silent: false });
      
      // Remove listener
      this.navigationService.removeListener(testListener, 'navigate');
      
      this.passedTests++;
    } catch (error) {
      console.log('❌ Event listener test failed');
      this.failedTests++;
      this.testResults.push({
        test: 'Event Listeners',
        status: 'FAILED',
        error: error.message
      });
    }
  }
  
  /**
   * Print test results
   */
  printTestResults() {
    console.log('\n📊 Test Results');
    console.log('==============');
    console.log(`Total Tests: ${this.totalTests}`);
    console.log(`Passed: ${this.passedTests}`);
    console.log(`Failed: ${this.failedTests}`);
    console.log(`Success Rate: ${((this.passedTests / this.totalTests) * 100).toFixed(1)}%`);
    
    if (this.failedTests > 0) {
      console.log('\n❌ Failed Tests:');
      this.testResults.forEach(result => {
        console.log(`- ${result.test}: ${result.status}`);
        if (result.error) {
          console.log(`  Error: ${result.error}`);
        }
      });
    } else {
      console.log('\n🎉 All tests passed!');
    }
  }
}

// Run tests when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  const tester = new NavigationTester();
  tester.runAllTests();
});