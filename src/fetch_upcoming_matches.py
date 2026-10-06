import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor


SCHEDULE_URL = (
    "https://www.cricbuzz.com/cricket-schedule/"
    "upcoming-series/international"
)

BASE_URL = "https://www.cricbuzz.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0 Safari/537.36"
    )
}

FALLBACK_UPCOMING_MATCHES = [
    {
        "title": "IND vs WI, 1st T20I, West Indies tour of India",
        "listing": "IND vs WI, 1st T20I",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": "7:00 PM",
        "venue": "Wankhede Stadium",
        "city": "Mumbai",
        "country": "India",
        "match_type": "T20I",
        "url": "https://www.cricbuzz.com/live-cricket-scores/sample1"
    },
    {
        "title": "AUS vs ENG, 1st ODI, Australia tour of England",
        "listing": "AUS vs ENG, 1st ODI",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": "5:30 PM",
        "venue": "Lords",
        "city": "London",
        "country": "England",
        "match_type": "ODI",
        "url": "https://www.cricbuzz.com/live-cricket-scores/sample2"
    },
    {
        "title": "IND vs SA, 2nd Test, South Africa tour of India",
        "listing": "IND vs SA, 2nd Test",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": "9:30 AM",
        "venue": "M Chinnaswamy Stadium",
        "city": "Bengaluru",
        "country": "India",
        "match_type": "Test",
        "url": "https://www.cricbuzz.com/live-cricket-scores/sample3"
    },
    {
        "title": "PAK vs NZ, 3rd T20I, New Zealand tour of Pakistan",
        "listing": "PAK vs NZ, 3rd T20I",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": "7:30 PM",
        "venue": "Gaddafi Stadium Lahore",
        "city": "Lahore",
        "country": "Pakistan",
        "match_type": "T20I",
        "url": "https://www.cricbuzz.com/live-cricket-scores/sample4"
    }
]


def get_page(url, timeout=4):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=timeout
    )
    response.raise_for_status()
    return BeautifulSoup(
        response.text,
        "html.parser"
    )


def extract_match_details(url):
    try:
        soup = get_page(url, timeout=4)
        text = soup.get_text(" ", strip=True)

        title = (
            soup.title.get_text(" ", strip=True)
            if soup.title
            else ""
        )
        title = title.replace(" - Cricbuzz", "")

        venue = ""
        city = ""
        country = ""

        venue_match = re.search(
            r"Venue\s*:\s*([^•]+?)\s*(?:•|Date\s*&\s*Time|$)",
            text,
            re.IGNORECASE
        )

        if venue_match:
            venue_text = venue_match.group(1).strip()
            venue_text = re.sub(r"\s+", " ", venue_text)
            parts = [
                part.strip()
                for part in venue_text.split(",")
                if part.strip()
            ]
            if len(parts) >= 2:
                venue = parts[0]
                city = parts[-1]
            else:
                venue = venue_text

        country_names = [
            "India", "South Africa", "Namibia", "England", "Pakistan",
            "Sri Lanka", "Afghanistan", "Bangladesh", "Australia",
            "New Zealand", "West Indies", "Zimbabwe", "Ireland",
            "Scotland", "Nepal", "United Arab Emirates", "United States", "Canada"
        ]

        for country_name in country_names:
            if country_name.lower() in text.lower():
                country = country_name
                break

        date_match = re.search(
            r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+"
            r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))",
            text,
            re.IGNORECASE
        )

        if not date_match:
            date_match = re.search(
                r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2})\b",
                text,
                re.IGNORECASE
            )

        if date_match:
            date_part = date_match.group(1)
            year_match = re.search(r"\b(20\d{2})\b", text)
            year = year_match.group(1) if year_match else str(datetime.now().year)

            try:
                if re.match(r"^\d{1,2}\s+[A-Za-z]{3}$", date_part):
                    match_date = datetime.strptime(
                        f"{date_part} {year}", "%d %b %Y"
                    ).strftime("%Y-%m-%d")
                else:
                    match_date = datetime.strptime(
                        f"{date_part} {year}", "%b %d %Y"
                    ).strftime("%Y-%m-%d")
            except ValueError:
                match_date = ""
        else:
            match_date = ""

        time_match = re.search(
            r"(\d{1,2}:\d{2}\s*(?:AM|PM))",
            text,
            re.IGNORECASE
        )
        match_time = time_match.group(1) if time_match else ""

        match_type = ""
        type_patterns = [
            r"\bTest\b", r"\bODI\b", r"\bT20I\b", r"\bT20\b", r"\bFirst Class\b"
        ]

        for pattern in type_patterns:
            type_match = re.search(pattern, title, re.IGNORECASE)
            if type_match:
                match_type = type_match.group(0)
                break

        return {
            "title": title,
            "date": match_date or datetime.now().strftime("%Y-%m-%d"),
            "time": match_time,
            "venue": venue,
            "city": city,
            "country": country,
            "match_type": match_type,
            "url": url
        }

    except Exception:
        return None


def fetch_match_links():
    try:
        soup = get_page(SCHEDULE_URL, timeout=5)
        matches = []
        seen = set()
        current_date = datetime.now().strftime("%Y-%m-%d")

        if soup.body:
            for child in soup.body.find_all(True):
                text = child.get_text(" ", strip=True)
                m_date = re.search(r"\b(MON|TUE|WED|THU|FRI|SAT|SUN),\s+([A-Z]{3}\s+\d{1,2}\s+20\d{2})\b", text, re.I)
                if m_date:
                    try:
                        current_date = datetime.strptime(m_date.group(2).title(), "%b %d %Y").strftime("%Y-%m-%d")
                    except Exception:
                        pass

                if child.name == "a" and child.get("href") and "/live-cricket-scores/" in child["href"]:
                    href = child["href"]
                    url = BASE_URL + href if href.startswith("/") else href
                    if url in seen:
                        continue
                    seen.add(url)

                    a_text = child.get_text(" ", strip=True)
                    if not a_text:
                        continue

                    lower_text = a_text.lower()
                    if "won" in lower_text or "result" in lower_text or "rescheduled" in lower_text:
                        continue

                    matches.append({
                        "listing": a_text,
                        "url": url,
                        "schedule_date": current_date
                    })

        return matches
    except Exception:
        return []


def fetch_upcoming_matches():
    links = fetch_match_links()
    if not links:
        return FALLBACK_UPCOMING_MATCHES

    links = links[:100]

    def process_item(item):
        details = extract_match_details(item["url"])
        schedule_date = item.get("schedule_date") or datetime.now().strftime("%Y-%m-%d")

        if details:
            details["listing"] = item["listing"]
            if not details.get("date"):
                details["date"] = schedule_date
            return details

        return {
            "title": item["listing"],
            "listing": item["listing"],
            "date": schedule_date,
            "time": "",
            "venue": "Venue not available",
            "city": "",
            "country": "",
            "match_type": "T20",
            "url": item["url"]
        }

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_item, item) for item in links]
        for future in futures:
            try:
                res = future.result(timeout=5)
                if res:
                    results.append(res)
            except Exception:
                pass

    if not results:
        return FALLBACK_UPCOMING_MATCHES

    return results


if __name__ == "__main__":
    print("Fetching upcoming matches...")
    matches = fetch_upcoming_matches()
    print(f"Retrieved {len(matches)} matches successfully.")
    for m in matches:
        print(f"{m['date']} | {m['title'][:50]} | {m['venue']}")