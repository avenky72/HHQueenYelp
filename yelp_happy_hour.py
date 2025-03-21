import requests
import json
import argparse
from datetime import datetime

def search_businesses(eGU2qoxtM-LNjwtaQEdBE4NOgqRz1Se5s2iCZWovw-RCh8gA8bHYlLc4Iy1T2QsX7TKe1xALV3gcVDclIgEhf2Kb785gcoYUpe_8_OkwO4I2ieGvXomtekp3EnHcZ3Yx, latitude, longitude, radius_miles=25, term="happy hour", limit=50):
    """
    Search for businesses on Yelp based on location and search term.
    
    Args:
        api_key (str): Your Yelp Fusion API key
        latitude (float): Latitude of the center point
        longitude (float): Longitude of the center point
        radius_miles (int): Search radius in miles (max 25 miles for Yelp API)
        term (str): Search term, e.g., "happy hour"
        limit (int): Number of results per request (max 50 for Yelp API)
        
    Returns:
        list: List of businesses matching the search criteria
    """
    # Convert miles to meters for the Yelp API
    radius_meters = int(radius_miles * 1609.34)
    
    # Yelp API endpoint
    url = "https://api.yelp.com/v3/businesses/search"
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
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
            "offset": offset
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

def extract_business_info(businesses):
    """
    Extract relevant information from businesses.
    
    Args:
        businesses (list): List of business data from Yelp API
        
    Returns:
        list: List of dictionaries with extracted business information
    """
    business_info = []
    
    for business in businesses:
        info = {
            "name": business.get("name"),
            "rating": business.get("rating"),
            "review_count": business.get("review_count"),
            "address": ", ".join(business.get("location", {}).get("display_address", [])),
            "city": business.get("location", {}).get("city"),
            "zip_code": business.get("location", {}).get("zip_code"),
            "phone": business.get("phone"),
            "website": business.get("url"),
            "coordinates": business.get("coordinates"),
            "categories": [category.get("title") for category in business.get("categories", [])],
            "price": business.get("price", "N/A")
        }
        business_info.append(info)
    
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
    parser.add_argument("--radius", type=int, default=25, help="Search radius in miles (max 25)")
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
    
    business_info = extract_business_info(businesses)
    
    filename = save_to_json(business_info, args.output)
    print(f"Business information saved to {filename}")

if __name__ == "__main__":
    main()
