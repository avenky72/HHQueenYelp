import time

from src.api.yelp import get_business_details
from src.scraping.email_scraper import enhanced_email_scraper
from src.scraping.website_scraper import (
    scrape_website_url,
    scrape_website_url_with_google,
)


def extract_business_info(businesses, api_key):
    """Extract business information with improved progress tracking."""
    business_info = []
    businesses_with_emails = 0
    total_businesses = len(businesses)

    for i, business in enumerate(businesses):
        business_id = business.get("id")
        business_name = business.get("name")
        location_info = business.get("location", {})
        location = location_info.get("address1", "")
        city = location_info.get("city", "")
        zip_code = location_info.get("zip_code", "")
        coordinates = business.get("coordinates", {})
        categories = [c.get("title") for c in business.get("categories", [])]
        price = business.get("price", "N/A")

        # Print business name being processed with progress counter
        print(f"Processing {i+1}/{total_businesses}: {business_name}")

        # Get full details from Yelp
        details = get_business_details(api_key, business_id)

        # Extract attributes
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

        # Get the website URL from the API
        website_url = ""
        if details and "attributes" in details:
            website_url = details.get("attributes", {}).get("business_url", "")
        website_error = None

        # If no website in API attributes, try scraping (only print errors)
        if not website_url:
            website_url, website_error = scrape_website_url(yelp_url)
            if website_error:
                print(f"  Error: Could not get website - {website_error}")
            time.sleep(1)

        # If still no website, try Google (only print errors)
        if not website_url:
            website_url_google, google_error = scrape_website_url_with_google(
                business_name, location
            )
            if website_url_google:
                website_url = website_url_google
                website_error = None
            elif google_error:
                print(f"  Error: Google search failed - {google_error}")
            time.sleep(1)

        # Get emails if we have a website (only print errors)
        email_error = None
        emails = []
        if website_url:
            emails, email_error = enhanced_email_scraper(website_url)
            if emails:
                businesses_with_emails += 1
            elif email_error:
                print(f"  Error: Email extraction failed - {email_error}")

        # Build business info
        info = {
            "name": business_name,
            "emails": emails,
            "address": ", ".join(location_info.get("display_address", [])),
            "city": city,
            "zip_code": zip_code,
            "website": website_url,
            "good_for_kids": good_for_kids,
            "dogs_allowed": dogs_allowed,
            "price": price,
            "yelp_url": yelp_url,
            "rating": business.get("rating"),
            "categories": categories,
            "review_count": business.get("review_count"),
            "phone": business.get("phone") or details.get("phone", ""),
            "website_error": website_error,
            "email_error": email_error,
        }

        # Add the business
        business_info.append(info)

    return business_info, businesses_with_emails
