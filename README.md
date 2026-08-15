# DataFusionX — Milestone 1: Foundation

DataFusionX is a full-stack data engineering and analytics platform foundation. Milestone 1 establishes the containerized architecture connecting a React frontend, a FastAPI backend, and a PostgreSQL database using Docker Compose.

---

## 🚀 Technology Stack

### Frontend
- **Framework**: React 18 + Vite
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Routing**: React Router v6
- **Icons**: Lucide React

### Backend
- **Framework**: Python 3.11 + FastAPI
- **ORM & Migrations**: SQLAlchemy 2.0 + Alembic
- **Validation**: Pydantic v2
- **ASGI Server**: Uvicorn

### Database
- **Database**: PostgreSQL 16 Alpine
- **Persistence**: Named Docker Volume (`postgres_data`)

### DevOps & Containerization
- **Orchestration**: Docker & Docker Compose

---

## 📁 Folder Structure

```text
DataFusionX/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Navbar.tsx
│   │   │   └── StatusCard.tsx
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   └── DashboardPage.tsx
│   │   ├── layouts/
│   │   │   └── MainLayout.tsx
│   │   ├── services/
│   │   │   └── api.ts
│   │   ├── hooks/
│   │   │   └── useHealth.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   ├── App.tsx
│   │   ├── index.css
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── nginx.conf
│   └── Dockerfile
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   └── config.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   └── base.py
│   │   ├── models/
│   │   │   └── __init__.py
│   │   ├── schemas/
│   │   │   └── health.py
│   │   ├── api/
│   │   │   ├── router.py
│   │   │   └── endpoints/
│   │   │       └── health.py
│   │   └── services/
│   │       └── health.py
│   ├── alembic/
│   │   ├── versions/
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
├── data/
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## ⚙️ Requirements & Environment Setup

### System Prerequisites
- Docker & Docker Compose v2+
- Python 3.11+ (for local non-docker execution, optional)
- Node.js 20+ (for local non-docker execution, optional)

### Environment Setup
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Verify `.env` values (defaults pre-configured for Docker Compose):
   ```env
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres
   POSTGRES_DB=datafusionx
   POSTGRES_PORT=5432
   POSTGRES_HOST=postgres
   DATABASE_URL=postgresql://postgres:postgres@postgres:5432/datafusionx
   BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
   VITE_API_BASE_URL=http://localhost:8000
   ```

---

## 🐳 How to Run with Docker Compose

Start all services (`postgres`, `backend`, `frontend`) with automatic builds:

```bash
docker compose up --build
```

To run in detached background mode:
```bash
docker compose up --build -d
```

To stop all services:
```bash
docker compose down
```

---

## 🌐 URLs & Service Endpoints

- **Frontend Application Shell**: [http://localhost:3000](http://localhost:3000)
- **Backend API Base**: [http://localhost:8000](http://localhost:8000)
- **Interactive OpenAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

### Health Check Endpoints

| Endpoint | Method | Expected Output | Description |
| :--- | :--- | :--- | :--- |
| `/health` | `GET` | `{"status": "healthy"}` | FastAPI backend service health check |
| `/api/health/database` | `GET` | `{"status": "healthy", "database": "connected"}` | Tests active PostgreSQL connection via SQLAlchemy |

---

## 🧪 Database Migrations (Alembic)

Run migrations inside the running backend container:

```bash
docker compose exec backend alembic upgrade head
```

To generate new migrations in future development:
```bash
docker compose exec backend alembic revision --autogenerate -m "Migration description"
```
