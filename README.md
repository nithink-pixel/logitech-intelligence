# Logitech Brand Intelligence Platform

A live brand intelligence dashboard that scrapes 10 Logitech products across 12 Amazon global marketplaces, calculates opportunity scores, and displays actionable insights.

## Live Demo
https://logitech-intelligence-rqvvsmm63hi2ka67c78ok9.streamlit.app

## Features
- Scrapes 10 products × 12 Amazon markets (US, UK, DE, CA, JP, FR, IT, ES, MX, AU, IN, SG)
- Auto-scrapes every 6 hours via scheduler
- Opportunity scoring engine (velocity, price, distribution, content)
- Real-time alerts — OOS, price drops, MAP violations
- Global price comparison with live FX rates
- Price history charts with trend indicators
- One-click PDF export — 4-page professional report

## Stack
Python · BeautifulSoup · SQLite · Streamlit · Plotly · ReportLab

## Run Locally
```bash
pip install -r requirements.txt
python database/schema.py
python scrape.py amazon_us
streamlit run dashboard.py
```

## Auto-Scheduler
```bash
python scheduler.py --interval 6
```
