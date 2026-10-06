import pandas as pd
import math
import os


def load_condition_data():
    """Load all datasets used by condition metrics with fast CSV fallback."""
    try:
        pitch_data = pd.read_csv("data/pitch_ml_dataset.csv")
    except Exception:
        pitch_data = pd.DataFrame()

    if os.path.exists("data/arena_subset.csv"):
        arena_data = pd.read_csv("data/arena_subset.csv")
    else:
        try:
            arena_data = pd.read_excel(
                "data/arena_player_rating_calculated.xlsx",
                header=5
            )
        except Exception:
            arena_data = pd.DataFrame()

    if os.path.exists("data/cricket_player_stats_subset.csv"):
        cricket_player_stats = pd.read_csv("data/cricket_player_stats_subset.csv")
    else:
        try:
            cricket_player_stats = pd.read_excel(
                "data/cricket_player_stats.xlsx"
            )
        except Exception:
            cricket_player_stats = pd.DataFrame()

    return pitch_data, arena_data, cricket_player_stats


def load_stadium_analytics():
    """Load venue-level pitch and ball-by-ball stats dataset."""
    try:
        if os.path.exists("data/stadium_pitch_analytics.csv"):
            return pd.read_csv("data/stadium_pitch_analytics.csv")
    except Exception:
        pass
    return pd.DataFrame()


def get_stadium_profile(stadium_analytics, venue_name):
    """Retrieve or synthesize pitch profile for a venue."""
    default_profile = {
        "venue": str(venue_name or "Default Stadium").strip(),
        "country": "Unknown",
        "avg_1inn_runs": 165.0,
        "pace_wicket_pct": 60.0,
        "spin_wicket_pct": 40.0,
        "pace_econ": 8.1,
        "spin_econ": 7.2,
        "bounce_rating": 7.0,
        "seam_swing_rating": 6.5,
        "turn_rating": 6.0,
        "boundary_freq": 5.5
    }

    if stadium_analytics is None or stadium_analytics.empty or not venue_name:
        return default_profile

    target = str(venue_name).strip().lower()
    matches = stadium_analytics[
        stadium_analytics["venue"].astype(str).str.lower().str.contains(target, regex=False, na=False)
    ]

    if not matches.empty:
        return matches.iloc[0].to_dict()

    # Fallback substring search
    parts = target.split()
    for part in parts:
        if len(part) >= 4:
            sub = stadium_analytics[
                stadium_analytics["venue"].astype(str).str.lower().str.contains(part, regex=False, na=False)
            ]
            if not sub.empty:
                return sub.iloc[0].to_dict()

    return default_profile


def validate_condition_data(
    pitch_data,
    arena_data,
    cricket_player_stats
):
    """Basic validation for condition datasets."""
    required_pitch = {"venue", "pitch_score", "pitch_class"}
    return required_pitch.issubset(pitch_data.columns) if (pitch_data is not None and not pitch_data.empty) else False


def normalize_venue_name(venue):
    """Map common venue aliases to canonical venue names."""
    if venue is None:
        return ""

    value = str(venue).strip().lower()

    aliases = {
        "wankhede": "Wankhede Stadium",
        "wankhede stadium": "Wankhede Stadium",
        "arun jaitley": "Arun Jaitley Stadium",
        "arun jaitley stadium": "Arun Jaitley Stadium",
        "m chinnaswamy": "M Chinnaswamy Stadium",
        "m chinnaswamy stadium": "M Chinnaswamy Stadium",
        "chinnaswamy": "M Chinnaswamy Stadium",
        "ma chidambaram": "MA Chidambaram Stadium",
        "ma chidambaram stadium": "MA Chidambaram Stadium",
        "chepauk": "MA Chidambaram Stadium",
        "narendra modi": "Narendra Modi Stadium",
        "narendra modi stadium": "Narendra Modi Stadium",
        "lords": "Lords",
        "lord's": "Lords",
    }

    return aliases.get(value, str(venue).strip())


def get_venue_matches(pitch_data, venue):
    """Return historical pitch records for a venue."""
    if pitch_data is None or pitch_data.empty:
        return pd.DataFrame()

    if "venue" not in pitch_data.columns:
        return pd.DataFrame()

    target = normalize_venue_name(venue)

    normalized = pitch_data["venue"].astype(str).apply(
        normalize_venue_name
    )

    matches = pitch_data[normalized == target]

    if not matches.empty:
        return matches.copy()

    target_text = str(venue).strip().lower()
    if not target_text:
        return pd.DataFrame()

    return pitch_data[
        pitch_data["venue"]
        .astype(str)
        .str.lower()
        .str.contains(target_text, regex=False, na=False)
    ].copy()


def calculate_batting_percentage(
    pitch_data,
    venue,
    cricket_player_stats=None,
    team1=None,
    team2=None,
    format_name=None,
    weather=None,
    stadium_analytics=None
):
    """
    Calculate dynamic batting percentage for a stadium, pitch, match, and weather.
    """
    profile = get_stadium_profile(stadium_analytics, venue)
    avg_runs = profile.get("avg_1inn_runs", 165.0)

    # Base venue batting score from stadium stats (scaled 130 -> 195 runs = 30% -> 85%)
    base_venue_score = max(20.0, min(90.0, ((avg_runs - 130.0) / (195.0 - 130.0)) * 60.0 + 30.0))

    if pitch_data is not None and not pitch_data.empty and "pitch_score" in pitch_data.columns:
        data = pitch_data.copy()
        data["pitch_score"] = pd.to_numeric(data["pitch_score"], errors="coerce")
        data = data.dropna(subset=["pitch_score"])

        if not data.empty:
            target_venue = normalize_venue_name(venue)
            historical_venues = data["venue"].astype(str).apply(normalize_venue_name)
            venue_data = data[historical_venues == target_venue]

            min_score = data["pitch_score"].min()
            max_score = data["pitch_score"].max()

            if max_score > min_score and not venue_data.empty:
                hist_score = ((venue_data["pitch_score"].mean() - min_score) / (max_score - min_score)) * 100
                base_venue_score = (base_venue_score * 0.5) + (hist_score * 0.5)

    # Team batting strength adjustment
    team_score = None
    if cricket_player_stats is not None and not cricket_player_stats.empty and team1 and team2:
        team_values = []
        for team in [team1, team2]:
            ids = _get_team_player_ids(cricket_player_stats, team, format_name)
            if not ids:
                continue
            players = cricket_player_stats[
                pd.to_numeric(cricket_player_stats["Player ID"], errors="coerce").isin(ids)
            ].copy()
            if players.empty:
                continue

            components = []
            for col in ["Batting Average", "Batting Strike Rate"]:
                if col in players.columns:
                    val = pd.to_numeric(players[col], errors="coerce").dropna()
                    if not val.empty:
                        all_val = pd.to_numeric(cricket_player_stats[col], errors="coerce").dropna()
                        if not all_val.empty and all_val.max() > all_val.min():
                            comp = ((val.median() - all_val.min()) / (all_val.max() - all_val.min())) * 100
                            components.append(max(0, min(100, comp)))
            if components:
                team_values.append(sum(components) / len(components))
        if team_values:
            team_score = sum(team_values) / len(team_values)

    final_score = (base_venue_score * 0.70) + (team_score * 0.30) if team_score is not None else base_venue_score

    # Weather influence on batting
    if weather is not None:
        humidity = weather.get("humidity", 50)
        rain_prob = weather.get("rain_probability", 0)
        cloud = weather.get("cloud", 0)
        temp = weather.get("temperature_max", 25)

        # Dew or clear weather makes batting easier
        dew_prob = calculate_dew_probability(weather.get("temperature_min", temp), humidity) or 0
        if dew_prob > 50:
            final_score += 5.0
        if cloud > 70 or rain_prob > 50:
            final_score -= 6.0
        if temp >= 32:
            final_score += 3.0

    return round(float(max(15.0, min(95.0, final_score))), 1)


def _format_filter(arena_data, format_name):
    """Return Arena rows for the requested match format."""
    if arena_data is None or arena_data.empty or format_name is None:
        return arena_data.copy() if arena_data is not None else pd.DataFrame()

    requested = str(format_name).strip()
    format_map = {"T20I": "T20", "T20": "T20", "ODI": "ODI", "Test": "Test"}
    target = format_map.get(requested, requested)

    if "Format" not in arena_data.columns:
        return arena_data.copy()

    return arena_data[
        arena_data["Format"].astype(str).str.strip().str.lower() == target.lower()
    ].copy()


def _normalize_team_text(value):
    text = str(value or "").strip().lower()
    text = text.replace("&", "and").replace("'", "").replace("-", " ")
    return " ".join(text.split())


TEAM_ALIASES = {
    "ind": "india", "india": "india",
    "wi": "west indies", "west indies": "west indies",
    "eng": "england", "england": "england",
    "aus": "australia", "australia": "australia",
    "sa": "south africa", "south africa": "south africa",
    "nz": "new zealand", "new zealand": "new zealand",
    "pak": "pakistan", "pakistan": "pakistan",
    "sl": "sri lanka", "sri lanka": "sri lanka",
    "ban": "bangladesh", "bangladesh": "bangladesh",
    "afg": "afghanistan", "afghanistan": "afghanistan",
    "ire": "ireland", "ireland": "ireland",
    "zim": "zimbabwe", "zimbabwe": "zimbabwe",
}


def _canonical_team_name(value):
    normalized = _normalize_team_text(value)
    return TEAM_ALIASES.get(normalized, normalized)


def _get_team_player_ids(cricket_player_stats, team_name, format_name=None):
    if cricket_player_stats is None or cricket_player_stats.empty:
        return set()
    if "Player ID" not in cricket_player_stats.columns:
        return set()

    target = _canonical_team_name(team_name)
    if not target:
        return set()

    data = cricket_player_stats
    mask = pd.Series(False, index=data.index)

    for col in ["Team Short", "Team Name"]:
        if col in data.columns:
            mask |= data[col].map(_canonical_team_name).eq(target)

    if not mask.any() and len(target) >= 4:
        for col in ["Team Short", "Team Name"]:
            if col in data.columns:
                mask |= data[col].map(_normalize_team_text).str.contains(target, regex=False, na=False)

    ids = pd.to_numeric(data.loc[mask, "Player ID"], errors="coerce").dropna()
    return set(ids.astype(int).tolist())


def _get_match_players(arena_data, cricket_player_stats, team1, team2, format_name):
    ids_1 = _get_team_player_ids(cricket_player_stats, team1, format_name)
    ids_2 = _get_team_player_ids(cricket_player_stats, team2, format_name)
    player_ids = ids_1 | ids_2

    if not player_ids or "ID" not in arena_data.columns:
        return pd.DataFrame()

    ids = pd.to_numeric(arena_data["ID"], errors="coerce")
    match_players = arena_data[ids.isin(player_ids)].copy()
    return _format_filter(match_players, format_name)


def _calculate_team_adjusted_metric(
    arena_data, cricket_player_stats, team1, team2, format_name, columns, lower_is_better=True
):
    if arena_data is None or arena_data.empty or cricket_player_stats is None or cricket_player_stats.empty:
        return None

    data = _get_match_players(arena_data, cricket_player_stats, team1, team2, format_name)
    if data.empty:
        return None

    components = []
    for col in columns:
        if col not in data.columns:
            continue
        values = pd.to_numeric(data[col], errors="coerce").dropna()
        global_values = pd.to_numeric(arena_data[col], errors="coerce").dropna()
        if values.empty or global_values.empty:
            continue

        min_val = global_values.min()
        max_val = global_values.max()

        if max_val == min_val:
            comp = 50.0
        elif lower_is_better:
            comp = ((max_val - values.median()) / (max_val - min_val)) * 100
        else:
            comp = ((values.median() - min_val) / (max_val - min_val)) * 100

        components.append(comp)

    if not components:
        return None

    return round(float(max(0, min(100, sum(components) / len(components)))), 1)


def calculate_pace_assistance(
    arena_data,
    format_name=None,
    cricket_player_stats=None,
    team1=None,
    team2=None,
    venue=None,
    weather=None,
    stadium_analytics=None
):
    """
    Calculate pace assistance dynamically based on stadium stats, pitch type, weather, format, and matchups.
    """
    profile = get_stadium_profile(stadium_analytics, venue)
    pace_pct = profile.get("pace_wicket_pct", 60.0)
    seam_swing = profile.get("seam_swing_rating", 6.5)
    bounce = profile.get("bounce_rating", 7.0)

    # Base venue pace score (0-100)
    base_venue_pace = (pace_pct * 0.5) + (seam_swing * 5.0) + (bounce * 2.0)
    base_venue_pace = max(20.0, min(90.0, base_venue_pace))

    # Matchup factor from arena player stats
    matchup_score = None
    if team1 and team2 and arena_data is not None and cricket_player_stats is not None:
        p1 = _calculate_team_adjusted_metric(
            arena_data, cricket_player_stats, team1, team2, format_name,
            ["Average vs LH Fast Bowler", "Average vs RH Fast Bowler", "Expected Strike Rate vs Fast Bowling"],
            lower_is_better=True
        )
        p2 = _calculate_team_adjusted_metric(
            arena_data, cricket_player_stats, team1, team2, format_name,
            ["Balls per Boundary Fast"],
            lower_is_better=False
        )
        if p1 is not None and p2 is not None:
            matchup_score = (p1 + p2) / 2
        elif p1 is not None:
            matchup_score = p1
        elif p2 is not None:
            matchup_score = p2

    score = (base_venue_pace * 0.65) + (matchup_score * 0.35) if matchup_score is not None else base_venue_pace

    # Weather influence on Pace Assistance (Cloud, Wind, Humidity boost swing & seam!)
    if weather is not None:
        cloud = weather.get("cloud", 0)
        wind = weather.get("wind", 0)
        humidity = weather.get("humidity", 50)

        if cloud >= 60:
            score += 8.0
        elif cloud >= 40:
            score += 4.0

        if wind >= 20:
            score += 6.0
        elif wind >= 12:
            score += 3.0

        if humidity >= 70:
            score += 5.0

    # Match format adjustment (Test matches have fresh pitch swing & seam)
    if format_name:
        fmt = str(format_name).upper()
        if "TEST" in fmt:
            score += 7.0
        elif "ODI" in fmt:
            score += 3.0

    return round(float(max(15.0, min(95.0, score))), 1)


def calculate_spin_assistance(
    arena_data,
    format_name=None,
    cricket_player_stats=None,
    team1=None,
    team2=None,
    venue=None,
    weather=None,
    stadium_analytics=None
):
    """
    Calculate spin assistance dynamically based on stadium turn rating, pitch dry/dustiness, dew, and matchups.
    """
    profile = get_stadium_profile(stadium_analytics, venue)
    spin_pct = profile.get("spin_wicket_pct", 40.0)
    turn_rating = profile.get("turn_rating", 6.0)

    # Base venue spin score (0-100)
    base_venue_spin = (spin_pct * 0.6) + (turn_rating * 6.5)
    base_venue_spin = max(15.0, min(90.0, base_venue_spin))

    # Matchup factor from arena player stats
    matchup_score = None
    if team1 and team2 and arena_data is not None and cricket_player_stats is not None:
        matchup_score = _calculate_team_adjusted_metric(
            arena_data, cricket_player_stats, team1, team2, format_name,
            ["Average vs LH Spin Bowler", "Average vs RH Spin Bowler"],
            lower_is_better=True
        )

    score = (base_venue_spin * 0.65) + (matchup_score * 0.35) if matchup_score is not None else base_venue_spin

    # Weather influence on Spin Assistance (Dew reduces spin grip; Hot/dry bakes pitch for turn!)
    if weather is not None:
        temp = weather.get("temperature_max", 25)
        humidity = weather.get("humidity", 50)
        dew_prob = calculate_dew_probability(weather.get("temperature_min", temp), humidity) or 0

        # Heavy Dew makes ball slippery -> reduces spin grip
        if dew_prob > 60:
            score -= 12.0
        elif dew_prob > 40:
            score -= 6.0

        # Hot dry sun bakes surface -> increases turn & spin assistance
        if temp >= 33 and humidity <= 45:
            score += 10.0
        elif temp >= 30 and humidity <= 55:
            score += 5.0

    # Match format adjustment (Test pitches deteriorate and turn sharply on day 4/5)
    if format_name:
        fmt = str(format_name).upper()
        if "TEST" in fmt:
            score += 10.0
        elif "ODI" in fmt:
            score += 2.0

    return round(float(max(10.0, min(95.0, score))), 1)


def calculate_dew_probability(temperature_c, humidity_percent):
    """Estimate dew probability from temperature and relative humidity using Magnus formula."""
    try:
        temperature_c = float(temperature_c)
        humidity_percent = float(humidity_percent)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(temperature_c) or not math.isfinite(humidity_percent):
        return None

    humidity_percent = max(1.0, min(100.0, humidity_percent))

    a = 17.62
    b = 243.12

    gamma = math.log(humidity_percent / 100.0) + (a * temperature_c) / (b + temperature_c)
    dew_point = b * gamma / (a - gamma)
    spread = temperature_c - dew_point

    if spread <= 1:
        probability = 95.0
    elif spread <= 2:
        probability = 85.0
    elif spread <= 4:
        probability = 85.0 - ((spread - 2) / 2) * 35.0
    elif spread <= 6:
        probability = 50.0 - ((spread - 4) / 2) * 30.0
    elif spread <= 8:
        probability = 20.0 - ((spread - 6) / 2) * 15.0
    else:
        probability = 5.0

    return round(float(max(0, min(100, probability))), 1)


def calculate_pitch_surface_badge(batting_pct, pace_ast, spin_ast, dew_prob=0, pitch_class=None):
    """
    Determine the dynamic surface label badge based on calculated metrics.
    """
    if batting_pct is not None and batting_pct >= 66.0 and (pace_ast or 0) < 65.0 and (spin_ast or 0) < 65.0:
        return "BATTING-FRIENDLY SURFACE"

    if pace_ast is not None and spin_ast is not None:
        if pace_ast >= 65.0 and pace_ast > spin_ast:
            return "PACER-FRIENDLY SURFACE"
        elif spin_ast >= 62.0 and spin_ast > pace_ast:
            return "SPIN-FRIENDLY SURFACE"
        elif pace_ast >= 60.0 or spin_ast >= 60.0:
            return "BOWLING-FRIENDLY SURFACE"

    if pitch_class:
        cls = str(pitch_class).upper()
        if "BATTING" in cls:
            return "BATTING-FRIENDLY SURFACE"
        elif "BOWLING" in cls:
            return "BOWLING-FRIENDLY SURFACE"

    return "BALANCED SURFACE"
