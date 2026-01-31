# SameDaySuits Operations Manual Updates

## Version 6.4.2 - Database, Queue & System Architecture

This document contains incremental updates to be integrated into SUIT_AI_Master_Operations_Manual_v6.4 after v6.4.1 content.

---

## Table of Contents (v6.4.2)

8. [Database Integration (Supabase)](#8-database-integration-supabase)
9. [Cutter Queue Management](#9-cutter-queue-management)
10. [Pattern Scaling & Graded Sizes](#10-pattern-scaling--graded-sizes)
11. [Real-time Systems (WebSocket)](#11-real-time-systems-websocket)
12. [System Architecture & Data Flow](#12-system-architecture--data-flow)
13. [Testing & Development Tools](#13-testing--development-tools)
14. [Alert Management System](#14-alert-management-system)

---

## 8. Database Integration (Supabase)

### 8.1 Overview

The Pattern Factory integrates with Supabase for persistent order storage and synchronization. The system supports both local Supabase instances (via Docker) and cloud-hosted Supabase projects.

### 8.2 Architecture

**Two-Layer Storage:**
1. **Local File System**: Fast, immediate storage during processing
2. **Supabase Database**: Persistent, queryable order history

**Sync Strategy**:
- Orders created locally first (immediate response)
- Background sync to Supabase (async)
- Conflict resolution: Local wins, Supabase is backup

### 8.3 Database Schema

**Core Tables:**

```sql
-- Orders table
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id VARCHAR(100) UNIQUE NOT NULL,
    customer_id VARCHAR(100),
    garment_type VARCHAR(50),
    fit_preference VARCHAR(50),
    status VARCHAR(50) DEFAULT 'pending',
    measurements JSONB,
    scaling_factors JSONB,
    fabric_required_cm FLOAT,
    utilization_percent FLOAT,
    plt_file_path VARCHAR(500),
    metadata_path VARCHAR(500),
    qc_report_path VARCHAR(500),
    qc_status VARCHAR(50),
    qc_score VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- Customers table
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200),
    email VARCHAR(200),
    phone VARCHAR(50),
    default_measurements JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Production Logs table
CREATE TABLE production_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id VARCHAR(100) REFERENCES orders(order_id),
    stage VARCHAR(100),
    status VARCHAR(50),
    details JSONB,
    processing_time_ms INTEGER,
    timestamp TIMESTAMP DEFAULT NOW()
);
```

### 8.4 Configuration

**Environment Variables:**
```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key

# Local Supabase (Docker)
SUPABASE_LOCAL_URL=http://localhost:54321
SUPABASE_LOCAL_KEY=your-local-key
```

**Configuration File** (`config/supabase.yaml`):
```yaml
supabase:
  mode: local  # or 'cloud'
  local:
    url: http://localhost:54321
    anon_key: ${SUPABASE_LOCAL_KEY}
  cloud:
    url: ${SUPABASE_URL}
    anon_key: ${SUPABASE_KEY}
    service_key: ${SUPABASE_SERVICE_KEY}
  
  sync:
    enabled: true
    interval_seconds: 30
    batch_size: 10
    retry_attempts: 3
    
  tables:
    orders: orders
    customers: customers
    production_logs: production_logs
```

### 8.5 Key Classes and Methods

**OrderDatabase Class:**
```python
from database_integration import OrderDatabase

# Initialize
db = OrderDatabase()

# Create order
db.create_order(order_data: dict) -> str

# Get order
db.get_order(order_id: str) -> dict

# Update order status
db.update_order_status(order_id: str, status: str, details: dict)

# List orders
db.list_orders(status: str = None, limit: int = 100) -> list

# Sync local to remote
db.sync_pending_orders()
```

**OrderSyncService Class:**
```python
from database_integration import OrderSyncService

# Initialize sync service
sync_service = OrderSyncService(db)

# Start background sync
sync_service.start_sync(interval_seconds=30)

# Stop sync
sync_service.stop_sync()

# Force immediate sync
sync_service.sync_now()
```

### 8.6 CLI Commands

```bash
# Check database status
sds db status

# Sync local orders to database
sds db sync

# Watch sync operations (real-time)
sds db watch

# Create test order in database
sds db test-order

# Display database schema
sds db schema
```

### 8.7 Sync Behavior

**Automatic Sync Triggers:**
1. Order created locally → Queued for sync
2. Order status changed → Immediate sync attempt
3. Order completed → Priority sync
4. Periodic sync every 30 seconds (configurable)

**Sync Status States:**
- `local_only`: Created locally, not yet synced
- `syncing`: Currently being synced
- `synced`: Successfully synced to Supabase
- `failed`: Sync failed, will retry
- `conflict`: Conflict detected, requires manual resolution

### 8.8 Data Retention

**Local Files:**
- PLT files: Retained indefinitely (production artifacts)
- Metadata: Retained indefinitely
- QC reports: Retained indefinitely
- Temp files: Cleaned after 7 days

**Supabase:**
- Orders: Retained indefinitely
- Production logs: Archived after 90 days
- Sync logs: Retained 30 days

### 8.9 New Section: 2.8 Database Integration

```
2.8 Database Integration (Supabase)

2.8.1 Overview
The Pattern Factory uses Supabase for persistent order storage, providing
queryable order history, customer management, and production analytics.
Supports both local (Docker) and cloud-hosted instances.

2.8.2 Database Modes

Local Mode (Development):
- Runs via Docker Compose
- URL: http://localhost:54321
- Best for: Development, testing, offline work
- Data persistence: Docker volumes

Cloud Mode (Production):
- Hosted on Supabase Cloud
- Managed infrastructure
- Best for: Production, multi-user access
- Automatic backups included

2.8.3 Connection Configuration
Configuration via environment variables:
- SUPABASE_URL / SUPABASE_LOCAL_URL
- SUPABASE_KEY / SUPABASE_LOCAL_KEY
- SUPABASE_SERVICE_KEY (for admin operations)

2.8.4 Schema Design

Orders Table:
- Primary order storage
- Tracks status, measurements, file paths
- JSONB fields for flexible metadata
- Timestamps for audit trail

Customers Table:
- Customer profile storage
- Default measurements
- Contact information

Production Logs Table:
- Detailed processing logs
- Per-stage timing
- Error tracking
- Supports debugging and optimization

2.8.5 Sync Architecture

Two-Layer Storage:
1. Local filesystem (fast, immediate)
2. Supabase (persistent, queryable)

Sync Strategy:
- Write-through: Local first, async to Supabase
- Conflict resolution: Local wins
- Retry logic: 3 attempts with exponential backoff
- Batch processing: 10 orders per sync cycle

2.8.6 CLI Reference
See Section 5.3 (CLI Reference) for db commands.

2.8.7 Monitoring
Check sync status via:
- sds db status (CLI)
- /api/metrics endpoint (API)
- Dashboard sync indicator (Web UI)

2.8.8 Troubleshooting

Sync Failures:
- Check network connectivity
- Verify Supabase credentials
- Review sync logs in production_logs table
- Manual retry: sds db sync

Missing Orders:
- Check local directory: DS-speciale/out/orders/
- Verify order_id format
- Check Supabase permissions

2.8.9 Backup Strategy
Local: Filesystem backups
Cloud: Supabase automatic daily backups
Manual: pg_dump for complete database export
```

---

## 9. Cutter Queue Management

### 9.1 Overview

The Cutter Queue manages the flow of orders to physical cutting machines. It provides job prioritization, spool management, and status tracking for production cutting operations.

### 9.2 Queue Architecture

**Components:**
1. **Job Queue**: In-memory priority queue
2. **Spool Directory**: Filesystem-based job storage
3. **Status Tracking**: Job state machine
4. **Priority System**: Urgent/High/Normal/Low priorities

### 9.3 Job Lifecycle

```
PENDING → QUEUED → PROCESSING → COMPLETED
   ↓         ↓          ↓           ↓
Cancel   Pause     Error      Archived
```

**States:**
- `PENDING`: Order submitted, awaiting queue
- `QUEUED`: In queue, waiting for cutter
- `PROCESSING`: Currently being cut
- `COMPLETED`: Successfully cut
- `FAILED`: Error during cutting
- `CANCELLED`: Cancelled before processing
- `PAUSED`: Temporarily paused

### 9.4 Priority System

| Priority | Value | Use Case |
|----------|-------|----------|
| URGENT | 1 | Rush orders, same-day delivery |
| HIGH | 2 | Priority customers |
| NORMAL | 3 | Standard orders (default) |
| LOW | 4 | Bulk orders, non-urgent |

**Priority Calculation:**
```python
priority_score = base_priority + time_penalty - customer_tier_bonus
```

### 9.5 Spool Management

**Spool Directory Structure:**
```
DS-speciale/out/cutter_spool/
├── pending/
│   ├── <job_id>.json        # Job metadata
│   └── <job_id>.plt         # PLT file (symlink)
├── processing/
│   └── <job_id>.json        # Currently cutting
├── completed/
│   └── <job_id>.json        # Successfully cut
└── failed/
    └── <job_id>.json        # Failed jobs
```

**Spool File Format:**
```json
{
  "job_id": "JOB-20260131-001",
  "order_id": "ORDER-20260131-001",
  "priority": 2,
  "status": "QUEUED",
  "garment_type": "jacket",
  "fabric_required_cm": 53.8,
  "plt_file": ".../order.plt",
  "created_at": "2026-01-31T10:00:00Z",
  "queued_at": "2026-01-31T10:00:05Z",
  "started_at": null,
  "completed_at": null,
  "cutter_id": null,
  "operator": null,
  "notes": ""
}
```

### 9.6 Key Classes and Methods

**CutterQueue Class:**
```python
from cutter_queue import CutterQueue, JobPriority, JobStatus

# Initialize queue
queue = CutterQueue(spool_dir="DS-speciale/out/cutter_spool")

# Submit job
job_id = queue.submit_job(
    order_id="ORDER-001",
    plt_file="path/to/file.plt",
    priority=JobPriority.NORMAL,
    garment_type="jacket",
    fabric_required_cm=53.8
)

# Get next job
job = queue.get_next_job()

# Update job status
queue.update_job_status(job_id, JobStatus.PROCESSING)
queue.update_job_status(job_id, JobStatus.COMPLETED)

# List jobs
pending = queue.list_jobs(status=JobStatus.QUEUED)
all_jobs = queue.list_jobs()

# Cancel job
queue.cancel_job(job_id)
```

### 9.7 CLI Commands

```bash
# View queue status
sds queue status

# List all jobs
sds queue list

# Watch queue (real-time updates)
sds queue watch

# Process next job in queue
sds queue process

# Cancel specific job
sds queue cancel <job_id>

# Pause queue
sds queue pause

# Resume queue
sds queue resume

# Requeue failed job
sds queue retry <job_id>
```

### 9.8 API Endpoints

```
GET /queue/status
  Returns current queue status:
  {
    "pending": 5,
    "processing": 1,
    "completed": 150,
    "failed": 3,
    "paused": false
  }

GET /queue/jobs?status=<status>
  List jobs with optional status filter

GET /queue/jobs/{job_id}
  Get specific job details

POST /queue/jobs/{job_id}/process
  Mark job as processing (cutter started)

POST /queue/jobs/{job_id}/complete
  Mark job as completed

POST /queue/process-next
  Process next highest priority job
```

### 9.9 Integration with Production Pipeline

**Automatic Queue Submission:**
When an order completes processing:
1. PLT file generated
2. QC validation passed
3. Job automatically submitted to cutter queue
4. Operator notified via dashboard

**Operator Workflow:**
1. Check queue status: `sds queue status`
2. Load fabric on cutter
3. Process next job: `sds queue process-next`
4. PLT file automatically sent to cutter
5. Mark complete after cutting

### 9.10 New Section: 2.9 Cutter Queue Management

```
2.9 Cutter Queue Management

2.9.1 Overview
The Cutter Queue manages the flow of production orders to physical cutting
machines. Provides job prioritization, status tracking, and operator workflow
management for the cutting stage of production.

2.9.2 Queue Components

Job Queue:
- In-memory priority queue (heapq)
- Prioritizes by: Priority level → Submission time
- Thread-safe for concurrent access

Spool Directory:
- Filesystem-based persistence
- Organized by status: pending/processing/completed/failed
- JSON metadata + PLT file references

Status Tracking:
- State machine: PENDING → QUEUED → PROCESSING → COMPLETED
- Alternative states: FAILED, CANCELLED, PAUSED
- Timestamp tracking for each state transition

2.9.3 Priority System

Four Priority Levels:
1. URGENT (1): Rush orders, same-day requirements
2. HIGH (2): VIP customers, priority shipping
3. NORMAL (3): Standard orders (default)
4. LOW (4): Bulk orders, future delivery

Priority Calculation:
Base priority value + time in queue (aging) - customer tier bonus

2.9.4 Job Lifecycle

Submission:
- Order completes QC validation
- Job automatically created and queued
- Metadata written to spool/pending/
- Notification sent to operators

Processing:
- Operator loads fabric
- Retrieves next job from queue
- PLT file transferred to cutter
- Status updated to PROCESSING

Completion:
- Pieces cut and verified
- Status updated to COMPLETED
- Job moved to spool/completed/
- Order marked complete in database

Failure Handling:
- Errors logged with details
- Job moved to spool/failed/
- Operator can retry or cancel
- Automatic retry for transient errors

2.9.5 Operator Workflow

Daily Operations:
1. Check queue status (sds queue status)
2. Monitor dashboard for new jobs
3. Load appropriate fabric
4. Process next job (sds queue process-next)
5. Verify cut pieces
6. Mark complete and stage for sewing

Priority Overrides:
- Operators can manually prioritize jobs
- Rush orders flagged in dashboard
- Queue can be paused/resumed

2.9.6 CLI Reference
See Section 5.3 (CLI Reference) for queue commands.

2.9.7 API Reference
See Section 3.2 (API Reference) for queue endpoints.

2.9.8 Monitoring

Queue Metrics:
- Jobs pending/processing/completed
- Average wait time
- Priority distribution
- Failure rate

Available via:
- sds monitor status (CLI)
- /api/metrics endpoint (API)
- Dashboard queue widget (Web)

2.9.9 Troubleshooting

Job Stuck in Processing:
- Check cutter connectivity
- Verify PLT file exists
- Review cutter logs
- Manually mark failed if cutter error

Queue Backup:
- Check operator capacity
- Verify fabric availability
- Consider adding cutter shifts
- Review priority distribution

Failed Jobs:
- Check error message in job metadata
- Verify PLT file integrity
- Review QC report for issues
- Retry or regenerate order
```

---

## 10. Pattern Scaling & Graded Sizes

### 10.1 Overview

Pattern scaling adjusts base garment templates to fit individual customer measurements. The system supports both proportional scaling and graded size extraction from PDS files.

### 10.2 Scaling Architecture

**Two-Stage Process:**
1. **Size Selection**: Choose base template (XS-4XL)
2. **Fine Scaling**: Apply X/Y scaling factors

**Input Measurements:**
- Chest circumference
- Waist circumference  
- Hip circumference
- Shoulder width
- Inseam length
- Arm length
- Torso length

### 10.3 Size Chart

**Standard Size Ranges (Chest):**

| Size | Chest (cm) | Chest (in) | Scale Base |
|------|------------|------------|------------|
| XS | < 86 | < 34 | XS template |
| S | 86-94 | 34-37 | S template |
| M | 94-102 | 37-40 | M template |
| L | 102-110 | 40-43 | L template |
| XL | 110-118 | 43-46 | XL template |
| 2XL | 118-126 | 46-50 | 2XL template |
| 3XL | 126-134 | 50-53 | 3XL template |
| 4XL | > 134 | > 53 | 4XL template |

**Note:** Size determined by chest measurement, then adjusted for other measurements.

### 10.4 Scaling Calculation

**Width Scaling (X-axis):**
```python
# Calculate width scale based on chest
width_scale = customer_chest / base_chest

# Clamp to reasonable range
width_scale = max(0.85, min(1.15, width_scale))

# Apply to pattern contours
scaled_contour = contour.scale_x(width_scale)
```

**Length Scaling (Y-axis):**
```python
# Calculate length scale based on inseam/arm/torso
length_scale = customer_inseam / base_inseam

# Clamp to reasonable range  
length_scale = max(0.85, min(1.15, length_scale))

# Apply to pattern contours
scaled_contour = contour.scale_y(length_scale)
```

**Proportional Scaling:**
```python
# Some pieces scale proportionally (buttons, pockets)
if piece.type in ['button', 'pocket', 'detail']:
    piece.scale = min(width_scale, length_scale)
```

### 10.5 Graded Size Extraction

**From PDS Files:**
```python
from graded_size_extractor import extract_graded_info

# Extract all sizes from PDS
sizes = extract_graded_info(pds_file_path)

# Returns:
{
  "XS": {"chest": 86, "waist": 72, "hip": 88},
  "S": {"chest": 94, "waist": 78, "hip": 94},
  "M": {"chest": 102, "waist": 86, "hip": 100},
  "L": {"chest": 110, "waist": 94, "hip": 108},
  "XL": {"chest": 118, "waist": 102, "hip": 116}
}
```

**Finding Best Size:**
```python
from graded_size_extractor import find_best_size

best_size = find_best_size(
    customer_measurements={"chest": 105, "waist": 90},
    graded_sizes=sizes
)
# Returns: "L" (closest match)
```

### 10.6 Key Classes and Methods

**PatternScaler Class:**
```python
from pattern_scaler import PatternScaler, SizeChart

# Initialize with size chart
scaler = PatternScaler(size_chart=SizeChart.STANDARD)

# Calculate scales for customer
scales = scaler.calculate_scales(
    customer_measurements={
        "chest": 102,
        "waist": 88,
        "hip": 100,
        "inseam": 81,
        "arm_length": 66
    },
    base_size="L"
)
# Returns: {"scale_x": 1.0, "scale_y": 0.958}

# Scale pattern contours
scaled_contours = scaler.scale_contours(
    contours=original_contours,
    scale_x=scales["scale_x"],
    scale_y=scales["scale_y"]
)
```

### 10.7 CLI Commands

```bash
# Show size chart
sds sizes --template jacket

# Show graded sizes for template
sds sizes --template trousers

# Output includes:
# - Size ranges for each measurement
# - Recommended measurements per size
# - Scaling recommendations
```

### 10.8 Scaling Constraints

**Minimum/Maximum Scales:**
- Width (X): 0.85 to 1.15 (±15%)
- Length (Y): 0.85 to 1.15 (±15%)

**Rationale:**
- Beyond 15% distorts garment proportions
- May affect fit, comfort, and aesthetics
- Extreme scaling requires pattern redrafting

**Exception Handling:**
- If calculated scale exceeds limits:
  1. Clamp to limit value
  2. Log warning
  3. Recommend next size up/down
  4. Notify operator of adjustment

### 10.9 New Section: 2.10 Pattern Scaling

```
2.10 Pattern Scaling & Graded Sizes

2.10.1 Overview
Pattern scaling adjusts base garment templates to match individual customer
measurements. Uses a two-stage approach: size selection then fine-tuning
with X/Y scaling factors.

2.10.2 Size Selection

Base Template Selection:
Determined primarily by chest measurement:
- XS: < 86 cm
- S: 86-94 cm
- M: 94-102 cm
- L: 102-110 cm
- XL: 110-118 cm
- 2XL: 118-126 cm
- 3XL: 126-134 cm
- 4XL: > 134 cm

Secondary Considerations:
- Waist measurement (for trousers)
- Hip measurement (for bottoms)
- Height estimate (affects length)

2.10.3 Scaling Methodology

Width Scaling (X-axis):
- Based on: chest, waist, hip, shoulder measurements
- Formula: customer_measurement / base_measurement
- Range: 0.85 to 1.15 (clamped)
- Application: Applied to pattern width dimensions

Length Scaling (Y-axis):
- Based on: inseam, arm_length, torso measurements
- Formula: customer_measurement / base_measurement
- Range: 0.85 to 1.15 (clamped)
- Application: Applied to pattern length dimensions

Proportional Pieces:
- Buttons, pockets, details scale uniformly
- Scale factor: minimum of X and Y scales
- Maintains visual proportions

2.10.4 Graded Size Extraction

From PDS Templates:
- Extracts all available sizes from graded patterns
- Maps size names to measurement tables
- Supports: XS, S, M, L, XL, 2XL, 3XL, 4XL
- Fallback to standard chart if extraction fails

Best Size Algorithm:
1. Calculate difference for each measurement
2. Weight by measurement importance (chest = 40%, waist = 30%, etc.)
3. Select size with minimum weighted difference
4. Apply fine scaling to match exactly

2.10.5 Scaling Constraints

Safety Limits:
- Minimum scale: 0.85 (15% reduction)
- Maximum scale: 1.15 (15% increase)
- Rationale: Prevents distortion, maintains proportions

Exceptions:
- Extreme sizes may require next size template
- Operator notification on clamping
- QC validation flags unusual scaling

2.10.6 CLI Reference
See Section 5.3 (CLI Reference) for sizes command.

2.10.7 API Integration

Automatic Scaling:
- Applied during order processing
- Uses customer measurements from order
- Logs scaling factors in metadata
- Validates with QC system

Manual Override:
- Operators can specify base size
- Custom scaling factors supported
- Requires manager approval for extreme values

2.10.8 Quality Assurance

Fit Validation:
- QC system compares scaled pattern to measurements
- Warns if deviations >20%
- Validates scaling factors in safe range
- Checks for extreme aspect ratios

Measurement Mismatch Handling:
- Normal: Some deviation expected (half vs full circumference)
- Warning: >20% deviation flagged for review
- Error: >30% deviation triggers rejection
```

---

## 11. Real-time Systems (WebSocket)

### 11.1 Overview

The Pattern Factory provides real-time updates via WebSocket connections for live dashboard updates, progress tracking, and system notifications.

### 11.2 WebSocket Architecture

**Connection Endpoint:**
```
ws://localhost:8000/ws
wss://production.samedaysuits.com/ws (SSL)
```

**Connection Flow:**
1. Client connects to `/ws`
2. Server accepts and registers client
3. Bidirectional communication established
4. Server pushes updates as events occur
5. Client can send commands/acknowledgments

### 11.3 Message Types

**Server → Client (Updates):**

```json
// Order Status Update
{
  "type": "order_update",
  "order_id": "ORDER-001",
  "status": "processing",
  "stage": "nesting",
  "progress": 65,
  "timestamp": "2026-01-31T10:30:00Z"
}

// Queue Update
{
  "type": "queue_update",
  "pending": 5,
  "processing": 1,
  "completed": 150,
  "timestamp": "2026-01-31T10:30:00Z"
}

// Alert
{
  "type": "alert",
  "alert_id": "ALT-001",
  "severity": "warning",
  "message": "Low fabric utilization detected",
  "timestamp": "2026-01-31T10:30:00Z"
}

// System Status
{
  "type": "system_status",
  "status": "healthy",
  "active_orders": 3,
  "api_latency_ms": 23
}
```

**Client → Server (Commands):**

```json
// Subscribe to order
{
  "action": "subscribe",
  "order_id": "ORDER-001"
}

// Acknowledge alert
{
  "action": "ack_alert",
  "alert_id": "ALT-001"
}

// Ping (keepalive)
{
  "action": "ping"
}
```

### 11.4 Dashboard Integration

**Real-time Widgets:**
- Order progress bars
- Queue status counters
- Alert notifications
- System health indicators
- Live fabric utilization charts

**Update Frequency:**
- Order progress: Every 5 seconds during processing
- Queue status: Every 10 seconds
- Alerts: Immediate
- System status: Every 30 seconds

### 11.5 Implementation Example

**JavaScript Client:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = function() {
  console.log('Connected to Pattern Factory');
  // Subscribe to specific order
  ws.send(JSON.stringify({
    action: 'subscribe',
    order_id: 'ORDER-001'
  }));
};

ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case 'order_update':
      updateProgressBar(data.order_id, data.progress);
      break;
    case 'alert':
      showNotification(data.severity, data.message);
      break;
    case 'queue_update':
      updateQueueCounters(data);
      break;
  }
};

ws.onerror = function(error) {
  console.error('WebSocket error:', error);
};
```

**Python Client:**
```python
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    if data['type'] == 'order_update':
        print(f"Order {data['order_id']}: {data['progress']}%")

ws = websocket.WebSocketApp("ws://localhost:8000/ws",
                            on_message=on_message)
ws.run_forever()
```

### 11.6 Connection Management

**Keepalive:**
- Ping every 30 seconds
- Connection timeout: 60 seconds
- Auto-reconnect with exponential backoff

**Client Limits:**
- Max 100 concurrent connections
- Rate limit: 10 messages/second per client
- Subscription limit: 50 orders per client

### 11.7 New Section: 3.4 WebSocket API

```
3.4 WebSocket API

3.4.1 Overview
The WebSocket API provides real-time bidirectional communication for 
live dashboard updates, order progress tracking, and system notifications.

3.4.2 Connection

Endpoint: ws://<host>:8000/ws
Protocol: WebSocket (RFC 6455)
Authentication: Same as REST API (token in query string or header)

Connection Lifecycle:
1. Client initiates WebSocket handshake
2. Server validates authentication
3. Connection established
4. Bidirectional messaging enabled
5. Auto-close on inactivity (60s timeout)

3.4.3 Message Format

All messages are JSON objects with required fields:
- type: Message category
- timestamp: ISO 8601 timestamp
- payload: Message-specific data

3.4.4 Server Messages (Server → Client)

order_update:
- Sent: During order processing stages
- Fields: order_id, status, stage, progress (0-100)
- Frequency: Every 5 seconds during processing

queue_update:
- Sent: When queue status changes
- Fields: pending, processing, completed counts
- Frequency: Every 10 seconds or on change

alert:
- Sent: When alert triggered
- Fields: alert_id, severity, message
- Frequency: Immediate

system_status:
- Sent: Periodic health updates
- Fields: status, active_orders, api_latency_ms
- Frequency: Every 30 seconds

3.4.5 Client Messages (Client → Server)

subscribe:
- Purpose: Subscribe to order updates
- Fields: action="subscribe", order_id
- Response: Confirmation or error

ack_alert:
- Purpose: Acknowledge alert receipt
- Fields: action="ack_alert", alert_id
- Response: None

ping:
- Purpose: Keep connection alive
- Fields: action="ping"
- Response: pong message

3.4.6 Error Handling

Connection Errors:
- Automatic reconnection with exponential backoff
- Max retry interval: 30 seconds
- Fallback to polling if WebSocket unavailable

Message Errors:
- Invalid JSON: Connection closed with code 1003
- Unauthorized: Connection closed with code 1008
- Rate limit: Message dropped, warning sent

3.4.7 Rate Limiting

Connection Limits:
- Max connections: 100 per server
- Max subscriptions: 50 per connection
- Message rate: 10/second per client

3.4.8 Security

Authentication:
- Token-based (same as REST API)
- Passed in query string: ?token=<jwt>
- Or in Sec-WebSocket-Protocol header

Authorization:
- Roles checked for subscription permissions
- Managers: All orders
- Operators: Assigned orders only
```

---

*End of Chunk 1 - Continue with sections 12-14 in next chunk*
