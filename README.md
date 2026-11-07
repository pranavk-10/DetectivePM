# 🔍 DetectivePM

DetectivePM is an automated job-scraping and analytics dashboard built for Product Management (PM) roles. It continuously scans LinkedIn and other sources for Product Management Internships and Junior/Associate Full-Time roles, classifies them by industry genre, extracts recruiter contact details, deduplicates entries, and provides a polished dark-themed SaaS analytics dashboard.

---

## 🛠️ Project Structure

```
detectivePM/
├── backend/
│   ├── main.py            # FastAPI application & REST endpoints
│   ├── scraper.py         # Playwright scraping engine + fallback mock generator
│   ├── database.py        # SQLite schema, deduplication & CSV export
│   ├── gsheets.py         # Google Sheets sync helper
│   ├── scheduler.py       # 5-hour recurring background scheduler (APScheduler)
│   ├── detective_pm.db    # SQLite database (auto-created)
│   └── detective_pm_jobs.csv # Exported CSV file
├── frontend/
│   ├── src/
│   │   ├── app/           # Next.js App Router (page.tsx, layout.tsx, globals.css)
│   │   ├── components/    # MetricsCards, GenreChart, PostsTable, Header
│   │   └── lib/           # TypeScript API client
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── tsconfig.json
├── requirements.txt
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- Node.js 18+

### 1. Backend Setup (FastAPI)
```bash
# Install Python dependencies
pip install -r requirements.txt

# (Optional) Install Playwright browsers
playwright install chromium

# Run the FastAPI server on port 8000
uvicorn backend.main:app --reload --port 8000
```

### 2. Frontend Setup (Next.js)
```bash
cd frontend

# Install Node dependencies
npm install

# Run the Next.js dev server on port 3000
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser to view the DetectivePM dashboard.

---

## ✨ Core Features

1. **Automated Scraping & Fallback Mock Engine**: Playwright scraping engine with stealth headers that extracts PM job postings. Includes a robust mock generator ensuring the dashboard works out of the box even without live LinkedIn credentials.
2. **Recurring 5-Hour Scheduler**: Powered by APScheduler, automatically runs scraping cycles every 5 hours and exports fresh data.
3. **SQLite Deduplication**: Prevents duplicate entries using SHA-256 content hashes and `INSERT OR IGNORE`.
4. **Genre & Role Classification**: Automatically tags listings into **Intern** vs **Full-time** and categorizes into **SaaS**, **B2C**, **FinTech**, **EdTech**, **HealthTech**, or **General/Other**.
5. **Contact Extraction**: Regex-based extraction of recruiter email addresses and phone numbers.
6. **Polished Dark-Themed UI**: Built with Tailwind CSS, Recharts analytics, Lucide icons, and glass-morphism cards.
7. **Google Sheets & CSV Export**: One-click CSV download and Google Sheets synchronization via service account credentials.
