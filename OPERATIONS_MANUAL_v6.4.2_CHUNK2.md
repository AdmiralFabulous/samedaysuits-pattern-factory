## 12. System Architecture & Data Flow

### 12.1 Overview

This section documents the complete data flow through the Pattern Factory system, from order intake to production file generation.

### 12.2 System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT INTERFACES                        │
├─────────────────────────────────────────────────────────────────┤
│  CLI (sds)        Web Dashboard        REST API        Scanner │
│  └── sds_cli.py   └── web_api.py       └── web_api.py  └── ... │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SAME DAY SUITS API                          │
│                   (samedaysuits_api.py)                         │
├─────────────────────────────────────────────────────────────────┤
│  Order Management │ Customer Mgmt │ Measurement │ Order Queue   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PRODUCTION PIPELINE                           │
│               (production_pipeline.py)                          │
├─────────────────────────────────────────────────────────────────┤
│  PDS Load → Extract → Scale → Nest → QC → PLT                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ PATTERN SCALER   │ │ NESTING ENGINE   │ │ QUALITY CONTROL  │
│ pattern_scaler.py│ │ master_nesting.py│ │ quality_control. │
└──────────────────┘ └──────────────────┘ └──────────────────┘
                │               │               │
                └───────────────┼───────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  CUTTER QUEUE                                   │
│                 (cutter_queue.py)                               │
├─────────────────────────────────────────────────────────────────┤
│  Job Queue → Spool Directory → Cutter Integration               │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              DATABASE & MONITORING                              │
│         (database_integration.py, production_monitor.py)        │
├─────────────────────────────────────────────────────────────────┤
│  Supabase Sync │ Metrics │ Alerts │ Historical Data            │
└─────────────────────────────────────────────────────────────────┘
```

### 12.3 Data Flow Diagram

**Order Processing Flow:**

```
1. ORDER INTAKE
   ↓
   Input: Customer measurements, garment type, fit preference
   Source: CLI, Web API, Scanner, or Database
   
2. ORDER VALIDATION
   ↓
   - Validate measurements (range checks)
   - Verify garment type available
   - Check fabric availability (optional)
   - Create order record
   
3. PATTERN SELECTION
   ↓
   - Map garment type to PDS template
   - Select base size from measurements
   - Load PDS file
   - Extract graded sizes if available
   
4. PATTERN SCALING
   ↓
   - Calculate X/Y scaling factors
   - Apply to pattern contours
   - Scale graded sizes if applicable
   - Log scaling parameters
   
5. NESTING
   ↓
   - Run master_nest algorithm
   - Optimize for fabric width (62")
   - Calculate utilization
   - Generate nested layout
   
6. QUALITY CONTROL
   ↓
   - Validate piece count
   - Check geometry integrity
   - Verify fit measurements
   - Check fabric utilization
   - Generate QC report
   
7. PLT GENERATION
   ↓
   - Convert nested layout to HPGL
   - Add cutter commands
   - Optimize cutting path
   - Generate .plt file
   
8. CUTTER QUEUE
   ↓
   - Create cutter job
   - Assign priority
   - Add to spool
   - Notify operators
   
9. DATABASE SYNC
   ↓
   - Save order to local files
   - Queue for Supabase sync
   - Update production logs
   - Archive completed order
```

### 12.4 File Storage Architecture

**Directory Structure:**
```
DS-speciale/
├── inputs/
│   ├── pds/                    # PDS template files
│   │   ├── Basic Tee_2D.PDS
│   │   ├── Light Jacket_2D.PDS
│   │   └── Skinny Trousers_2D.PDS
│   └── mrk/                    # MRK marker files
│
├── out/
│   ├── orders/                 # Generated orders
│   │   └── <order_id>/
│   │       ├── <order_id>.plt              # HPGL file
│   │       ├── <order_id>_metadata.json    # Order details
│   │       └── <order_id>_qc_report.json   # QC report
│   │
│   ├── cutter_spool/           # Cutter queue
│   │   ├── pending/            # Jobs waiting
│   │   ├── processing/         # Currently cutting
│   │   ├── completed/          # Successfully cut
│   │   └── failed/             # Failed jobs
│   │
│   ├── graded_sizes/           # Size-specific outputs
│   ├── extracted/              # Extracted patterns
│   ├── canonical/              # Canonical models
│   └── production_62inch/      # Final PLT outputs
│
└── oracle/                     # Oracle pattern data

scans/                          # TheBlackbox scan files
├── normal_man_scan.json
├── fat_man_scan.json
└── *.json

production_data/                # Monitoring data
├── metrics.json                # Current metrics
├── daily_*.json                # Daily summaries
└── monthly_*.json              # Monthly reports
```

### 12.5 Data Formats

**Order Metadata (JSON):**
```json
{
  "order_id": "ORDER-20260131-001",
  "customer_id": "CUST-001",
  "garment_type": "jacket",
  "fit_preference": "regular",
  "customer_measurements": {
    "chest": 102.0,
    "waist": 88.0,
    "hip": 100.0,
    "shoulder": 46.0,
    "inseam": 81.0
  },
  "base_size": "L",
  "scaling_factors": {
    "scale_x": 1.0,
    "scale_y": 0.958
  },
  "fabric_width_cm": 157.48,
  "fabric_length_cm": 53.8,
  "utilization_percent": 78.0,
  "nesting_algorithm": "guillotine",
  "piece_count": 15,
  "status": "completed",
  "created_at": "2026-01-31T10:00:00Z",
  "completed_at": "2026-01-31T10:00:45Z",
  "processing_time_seconds": 45.2,
  "plt_file": "DS-speciale/out/orders/.../ORDER-001.plt",
  "qc_status": "passed",
  "qc_score": "High"
}
```

**PLT File Format (HPGL):**
```
IN;              # Initialize plotter
SP1;             # Select pen 1
PU0,0;           # Pen up, move to origin
PD1000,0;        # Pen down, draw line
PD1000,1000;     # Continue drawing
PD0,1000;        # Continue drawing
PD0,0;           # Close shape
PU;              # Pen up
SP0;             # Deselect pen
IN;              # Finalize
```

### 12.6 API Integration Points

**Internal API (samedaysuits_api.py):**
```python
# Core processing
api.process_order(order) -> ProductionResult

# Batch operations  
api.batch_process(orders) -> List[ProductionResult]

# Template management
api.list_available_templates() -> Dict[str, bool]
api.get_template_path(garment_type) -> Path

# Database operations
api.sync_orders_to_database()
api.get_order_history(customer_id)
```

**REST API (web_api.py):**
```python
# Orders
POST /orders              # Submit new order
GET /orders/{id}          # Get order details
GET /orders/{id}/plt      # Download PLT file

# Queue
GET /queue/status         # Queue status
POST /queue/process-next  # Process next job

# Monitoring
GET /api/metrics          # Production metrics
GET /api/health           # Health check
GET /api/alerts           # Active alerts

# WebSocket
WS /ws                    # Real-time updates
```

### 12.7 New Section: 4.0 System Architecture

```
4.0 System Architecture & Data Flow

4.0.1 Overview
The Pattern Factory uses a layered architecture with clear separation of
concerns: client interfaces, business logic, processing pipeline, and
infrastructure services.

4.0.2 Architecture Layers

Layer 1: Client Interfaces
- CLI (sds_cli.py): Command-line operations
- Web Dashboard (web_api.py): Browser-based UI
- REST API (web_api.py): Programmatic access
- Scanner Integration (theblackbox_integration.py): 3D scan input

Layer 2: Business Logic
- SameDaySuitsAPI (samedaysuits_api.py): Core orchestration
- Order management and validation
- Customer measurement handling
- Queue management

Layer 3: Processing Pipeline
- ProductionPipeline (production_pipeline.py): End-to-end processing
- PatternScaler (pattern_scaler.py): Measurement-based scaling
- NestingEngine (master_nesting.py): Fabric optimization
- QualityControl (quality_control.py): Validation

Layer 4: Infrastructure
- Database (database_integration.py): Supabase persistence
- CutterQueue (cutter_queue.py): Physical production queue
- ProductionMonitor (production_monitor.py): Metrics and alerting
- FileSystem: Local storage for orders and artifacts

4.0.3 Data Flow

Order Intake → Validation → Pattern Selection → Scaling → 
Nesting → QC → PLT Generation → Cutter Queue → Database Sync

Each stage:
- Validates inputs
- Processes data
- Logs operations
- Passes to next stage
- Handles errors

4.0.4 Storage Strategy

Two-Tier Storage:
1. Local Filesystem: Fast access, immediate response
   - PLT files
   - Order metadata
   - QC reports
   - Temp processing files

2. Supabase Database: Persistent, queryable
   - Order history
   - Customer records
   - Production logs
   - Analytics data

Sync Strategy:
- Write-through: Local first, async to DB
- Conflict resolution: Local wins
- Retry logic: Exponential backoff

4.0.5 Key Files and Locations

Source Code:
- Core: samedaysuits_api.py, production_pipeline.py
- CLI: sds_cli.py
- Web: web_api.py, start_dashboard.py
- Processing: pattern_scaler.py, quality_control.py
- Queue: cutter_queue.py
- Database: database_integration.py
- Monitor: production_monitor.py

Data:
- Templates: DS-speciale/inputs/pds/
- Orders: DS-speciale/out/orders/
- Queue: DS-speciale/out/cutter_spool/
- Scans: scans/
- Monitoring: production_data/

4.0.6 Configuration

Environment Variables:
- SUPABASE_URL, SUPABASE_KEY (database)
- CUTTER_WIDTH_CM (hardware)
- NESTING_GAP_CM (processing)
- DEBUG, LOG_LEVEL (runtime)

Config Files:
- config/supabase.yaml
- config/cutter.yaml
- config/nesting.yaml

4.0.7 Scaling Considerations

Horizontal Scaling:
- Stateless API servers
- Shared database (Supabase)
- Distributed queue (Redis planned)
- Load balancer for multiple instances

Vertical Scaling:
- Multi-threaded nesting (planned)
- GPU acceleration for geometry (planned)
- Memory caching for templates

4.0.8 Security

Authentication:
- API tokens for REST/WebSocket
- Role-based access control
- Audit logging for sensitive operations

Data Protection:
- Customer measurements encrypted at rest
- PLT files access-controlled
- Database credentials in environment
- No secrets in code repository
```

---

## 13. Testing & Development Tools

### 13.1 Overview

The Pattern Factory includes comprehensive testing tools for development, validation, and quality assurance.

### 13.2 Test Profiles

**Built-in Test Profiles:**

| Profile | Size | Build | Measurements |
|---------|------|-------|--------------|
| normal | Large | Athletic | Chest:102, Waist:88, Hip:100 |
| fat | XXL | Heavyset | Chest:120, Waist:110, Hip:115 |
| slim | Medium | Lean | Chest:94, Waist:76, Hip:92 |
| tall | XL | Tall | Chest:108, Waist:90, Hip:104 |

**Generate Test Scans:**
```bash
# Generate normal man profile
sds scan generate --profile normal --output scans/test_normal.json

# Generate fat man profile  
sds scan generate --profile fat --output scans/test_fat.json

# Generate slim profile
sds scan generate --profile slim --output scans/test_slim.json

# Generate tall profile
sds scan generate --profile tall --output scans/test_tall.json
```

### 13.3 Pipeline Testing

**Run Full Pipeline Test:**
```bash
# Run standard pipeline test
sds test

# Expected output:
# - Loads test order
# - Processes through pipeline
# - Generates PLT file
# - Validates output
# - Reports timing and utilization
```

**Custom Test Orders:**
```bash
# Create test_orders.json file:
[
  {
    "customer_id": "TEST-001",
    "garment_type": "jacket",
    "fit": "regular",
    "measurements": {
      "chest": 102,
      "waist": 88,
      "hip": 100,
      "shoulder": 46,
      "inseam": 81
    }
  }
]

# Process test batch
sds batch test_orders.json
```

### 13.4 API Testing

**Test Web API:**
```bash
# Using curl
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "TEST-001",
    "garment_type": "tee",
    "fit_preference": "regular",
    "measurements": {
      "chest": 96,
      "waist": 82
    }
  }'

# Get order status
curl http://localhost:8000/orders/ORDER-001

# Download PLT file
curl http://localhost:8000/orders/ORDER-001/plt -o test.plt
```

**Test Script (test_web_api.py):**
```python
from test_web_api import APITestClient

client = APITestClient(base_url="http://localhost:8000")

# Test health endpoint
client.test_health()

# Test order creation
order_id = client.test_create_order(
    garment_type="jacket",
    measurements={"chest": 102, "waist": 88}
)

# Test order retrieval
client.test_get_order(order_id)

# Run all tests
client.run_all_tests()
```

### 13.5 Nesting Algorithm Testing

**Compare Algorithms:**
```bash
# Run master nesting comparison
python master_nesting.py --compare --all

# Test specific pattern
python master_nesting.py --pattern jacket --verbose

# Output includes:
# - Algorithm performance comparison
# - Utilization percentages
# - Processing times
# - Best algorithm selection
```

### 13.6 Performance Testing

**Load Testing:**
```bash
# Process multiple orders sequentially
for i in {1..10}; do
  sds order --garment tee --chest 96 --waist 82
done

# Monitor processing times
sds monitor metrics
```

**Benchmarking:**
```python
from production_pipeline import benchmark_nesting

results = benchmark_nesting(
    pattern="jacket",
    algorithms=['guillotine', 'skyline', 'hybrid'],
    iterations=5
)

print(f"Best algorithm: {results.best}")
print(f"Average time: {results.avg_time:.2f}s")
```

### 13.7 Development Utilities

**Direct PDS Testing:**
```bash
# Extract and view PDS contents
python extract_oracle_data.py --pds inputs/pds/Basic_Tee_2D.PDS --output tee_data.json

# View graded sizes
python graded_size_extractor.py --pds inputs/pds/Light_Jacket_2D.PDS
```

**Nesting Visualization:**
```bash
# Generate nesting preview (if matplotlib available)
python nesting_engine.py --visualize --pattern jacket

# Output: nesting_preview.png showing piece layout
```

### 13.8 New Section: 6.0 Testing & Development

```
6.0 Testing & Development Tools

6.0.1 Overview
The Pattern Factory includes comprehensive testing infrastructure for 
validating functionality, benchmarking performance, and ensuring quality.

6.0.2 Test Profiles

Built-in Profiles:
- normal: Size Large, athletic build (Chest:102, Waist:88)
- fat: Size XXL, heavyset build (Chest:120, Waist:110)
- slim: Size Medium, lean build (Chest:94, Waist:76)
- tall: Size XL, tall build (Chest:108, Waist:90)

Generation:
sds scan generate --profile <type> --output <path>

Usage:
- Development testing
- Algorithm benchmarking
- Demo scenarios
- Edge case validation

6.0.3 Pipeline Testing

Standard Test:
sds test
- Processes test order through full pipeline
- Validates PLT output
- Reports timing and utilization
- Checks for errors

Custom Batch Testing:
Create test_orders.json with array of orders
sds batch test_orders.json
- Processes multiple test orders
- Compares results
- Identifies outliers

6.0.4 API Testing

Using curl:
Test endpoints manually with HTTP requests
See examples in Section 13.4

Using Test Client (test_web_api.py):
Programmatic testing with assertions
- test_health(): Verify API responsive
- test_create_order(): Validate order creation
- test_get_order(): Check order retrieval
- test_download_plt(): Verify file download

6.0.5 Algorithm Testing

Compare Nesting Algorithms:
python master_nesting.py --compare --all
- Runs all algorithms on same pattern
- Compares utilization and speed
- Recommends best algorithm

Benchmark Specific Pattern:
python master_nesting.py --pattern <type> --verbose
- Detailed timing breakdown
- Memory usage tracking
- Multiple iterations for accuracy

6.0.6 Performance Testing

Load Testing:
Process multiple orders sequentially
Monitor for degradation
Identify bottlenecks

Benchmarking:
Measure processing times
Track resource usage
Compare algorithm performance
Establish baseline metrics

6.0.7 Development Utilities

PDS Inspection:
Extract and examine PDS file contents
View graded size tables
Validate pattern integrity

Nesting Visualization:
Generate layout previews
Debug piece positioning
Verify no overlaps

6.0.8 Continuous Integration

Test Suite:
- Unit tests for core functions
- Integration tests for pipeline
- API endpoint tests
- End-to-end workflow tests

Running Tests:
pytest tests/           # Run all tests
pytest tests/unit/     # Unit tests only
pytest tests/api/      # API tests only
pytest -v              # Verbose output

6.0.9 Debugging

Verbose Logging:
Set LOG_LEVEL=DEBUG
Outputs detailed processing logs
Shows intermediate calculations

Error Investigation:
Check production_logs table
Review order metadata
Examine QC reports
Trace execution flow
```

---

## 14. Alert Management System

### 14.1 Overview

The Alert Management System provides automated detection, notification, and resolution tracking for operational issues.

### 14.2 Alert Types

**System Alerts:**
- High failure rate (>5% orders failing)
- Low fabric utilization (<60% average)
- Queue backup (>10 pending jobs)
- Slow processing (>120s per order)
- Database sync failures
- Cutter communication errors

**Quality Alerts:**
- QC validation failures
- Pattern geometry errors
- Measurement mismatches (>30%)
- Missing pieces in output

**Infrastructure Alerts:**
- Disk space low (<10% free)
- Memory usage high (>80%)
- API response time slow (>500ms)
- WebSocket disconnections

### 14.3 Alert Severity Levels

| Level | Color | Response Time | Action |
|-------|-------|---------------|--------|
| CRITICAL | Red | Immediate | Page on-call engineer |
| ERROR | Orange | 15 minutes | Notify manager |
| WARNING | Yellow | 1 hour | Log and notify operators |
| INFO | Blue | None | Log only |

### 14.4 Alert Lifecycle

```
DETECTED → ACTIVE → ACKNOWLEDGED → RESOLVED → CLOSED
              ↓
         ESCALATED (if unacknowledged)
```

**States:**
- `DETECTED`: Issue identified by monitoring
- `ACTIVE`: Alert visible to operators
- `ACKNOWLEDGED`: Operator confirmed receipt
- `RESOLVED`: Issue fixed
- `CLOSED`: Alert archived
- `ESCALATED`: Escalated to management

### 14.5 Alert Configuration

**Thresholds (production_monitor.py):**
```python
ALERT_THRESHOLDS = {
    'utilization_low': 60.0,      # %
    'failure_rate_high': 5.0,     # %
    'queue_backup': 10,           # jobs
    'processing_time_slow': 120,  # seconds
    'disk_space_low': 10.0,       # % free
    'memory_high': 80.0,          # %
    'api_latency_slow': 500       # ms
}
```

**Notification Channels:**
```yaml
# config/alerts.yaml
notifications:
  critical:
    - pagerduty
    - sms
    - email
  error:
    - email
    - slack
  warning:
    - dashboard
    - email
  info:
    - dashboard
    - log

channels:
  pagerduty:
    service_key: ${PAGERDUTY_KEY}
  slack:
    webhook_url: ${SLACK_WEBHOOK}
  email:
    smtp_server: smtp.gmail.com
    from: alerts@samedaysuits.com
    to: ops@samedaysuits.com
```

### 14.6 CLI Commands

```bash
# View active alerts
sds monitor alerts

# Acknowledge alert
sds monitor ack <alert_id>

# Resolve alert
sds monitor resolve <alert_id>

# View alert history
sds monitor alerts --history

# Test alert channels
sds monitor test-alert --severity warning
```

### 14.7 API Endpoints

```
GET /api/alerts
  Returns active alerts:
  {
    "alerts": [
      {
        "id": "ALT-001",
        "severity": "warning",
        "type": "low_utilization",
        "message": "Average utilization below 60%",
        "detected_at": "2026-01-31T10:00:00Z",
        "acknowledged": false,
        "acknowledged_by": null
      }
    ]
  }

POST /api/alerts/{alert_id}/acknowledge
  Acknowledge alert
  Body: {"acknowledged_by": "operator_name"}

POST /api/alerts/{alert_id}/resolve
  Resolve alert
  Body: {"resolution_notes": "Fixed nesting algorithm"}
```

### 14.8 Dashboard Integration

**Alert Widget:**
- Displays active alerts in priority order
- Color-coded by severity
- One-click acknowledge
- Shows time since detection

**Alert Indicators:**
- Header bar shows alert count
- Flashing for CRITICAL alerts
- Sound notifications (optional)
- Badge counts on menu items

### 14.9 New Section: 2.11 Alert Management

```
2.11 Alert Management System

2.11.1 Overview
The Alert Management System provides automated detection and notification
of operational issues, ensuring rapid response to production problems.

2.11.2 Alert Categories

System Alerts:
- High failure rate (>5% orders failing)
- Low fabric utilization (<60%)
- Queue backup (>10 pending jobs)
- Slow processing (>120s per order)
- Database sync failures
- Infrastructure issues

Quality Alerts:
- QC validation failures
- Pattern geometry errors
- Extreme measurement mismatches (>30%)
- Missing pieces in output

2.11.3 Severity Levels

CRITICAL (Red):
- Immediate response required
- Pages on-call engineer
- Examples: System down, data loss risk

ERROR (Orange):
- Response within 15 minutes
- Notifies manager
- Examples: High failure rate, cutter offline

WARNING (Yellow):
- Response within 1 hour
- Notifies operators
- Examples: Low utilization, queue building

INFO (Blue):
- No response required
- Logged for awareness
- Examples: Routine completions

2.11.4 Alert Lifecycle

Detection: Monitoring system identifies issue
Activation: Alert created and notifications sent
Acknowledgment: Operator confirms awareness
Resolution: Issue fixed
Closure: Alert archived
Escalation: Auto-escalate if unacknowledged (30 min)

2.11.5 Configuration

Thresholds (production_monitor.py):
Configurable per-environment:
- Development: Relaxed thresholds
- Staging: Production-like
- Production: Strict monitoring

Notification Channels:
- PagerDuty: Critical alerts
- Slack: Team notifications
- Email: Managers and operators
- Dashboard: All alert visibility

2.11.6 CLI Reference
See Section 5.3 (CLI Reference) for alert commands.

2.11.7 API Reference
See Section 3.2 (API Reference) for alert endpoints.

2.11.8 Response Procedures

Critical Alert Response:
1. Acknowledge immediately
2. Assess severity and impact
3. Notify team if needed
4. Implement fix
5. Verify resolution
6. Document in post-mortem

Warning Alert Response:
1. Review within 1 hour
2. Determine if action needed
3. Implement preventive measures
4. Monitor for recurrence

2.11.9 Best Practices

Alert Fatigue Prevention:
- Tune thresholds to reduce false positives
- Group related alerts
- Provide clear action items
- Regular review of alert effectiveness

Escalation Policy:
- 30 min: Escalate to team lead
- 1 hour: Escalate to manager
- 2 hours: Escalate to director

Post-Incident Review:
- Document root cause
- Update procedures
- Adjust thresholds if needed
- Share learnings with team
```

---

## Appendix A: Complete CLI Reference (Updated)

### A.1 Command Summary

```bash
# Order Management
sds order [options]              # Process single order
sds batch <file>                 # Process batch from JSON

# Queue Management  
sds queue status                 # View queue status
sds queue list                   # List all jobs
sds queue watch                  # Watch queue real-time
sds queue process                # Process next job

# Templates & Sizes
sds templates                    # List available templates
sds sizes --template <type>      # Show graded sizes

# Database
sds db status                    # Check database status
sds db sync                      # Sync to database
sds db watch                     # Watch sync operations
sds db test-order                # Create test order
sds db schema                    # Show schema

# Monitoring
sds monitor status               # System status
sds monitor dashboard            # Open dashboard
sds monitor metrics              # View metrics
sds monitor summary              # Today's summary
sds monitor history              # Historical data
sds monitor alerts               # View alerts
sds monitor health               # Health check

# Quality Control
sds qc validate [options]        # Validate PLT file
sds qc list                      # List QC reports
sds qc report --order <id>       # View QC report

# Scanner Integration
sds scan list                    # List scan files
sds scan validate [options]      # Validate scan
sds scan process [options]       # Process scan
sds scan generate [options]      # Generate test scan

# Server
sds serve [options]              # Start web server

# Testing
sds test                         # Run pipeline test
```

### A.2 Global Options

```bash
--verbose, -v        # Verbose output
--quiet, -q          # Suppress non-error output
--config <path>      # Config file path
--dry-run            # Simulate without executing
--help               # Show help
--version            # Show version
```

---

## Appendix B: Environment Variables

### B.1 Required Variables

```bash
# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key

# Processing
CUTTER_WIDTH_CM=157.48
NESTING_GAP_CM=0.5
```

### B.2 Optional Variables

```bash
# Paths
TEMPLATE_DIR=DS-speciale/inputs/pds/
OUTPUT_DIR=DS-speciale/out/orders/
SPOOL_DIR=DS-speciale/out/cutter_spool/

# Performance
MAX_WORKERS=4
NESTING_TIMEOUT=300
ENABLE_CACHE=true

# Monitoring
METRICS_RETENTION_DAYS=90
ALERT_EMAIL=ops@samedaysuits.com
ENABLE_PAGERDUTY=false

# Development
DEBUG=false
LOG_LEVEL=INFO
TEST_MODE=false
```

---

## Appendix C: File Formats Reference

### C.1 Order JSON Format

```json
{
  "order_id": "string",
  "customer_id": "string",
  "garment_type": "tee|jacket|trousers|cargo",
  "fit_preference": "slim|regular|loose",
  "customer_measurements": {
    "chest": "float (cm)",
    "waist": "float (cm)",
    "hip": "float (cm)",
    "shoulder": "float (cm)",
    "inseam": "float (cm)",
    "arm_length": "float (cm)",
    "torso_length": "float (cm)"
  },
  "created_at": "ISO 8601 timestamp"
}
```

### C.2 Scan JSON Format

```json
{
  "scan_id": "string",
  "timestamp": "ISO 8601",
  "scanner_model": "string",
  "measurements": {
    "chest": "float",
    "waist": "float",
    "hip": "float",
    "shoulder_width": "float",
    "neck": "float",
    "arm_length": "float",
    "inseam": "float",
    "torso_length": "float"
  },
  "quality_score": "float (0.0-1.0)",
  "posture": "normal|forward|back",
  "notes": "string"
}
```

### C.3 QC Report Format

```json
{
  "order_id": "string",
  "timestamp": "ISO 8601",
  "status": "PASSED|FAILED|WARNING",
  "checks": {
    "piece_count": {"status": "OK|FAIL", "count": int, "expected": "string"},
    "geometry": {"status": "OK|FAIL", "invalid_pieces": []},
    "fit_validation": {"status": "OK|FAIL", "mismatches": int},
    "utilization": {"status": "OK|FAIL", "percentage": float},
    "small_pieces": {"status": "OK|FAIL", "count": int}
  },
  "overall_score": "High|Medium|Low",
  "errors": [],
  "warnings": [],
  "recommendations": []
}
```

---

*End of v6.4.2 - Document continues system architecture, testing tools, and alert management documentation*

**Document Version:** 6.4.2  
**Last Updated:** 2026-01-31  
**Author:** Pattern Factory Development Team  
**Previous Version:** 6.4.1
