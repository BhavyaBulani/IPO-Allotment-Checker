# IPO Allotment Checker

A full-stack web application that automates IPO allotment status verification for multiple clients across all major Indian registrars — **Link Intime**, **KFin Technologies**, **Bigshare**, and **MUFG**. Built for brokers, sub-brokers, and individual investors who need to check allotment results at scale.

---

## Features

- 🔍 **Single & Bulk Client Lookup** — Check one PAN or upload a CSV/Excel sheet with multiple clients
- 📋 **Multi-IPO Selection** — Query a client against multiple IPOs in a single run
- 🤖 **Auto-CAPTCHA Support** — Built-in automatic CAPTCHA solver with manual fallback
- 📡 **Real-Time Progress Tracking** — Live progress bar and per-client status updates
- 📊 **Results Dashboard** — Color-coded summary with allotment counts and quick filters
- 📁 **Session History** — Browse and re-download past check results
- 🔄 **Auto IPO Sync** — Automatically detects and seeds live IPOs from the web on startup
- 🛡️ **Rate Limiting** — Per-registrar rate limiting to avoid IP bans
- 🐳 **Docker Support** — One-command MySQL setup via Docker Compose

---

## Tech Stack

### Backend
| Technology | Role |
|---|---|
| **FastAPI** | REST API framework |
| **SQLAlchemy** + **Alembic** | ORM and database migrations |
| **MySQL** | Primary data store |
| **Playwright** | Headless browser scraping for registrar sites |
| **PyMySQL** | MySQL driver |
| **python-dotenv** | Environment variable management |

### Frontend
| Technology | Role |
|---|---|
| **React 19** | UI framework |
| **Vite** | Build tool & dev server |
| **TailwindCSS** | Utility-first styling |
| **Axios** | HTTP client |
| **lucide-react** | Icon library |
| **react-dropzone** | File upload with drag & drop |
| **react-router-dom** | Client-side routing |

---

## Project Structure

```
project_ipo/
├── IPO_Checker/
│   ├── backend/
│   │   ├── api/
│   │   │   ├── endpoints/         # Route handlers (ipos, check, progress, results, history, etc.)
│   │   │   └── router.py          # Central API router
│   │   ├── db/
│   │   │   ├── models.py          # SQLAlchemy ORM models
│   │   │   └── session.py         # DB engine, pool config & slow query monitoring
│   │   ├── registrar_services/    # Registrar-specific scrapers
│   │   │   ├── link_intime.py
│   │   │   ├── kfin.py
│   │   │   ├── bigshare.py
│   │   │   ├── mufg.py
│   │   │   ├── captcha_manager.py
│   │   │   └── orchestrator.py
│   │   ├── ipo_sync/
│   │   │   └── auto_detect.py     # Web-based IPO auto-discovery
│   │   ├── schemas/
│   │   │   └── input.py           # Pydantic request schemas
│   │   ├── alembic/               # Database migrations
│   │   ├── jobs/                  # Background job (purge old records)
│   │   ├── queue/
│   │   │   └── worker.py          # Async task queue worker
│   │   ├── scripts/               # Utility scripts (backup, etc.)
│   │   ├── tests/                 # Load tests
│   │   ├── main.py                # FastAPI app entry point
│   │   ├── requirements.txt
│   │   ├── docker-compose.yml     # MySQL via Docker
│   │   ├── alembic.ini
│   │   └── .env.example           # Environment variable template
│   └── frontend/
│       ├── src/
│       │   ├── components/        # Reusable UI components
│       │   │   ├── IpoMultiSelect.jsx
│       │   │   ├── CaptchaPrompt.jsx
│       │   │   └── ClientUploadModal.jsx
│       │   ├── pages/             # Route-level page components
│       │   │   ├── ModeSelection.jsx
│       │   │   ├── SingleClientEntry.jsx
│       │   │   ├── BulkUpload.jsx
│       │   │   ├── ProgressScreen.jsx
│       │   │   ├── ResultsDashboard.jsx
│       │   │   └── HistoryScreen.jsx
│       │   ├── lib/
│       │   │   └── api.js         # Axios instance (base URL config)
│       │   ├── App.jsx
│       │   └── main.jsx
│       ├── package.json
│       └── vite.config.js
└── docs/                          # Project documentation (PDFs)
```

---

## Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **Docker & Docker Compose** (for MySQL) — or a local MySQL 8.0 installation
- **Git**

---

### Backend Setup

```bash
# 1. Navigate to the backend directory
cd IPO_Checker/backend

# 2. Create and activate a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install Playwright browsers (for scraping)
playwright install chromium

# 5. Set up environment variables
cp .env.example .env
# Edit .env with your MySQL credentials

# 6. Start MySQL (via Docker)
docker-compose up -d

# 7. Run database migrations
alembic upgrade head

# 8. Start the FastAPI server
uvicorn main:app --reload --port 8000
```

The API will be available at: **http://localhost:8000**  
Interactive API docs: **http://localhost:8000/docs**

---

### Frontend Setup

```bash
# 1. Navigate to the frontend directory
cd IPO_Checker/frontend

# 2. Install dependencies
npm install

# 3. Start the development server
npm run dev
```

The frontend will be available at: **http://localhost:5173**

> **Note:** The frontend expects the backend running at `http://localhost:8000`. This is configured in `src/lib/api.js`.

---

## API Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/ipos` | List all available IPOs |
| `POST` | `/api/sync` | Trigger IPO sync from registrar websites |
| `POST` | `/api/check/single` | Check allotment for a single client |
| `POST` | `/api/check/bulk` | Submit bulk check job from CSV/Excel |
| `GET` | `/api/progress/{job_id}` | Poll real-time progress of a running job |
| `GET` | `/api/results/{job_id}` | Fetch results for a completed job |
| `GET` | `/api/history` | List all past check sessions |
| `GET` | `/api/captcha/pending` | Get pending manual CAPTCHA challenges |
| `POST` | `/api/captcha/solve` | Submit CAPTCHA solution |
| `GET` | `/health` | Health check |

---

## Environment Variables

Copy `IPO_Checker/backend/.env.example` to `IPO_Checker/backend/.env` and configure:

| Variable | Default | Description |
|---|---|---|
| `MYSQL_USER` | `ipo_user` | MySQL username |
| `MYSQL_PASSWORD` | *(required)* | MySQL password |
| `MYSQL_HOST` | `localhost` | MySQL host |
| `MYSQL_PORT` | `3306` | MySQL port |
| `MYSQL_DATABASE` | `ipo_checker` | Database name |

---

## Database Migrations

Alembic is used for schema versioning:

```bash
# Apply all migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "describe your change"

# Roll back one step
alembic downgrade -1
```

---

## Supported Registrars

| Registrar | Status |
|---|---|
| Link Intime | ✅ Integrated (mock + real scraper ready) |
| KFin Technologies | ✅ Integrated (mock) |
| Bigshare | ✅ Integrated (mock) |
| MUFG Intime | ✅ Integrated (mock) |

> Real Playwright-based scrapers replace the mock implementations in production.

---

## Running Linting

**Frontend:**
```bash
cd IPO_Checker/frontend
npm run lint
```

---

## Documentation

Project design and specification documents are located in the [`docs/`](./docs/) folder:

- `01_Project_Requirements_Document.pdf`
- `02_Technical_Architecture_Document.pdf`
- `03_Database_Design_Document.pdf`
- `04_Security_Access_Control_Document.pdf`
- `05_Frontend_Specification_Document.pdf`
- `06_Feature_Ticket_List.pdf`
- `CAPTCHA_COMPLIANCE.md`
- `BACKUP_PROCEDURE.md`

---

## Security Notes

- **Never commit `.env` files** — use `.env.example` as a template.
- CORS is currently set to `allow_origins=["*"]`. Restrict to your frontend domain in production.
- CAPTCHA interactions comply with the [CAPTCHA Compliance Policy](./docs/CAPTCHA_COMPLIANCE.md).

---

## License

This project is proprietary. All rights reserved.

---

## Author

**Bhavya Bulani** — [bhavyabulani9@gmail.com](mailto:bhavyabulani9@gmail.com)
