import math
import time

import requests


def search_businesses(
    api_key,
    latitude,
    longitude,
    radius_miles=10,
    term="happy hour",
    limit=50,
    max_results=500,
):
    """
    Search for businesses on Yelp based on location and search term,
    focusing on higher-rated bars and restaurants that might have happy hours.
    """
    # Convert miles to meters for the Yelp API, capping at 40000 meters (Yelp's max)
    radius_meters = min(int(radius_miles * 1609.34), 40000)

    url = "https://api.yelp.com/v3/businesses/search"
    headers = {"Authorization": f"Bearer {api_key}"}

    all_businesses = []
    offset = 0

    # Yelp API limits results to a maximum of 1000, but only allows
    # access to at most 240 results with pagination (offset)
    max_api_results = min(max_results, 240)

    # Calculate optimal batch size to avoid the cutoff issue
    # If max_results is 240, we want to use a batch size that divides it evenly
    # to ensure we get all results without running into the cutoff issue
    if max_api_results == 240:
        # Use 40 as batch size since 240 ÷ 40 = 6 (even batches)
        request_limit = 40
    else:
        # Otherwise use the provided limit (capped at 50 per Yelp's restriction)
        request_limit = min(limit, 50)

    # Focus on quality bars and pubs
    bar_categories = "bars,pubs,beergardens,cocktailbars,sportsbars,wine_bars,breweries,lounges,divebars,irish_pubs,gastropubs,whiskeybars,tikibars,hookah_bars,tapas,restaurants"

    # Keep making requests until we hit max_results or run out of businesses
    while len(all_businesses) < max_api_results and offset < max_api_results:
        params = {
            "term": term,
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius_meters,
            "categories": bar_categories,
            "limit": request_limit,
            "offset": offset,
            "sort_by": "rating",
            "price": "1,2,3,4",
        }

        try:
            response = requests.get(url, headers=headers, params=params)

            # Rate limiting - prevent hitting Yelp's rate limits
            time.sleep(0.5)

            if response.status_code == 200:
                data = response.json()
                businesses = data.get("businesses", [])
                total = data.get("total", 0)

                if not businesses:
                    # No more results to fetch
                    break

                # Filter to only include businesses with at least 3.0 stars and some reviews
                filtered_businesses = [
                    b
                    for b in businesses
                    if b.get("rating", 0) >= 3.0 and b.get("review_count", 0) >= 5
                ]

                print(
                    f"Batch {offset//request_limit + 1}: Found {len(filtered_businesses)} quality bars/pubs out of {len(businesses)} results"
                )
                all_businesses.extend(filtered_businesses)

                # Update offset for next batch
                offset += request_limit

                # Check if we've processed all available results
                if offset >= total or offset >= max_api_results:
                    print(f"Reached maximum available results ({offset}/{total})")
                    break

            elif response.status_code == 429:
                # Too many requests - wait longer before retry
                print("Rate limit hit, waiting 3 seconds...")
                time.sleep(3)
                continue
            else:
                print(f"Error: {response.status_code}")
                print(response.text)
                break

        except Exception as e:
            print(f"Exception during API request: {e}")
            break

    print(f"Total businesses fetched: {len(all_businesses)}")
    return all_businesses[:max_results]  # Trim to max_results if needed


def get_business_details(api_key, business_id):
    """Get detailed information about a business from Yelp API."""
    url = f"https://api.yelp.com/v3/businesses/{business_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            details = response.json()
            # Check for website field
            if "website" in details:
                print(f"  API provided website: {details['website']}")
            return details
        else:
            print(
                f"Error getting details for business {business_id}: {response.status_code}"
            )
            print(response.text)
            return {}
    except Exception as e:
        print(f"Exception getting business details: {e}")
        return {}


def get_location_coordinates(location_name):
    """
    Get the coordinates and appropriate radius for a specific location using Nominatim API.
    Returns a dictionary with 'latitude', 'longitude', and 'radius' if found, otherwise None.
    The radius is calculated based on the location's bounding box.
    """
    # Format the search query (add USA for better specificity)
    query = f"{location_name}, USA"

    url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1&addressdetails=1&extratags=1&bounded=1"
    headers = {"User-Agent": "HappyHourFinder/1.0"}

    print(f"Geocoding location: {location_name}...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        time.sleep(1)  # Respect rate limit (1 request per second)

        if response.status_code == 200:
            data = response.json()
            if data:
                # Get the first result
                result = data[0]

                # Default radius in miles (will be overridden by user input in main.py)
                radius = 5

                if "boundingbox" in result:
                    # Bounding box is [min_lat, max_lat, min_lon, max_lon]
                    bbox = result["boundingbox"]
                    try:
                        min_lat, max_lat, min_lon, max_lon = map(float, bbox)

                        # Calculate distance from center to corner of bounding box (rough approximation)
                        center_lat = float(result["lat"])
                        center_lon = float(result["lon"])

                        # Haversine formula for approximate distance in miles
                        R = 3958.8  # Earth radius in miles

                        # Calculate distance from center to northeast corner of bounding box
                        dlat = math.radians(max_lat - center_lat)
                        dlon = math.radians(max_lon - center_lon)

                        a = (
                            math.sin(dlat / 2) ** 2
                            + math.cos(math.radians(center_lat))
                            * math.cos(math.radians(max_lat))
                            * math.sin(dlon / 2) ** 2
                        )
                        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                        distance = R * c  # Distance in miles

                        # Use half the diagonal as a reasonable radius (max 24 miles - Yelp's limit)
                        radius = min(distance / 2, 24)
                    except Exception as e:
                        print(f"Error calculating radius from bounding box: {e}")
                        # Fall back to default radius

                print(
                    f"Found coordinates for {location_name}: Lat {result['lat']}, Lon {result['lon']}"
                )
                print(f"Calculated appropriate radius: {radius} miles")

                return {
                    "latitude": float(result["lat"]),
                    "longitude": float(result["lon"]),
                    "radius": radius,
                }
            else:
                print(f"Could not find coordinates for {location_name}")
                return None
        else:
            print(
                f"Nominatim API error for {location_name}: Status {response.status_code}"
            )
            return None

    except Exception as e:
        print(f"Error during geocoding for {location_name}: {str(e)}")
        return None
