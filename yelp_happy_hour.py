import argparse
import csv
import json
import os
import re
import time
import urllib.parse
from datetime import datetime

import requests
from bs4 import BeautifulSoup


def search_businesses(
    api_key, latitude, longitude, radius_miles=10, term="happy hour", limit=50
):
    """
    Search for businesses on Yelp based on location and search term,
    focusing on higher-rated bars and restaurants that might have happy hours.
    """
    # Convert miles to meters for the Yelp API, capping at 40000 meters
    radius_meters = min(int(radius_miles * 1609.34), 40000)

    url = "https://api.yelp.com/v3/businesses/search"

    headers = {"Authorization": f"Bearer {api_key}"}

    all_businesses = []
    offset = 0

    # Maximum number of businesses to fetch (to avoid hitting limits)
    max_businesses = 100

    # Focus on quality bars and pubs
    bar_categories = "bars,pubs,beergardens,cocktailbars,sportsbars,wine_bars,breweries"

    params = {
        "term": term,
        "latitude": latitude,
        "longitude": longitude,
        "radius": radius_meters,
        "categories": bar_categories,
        "limit": limit,
        "sort_by": "rating",  # Sort by rating to get the best places first
        "price": "1,2,3",  # Price levels $, $$, and $$$ (exclude $$$$ very expensive places)
        "attributes": "dogs_allowed,good_for_kids",
        "open_now": True,  # Only show places that are currently open
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        businesses = data.get("businesses", [])
        total = data.get("total", 0)

        # Filter to only include businesses with at least 3.5 stars and some reviews
        filtered_businesses = [
            b
            for b in businesses
            if b.get("rating", 0) >= 3.5 and b.get("review_count", 0) >= 10
        ]

        print(
            f"Found {len(filtered_businesses)} quality bars/pubs out of {len(businesses)} results"
        )
        all_businesses.extend(filtered_businesses)
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

    return all_businesses


def get_business_details(api_key, business_id):
    """Get detailed information about a business from Yelp API."""
    url = f"https://api.yelp.com/v3/businesses/{business_id}"

    headers = {"Authorization": f"Bearer {api_key}"}

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(
            f"Error getting details for business {business_id}: {response.status_code}"
        )
        print(response.text)
        return {}


def scrape_website_url(yelp_url):
    """Extract website URL using BeautifulSoup from Yelp page HTML."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        response = requests.get(yelp_url, headers=headers, timeout=10)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # Method 1: Look for "website" button which contains the URL
            website_element = soup.find(
                "a", href=re.compile(r"https://www\.yelp\.com/biz_redir\?url=http")
            )

            if website_element and "href" in website_element.attrs:
                redirect_url = website_element["href"]
                match = re.search(r"url=(.*?)&", redirect_url)
                if match:
                    return urllib.parse.unquote(match.group(1))

            # Method 2: Look for business website text links
            for a_tag in soup.find_all("a"):
                if a_tag.text and "website" in a_tag.text.lower():
                    if "href" in a_tag.attrs:
                        redirect_url = a_tag["href"]
                        match = re.search(r"url=(.*?)&", redirect_url)
                        if match:
                            return urllib.parse.unquote(match.group(1))

            # Method 3: Look for structured data in JSON-LD script tags
            for script in soup.find_all("script", type="application/ld+json"):
                if script.string:
                    try:
                        data = json.loads(script.string)
                        if (
                            isinstance(data, dict)
                            and "url" in data
                            and "yelp.com" not in data["url"]
                        ):
                            return data["url"]
                    except:
                        pass

        return ""
    except Exception as e:
        print(f"Error scraping website URL: {e}")
        return ""


def extract_business_info(businesses, api_key):
    """Extract relevant information from businesses, including website URLs and emails."""
    business_info = []

    for i, business in enumerate(businesses):
        business_id = business.get("id")
        business_name = business.get("name")
        print(f"Getting details for business {i+1}/{len(businesses)}: {business_name}")

        # Get additional details for this business
        details = get_business_details(api_key, business_id)

        # Extract attributes from details
        attributes = details.get("attributes", {}) if details else {}

        dogs_allowed = "Unknown"
        if "DogsAllowed" in attributes:
            value = attributes.get("DogsAllowed", {}).get("value_type", "")
            dogs_allowed = (
                "Yes"
                if value in ["yes_free", "yes"]
                else ("Yes (Paid)" if value == "yes_paid" else "No")
            )

        good_for_kids = "Unknown"
        if "GoodForKids" in attributes:
            value = attributes.get("GoodForKids", {}).get("value_type", "")
            good_for_kids = "Yes" if value in ["yes_free", "yes"] else "No"

        yelp_url = business.get("url", "")
        website_url = details.get("website", "") if details else ""

        if not website_url or "yelp.com" in website_url:
            print(f"  Scraping website URL for {business_name}...")
            website_url = scrape_website_url(yelp_url)
            time.sleep(1)

        if website_url and "yelp.com" not in website_url:
            print(f"  Scraping emails from {website_url}...")
            emails = extract_emails_from_website(website_url)

            info = {
                "name": business_name,
                "rating": business.get("rating"),
                "review_count": business.get("review_count"),
                "address": ", ".join(
                    business.get("location", {}).get("display_address", [])
                ),
                "city": business.get("location", {}).get("city"),
                "zip_code": business.get("location", {}).get("zip_code"),
                "phone": business.get("phone"),
                "yelp_url": yelp_url,
                "website": website_url,
                "emails": emails,
                "coordinates": business.get("coordinates"),
                "categories": [
                    category.get("title") for category in business.get("categories", [])
                ],
                "price": business.get("price", "N/A"),
                "dogs_allowed": dogs_allowed,
                "good_for_kids": good_for_kids,
            }

            business_info.append(info)
            print(f"  ✓ Added {business_name} with website: {website_url}")
        else:
            print(f"  ✗ Skipped {business_name} - No website found")

    return business_info


def extract_emails_from_website(base_url, max_links=10):
    """Scrape the main page and subpages (1 level deep) of a website for emails."""
    visited = set()
    emails = set()

    def get_emails_from_url(url):
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                raw_text = soup.get_text(separator=" ")
                candidates = re.findall(
                    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", raw_text
                )
                found = {
                    email.strip().lower()
                    for email in candidates
                    if "@" in email and "." in email
                }

                return found, soup
        except:
            pass
        return set(), None

    # Scrape the base page
    visited.add(base_url)
    base_emails, soup = get_emails_from_url(base_url)
    emails.update(base_emails)

    # Always go 1 level deep: check internal links
    if soup:
        links = soup.find_all("a", href=True)
        internal_links = []

        for link in links:
            href = link["href"]
            if href.startswith("/") or base_url in href:
                full_url = urllib.parse.urljoin(base_url, href)
                if full_url not in visited:
                    internal_links.append(full_url)
            if len(internal_links) >= max_links:
                break

        for link in internal_links:
            visited.add(link)
            sub_emails, _ = get_emails_from_url(link)
            emails.update(sub_emails)

    return list(emails) if emails else None


def save_to_csv(data, filename=None):
    """Save business data to a CSV file in the 'dat' folder."""
    if not os.path.exists("dat"):
        os.makedirs("dat")

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dat/happy_hour_businesses_{timestamp}.csv"
    else:
        filename = os.path.join("dat", filename)

    # Get all unique keys for CSV headers
    fieldnames = set()
    for item in data:
        fieldnames.update(item.keys())
    fieldnames = list(fieldnames)

    # Flatten any list fields (like emails)
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            flat_row = {
                k: ", ".join(v) if isinstance(v, list) else v for k, v in row.items()
            }
            writer.writerow(flat_row)

    return filename


def main():
    parser = argparse.ArgumentParser(
        description="Search for happy hour businesses on Yelp"
    )
    parser.add_argument("--api-key", required=True, help="Yelp Fusion API key")
    parser.add_argument(
        "--latitude", required=True, type=float, help="Latitude of the center point"
    )
    parser.add_argument(
        "--longitude", required=True, type=float, help="Longitude of the center point"
    )
    parser.add_argument(
        "--radius", type=int, default=10, help="Search radius in miles (max 24.85)"
    )
    parser.add_argument("--term", default="happy hour", help="Search term")
    parser.add_argument("--output", help="Output filename")

    args = parser.parse_args()

    print(f"Searching for '{args.term}' businesses within {args.radius} miles...")
    businesses = search_businesses(
        args.api_key, args.latitude, args.longitude, args.radius, args.term
    )

    print(f"Found {len(businesses)} businesses")

    business_info = extract_business_info(businesses, args.api_key)

    print(
        f"Successfully extracted website URLs for {len(business_info)} of {len(businesses)} businesses"
    )

    filename = save_to_csv(business_info, args.output)

    print(f"Business information saved to {filename}")


if __name__ == "__main__":
    main()
