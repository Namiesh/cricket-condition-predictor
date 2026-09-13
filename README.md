# 🏏 Cricket Condition Predictor

A Streamlit web application that predicts match-day weather conditions, pitch behavior, and displays venue capacity for upcoming cricket matches.

---

## 📌 Features

- **Upcoming Fixtures**: Fetches live upcoming international match fixtures from Cricbuzz.
- **Venue Capacity**: Automatically extracts the official stadium capacity.
- **Live Weather Forecast**: Fetches high-resolution match-day weather forecasts (temperature, humidity, rain probability, wind speed, cloud cover) via Open-Meteo API using venue coordinates.
- **Pitch Condition Prediction**: Assesses pitch conditions (Batting-friendly, Bowling-friendly, Balanced) using historical venue dataset combined with meteorological influence rules.

---

## 📂 Project Structure

```text
cricket-condition-predictor/
├── app.py                      # Main Streamlit web application
├── requirements.txt            # Python dependencies
├── README.md                   # Project documentation
├── data/
│   ├── pitch_ml_dataset.csv    # Historical match & pitch dataset for venue tendencies
│   └── venues.csv              # Coordinate mappings for cricket venues
└── src/
    ├── __init__.py
    └── fetch_upcoming_matches.py # Module to scrape upcoming matches from Cricbuzz
```

---

## 🚀 Getting Started

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Application

```bash
streamlit run app.py
```
