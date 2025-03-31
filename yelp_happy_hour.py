import requests
import json
import argparse
from datetime import datetime
import re
from bs4 import BeautifulSoup
import time
import urllib.parse

def search_businesses(api_key, latitude, longitude, radius_miles=15, term="bar restaurant", limit=50):
    """
    Search for businesses on Yelp based on location and search term.
    
    Args:
        api_key (str): Your Yelp Fusion API key
        latitude (float): Latitude of the center point
        longitude (float): Longitude of the center point
        radius_miles (int): Search radius in miles (max 24.85 miles for Yelp API)
        term (str): Search term, e.g., "bar restaurant"
        limit (int): Number of results per request (max 50 for Yelp API)
        
    Returns:
        list: List of businesses matching the search criteria
    """
    # Convert miles to meters for the Yelp API, capping at 40000 meters
    radius_meters = min(int(radius_miles * 1609.34), 40000)
    
    url = "https://api.yelp.com/v3/businesses/search"
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    all_businesses = []
    offset = 0
    total_fetched = 0
    
    # Broader categories that include all restaurants and bars
    categories = "restaurants,bars,food,nightlife"
    
    while True:
        params = {
            "term": term,
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius_meters,
            "categories": categories,
            "limit": limit,
            "offset": offset,
            "attributes": "dogs_allowed,good_for_kids"
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
    """
    Scrape the actual website URL from the Yelp business page.
    
    Args:
        yelp_url (str): URL of the Yelp business page
        
    Returns:
        str: The business's actual website URL or empty string if not found
    """
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
        if details and "url" in details:
            website_url = details.get("url", "")
        
        # If API didn't provide website or it's just the Yelp URL, try scraping
        if not website_url or "yelp.com" in website_url:
            print(f"  Scraping website URL for {business_name}...")
            website_url = scrape_website_url(yelp_url)
            # Add a small delay to avoid overloading Yelp's servers
            time.sleep(1)
        
        # Only include businesses where we successfully found a website URL
        if website_url and "yelp.com" not in website_url:
            # Filter for keywords that indicate a bar/restaurant might have happy hours
            categories_str = " ".join(category.lower() for category in [category.get("title", "") for category in business.get("categories", [])])
            name_lower = business_name.lower()
            
            # Create a list of bar/restaurant types likely to have happy hours
            bar_keywords = ["bar", "pub", "taver", "brew", "lounge", "cocktail", "beer", "wine", "liquor", "grill", "bistro", "cantina"]
            
            # Check if any of these keywords appear in the name or categories
            is_likely_bar = any(keyword in name_lower or keyword in categories_str for keyword in bar_keywords)
            
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
                "good_for_kids": good_for_kids,
                "is_likely_bar": is_likely_bar
            }
            business_info.append(info)
            print(f"  ✓ Added {business_name} with website: {website_url}")
        else:
            print(f"  ✗ Skipped {business_name} - No website found")
    
    return business_info

def save_to_json(data, filename=None):
    """
    Save data to a JSON file.
    
    Args:
        data (list): Data to save
        filename (str, optional): Filename to save to. If None, generates a timestamped filename.
        
    Returns:
        str: Filename where data was saved
    """
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
    parser.add_argument("--radius", type=int, default=15, help="Search radius in miles (max 24.85)")
    parser.add_argument("--term", default="bar restaurant", help="Search term")
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