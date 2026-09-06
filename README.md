# DataFusionX — Enterprise Data Engineering & AI Analytics Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-indigo.svg)](https://opensource.org/licenses/MIT)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-v2+-blue.svg?logo=docker)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg?logo=react)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6.svg?logo=typescript)](https://www.typescriptlang.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg?logo=postgresql)](https://www.postgresql.org/)
[![Celery & Redis](https://img.shields.io/badge/Celery%20%26%20Redis-Distributed-red.svg?logo=redis)](https://docs.celeryq.dev/)
[![Prometheus & Grafana](https://img.shields.io/badge/Monitoring-Prometheus%20%26%20Grafana-orange.svg?logo=grafana)](https://grafana.com/)

**DataFusionX** is a generalized, production-ready, full-stack Data Engineering and Analytics Platform. It unifies multi-tenant data ingestion, interactive Visual DAG pipeline construction, distributed asynchronous ETL execution, star-schema data warehousing, automated cron scheduling, real-time observability, AI Pipeline Copilot, and deterministic **AI Data Quality & Anomaly Intelligence**.

---

## 📑 Table of Contents
- [Platform Architecture](#-platform-architecture)
- [Key Features & Capabilities](#-key-features--capabilities)
- [Technology Stack](#-technology-stack)
- [Subsystem Breakdown](#-subsystem-breakdown)
  - [1. Visual DAG Pipeline Builder](#1-visual-dag-pipeline-builder)
  - [2. Asynchronous ETL Engine & Worker Pool](#2-asynchronous-etl-engine--worker-pool)
  - [3. Multi-Domain Data Warehouse](#3-multi-domain-data-warehouse)
  - [4. AI Pipeline Copilot & Text-to-SQL](#4-ai-pipeline-copilot--text-to-sql)
  - [5. AI Data Quality & Anomaly Intelligence](#5-ai-data-quality--anomaly-intelligence)
  - [6. Monitoring & Observability](#6-monitoring--observability)
- [Repository Structure](#-repository-structure)
- [Quick Start Guide](#-quick-start-guide)
- [Environment Configuration](#-environment-configuration)
- [API & Service Endpoints](#-api--service-endpoints)
- [Running Automated Tests](#-running-automated-tests)
- [License](#-license)

---

## 🏛 Platform Architecture

```
                                  +---------------------------------------+
                                  |         DataFusionX Web UI            |
                                  |  (React 18 + TypeScript + Vite + CSS) |
                                  +-------------------+-------------------+
                                                      |
                                     HTTP REST / WS   | (Port 3000 -> 8000)
                                                      v
+---------------------------------------------------------------------------------------------------+
|                                      FastAPI Backend Gateway                                      |
|  - Multi-tenant JWT Auth & RBAC     - Dynamic Schema Normalizer    - Health & Observability      |
|  - DAG Validation & Compiler        - SQL Safety Guardrails        - AI Service & LLM Grounding  |
+-------------------+-----------------------------+---------------------------------+---------------+
                    |                             |                                 |
         SQLAlchemy |                  Celery Bus | Task Queue                      | Task Schedule
                    v                             v                                 v
+-----------------------------+       +-----------------------+         +-----------------------+
|    PostgreSQL 16 Database   |       |  Redis 7 Cache/Queue  | <-------+  Celery Beat Scheduler|
|  - Multi-Tenant Schema      |       +-----------+-----------+         |  - Cron Schedules     |
|  - Metadata & DAGs          |                   |                     |  - Overlap Protection |
|  - Star Schema Warehouses   |                   v                     +-----------------------+
|  - Execution Audit Logs     |       +-----------------------+
+-----------------------------+       | Celery Worker Engine  |
                                      | - Batch Ingestion     |
                                      | - Transformations     |
                                      | - Data Quality Checks |
                                      | - Star-Schema Loading |
                                      +-----------+-----------+
                                                  | Metrics
                                                  v
                                      +-----------------------+         +-----------------------+
                                      |  Prometheus Metrics   +-------->+   Grafana Dashboards  |
                                      |  (Port 9090)          |         |   (Port 3001)         |
                                      +-----------------------+         +-----------------------+
```

---

## 🌟 Key Features & Capabilities

- 🏢 **Multi-Tenant Enterprise Security**: Strict tenant isolation across organizations, project workspaces, and users with JWT authentication and Role-Based Access Control (RBAC).
- 🔌 **Universal Data Ingestion**: Standardized ingestion and normalization of CSV, JSON, Excel, REST APIs, and external PostgreSQL databases into unified internal DataFrames.
- 🎨 **Visual Drag-and-Drop DAG Builder**: Construct transformation and validation Directed Acyclic Graphs (DAGs) using an interactive canvas powered by ReactFlow.
- ⚡ **Distributed Asynchronous ETL**: Resilient background execution powered by Celery and Redis with live WebSocket status streaming, automatic retries, and failure auditing.
- 🏬 **Pluggable Data Warehouses**: Ingest directly into:
  - **Generic Warehouse**: Dynamic flat tables for arbitrary schemas.
  - **Sales Analytics**: Enterprise star schema (`fact_sales`, `dim_customer`, `dim_product`, `dim_date`).
  - **Manufacturing Analytics**: Production star schema (`fact_production`, `dim_machine`, `dim_plant`, `dim_operator`).
- ⏰ **Automated Pipeline Scheduling**: Celery Beat scheduler with cron expressions, timezone support, and duplicate dispatch protection.
- 🤖 **AI Pipeline Copilot & Text-to-SQL**: Natural language pipeline generation with domain grounding and validated AST SQL generation that prevents unsafe queries.
- 🛡️ **AI Data Quality & Anomaly Intelligence (M13)**:
  - Single Source of Truth architecture with zero client-side calculation.
  - Non-parametric **IQR Outlier Detection** ($Q_1, Q_3, \text{IQR}$, dynamic statistical fences).
  - Generalized missing-value and NULL spike analysis across arbitrary columns.
  - Duplicate row and primary key collision detection.
  - Text casing normalization and regex format anomaly detection.
  - Strict mathematical score reconciliation:
    $$\text{Base Score} = (\text{Completeness} \times 0.35) + (\text{Uniqueness} \times 0.35) + (\text{Validity} \times 0.30)$$
    $$\text{Final Score} = \max(0, \min(100, \text{Base Score} - \text{Total Penalties}))$$
  - LLM-enriched natural language executive summaries and remediation recommendations.
- 📊 **Full-Stack Observability**: Native Prometheus metrics exporter and provisioned Grafana dashboards tracking ETL throughput, execution latency, error rates, and database connections.

---

## 🛠 Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend UI** | React 18, TypeScript, Vite, Tailwind CSS, React Router v6, Lucide React, ReactFlow |
| **Backend Core** | Python 3.11, FastAPI, Uvicorn, Pydantic v2, Pandas, NumPy, Scikit-Learn |
| **Database & ORM** | PostgreSQL 16 Alpine, SQLAlchemy 2.0, Alembic database migrations |
| **Asynchronous Engine** | Celery 5.3, Redis 7 Alpine, WebSockets |
| **Observability** | Prometheus v2.51, Grafana 10.4 |
| **DevOps & Containers** | Docker, Docker Compose, Nginx (Frontend Reverse Proxy) |

---

## 🔍 Subsystem Breakdown

### 1. Visual DAG Pipeline Builder
- Visual node-based workflow builder (`/pipelines/:id/visual`) allowing users to drag nodes from a component drawer onto an infinite canvas.
- Node categories:
  - **Sources**: CSV, JSON, PostgreSQL, REST API.
  - **Transformations**: Remove Duplicates, Fill NULL, Drop NULL, Trim Text, Normalize Text, Rename Columns, Change Types, Filter Rows, Calculate Column.
  - **Validations**: NOT NULL, UNIQUE, RANGE, REGEX rules.
  - **Destinations**: Generic Warehouse, Sales Analytics, Manufacturing Analytics.
- Pre-compilation validation prevents malformed DAGs (missing expressions, cycles, or unreferenced columns) from being scheduled or executed.

### 2. Asynchronous ETL Engine & Worker Pool
- Decouples API request lifecycles from long-running batch ingestion.
- Tasks execute in isolated Celery worker processes with Redis message queuing.
- Real-time execution updates (`PENDING` $\rightarrow$ `RUNNING` $\rightarrow$ `EXTRACTING` $\rightarrow$ `TRANSFORMING` $\rightarrow$ `VALIDATING` $\rightarrow$ `LOADING` $\rightarrow$ `SUCCESS` / `FAILED`) stream over WebSockets to the frontend.

### 3. Multi-Domain Data Warehouse
- **Domain Compatibility Engine**: Validates dataset schemas against target destination schemas prior to execution.
- Prevents domain schema pollution (e.g. attempting to load inventory or sensor data into `Sales Analytics` triggers a guided fallback to `Generic Warehouse`).
- Clean separation of tenant data via organizational scoping.

### 4. AI Pipeline Copilot & Text-to-SQL
- Natural language chat assistant translating user prompts into verified DAG pipeline proposals.
- Grounded in live warehouse metadata to prevent hallucinated columns or invalid table joins.
- AST SQL validation and sanitization ensures queries are bounded (`LIMIT 500`), read-only (`SELECT`), and free from SQL injection attacks.

### 5. AI Data Quality & Anomaly Intelligence
- **Deterministic First**: Statistical profiling and scoring run strictly prior to AI explanation.
- **Atomic State Transitions**: Eliminates stale data leakage across datasets during rapid selection using sequential request IDs.
- **Transparent Score Reconciliation**: Every detected finding includes its exact mathematical deduction (Critical = $-10.0\text{ pts}$, Warning = $-3.0\text{ pts}$, Info = $0.0\text{ pts}$, capped at $-50.0\text{ pts}$ max).
- **Graceful Fallback**: If LLM services are offline, deterministic profiling and scoring remain 100% operational with an `"AI explanation unavailable"` notice.

### 6. Monitoring & Observability
- Native `/metrics` Prometheus endpoint exposing latency histograms, active worker counts, and pipeline execution success/failure counters.
- Automated Grafana dashboard provisioning with pre-configured data sources and visualization panels.

---

## 📁 Repository Structure

```text
DataFusionX/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── router.py                  # API router aggregation
│   │   │   └── endpoints/                 # REST endpoints (auth, sources, pipelines, ai, warehouse, etc.)
│   │   ├── core/                          # Config, Celery app, security, and metrics
│   │   ├── db/                            # SQLAlchemy session and model base
│   │   ├── models/                        # ORM models (User, Org, Pipeline, DataSource, Warehouse, etc.)
│   │   ├── schemas/                       # Pydantic v2 schemas (Auth, ETL, AI, DataQuality, etc.)
│   │   ├── services/                      # Core business logic
│   │   │   ├── ai_service.py              # AI Copilot & Data Quality LLM orchestration
│   │   │   ├── dag_compiler.py            # Visual DAG compilation and graph verification
│   │   │   ├── etl_engine.py              # Batch extraction, transformation, and validation
│   │   │   ├── profiling.py               # Statistical profiling, IQR outlier & quality scoring engine
│   │   │   ├── sql_safety.py              # AST SQL validation & sanitization
│   │   │   └── warehouse.py               # Star-schema & generic warehouse loaders
│   │   ├── tasks/                         # Celery background tasks
│   │   └── tests/                         # Pytest test suites (Unit, Integration, Generalization)
│   ├── alembic/                           # Database migration scripts
│   ├── requirements.txt                   # Backend Python dependencies
│   └── Dockerfile                         # Python 3.11 container image
├── frontend/
│   ├── src/
│   │   ├── components/                    # UI components (Sidebar, Navbar, StatusCard, Toast, DAG drawers)
│   │   ├── pages/                         # Application routes
│   │   │   ├── DashboardPage.tsx          # Platform overview & metrics
│   │   │   ├── AIDataQualityPage.tsx      # AI Data Quality & Anomaly Intelligence (M13)
│   │   │   ├── AICopilotPage.tsx          # Natural language pipeline generator & SQL assistant
│   │   │   ├── VisualPipelineBuilderPage.tsx # ReactFlow DAG pipeline builder
│   │   │   ├── PipelineExecutionsPage.tsx # Live pipeline execution history & WebSocket logs
│   │   │   ├── WarehouseDashboardPage.tsx # Star-schema & generic warehouse explorer
│   │   │   └── DataSourcesListPage.tsx    # Dataset ingestion & management
│   │   ├── services/                      # Axios API clients
│   │   └── types/                         # TypeScript interfaces
│   ├── nginx.conf                         # Production Nginx reverse proxy configuration
│   ├── package.json                       # Frontend dependencies & scripts
│   └── Dockerfile                         # Multi-stage Node build + Nginx alpine production image
├── docker/
│   ├── prometheus.yml                     # Prometheus scraping configuration
│   └── grafana/                           # Grafana dashboards & datasource provisioning
├── docker-compose.yml                     # Multi-container service orchestrator
└── README.md
```

---

## 🚀 Quick Start Guide

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) (v24.0+)
- [Docker Compose](https://docs.docker.com/compose/) (v2.0+)

### 1. Clone & Configure Environment
```bash
git clone https://github.com/Veeresh502/DataFusionX.git
cd DataFusionX

# Copy sample environment variables
cp .env.example .env
```

### 2. Launch All Services with Docker Compose
```bash
# Build and start all containers in detached mode
docker compose up -d --build
```

### 3. Verify Container Health
```bash
docker compose ps
```
All containers should report `Up` / `healthy`:
- `datafusionx-frontend` (Port 3000)
- `datafusionx-backend` (Port 8000)
- `datafusionx-postgres` (Port 5432)
- `datafusionx-redis` (Port 6379)
- `datafusionx-celery-worker`
- `datafusionx-celery-beat`
- `datafusionx-prometheus` (Port 9090)
- `datafusionx-grafana` (Port 3001)

### 4. Run Database Migrations
```bash
docker compose exec backend alembic upgrade head
```

### 5. Access the Platform
- **Web Application**: [http://localhost:3000](http://localhost:3000)
- **API Documentation (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Grafana Dashboards**: [http://localhost:3001](http://localhost:3001) *(Login: `admin` / `admin`)*
- **Prometheus UI**: [http://localhost:9090](http://localhost:9090)

---

## ⚙️ Environment Configuration

Default configuration parameters in `.env`:

```ini
# PostgreSQL Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=datafusionx
POSTGRES_PORT=5432
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/datafusionx

# Redis & Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Security & Authentication
JWT_SECRET=super_secret_jwt_key_change_me_in_production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]

# Frontend API Configuration
VITE_API_BASE_URL=http://localhost:8000
```

---

## 🌐 API & Service Endpoints

| Service / Route | Method | Description |
| :--- | :---: | :--- |
| `/health` | `GET` | System health check (DB, Redis, Celery, Version) |
| `/metrics` | `GET` | Prometheus telemetry & operational metrics |
| `/api/auth/register` | `POST` | Organization and administrator registration |
| `/api/auth/login` | `POST` | User authentication & JWT bearer token issue |
| `/api/data-sources/` | `GET/POST` | Ingest and list datasets (CSV, JSON, SQL) |
| `/api/data-sources/{id}/profile` | `GET` | Statistical column profiling & schema inspection |
| `/api/pipelines/` | `GET/POST` | Manage ETL pipelines and DAG specifications |
| `/api/pipelines/{id}/execute` | `POST` | Trigger asynchronous pipeline execution |
| `/api/pipelines/{id}/executions` | `GET` | Retrieve execution history and record counts |
| `/api/warehouse/tables` | `GET` | Query warehouse tables across domains |
| `/api/ai/data-quality/{source_id}` | `GET` | Deterministic Data Quality & Anomaly Intelligence (M13) |
| `/api/ai/copilot/generate-pipeline` | `POST` | Generate verified ETL DAG from natural language |
| `/api/ai/copilot/text-to-sql` | `POST` | AST-validated, schema-grounded natural language SQL |

---

## 🧪 Running Automated Tests

DataFusionX includes a rigorous Pytest suite covering unit functionality, multi-tenant isolation, pipeline compilers, transformation engines, and generalized data quality lifecycle tests:

```bash
# Run full automated test suite inside backend container
docker compose exec backend pytest -v

# Or run specific test modules
docker compose exec backend pytest -v app/tests/test_ai_data_quality.py app/tests/test_generalized_data_quality_lifecycle.py
```

To run tests locally using Python virtual environment:
```powershell
cd backend
$env:DATABASE_URL="postgresql://postgres:postgres@localhost:5432/datafusionx"
python -m pytest -v app/tests/
```

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
