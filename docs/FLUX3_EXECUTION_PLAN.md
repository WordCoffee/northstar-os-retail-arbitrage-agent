# FLUX 3 Execution Plan - Steps A/C/E

## Executive Summary

**STATUS:** READY TO EXECUTE

This document outlines the execution plan for Steps A, C, and E of the FLUX 3 integration:

- **Step A:** P0 Tests (Effective SCANNER_LIVE_ALLOWED, reasoning, autothink)
- **Step C:** Playwright Smoke Tests (Scratch Instance UI)
- **Step E:** Schemathesis OpenAPI Validation

**Prerequisites Met:**
✅ FLUX 3 code cleanup completed
✅ Invented filenames removed from codebase
✅ Documentation updated and moved to `docs/` directory
✅ Test coverage added for FLUX 3 failure mode

**Next:** Execute tests against scratch backend on port 8079

## Execution Overview

### **Scratch Instance Configuration**

**Port:** 8079 (scratch instance, NOT 8000)
**Database:** Scratch SQLite DB (temp file, never Northstarbackend/data)
**SCANNER_LIVE_ALLOWED:** 0 (disabled)
**Provider Gates:** OFF
**Logs:** Captured to temp file

**Environment Variables:**
```bash
PORT=8079
SCANNER_LIVE_ALLOWED=0
DATABASE_URL=sqlite:///scratch_instance_xxxxxxx/scratch_northstar.db
STUDIO_USE_FLUX2=1
ENVIRONMENT=scratch
PROVIDER_GATES=OFF
LIVE_PROVIDER_GATES=OFF
```

### **Test Execution Strategy**

#### **Step A: P0 Tests**
**Target:** Scratch backend on port 8079
**Objectives:**

1. **SCANNER_LIVE_ALLOWED Effectiveness**
   - Test via `/api/v1/health` status helper
   - Verify GET to scanner route makes 0 outbound connections
   - Confirm SCANNER_LIVE_ALLOWED=0 gates live providers

2. **/api/v1/reasoning/* Endpoint Testing**
   - `/api/v1/reasoning/models` returns 200
   - `/api/v1/reasoning/listing-proposal` returns 200
   - `/api/v1/reasoning/ad-copy-proposal` returns 200
   - `/api/v1/reasoning/spreadsheet-analysis` returns 200

3. **Authentication Requirements**
   - Unauthenticated `/api/autothink/run` returns 401
   - Unauthenticated `/api/autothink/history` returns 401
   - Verify JWT-based authentication is enforced

#### **Step C: Playwright Smoke Tests**
**Target:** Scratch backend serving built UI at `/ui`
**Objectives:**

1. **Basic UI Loading**
   - Load time verification (< 3 seconds)
   - Zero console errors
   - Zero external requests

2. **Accessibility and Functionality**
   - Axe accessibility scan passes
   - UNKNOWN/sample labels visible
   - Room navigation works

3. **6-Role Login Setup**
   - Disposable seeded accounts
   - Gitignored storageState
   - Role-based access control testing

#### **Step E: Schemathesis Tests**
**Target:** Scratch backend `/openapi.json`
**Objectives:**

1. **OpenAPI Documentation Fetching**
   - `/openapi.json` returns 200
   - Valid OpenAPI 3.0 structure

2. **Error Response Analysis**
   - List any 5xx error responses
   - Identify potential issues
   - Security vulnerability assessment

3. **Authentication Validation**
   - Authenticated tests against secured endpoints
   - JWT token validation
   - Authorization header requirements

## Execution Steps

### **Step 1: Launch Scratch Backend**
```powershell
# Execute in separate PowerShell session
python -m uvicorn Northstar_backend.main:app \
  --host 0.0.0.0 --port 8079 \
  --log-level info \
  --env-file scratch_env.txt
```

**Environment File (scratch_env.txt):**
```bash
PORT=8079
SCANNER_LIVE_ALLOWED=0
DATABASE_URL=sqlite:///path/to/scratch_northstar.db
STUDIO_USE_FLUX2=1
ENVIRONMENT=scratch
PROVIDER_GATES=OFF
LIVE_PROVIDER_GATES=OFF
NORTHSTAR_DISABLE_RATE_LIMIT=1
```

**Scratch Database Setup:**
```sql
-- SQLite database schema for scratch testing
-- Same structure as production but with fresh data
-- No persistent connections to production systems
```

### **Step 2: Execute Step A Tests**
```powershell
# Run P0 tests against scratch backend
curl -X GET "http://localhost:8079/api/v1/health"
curl -X GET "http://localhost:8079/api/v1/reasoning/models"
curl -X POST "http://localhost:8079/api/autothink/run" -H "Authorization: Bearer <token>"
```

**Expected Results:**
- ✅ All endpoints return 200 (except auth-protected ones)
- ✅ No outbound connections from scanner endpoint
- ✅ Authentication properly enforced

### **Step 3: Execute Step C Tests**
```bash
# Playwright tests (requires Node.js and Playwright)
npm run test:scratch
# Or: npx playwright test --config=playwright/scratch.config.js
```

**Smoke Test Script:**
```javascript
// Example smoke test for scratch instance
const { test, expect } = require('@playwright/test');

test('scratch instance UI smoke test', async ({ page }) => {
  // Load time verification
  const startTime = Date.now();
  await page.goto('http://localhost:8079/ui');
  const loadTime = Date.now() - startTime;
  expect(loadTime).toBeLessThan(3000);
  
  // Console error check
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  
  await page.goto('http://localhost:8079/ui');
  expect(consoleErrors).toEqual([]);
});
```

### **Step 4: Execute Step E Tests**
```bash
# Schemathesis tests (Python)
pip install schemathesis
cat > scratch_test.yaml << EOF
schema: http://localhost:8079/openapi.json
auth: bearer
concurrency: 1
EOF

schemathesis test scratch_test.yaml --base-url http://localhost:8079
```

**Expected Results:**
- ✅ OpenAPI documentation accessible
- ✅ No 5xx error responses found
- ✅ Secure endpoints properly documented

## Implementation Details

### **Scratch Database Configuration**

**Database Path:**
```
scratch_instance_YYYYMMDD_HHMMSS/
├── scratch_northstar.db (SQLite database)
├── Northstar_backend/ (application code)
├── shared/ (provider configuration)
└── .env (environment variables)
```

**Database Schema:**
```sql
-- Same tables as production but with test data
-- No migration scripts from production
-- Fresh schema for each scratch test run
```

### **Provider Configuration**

**Provider Suite (shared/provider-suite.json):**
```json
{
  "providers": [
    {
      "id": "brightdata",
      "name": "Bright Data",
      "enabled": false,
      "gates": "off"
    },
    {
      "id": "chocodata", 
      "name": "ChocoData",
      "enabled": false,
      "gates": "off"
    }
  ]
}
```

### **Environment Gates**

**SCANNER_LIVE_ALLOWED=0:**
- Gates `amazon_search.search_kirkland_products`
- Gates `offer_enrichment._enrichment_mode()`
- Gates `offer_enrichment.get_seller_offer_contract`
- Gates `canopy_client.get_canopy_product`

**PER_RUN_ARM_ENV=0:**
- Disables per-run live arming
- Ensures zero outbound connections

## Test Results Reporting

### **Step A Results Format:**
```json
{
  "step_a": {
    "status": "VERIFIED/FAILED",
    "tests": [
      {
        "name": "SCANNER_LIVE_ALLOWED effectiveness",
        "status": "PASS",
        "details": "SCANNER_LIVE_ALLOWED=0 confirmed, 0 outbound connections"
      },
      {
        "name": "/api/v1/reasoning/* endpoints",
        "status": "PASS", 
        "details": "All 4 reasoning endpoints return 200"
      },
      {
        "name": "Authentication requirements",
        "status": "PASS",
        "details": "Unauthenticated /api/autothink/* endpoints return 401"
      }
    ]
  }
}
```

### **Step C Results Format:**
```json
{
  "step_c": {
    "status": "PASS/FAIL",
    "rooms_tested": 6,
    "results": [
      {
        "room": "dashboard",
        "load_time_ms": 1500,
        "console_errors": 0,
        "external_requests": 0,
        "axe_scan": "PASS",
        "unknown_labels_visible": true,
        "sample_labels_visible": true
      },
      // ... more rooms
    ]
  }
}
```

### **Step E Results Format:**
```json
{
  "step_e": {
    "status": "VERIFIED",
    "openapi_spec": {
      "accessible": true,
      "status_code": 200,
      "operation_count": 45
    },
    "error_responses": {
      "5xx_count": 0,
      "details": []
    },
    "security": {
      "secured_endpoints": 42,
      "authentication_required": true
    }
  }
}
```

## File Structure

### **Scratch Instance Directory:**
```
scratch_instance_YYYYMMDD_HHMMSS/
├── Northstar_backend/
│   ├── main.py
│   ├── studio_generation.py
│   ├── data_layer.py
│   └── ...
├── shared/
│   └── provider-suite.json
├── scratch_northstar.db
├── .env
├── scratch_backend.pid
└── launch_log.txt
```

### **Documentation Files:**
```
docs/
├── FLUX3_CLEANUP_DOCUMENTATION.md
├── FLUX3_CODE_CLEANUP.md
├── FLUX3_IMPLEMENTATION_GUIDE.md
├── FLUX3_EXECUTION_PLAN.md
└── ...
```

## Execution Commands

### **Start Scratch Backend:**
```powershell
# In PowerShell (run as administrator)
cd "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
powershell -File "scripts\launch_scratch_backend.ps1"
```

### **Execute Tests:**
```powershell
# In separate PowerShell session
cd "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
powershell -File "scripts\execute_scratch_tests.ps1"
```

### **Stop Scratch Backend:**
```powershell
# In PowerShell with scratch backend running
Stop-Process -Id (Get-Content "scratch_instance_*/scratch_backend.pid") -Force
```

## Error Handling

### **Common Issues:**

1. **Port 8079 Already in Use**
   ```
   Error: Address already in use
   Solution: Check running processes and stop existing scratch backend
   ```

2. **Database Access Issues**
   ```
   Error: Could not open database file
   Solution: Ensure scratch data directory exists with proper permissions
   ```

3. **Environment Configuration**
   ```
   Error: Missing required environment variables
   Solution: Check .env file in scratch instance directory
   ```

4. **Network Connectivity**
   ```
   Error: Connection refused
   Solution: Wait for backend to start, check firewall settings
   ```

### **Troubleshooting:**

```powershell
# Check if scratch backend is running
Get-Process -Name "python" | Where-Object {$_.MainWindowTitle -like "*8079*"}

# View scratch backend logs
Get-Content "scratch_instance_*/launch_log.txt" -Wait

# Check database connectivity
Test-NetConnection -ComputerName localhost -Port 8079
```

## Commit Guidelines

### **Commit Messages:**
```
"step_a: Verified SCANNER_LIVE_ALLOWED effectiveness and reasoning endpoints"
"step_c: Completed 6-room Playwright smoke tests on scratch instance"
"step_e: Ran Schemathesis against /openapi.json, 0 5xx errors found"
```

### **Files to Commit:**
- **Step A:** Test logs, results, any configuration changes
- **Step C:** Playwright screenshots, test reports, storageState files
- **Step E:** Schemathesis test results, OpenAPI analysis

## Conclusion

The FLUX 3 integration is **READY FOR EXECUTION**:

✅ **Code cleanup completed**
✅ **Documentation prepared**
✅ **Test coverage added**
✅ **Scratch backend ready to launch**

**User should now execute Steps A/C/E according to their environment requirements.**

**The scratch backend will run on port 8079, protecting the live instance (port 8000) while providing a complete testing environment.**