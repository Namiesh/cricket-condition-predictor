import streamlit as st
import pandas as pd
import requests
import re
import os
import textwrap
from bs4 import BeautifulSoup
from datetime import date, timedelta

from src.condition_metrics import (
    calculate_batting_percentage,
    calculate_pace_assistance,
    calculate_spin_assistance,
    calculate_dew_probability,
    calculate_pitch_surface_badge,
    load_stadium_analytics,
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Cricket Condition Predictor",
    page_icon="🏏",
    layout="wide"
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown("""
<style>

.stApp {
    background: #07111f;
    color: #e8eef7;
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1400px;
}

.main-title {
    font-size: 42px;
    font-weight: 700;
    letter-spacing: -1px;
    margin-bottom: 4px;
}

.subtitle {
    color: #8fa3bd;
    font-size: 16px;
    margin-bottom: 30px;
}

.section-title {
    font-size: 20px;
    font-weight: 650;
    margin-top: 25px;
    margin-bottom: 14px;
}

.card {
    background: #0d1a2b;
    border: 1px solid #1b2b40;
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 15px;
}

.pitch-surface-card {
    background: #0d1728;
    border: 1px solid #1c2c44;
    border-radius: 16px;
    padding: 24px;
    margin-top: 15px;
    margin-bottom: 25px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}

.pitch-surface-header {
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 20px;
}

.surface-badge-box {
    background: #111e34;
    border: 1px solid #203554;
    border-radius: 10px;
    padding: 14px 20px;
    text-align: center;
    color: #d8e5ff;
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 1.2px;
    margin-bottom: 25px;
    box-shadow: inset 0 0 10px rgba(0,0,0,0.2);
}

.progress-group {
    margin-bottom: 18px;
}

.progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 7px;
    font-size: 14px;
    font-weight: 500;
    color: #c0d1e5;
}

.progress-track {
    width: 100%;
    height: 10px;
    background-color: #162438;
    border-radius: 5px;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #1d75f2, #38bdf8);
    border-radius: 5px;
    box-shadow: 0 0 10px rgba(56, 189, 248, 0.4);
}

.prediction-card {
    background: linear-gradient(135deg, #10243b, #0c1828);
    border: 1px solid #274563;
    border-radius: 16px;
    padding: 28px;
    text-align: center;
    margin-bottom: 20px;
}

.prediction-label {
    color: #8fa3bd;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}

.prediction-value {
    font-size: 34px;
    font-weight: 750;
    margin-top: 8px;
}

.metric-card {
    background: #0d1a2b;
    border: 1px solid #1b2b40;
    border-radius: 12px;
    padding: 17px;
    text-align: center;
}

.metric-label {
    color: #8fa3bd;
    font-size: 12px;
    margin-bottom: 5px;
}

.metric-value {
    font-size: 23px;
    font-weight: 650;
}

.small-text {
    color: #8fa3bd;
    font-size: 13px;
}

.info-box {
    background: #0b1726;
    border-left: 3px solid #3c82c4;
    padding: 15px 18px;
    border-radius: 8px;
    color: #b9c8da;
}

.warning-box {
    background: #241b0c;
    border-left: 3px solid #d69e2e;
    padding: 15px 18px;
    border-radius: 8px;
    color: #e7d3a2;
}

.success-box {
    background: #0c2119;
    border-left: 3px solid #38a169;
    padding: 15px 18px;
    border-radius: 8px;
    color: #b8dfca;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# DATA
# ============================================================

@st.cache_data
def load_pitch_data():
    try:
        return pd.read_csv("data/pitch_ml_dataset.csv")
    except Exception:
        return pd.DataFrame()


@st.cache_data
def load_arena_data():
    try:
        if os.path.exists("data/arena_subset.csv"):
            return pd.read_csv("data/arena_subset.csv")
        return pd.read_excel(
            "data/arena_player_rating_calculated.xlsx",
            header=5,
            usecols=[
                "ID",
                "Format",
                "Average vs LH Fast Bowler",
                "Average vs RH Fast Bowler",
                "Average vs LH Spin Bowler",
                "Average vs RH Spin Bowler",
                "Expected Strike Rate vs Fast Bowling",
                "Expected Strike Rate vs Spin",
                "Balls per Boundary Fast",
            ]
        )
    except Exception:
        return pd.DataFrame()


@st.cache_data
def load_cricket_player_stats():
    try:
        if os.path.exists("data/cricket_player_stats_subset.csv"):
            return pd.read_csv("data/cricket_player_stats_subset.csv")
        return pd.read_excel(
            "data/cricket_player_stats.xlsx",
            usecols=[
                "Player ID",
                "Player Name",
                "Team Name",
                "Team Short",
                "Format",
                "Batting Average",
                "Batting Strike Rate",
            ]
        )
    except Exception:
        return pd.DataFrame()


@st.cache_data
def load_stadium_analytics_data():
    try:
        return load_stadium_analytics()
    except Exception:
        return pd.DataFrame()


pitch_data = load_pitch_data()
arena_data = load_arena_data()
cricket_player_stats = load_cricket_player_stats()
stadium_analytics = load_stadium_analytics_data()



# ============================================================
# WEATHER CODE
# ============================================================

def weather_description(code):

    code = int(code)

    descriptions = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with hail",
        99: "Thunderstorm with heavy hail"
    }

    return descriptions.get(code, "Unknown conditions")


# ============================================================
# GEOCODE VENUE
# ============================================================

@st.cache_data(ttl=3600)
def geocode_venue(venue_name):

    url = "https://geocoding-api.open-meteo.com/v1/search"

    params = {
        "name": venue_name,
        "count": 5,
        "language": "en",
        "format": "json"
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        if "results" not in data or not data["results"]:
            return None

        results = data["results"]

        # Prefer places with the closest name match
        selected = results[0]

        return {
            "name": selected.get("name", venue_name),
            "latitude": selected["latitude"],
            "longitude": selected["longitude"],
            "country": selected.get("country", ""),
            "admin1": selected.get("admin1", "")
        }

    except Exception:
        return None


# ============================================================
# GEOCODE CITY FALLBACK
# ============================================================

@st.cache_data(ttl=3600)
def geocode_city(city_name):

    if not city_name:
        return None

    url = "https://geocoding-api.open-meteo.com/v1/search"

    params = {
        "name": city_name,
        "count": 5,
        "language": "en",
        "format": "json"
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()
        data = response.json()

        if not data.get("results"):
            return None

        selected = data["results"][0]

        return {
            "name": selected.get("name", city_name),
            "latitude": selected["latitude"],
            "longitude": selected["longitude"],
            "country": selected.get("country", ""),
            "admin1": selected.get("admin1", "")
        }

    except Exception:
        return None


# ============================================================
# VENUE CAPACITY
# ============================================================

@st.cache_data(ttl=3600)
def get_venue_capacity(match_url):
    """Read the selected venue capacity from Cricbuzz match-facts page."""

    if not match_url:
        return None

    try:
        facts_url = match_url.replace(
            "/live-cricket-scores/",
            "/cricket-match-facts/",
            1
        )

        response = requests.get(
            facts_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/139.0 Safari/537.36"
                )
            },
            timeout=15
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        # Cricbuzz sometimes changes the exact structure of the
        # VENUE GUIDE section. Search the whole page as a fallback.
        capacity_match = re.search(
            r"Capacity\s*([0-9][0-9,]*)",
            text,
            re.IGNORECASE
        )

        if not capacity_match:
            capacity_match = re.search(
                r"Capacity.{0,80}?([0-9][0-9,]*)",
                text,
                re.IGNORECASE
            )

        if not capacity_match:
            return None

        return int(capacity_match.group(1).replace(",", ""))

    except Exception:
        return None


# ============================================================
# LIVE WEATHER FORECAST
# ============================================================

@st.cache_data(ttl=900)
def get_weather_forecast(latitude, longitude):

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "relative_humidity_2m_mean",
            "precipitation_probability_max",
            "precipitation_sum",
            "rain_sum",
            "wind_speed_10m_max",
            "cloud_cover_mean"
        ]),
        "forecast_days": 16,
        "timezone": "auto"
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()

        return response.json()

    except Exception as e:
        return None


# ============================================================
# FIND SELECTED DATE
# ============================================================

def get_forecast_for_date(weather_data, selected_date):

    if weather_data is None:
        return None

    daily = weather_data.get("daily")

    if not daily:
        return None

    dates = daily.get("time", [])

    target = selected_date.strftime("%Y-%m-%d")

    if target not in dates:
        return None

    index = dates.index(target)

    return {
        "date": target,
        "weather_code": daily["weather_code"][index],
        "temperature_max": daily["temperature_2m_max"][index],
        "temperature_min": daily["temperature_2m_min"][index],
        "humidity": daily["relative_humidity_2m_mean"][index],
        "rain_probability": daily["precipitation_probability_max"][index],
        "precipitation": daily["precipitation_sum"][index],
        "rain": daily["rain_sum"][index],
        "wind": daily["wind_speed_10m_max"][index],
        "cloud": daily["cloud_cover_mean"][index]
    }


# ============================================================
# WEATHER-BASED PITCH INFLUENCE
# ============================================================

def calculate_weather_influence(weather):

    score = 0
    reasons = []

    rain = weather["rain"]
    rain_probability = weather["rain_probability"]
    humidity = weather["humidity"]
    wind = weather["wind"]
    cloud = weather["cloud"]
    temperature = weather["temperature_max"]

    # Rain
    if rain >= 10:
        score -= 2
        reasons.append("High expected rainfall")
    elif rain >= 2:
        score -= 1
        reasons.append("Some expected rainfall")

    # Rain probability
    if rain_probability >= 70:
        score -= 1
        reasons.append("High rain probability")

    # Humidity
    if humidity >= 75:
        score -= 1
        reasons.append("High humidity")
    elif humidity <= 45:
        score += 1
        reasons.append("Low humidity")

    # Wind
    if wind >= 25:
        score -= 1
        reasons.append("Strong winds")

    # Cloud
    if cloud >= 70:
        score -= 1
        reasons.append("Heavy cloud cover")

    # Temperature
    if temperature >= 35:
        score += 1
        reasons.append("Hot conditions")

    if score <= -2:
        result = "Bowling Influence"
    elif score >= 2:
        result = "Batting Influence"
    else:
        result = "Neutral"

    return result, score, reasons


# ============================================================
# HISTORICAL VENUE ANALYSIS
# ============================================================

def get_historical_pitch_analysis(venue_name):

    if pitch_data.empty:
        return None

    venue_column = None

    possible_columns = [
        "venue",
        "Venue",
        "venue_clean",
        "clean_venue"
    ]

    for column in possible_columns:
        if column in pitch_data.columns:
            venue_column = column
            break

    if venue_column is None:
        return None

    matches = pitch_data[
        pitch_data[venue_column]
        .astype(str)
        .str.lower()
        .str.contains(
            venue_name.lower(),
            regex=False,
            na=False
        )
    ].copy()

    if matches.empty:
        return None

    if "pitch_class" not in matches.columns:
        return None

    distribution = (
        matches["pitch_class"]
        .value_counts(normalize=True)
        .mul(100)
        .round(1)
        .to_dict()
    )

    recent = matches.copy()

    if "date" in recent.columns:
        recent["date"] = pd.to_datetime(
            recent["date"],
            errors="coerce"
        )

        recent = recent.sort_values(
            "date",
            ascending=False
        )

    recent = recent.head(10)

    recent_prediction = None

    if not recent.empty:
        recent_prediction = recent["pitch_class"].mode().iloc[0]

    return {
        "matches": len(matches),
        "distribution": distribution,
        "recent_prediction": recent_prediction,
        "recent_matches": recent
    }


# ============================================================
# FINAL PITCH ASSESSMENT
# ============================================================

def final_pitch_prediction(historical, weather_influence):

    # No historical venue data
    if historical is None:

        if weather_influence == "Bowling Influence":
            return "Bowling Friendly", "Low"

        if weather_influence == "Batting Influence":
            return "Batting Friendly", "Low"

        return "Balanced", "Low"

    recent = historical["recent_prediction"]

    if recent is None:
        return "Balanced", "Low"

    prediction = recent

    # Weather can shift the historical tendency
    if weather_influence == "Bowling Influence":

        if prediction == "Batting Friendly":
            prediction = "Balanced"

        elif prediction == "Balanced":
            prediction = "Bowling Friendly"

    elif weather_influence == "Batting Influence":

        if prediction == "Bowling Friendly":
            prediction = "Balanced"

        elif prediction == "Balanced":
            prediction = "Batting Friendly"

    if historical["matches"] >= 50:
        confidence = "High"
    elif historical["matches"] >= 20:
        confidence = "Medium"
    else:
        confidence = "Low"

    return prediction, confidence


# ============================================================
# UPCOMING MATCHES
# ============================================================

@st.cache_data(ttl=600)
def load_upcoming_matches():
    try:
        from src.fetch_upcoming_matches import fetch_upcoming_matches
        matches = fetch_upcoming_matches()

        cleaned = []
        seen = set()

        for match in matches:
            title = str(match.get("title", "")).strip()
            venue = str(match.get("venue", "")).strip()
            match_date = str(match.get("date", "")).strip()
            match_time = str(match.get("time", "")).strip()

            if not match_date or not title:
                continue

            key = (
                title.lower(),
                match_date,
                match_time,
                venue.lower()
            )

            if key in seen:
                continue

            seen.add(key)
            cleaned.append(match)

        return cleaned

    except Exception as error:
        return []


def split_teams(title, listing=""):
    """Try to extract the two teams from the Cricbuzz title/listing."""

    text = f"{title} {listing}".strip()

    # Common format: Cricket commentary | NAM vs RSA, 3rd ODI...
    match = pd.Series([text]).str.extract(
        r"\b([A-Z]{2,4})\s+vs\s+([A-Z]{2,4})\b",
        expand=True
    )

    if not match.empty and pd.notna(match.iloc[0, 0]):
        return match.iloc[0, 0], match.iloc[0, 1]

    # Fallback for titles containing full team names.
    clean = text.split("|")[-1].strip()

    if " vs " in clean:
        parts = clean.split(" vs ", 1)
        return parts[0].strip(), parts[1].split(",")[0].strip()

    return "Team 1", "Team 2"


@st.cache_data

def load_venue_coordinates():
    try:
        return pd.read_csv("data/venues.csv")
    except Exception:
        return pd.DataFrame()


VENUE_FALLBACK_COORDINATES = {
    "namibia cricket ground": {
        "name": "Namibia Cricket Ground",
        "latitude": -22.60576,
        "longitude": 17.08780,
        "country": "Namibia",
        "admin1": "Windhoek"
    }
}


def find_venue_coordinates(venue_name, city=""):
    """Find coordinates from known venues, then venue/city, then city."""

    target = venue_name.lower().strip()

    if target in VENUE_FALLBACK_COORDINATES:
        return VENUE_FALLBACK_COORDINATES[target]

    venues = load_venue_coordinates()

    if not venues.empty and "venue" in venues.columns:

        exact = venues[
            venues["venue"].astype(str).str.lower().str.strip() == target
        ]

        if not exact.empty:
            row = exact.iloc[0]
            return {
                "name": row["venue"],
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "country": row.get("country", ""),
                "admin1": row.get("city", "")
            }

        partial = venues[
            venues["venue"].astype(str).str.lower().str.contains(
                target,
                regex=False,
                na=False
            )
        ]

        if not partial.empty:
            row = partial.iloc[0]
            return {
                "name": row["venue"],
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "country": row.get("country", ""),
                "admin1": row.get("city", "")
            }

    # Try the venue together with its city. This is much more reliable
    # than searching for a cricket ground name by itself.
    if city:
        location = geocode_venue(f"{venue_name}, {city}")
        if location is not None:
            return location

        # Final fallback: geocode the city itself.
        location = geocode_city(city)
        if location is not None:
            return location

    # Last resort for matches where the scraper did not obtain a city.
    return geocode_venue(venue_name)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">Cricket Condition Predictor</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Upcoming match weather & pitch-condition analysis'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## 🏏 Match Setup")

    with st.spinner("Loading upcoming matches..."):
        upcoming_matches = load_upcoming_matches()

    if not upcoming_matches:
        st.error(
            "Could not load upcoming matches. "
            "Make sure you have an internet connection and that "
            "the Cricbuzz schedule is reachable."
        )
        selected_match = None
        analyze_button = False

    else:
        match_options = []

        for match in upcoming_matches:
            team1, team2 = split_teams(
                match.get("title", ""),
                match.get("listing", "")
            )

            label = (
                f"{match['date']} • "
                f"{team1} vs {team2} • "
                f"{match.get('venue') or 'Venue not available'}"
            )

            match_options.append(label)

        selected_index = st.selectbox(
            "Upcoming Match",
            range(len(match_options)),
            format_func=lambda i: match_options[i]
        )

        selected_match = upcoming_matches[selected_index]

        team1, team2 = split_teams(
            selected_match.get("title", ""),
            selected_match.get("listing", "")
        )

        st.markdown("---")

        st.markdown(
            f'<div class="small-text">'
            f'<b>{team1} vs {team2}</b><br>'
            f'📅 {selected_match["date"]}<br>'
            f'🕒 {selected_match.get("time") or "Time not available"}<br>'
            f'📍 {selected_match.get("venue") or "Venue not available"}'
            f'</div>',
            unsafe_allow_html=True
        )

        st.markdown("<br>", unsafe_allow_html=True)

        analyze_button = st.button(
            "Analyze Match",
            use_container_width=True,
            type="primary"
        )

    st.markdown("---")

    st.markdown(
        '<div class="small-text">'
        'Matches: Cricbuzz upcoming schedule<br>'
        'Weather: Open-Meteo live forecast<br>'
        'Pitch: historical venue behaviour + weather context'
        '</div>',
        unsafe_allow_html=True
    )


# ============================================================
# MAIN ANALYSIS
# ============================================================

if analyze_button and selected_match is not None:

    team1, team2 = split_teams(
        selected_match.get("title", ""),
        selected_match.get("listing", "")
    )

    venue = str(selected_match.get("venue", "")).strip()

    try:
        match_date = pd.to_datetime(
            selected_match["date"]
        ).date()
    except Exception:
        match_date = None

    if not venue:
        st.error(
            "This match does not have a venue in the schedule. "
            "Please choose another upcoming match."
        )

    elif match_date is None:
        st.error("Could not determine the match date.")

    else:

        # ----------------------------------------------------
        # GEOCODING
        # ----------------------------------------------------

        with st.spinner("Finding venue and retrieving forecast..."):
            location = find_venue_coordinates(
                venue,
                str(selected_match.get("city", "")).strip()
            )

        if location is None:

            st.error(
                "Could not find this venue. "
                "Try another upcoming match or add the venue to data/venues.csv."
            )

        else:

            venue_capacity = get_venue_capacity(
                selected_match.get("url", "")
            )

            # ------------------------------------------------
            # LOCATION CARD
            # ------------------------------------------------

            st.markdown(
                '<div class="section-title">Match</div>',
                unsafe_allow_html=True
            )

            city = str(selected_match.get("city", "")).strip()
            city_text = f" • {city}" if city else ""
            time_text = selected_match.get("time") or "Time not available"

            st.markdown(
                f"""
                <div class="card">
                    <h2 style="margin-bottom:5px;">{team1} vs {team2}</h2>
                    <div class="small-text">
                        📍 {venue}{city_text}
                        &nbsp;&nbsp;•&nbsp;&nbsp;
                        📅 {match_date.strftime("%d %B %Y")}
                        &nbsp;&nbsp;•&nbsp;&nbsp;
                        🕒 {time_text}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            if venue_capacity is not None:
                st.markdown(
                    f"""
                    <div class="metric-card" style="margin-bottom:20px; text-align:left;">
                        <div class="metric-label">VENUE CAPACITY</div>
                        <div class="metric-value">{venue_capacity:,} spectators</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    """
                    <div class="info-box" style="margin-bottom:20px;">
                        Venue capacity is not available from Cricbuzz.
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # ------------------------------------------------
            # WEATHER
            # ------------------------------------------------

            weather_data = get_weather_forecast(
                location["latitude"],
                location["longitude"]
            )

            forecast = get_forecast_for_date(
                weather_data,
                match_date
            )

            if forecast is None:

                st.warning(
                    "The selected match date is outside the currently available "
                    "forecast window. Open-Meteo currently provides a forecast "
                    "for up to 16 days."
                )

            else:

                weather_text = weather_description(
                    forecast["weather_code"]
                )

                weather_influence, weather_score, reasons = (
                    calculate_weather_influence(forecast)
                )

                # ------------------------------------------------
                # CONDITION METRICS
                # ------------------------------------------------

                match_type = str(
                    selected_match.get("match_type", "")
                ).strip()

                if not match_type:
                    match_text = (
                        str(selected_match.get("title", ""))
                        + " "
                        + str(selected_match.get("listing", ""))
                    ).lower()

                    if "test" in match_text:
                        match_type = "Test"
                    elif "odi" in match_text:
                        match_type = "ODI"
                    elif "t20" in match_text:
                        match_type = "T20"

                batting_percentage = calculate_batting_percentage(
                    pitch_data,
                    venue,
                    cricket_player_stats,
                    team1,
                    team2,
                    match_type,
                    weather=forecast,
                    stadium_analytics=stadium_analytics
                )

                pace_assistance = calculate_pace_assistance(
                    arena_data,
                    match_type,
                    cricket_player_stats,
                    team1,
                    team2,
                    venue=venue,
                    weather=forecast,
                    stadium_analytics=stadium_analytics
                )

                spin_assistance = calculate_spin_assistance(
                    arena_data,
                    match_type,
                    cricket_player_stats,
                    team1,
                    team2,
                    venue=venue,
                    weather=forecast,
                    stadium_analytics=stadium_analytics
                )

                dew_probability = calculate_dew_probability(
                    forecast["temperature_min"],
                    forecast["humidity"]
                )

                surface_badge = calculate_pitch_surface_badge(
                    batting_percentage,
                    pace_assistance,
                    spin_assistance,
                    dew_probability
                )

                # ------------------------------------------------
                # PITCH & SURFACE CARD (as in screenshot)
                # ------------------------------------------------

                batting_val = batting_percentage if batting_percentage is not None else 50.0
                pace_val = pace_assistance if pace_assistance is not None else 50.0
                spin_val = spin_assistance if spin_assistance is not None else 50.0
                dew_val = dew_probability if dew_probability is not None else 50.0

                pitch_surface_html = f"""<div class="pitch-surface-card">
<div class="pitch-surface-header">Pitch &amp; Surface</div>
<div class="surface-badge-box">{surface_badge}</div>
<div class="progress-group">
<div class="progress-header">
<span>Batting</span>
<span>{batting_val:.0f}%</span>
</div>
<div class="progress-track">
<div class="progress-fill" style="width: {batting_val:.0f}%;"></div>
</div>
</div>
<div class="progress-group">
<div class="progress-header">
<span>Pace Assistance</span>
<span>{pace_val:.0f}%</span>
</div>
<div class="progress-track">
<div class="progress-fill" style="width: {pace_val:.0f}%;"></div>
</div>
</div>
<div class="progress-group">
<div class="progress-header">
<span>Spin Assistance</span>
<span>{spin_val:.0f}%</span>
</div>
<div class="progress-track">
<div class="progress-fill" style="width: {spin_val:.0f}%;"></div>
</div>
</div>
<div class="progress-group">
<div class="progress-header">
<span>Dew Probability</span>
<span>{dew_val:.0f}%</span>
</div>
<div class="progress-track">
<div class="progress-fill" style="width: {dew_val:.0f}%;"></div>
</div>
</div>
</div>"""

                st.markdown(
                    pitch_surface_html,
                    unsafe_allow_html=True
                )

                st.markdown(
                    '<div class="section-title">Match-Day Weather</div>',
                    unsafe_allow_html=True
                )

                # Weather metrics
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-label">TEMPERATURE</div>
                            <div class="metric-value">
                                {forecast["temperature_max"]:.0f}°C
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with col2:
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-label">HUMIDITY</div>
                            <div class="metric-value">
                                {forecast["humidity"]:.0f}%
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with col3:
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-label">RAIN PROBABILITY</div>
                            <div class="metric-value">
                                {forecast["rain_probability"]:.0f}%
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with col4:
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-label">EXPECTED RAIN</div>
                            <div class="metric-value">
                                {forecast["rain"]:.1f} mm
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                st.markdown("<br>", unsafe_allow_html=True)

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-label">LOW TEMPERATURE</div>
                            <div class="metric-value">
                                {forecast["temperature_min"]:.0f}°C
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with col2:
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-label">WIND</div>
                            <div class="metric-value">
                                {forecast["wind"]:.0f} km/h
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with col3:
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-label">CLOUD COVER</div>
                            <div class="metric-value">
                                {forecast["cloud"]:.0f}%
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with col4:
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-label">CONDITION</div>
                            <div class="metric-value"
                                 style="font-size:17px;">
                                {weather_text}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                # ------------------------------------------------
                # MATCH CONDITION METRICS
                # ------------------------------------------------

                st.markdown(
                    '<div class="section-title">Match Condition Metrics</div>',
                    unsafe_allow_html=True
                )

                metric_values = [
                    (
                        "BATTING PERCENTAGE",
                        batting_percentage,
                        "%",
                        "Dynamic venue & matchup batting index"
                    ),
                    (
                        "PACE ASSISTANCE",
                        pace_assistance,
                        "%",
                        "Stadium pitch & atmospheric swing index"
                    ),
                    (
                        "SPIN ASSISTANCE",
                        spin_assistance,
                        "%",
                        "Stadium pitch turn & dry track index"
                    ),
                    (
                        "DEW PROBABILITY",
                        dew_probability,
                        "%",
                        "Weather dew condensation estimate"
                    ),
                ]

                metric_cols = st.columns(4)

                for column, (label, value, suffix, description) in zip(
                    metric_cols,
                    metric_values
                ):
                    with column:
                        if value is None:
                            display_value = "N/A"
                        else:
                            display_value = f"{value:.1f}{suffix}"

                        st.markdown(
                            f"""
                            <div class="metric-card">
                                <div class="metric-label">{label}</div>
                                <div class="metric-value">
                                    {display_value}
                                </div>
                                <div class="small-text" style="margin-top:6px;">
                                    {description}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                st.markdown(
                    """
                    <div class="info-box" style="margin-top:12px;">
                        <b>Metric note:</b> Batting percentage, pace assistance, spin assistance,
                        and dew probability are dynamically calculated for each stadium, pitch, match,
                        and weather forecast using historical ball-by-ball venue analytics and matchup data.
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # ------------------------------------------------
                # PITCH ANALYSIS
                # ------------------------------------------------

                st.markdown(
                    '<div class="section-title">Pitch Analysis</div>',
                    unsafe_allow_html=True
                )

                historical = get_historical_pitch_analysis(
                    venue
                )

                final_prediction, confidence = final_pitch_prediction(
                    historical,
                    weather_influence
                )

                # Prediction card
                st.markdown(
                    f"""
                    <div class="prediction-card">
                        <div class="prediction-label">
                            Predicted Pitch Condition
                        </div>
                        <div class="prediction-value">
                            🏏 {final_prediction}
                        </div>
                        <div class="small-text">
                            Confidence: {confidence}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # ------------------------------------------------
                # HISTORICAL DATA
                # ------------------------------------------------

                if historical is not None:

                    st.markdown(
                        f"""
                        <div class="success-box">
                            Historical venue data available:
                            <b>{historical["matches"]}</b> matches analyzed.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    st.markdown(
                        '<div class="section-title">'
                        'Historical Venue Tendency'
                        '</div>',
                        unsafe_allow_html=True
                    )

                    distribution = historical["distribution"]

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric(
                            "Batting Friendly",
                            f'{distribution.get("Batting Friendly", 0):.1f}%'
                        )

                    with col2:
                        st.metric(
                            "Balanced",
                            f'{distribution.get("Balanced", 0):.1f}%'
                        )

                    with col3:
                        st.metric(
                            "Bowling Friendly",
                            f'{distribution.get("Bowling Friendly", 0):.1f}%'
                        )

                    st.markdown(
                        f"""
                        <div class="info-box">
                            Recent venue tendency:
                            <b>{historical["recent_prediction"]}</b>
                            <br>
                            Based on the most recent 10 available matches.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                else:

                    st.markdown(
                        """
                        <div class="warning-box">
                            No historical pitch dataset is currently
                            available for this venue.
                            <br><br>
                            The prediction therefore relies primarily on
                            forecast weather conditions and is marked
                            <b>Low Confidence</b>.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                # ------------------------------------------------
                # WEATHER INFLUENCE
                # ------------------------------------------------

                st.markdown(
                    '<div class="section-title">'
                    'Weather Influence on Pitch'
                    '</div>',
                    unsafe_allow_html=True
                )

                if weather_influence == "Bowling Influence":
                    influence_text = (
                        "Weather conditions may favour bowlers, "
                        "especially through moisture, humidity or rain."
                    )

                elif weather_influence == "Batting Influence":
                    influence_text = (
                        "Weather conditions are relatively favourable "
                        "for batting."
                    )

                else:
                    influence_text = (
                        "Weather conditions do not strongly favour "
                        "either batting or bowling."
                    )

                st.markdown(
                    f"""
                    <div class="card">
                        <h3>{weather_influence}</h3>
                        <p class="small-text">
                            {influence_text}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if reasons:
                    st.markdown(
                        "**Factors considered:** "
                        + " • ".join(reasons)
                    )

                # ------------------------------------------------
                # METHODOLOGY
                # ------------------------------------------------

                st.markdown(
                    '<div class="section-title">Methodology</div>',
                    unsafe_allow_html=True
                )

                st.markdown(
                    """
                    <div class="info-box">
                    <b>Match:</b> Upcoming fixture retrieved from the
                    online Cricbuzz schedule.
                    <br><br>
                    <b>Weather:</b> Live forecast retrieved from Open-Meteo
                    using the selected venue's geographic coordinates.
                    <br><br>
                    <b>Pitch:</b> Historical venue behaviour is combined
                    with the expected weather influence.
                    <br><br>
                    <b>Important:</b> The pitch result represents a
                    <i>pitch tendency assessment</i>, not a direct
                    measurement of the physical pitch.
                    </div>
                    """,
                    unsafe_allow_html=True
                )

