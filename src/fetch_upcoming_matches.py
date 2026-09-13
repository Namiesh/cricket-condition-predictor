import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime


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


def get_page(url):

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()

    return BeautifulSoup(
        response.text,
        "html.parser"
    )


def extract_match_details(url):

    try:

        soup = get_page(url)

        text = soup.get_text(
            " ",
            strip=True
        )

        # ========================================================
        # MATCH TITLE
        # ========================================================

        title = (
            soup.title.get_text(
                " ",
                strip=True
            )
            if soup.title
            else ""
        )

        title = title.replace(
            " - Cricbuzz",
            ""
        )

        # ========================================================
        # VENUE + CITY
        # ========================================================

        venue = ""
        city = ""
        country = ""

        # Cricbuzz normally contains:
        #
        # Venue: Namibia Cricket Ground, Windhoek
        #
        venue_match = re.search(
            r"Venue\s*:\s*"
            r"([^•]+?)"
            r"\s*(?:•|Date\s*&\s*Time|$)",
            text,
            re.IGNORECASE
        )

        if venue_match:

            venue_text = venue_match.group(1).strip()

            # Remove unwanted whitespace
            venue_text = re.sub(
                r"\s+",
                " ",
                venue_text
            )

            # Split venue and city
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

        # ========================================================
        # COUNTRY
        # ========================================================

        # Try to get country from title/page text where possible.
        country_names = [
            "India",
            "South Africa",
            "Namibia",
            "England",
            "Pakistan",
            "Sri Lanka",
            "Afghanistan",
            "Bangladesh",
            "Australia",
            "New Zealand",
            "West Indies",
            "Zimbabwe",
            "Ireland",
            "Scotland",
            "Nepal",
            "Kenya",
            "Rwanda",
            "Uganda",
            "Botswana",
            "Malaysia",
            "United Arab Emirates",
            "United States",
            "Canada"
        ]

        for country_name in country_names:

            if country_name.lower() in text.lower():

                country = country_name

                break

        # ========================================================
        # DATE
        # ========================================================

        date_match = re.search(
            r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+"
            r"(\d{1,2}\s+"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))",
            text,
            re.IGNORECASE
        )

        if not date_match:

            date_match = re.search(
                r"\b("
                r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                r"\s+\d{1,2}"
                r")\b",
                text,
                re.IGNORECASE
            )

        if date_match:

            date_part = date_match.group(1)

            year_match = re.search(
                r"\b(20\d{2})\b",
                text
            )

            if year_match:

                year = year_match.group(1)

            else:

                year = str(datetime.now().year)

            try:

                if re.match(
                    r"^\d{1,2}\s+[A-Za-z]{3}$",
                    date_part
                ):

                    match_date = datetime.strptime(
                        f"{date_part} {year}",
                        "%d %b %Y"
                    ).strftime("%Y-%m-%d")

                else:

                    match_date = datetime.strptime(
                        f"{date_part} {year}",
                        "%b %d %Y"
                    ).strftime("%Y-%m-%d")

            except ValueError:

                match_date = ""

        else:

            match_date = ""

        # ========================================================
        # TIME
        # ========================================================

        time_match = re.search(
            r"(\d{1,2}:\d{2}\s*(?:AM|PM))",
            text,
            re.IGNORECASE
        )

        match_time = (
            time_match.group(1)
            if time_match
            else ""
        )

        # ========================================================
        # MATCH TYPE
        # ========================================================

        match_type = ""

        type_patterns = [
            r"\bTest\b",
            r"\bODI\b",
            r"\bT20I\b",
            r"\bT20\b",
            r"\bFirst Class\b"
        ]

        for pattern in type_patterns:

            type_match = re.search(
                pattern,
                title,
                re.IGNORECASE
            )

            if type_match:

                match_type = type_match.group(0)

                break

        # ========================================================
        # RETURN
        # ========================================================

        return {
            "title": title,
            "date": match_date,
            "time": match_time,
            "venue": venue,
            "city": city,
            "country": country,
            "match_type": match_type,
            "url": url
        }

    except Exception as error:

        print(
            f"Could not read match page: {url}"
        )

        print(error)

        return None


def fetch_match_links():

    soup = get_page(
        SCHEDULE_URL
    )

    matches = []

    seen = set()

    for link in soup.find_all(
        "a",
        href=True
    ):

        href = link["href"]

        if "/live-cricket-scores/" not in href:
            continue

        if href.startswith("/"):
            url = BASE_URL + href
        else:
            url = href

        if url in seen:
            continue

        seen.add(url)

        text = link.get_text(
            " ",
            strip=True
        )

        if not text:
            continue

        lower_text = text.lower()

        # Ignore completed matches
        if "won" in lower_text:
            continue

        if "result" in lower_text:
            continue

        # Ignore rescheduled duplicate
        if "rescheduled" in lower_text:
            continue

        matches.append({
            "listing": text,
            "url": url
        })

    return matches


def fetch_upcoming_matches():

    links = fetch_match_links()

    results = []

    processed_urls = set()

    for item in links:

        url = item["url"]

        if url in processed_urls:
            continue

        processed_urls.add(url)

        details = extract_match_details(
            url
        )

        if details is None:
            continue

        details["listing"] = item["listing"]

        results.append(
            details
        )

    return results


if __name__ == "__main__":

    print("\n")
    print("=" * 80)
    print("UPCOMING CRICKET MATCH DETAILS")
    print("=" * 80)

    try:

        matches = fetch_upcoming_matches()

        for index, match in enumerate(
            matches,
            1
        ):

            print(
                f"\n{index}. {match['title']}"
            )

            print(
                f"   Date: {match['date']}"
            )

            print(
                f"   Time: {match['time']}"
            )

            print(
                f"   Type: {match['match_type']}"
            )

            print(
                f"   Venue: {match['venue']}"
            )

            print(
                f"   City: {match['city']}"
            )

            print(
                f"   Country: {match['country']}"
            )

            print(
                f"   URL: {match['url']}"
            )

        print("\n")
        print(
            f"Total matches: {len(matches)}"
        )

    except Exception as error:

        print("\nERROR:")
        print(error)