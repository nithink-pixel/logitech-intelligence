# 🖱️ Logitech Brand Intelligence Platform

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35-red?logo=streamlit)
![SQLite](https://img.shields.io/badge/Database-SQLite-green?logo=sqlite)
![License](https://img.shields.io/badge/License-MIT-yellow)

A live brand intelligence platform that automatically scrapes **10 Logitech products** across **12 Amazon global marketplaces**, calculates opportunity scores, detects price anomalies, and generates professional PDF reports.

## 🌐 Live Demo
**[logitech-intelligence-rqvvsmm63hi2ka67c78ok9.streamlit.app](https://logitech-intelligence-rqvvsmm63hi2ka67c78ok9.streamlit.app)**

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔍 Auto Scraping | 10 products × 12 Amazon markets, runs every 6 hours |
| 📊 Opportunity Scoring | Velocity + Price + Distribution + Content quality |
| 🚨 Real-time Alerts | OOS, price drops >5%, MAP violations, high opportunity |
| 🌍 Global Comparison | Live FX rates across 12 currencies |
| 📈 Price History | Track price trends over time with change indicators |
| 📄 PDF Export | 4-page professional report with executive summary |
| 🌐 Deployed | Live on Streamlit Cloud |

---

## 🗂️ Project Structure
```
├── dashboard.py          # 8-tab Streamlit dashboard
├── scrape.py             # Standalone scraper
├── scheduler.py          # Auto-scheduler (runs every N hours)
├── alerts.py             # Alert detection engine
├── global_comparison.py  # Global FX price comparison
├── pdf_export.py         # PDF report generator
├── database/
│   └── schema.py         # SQLite schema + seed data
├── scrapers/
│   ├── base.py           # Base scraper with retry + UA rotation
│   └── all_channels.py   # 31 channel scrapers
└── scoring/
    └── opportunity_engine.py  # Scoring algorithm
```

---

## 🚀 Run Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
python database/schema.py

# Scrape Amazon US
python scrape.py amazon_us

# Launch dashboard
streamlit run dashboard.py
```

## ⏰ Auto-Scheduler
```bash
# Scrape all Amazon markets every 6 hours
python scheduler.py --interval 6

# Scrape specific channels every 2 hours
python scheduler.py --channels amazon_us amazon_uk amazon_de --interval 2
```

---

## 📊 Channels Supported

| Tier | Channels |
|---|---|
| Amazon Global | US, UK, DE, CA, JP, FR, IT, ES, MX, AU, IN, SG |
| Tier A | Walmart, Target, Best Buy, eBay, Logitech.com |
| Tier B | Newegg, Costco, B&H Photo, Staples, and 10 more |

---

## 🧠 Opportunity Score

Each product-channel combo gets a score (0–100) based on:
- **Velocity (30%)** — Review count, BSR rank, review growth rate
- **Price Competitiveness (25%)** — vs MSRP and cross-channel average
- **Distribution Gap (25%)** — Stock availability and OOS frequency
- **Content Quality (20%)** — Rating, review volume, deal badges

---

## 🛠️ Tech Stack

- **Scraping** — Python, Requests, BeautifulSoup
- **Database** — SQLite with WAL mode
- **Dashboard** — Streamlit, Plotly
- **PDF** — ReportLab
- **FX Rates** — exchangerate-api.com (live, cached 1hr)
- **Deploy** — Streamlit Cloud

---

## 📄 License
MIT
