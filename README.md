# CommerceFlow

**Ecommerce intelligence and operational automation platform** — detect profit leakage, inventory risks, pricing issues, and product performance trends using deterministic analytics (no AI API required).

![CommerceFlow](https://img.shields.io/badge/Python-3.11+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green) ![License](https://img.shields.io/badge/License-MIT-lightgrey)

## Features

| Module | Capabilities |
|--------|-------------|
| **Data Import** | Shopify, WooCommerce, CSV, XLSX — drag & drop, validation, history |
| **Product Intelligence** | Health scores, rankings, rising/declining/unstable detection |
| **Profit Leakage** | Low margin, discounts, pricing inconsistencies, revenue anomalies |
| **Inventory Risk** | Low stock, overstock, dead inventory, reorder suggestions |
| **Data Cleaning** | Duplicate SKUs, fuzzy title matching, missing fields, category normalization |
| **Business Insights** | Executive dashboard, revenue trends, category breakdown |
| **Alerts** | Severity-scored operational warnings |
| **Exports** | CSV, XLSX, JSON management reports |
| **Competitor Tracking** | Architecture placeholder for future scraping |

## Quick Start

### Prerequisites

- Python 3.11+
- pip

### Installation

```bash
# Clone or open the project directory
cd CommerceFlow

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env   # Windows
# cp .env.example .env  # macOS/Linux

# Load sample data
python scripts/seed_sample_data.py

# Start the server
python run.py
```

Open **http://localhost:8000** in your browser.

### First Steps

1. Visit the **Executive Overview** dashboard
2. Click **Run Analysis** in the sidebar
3. Click the bell icon or visit **Alerts Center** → **Regenerate Alerts**
4. Explore **Product Intelligence**, **Inventory Health**, and **Profit Leakage**
5. Upload your own CSV/XLSX on **Import History**

## Project Structure

```
CommerceFlow/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings (pydantic-settings)
│   ├── database.py          # Async SQLAlchemy + SQLite
│   ├── models/              # ORM models
│   ├── schemas/             # Pydantic schemas
│   ├── api/routes/          # REST + page routes
│   ├── engines/             # Analytics engines (deterministic)
│   ├── services/            # Business logic layer
│   ├── competitors/         # Future scraping architecture
│   └── utils/               # Scoring, normalization, cache
├── templates/               # Jinja2 dashboard pages
├── static/                  # CSS + JavaScript
├── data/sample/             # Demo CSV datasets
├── scripts/seed_sample_data.py
├── requirements.txt
└── run.py
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/imports/upload` | Upload data file |
| GET | `/api/imports/history` | Import history |
| GET | `/api/analytics/dashboard` | Executive metrics |
| GET | `/api/analytics/full` | Full analysis run |
| GET | `/api/analytics/products` | Product intelligence |
| GET | `/api/analytics/profit-leakage` | Profit leakage report |
| GET | `/api/analytics/inventory` | Inventory risk report |
| POST | `/api/alerts/generate` | Generate alerts from analysis |
| GET | `/api/alerts` | List alerts (filterable) |
| POST | `/api/exports/{type}` | Export reports (csv/xlsx/json) |

## Import File Formats

### Generic CSV

```csv
sku,title,category,price,cost,quantity,revenue,sold_at
SKU-001,Product Name,Electronics,49.99,20.00,100,499.90,2026-05-01
```

### Shopify

Export products CSV — CommerceFlow auto-maps `Variant SKU`, `Title`, `Variant Price`, etc.

### WooCommerce

Export products CSV — maps `SKU`, `Name`, `Regular price`, `Categories`.

## Configuration

See `.env.example` for all options:

- `LOW_STOCK_THRESHOLD` — quantity triggering low-stock alerts (default: 10)
- `DEAD_INVENTORY_DAYS` — days before inventory classified as dead (default: 120)
- `MARGIN_WARNING_PCT` — margin % threshold for profit leakage (default: 15)

## Architecture Notes

- **No AI APIs in v1** — scoring, statistics, and rule-based engines only
- **Modular engines** — swap or extend `app/engines/` independently
- **TTL cache** — placeholder for Redis in production (`app/utils/cache.py`)
- **Multi-tenant ready** — `Organization` and `User` models as placeholders
- **Competitor module** — `CompetitorTrackerBase` + registry for future integrations

## Future Roadmap

- [ ] Shopify / WooCommerce live API sync
- [ ] OpenAI insight summaries (optional layer)
- [ ] Competitor price scraping
- [ ] Stripe billing + team accounts
- [ ] Scheduled reports & email alerts
- [ ] PostgreSQL + Redis production stack

## Git / GitHub (Windows)

Git must run **only** from this project folder, not from `C:\Users\User`.

**Cursor / VS Code:** Open **File → Open Folder** and select the CommerceFlow folder. The integrated terminal starts here automatically (see `.vscode/settings.json`).

**External terminal — pick one:**

```powershell
# PowerShell: go to project first
$proj = (Get-ChildItem "$env:USERPROFILE\Desktop" | Where-Object { $_.Name -match 'CommerceFlow' }).FullName
Set-Location $proj
git status
```

Or double-click **`CommerceFlow-Git.cmd`** on the Desktop project folder — opens CMD already in the right directory.

```powershell
# Or use the helper script (any git command)
.\scripts\git-here.ps1 push -u origin main
```

Remote: `https://github.com/a-sehic-dev/CommerceFlow.git`

## License

MIT
