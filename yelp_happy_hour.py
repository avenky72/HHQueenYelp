import argparse
import json
import os
from datetime import datetime

import pandas as pd
import requests


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

    # Yelp API endpoint
    url = "https://api.yelp.com/v3/businesses/search"

    headers = {"Authorization": f"Bearer {api_key}"}

    # Initialize results list and offset
    all_businesses = []
    offset = 0
    total_fetched = 0

    # Yelp API allows a maximum of 1000 results (50 per request with a maximum of 20 requests)
    while True:
        params = {
            "term": term,
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius_meters,
            "categories": "restaurants,bars",
            "limit": limit,
            "offset": offset,
            # Add attributes to help with filtering
            "attributes": "dogs_allowed,happy_hour,good_for_kids",
        }

        response = requests.get(url, headers=headers, params=params)

        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            businesses = data.get("businesses", [])
            total = data.get("total", 0)

            # No more results
            if not businesses:
                break

            all_businesses.extend(businesses)
            total_fetched += len(businesses)

            print(f"Fetched {total_fetched} of {total} businesses...")

            # If we've fetched all available businesses or reached Yelp's limit
            if total_fetched >= total or total_fetched >= 1000:
                break

            # Increment offset for next request
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

        # Get additional details for this business
        details = get_business_details(api_key, business_id)

        # Extract attributes from details
        attributes = {}
        if details:
            attributes = details.get("attributes", {})

        # Check if dogs are allowed
        dogs_allowed = "Unknown"
        if "DogsAllowed" in attributes:
            dogs_option = attributes.get("DogsAllowed", {}).get("value_type", "")
            if dogs_option in ["yes_free", "yes"]:
                dogs_allowed = "Yes"
            elif dogs_option == "yes_paid":
                dogs_allowed = "Yes (Paid)"
            else:
                dogs_allowed = "No"

        # Check if good for kids
        good_for_kids = "Unknown"
        if "GoodForKids" in attributes:
            kids_option = attributes.get("GoodForKids", {}).get("value_type", "")
            if kids_option in ["yes_free", "yes"]:
                good_for_kids = "Yes"
            else:
                good_for_kids = "No"

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
            "website": business.get("url"),
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
