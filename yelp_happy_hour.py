import argparse
import os
import re
import time
import urllib.parse
from datetime import datetime

import pandas as pd
import requests
import undetected_chromedriver as uc
from bs4 import BeautifulSoup


def search_businesses(
    api_key, latitude, longitude, radius_miles=25, term="happy hour", limit=50
):
    """
    Search for businesses on Yelp based on location and search term.

    Args:
        api_key (str): Your Yelp Fusion API key
        latitude (float): Latitude of the center point
        longitude (float): Longitude of the center point
        radius_miles (int): Search radius in miles (max 24.85 miles for Yelp API)
        term (str): Search term, e.g., "happy hour"
        limit (int): Number of results per request (max 50 for Yelp API)

    Returns:
        list: List of businesses matching the search criteria
    """
    # Convert miles to meters for the Yelp API, capping at 40000 meters
    radius_meters = min(int(radius_miles * 1609.34), 40000)

    url = "https://api.yelp.com/v3/businesses/search"

    headers = {"Authorization": f"Bearer {api_key}"}

    all_businesses = []
    offset = 0
    total_fetched = 0

    while True:
        params = {
            "term": term,
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius_meters,
            "categories": "restaurants,bars",
            "limit": limit,
            "offset": offset,
            "attributes": "dogs_allowed,hot_and_new,good_for_kids",
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            businesses = data.get("businesses", [])
            total = data.get("total", 0)

            if not businesses:
                break

            all_businesses.extend(businesses)
            total_fetched += len(businesses)

            print(f"Fetched {total_fetched} of {total} businesses...")

            if total_fetched >= total or total_fetched >= 1000:
                break

            offset += limit
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            break

    return all_businesses


def get_business_details(api_key, business_id):
    """
    Get detailed information about a business from Yelp API.

    Args:
        api_key (str): Your Yelp Fusion API key
        business_id (str): Yelp business ID

    Returns:
        dict: Detailed business information
    """
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
    """
    Scrape and clean the actual website URL from a Yelp business page using Selenium.
    """
    try:
        # Start a headless browser
        options = uc.ChromeOptions()
        # options.headless = True
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControlled")
        driver = uc.Chrome(options=options)

        driver.get(yelp_url)
        time.sleep(3)  # Give it a moment to load dynamic content

        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()

        outer_div = soup.find("div", class_="y-css-4cg16w")
        if not outer_div:
            print("Outer div not found")
            return ""

        link_tag = outer_div.find("a", class_="y-css-14cka3", href=True)
        if not link_tag:
            print("Link tag not found")
            return ""

        redirect_url = link_tag["href"]
        match = re.search(r"url=(.*?)&", redirect_url)
        if not match:
            print("No URL found in redirect")
            return ""

        raw_url = urllib.parse.unquote(match.group(1))
        parsed_url = urllib.parse.urlparse(raw_url)
        clean_url = (
            f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}".rstrip("/")
        )

        print(f"Scraped: {clean_url}")
        return clean_url

    except Exception as e:
        print(f"Error scraping website URL with Selenium: {e}")
        return ""

    except Exception as e:
        print(f"Error scraping website URL: {e}")
        return ""


def extract_business_info(businesses, api_key):
    """
    Extract relevant information from businesses.

    Args:
        businesses (list): List of business data from Yelp API
        api_key (str): Your Yelp Fusion API key

    Returns:
        list: List of dictionaries with extracted business information
    """
    business_info = []

    for i, business in enumerate(businesses):
        business_id = business.get("id")
        print(
            f"Getting details for business {i+1}/{len(businesses)}: {business.get('name')}"
        )

        details = get_business_details(api_key, business_id)

        attributes = {}
        if details:
            attributes = details.get("attributes", {})

        dogs_allowed = "Unknown"
        if "DogsAllowed" in attributes:
            dogs_option = attributes.get("DogsAllowed", {}).get("value_type", "")
            if dogs_option in ["yes_free", "yes"]:
                dogs_allowed = "Yes"
            elif dogs_option == "yes_paid":
                dogs_allowed = "Yes (Paid)"
            else:
                dogs_allowed = "No"

        good_for_kids = "Unknown"
        if "GoodForKids" in attributes:
            kids_option = attributes.get("GoodForKids", {}).get("value_type", "")
            if kids_option in ["yes_free", "yes"]:
                good_for_kids = "Yes"
            else:
                good_for_kids = "No"

        yelp_url = business.get("url", "")

        # Try to get website from API first
        website_url = ""
        if details and "url" in details:
            website_url = details.get("url", "")

        # If API didn't provide website or it's just the Yelp URL, try scraping
        if not website_url or "yelp.com" in website_url:
            print(f"  Scraping website URL for {business.get('name')}...")
            website_url = scrape_website_url(yelp_url)
            # Add a small delay to avoid overloading Yelp's servers
            time.sleep(1)

        info = {
            "name": business.get("name"),
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
            "coordinates": business.get("coordinates"),
            "categories": [
                category.get("title") for category in business.get("categories", [])
            ],
            "price": business.get("price", "N/A"),
            "dogs_allowed": dogs_allowed,
            "good_for_kids": good_for_kids,
        }
        business_info.append(info)

    return business_info


def save_to_csv(data, filename=None):
    """
    Save data to a CSV file in the 'dat' folder.

    Args:
        data (list): Data to save
        filename (str, optional): Base filename (with or without .csv). If None, generates a timestamped filename.

    Returns:
        str: Full path to the saved CSV file
    """
    os.makedirs("dat", exist_ok=True)

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"happy_hour_businesses_{timestamp}.csv"
    elif not filename.endswith(".csv"):
        filename += ".csv"

    filepath = os.path.join("dat", filename)

    try:
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False)
        return filepath
    except Exception as e:
        print(f"Error saving CSV: {e}")
        return None


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
        "--radius", type=int, default=24, help="Search radius in miles (max 24.85)"
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

    filename = save_to_csv(business_info, args.output)
    print(f"Business information saved to {filename}")


if __name__ == "__main__":
    main()
