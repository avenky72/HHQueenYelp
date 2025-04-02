import requests
import json
import argparse
from datetime import datetime
import re
from bs4 import BeautifulSoup
import time
import urllib.parse

def search_businesses(api_key, latitude, longitude, radius_miles=10, term="happy hour", limit=50):
    """
    Search for businesses on Yelp based on location and search term,
    focusing on higher-rated bars and restaurants that might have happy hours.
    """
    # Convert miles to meters for the Yelp API, capping at 40000 meters
    radius_meters = min(int(radius_miles * 1609.34), 40000)
    
    url = "https://api.yelp.com/v3/businesses/search"
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
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
        "price": "1,2,3",     # Price levels $, $$, and $$$ (exclude $$$$ very expensive places)
        "attributes": "dogs_allowed,good_for_kids",
        "open_now": True      # Only show places that are currently open
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        businesses = data.get("businesses", [])
        total = data.get("total", 0)
        
        # Filter to only include businesses with at least 3.5 stars and some reviews
        filtered_businesses = [
            b for b in businesses 
            if b.get("rating", 0) >= 3.5 and b.get("review_count", 0) >= 10
        ]
        
        print(f"Found {len(filtered_businesses)} quality bars/pubs out of {len(businesses)} results")
        all_businesses.extend(filtered_businesses)
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
    
    return all_businesses

def get_business_details(api_key, business_id):
    """Get detailed information about a business from Yelp API."""
    url = f"https://api.yelp.com/v3/businesses/{business_id}"
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error getting details for business {business_id}: {response.status_code}")
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
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Method 1: Look for "website" button which contains the URL
            website_element = soup.find('a', href=re.compile(r'https://www\.yelp\.com/biz_redir\?url=http'))
            
            if website_element and 'href' in website_element.attrs:
                redirect_url = website_element['href']
                match = re.search(r'url=(.*?)&', redirect_url)
                if match:
                    return urllib.parse.unquote(match.group(1))
            
            # Method 2: Look for business website text links
            for a_tag in soup.find_all('a'):
                if a_tag.text and 'website' in a_tag.text.lower():
                    if 'href' in a_tag.attrs:
                        redirect_url = a_tag['href']
                        match = re.search(r'url=(.*?)&', redirect_url)
                        if match:
                            return urllib.parse.unquote(match.group(1))
            
            # Method 3: Look for structured data in JSON-LD script tags
            for script in soup.find_all('script', type='application/ld+json'):
                if script.string:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and 'url' in data and 'yelp.com' not in data['url']:
                            return data['url']
                    except:
                        pass
        
        return ""
    except Exception as e:
        print(f"Error scraping website URL: {e}")
        return ""

def extract_business_info(businesses, api_key):
    """Extract relevant information from businesses, including website URLs."""
    business_info = []
    
    for i, business in enumerate(businesses):
        business_id = business.get("id")
        business_name = business.get("name")
        print(f"Getting details for business {i+1}/{len(businesses)}: {business_name}")
        
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
        
        # Get the Yelp URL
        yelp_url = business.get("url", "")
        
        # Try to get website from API first
        website_url = ""
        if details and "website" in details:
            website_url = details.get("website", "")
        
        # If API didn't provide website or it's just the Yelp URL, try scraping
        if not website_url or "yelp.com" in website_url:
            print(f"  Scraping website URL for {business_name}...")
            website_url = scrape_website_url(yelp_url)
            # Add a small delay to avoid overloading Yelp's servers
            time.sleep(1)
        
        # Only include businesses where we successfully found a website URL
        if website_url and "yelp.com" not in website_url:
            info = {
                "name": business_name,
                "rating": business.get("rating"),
                "review_count": business.get("review_count"),
                "address": ", ".join(business.get("location", {}).get("display_address", [])),
                "city": business.get("location", {}).get("city"),
                "zip_code": business.get("location", {}).get("zip_code"),
                "phone": business.get("phone"),
                "yelp_url": yelp_url,
                "website": website_url,
                "coordinates": business.get("coordinates"),
                "categories": [category.get("title") for category in business.get("categories", [])],
                "price": business.get("price", "N/A"),
                "dogs_allowed": dogs_allowed,
                "good_for_kids": good_for_kids
            }
            business_info.append(info)
            print(f"  ✓ Added {business_name} with website: {website_url}")
        else:
            print(f"  ✗ Skipped {business_name} - No website found")
    
    return business_info

def save_to_json(data, filename=None):
    """Save business data to a JSON file."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"happy_hour_businesses_{timestamp}.json"
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    
    return filename

def main():
    parser = argparse.ArgumentParser(description="Search for happy hour businesses on Yelp")
    parser.add_argument("--api-key", required=True, help="Yelp Fusion API key")
    parser.add_argument("--latitude", required=True, type=float, help="Latitude of the center point")
    parser.add_argument("--longitude", required=True, type=float, help="Longitude of the center point")
    parser.add_argument("--radius", type=int, default=10, help="Search radius in miles (max 24.85)")
    parser.add_argument("--term", default="happy hour", help="Search term")
    parser.add_argument("--output", help="Output filename")
    
    args = parser.parse_args()
    
    print(f"Searching for '{args.term}' businesses within {args.radius} miles...")
    businesses = search_businesses(
        args.api_key, 
        args.latitude, 
        args.longitude, 
        args.radius, 
        args.term
    )
    
    print(f"Found {len(businesses)} businesses")
    
    business_info = extract_business_info(businesses, args.api_key)
    
    print(f"Successfully extracted website URLs for {len(business_info)} of {len(businesses)} businesses")
    
    filename = save_to_json(business_info, args.output)
    print(f"Business information saved to {filename}")

if __name__ == "__main__":
    main()