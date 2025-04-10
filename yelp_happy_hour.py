import argparse
import csv
import json
import os
import random
import re
import time
import urllib.parse
from datetime import datetime
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


# Configure a session with retries for more reliable requests
def get_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


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

    # Ensure limit is within Yelp's restrictions (max 50 per call)
    request_limit = min(limit, 50)

    # Yelp API limits results to a maximum of 1000, but only allows
    # access to at most 240 results with pagination (offset)
    max_api_results = min(max_results, 240)

    # Focus on quality bars and pubs
    bar_categories = "bars,pubs,beergardens,cocktailbars,sportsbars,wine_bars,breweries"

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
            "price": "1,2,3",
            "attributes": "dogs_allowed,good_for_kids",
            "open_now": True,
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

                # Filter to only include businesses with at least 3.5 stars and some reviews
                filtered_businesses = [
                    b
                    for b in businesses
                    if b.get("rating", 0) >= 3.5 and b.get("review_count", 0) >= 10
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


def scrape_website_url(yelp_url):
    """
    Extract website URL from Yelp page HTML with improved detection methods.
    Returns tuple: (url, error_message)
    """
    error_message = None

    try:
        # Use a session with retries
        session = get_session()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
            "TE": "Trailers",
        }

        # Add a random delay to appear more human-like
        time.sleep(1 + random.random() * 2)

        # First try a HEAD request to check if the page is accessible
        try:
            head_response = session.head(yelp_url, headers=headers, timeout=10)
            if head_response.status_code != 200:
                return (
                    "",
                    f"Yelp page not accessible. Status code: {head_response.status_code}",
                )
        except Exception:
            # Continue anyway, the HEAD request is just a check
            pass

        response = session.get(yelp_url, headers=headers, timeout=15)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # Method 1: Look for the "Business website" element
            website_label = soup.find(
                "p", string=re.compile(r"Business website", re.IGNORECASE)
            )
            if website_label:
                # Get the parent container
                parent_div = website_label.find_parent("div")
                if parent_div:
                    # Find the anchor tag within this section
                    website_link = parent_div.find("a", href=True)
                    if website_link and "href" in website_link.attrs:
                        href = website_link["href"]
                        # Check if it's a redirect URL
                        if "biz_redir" in href:
                            # Extract the destination URL from the redirect
                            url_param = re.search(r"url=([^&]+)", href)
                            if url_param:
                                return urllib.parse.unquote(url_param.group(1)), None

            # Method 2: Look for any link with "y-css-14ckas3" class (as seen in your screenshot)
            website_elements = soup.find_all("a", class_="y-css-14ckas3")
            for element in website_elements:
                href = element.get("href", "")
                if "biz_redir" in href and "url=" in href:
                    url_param = re.search(r"url=([^&]+)", href)
                    if url_param:
                        return urllib.parse.unquote(url_param.group(1)), None

            # Method 3: Look for data-testid="website-link"
            website_element = soup.find("a", attrs={"data-testid": "website-link"})
            if website_element and "href" in website_element.attrs:
                href = website_element["href"]
                if "biz_redir" in href:
                    url_param = re.search(r"url=([^&]+)", href)
                    if url_param:
                        return urllib.parse.unquote(url_param.group(1)), None

            # Method 4: Look for any element containing "website"
            for a_tag in soup.find_all("a", href=True):
                href = a_tag.get("href", "")
                text = a_tag.get_text().lower()
                if "website" in text and "biz_redir" in href and "url=" in href:
                    url_param = re.search(r"url=([^&]+)", href)
                    if url_param:
                        return urllib.parse.unquote(url_param.group(1)), None

            # Method 5: Generic approach - find all biz_redir links
            for a_tag in soup.find_all("a", href=re.compile(r"biz_redir")):
                href = a_tag.get("href", "")
                if "url=" in href:
                    url_param = re.search(r"url=([^&]+)", href)
                    if url_param:
                        cleaned_url = urllib.parse.unquote(url_param.group(1))
                        # Make sure it's not pointing back to Yelp
                        if "yelp.com" not in cleaned_url:
                            return cleaned_url, None

            error_message = "No website link found in Yelp page HTML"
        else:
            error_message = (
                f"Failed to access Yelp page. Status code: {response.status_code}"
            )
    except Exception as e:
        error_message = f"Error scraping website URL: {str(e)}"

    return "", error_message


def get_emails_from_html(html: str) -> List[str]:
    """Extract email addresses from HTML text with improved pattern matching."""
    try:
        # Parse the HTML
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()

        # Get text content
        raw_text = soup.get_text(separator=" ")

        # Standard email pattern
        standard_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]{2,}"

        # Find emails with standard pattern
        candidates = re.findall(standard_pattern, raw_text)

        # Look for email-like text that might be obfuscated
        obfuscated_pattern = (
            r"\b[a-zA-Z0-9_.+-]+ ?\(at\) ?[a-zA-Z0-9-]+ ?\(dot\) ?[a-zA-Z0-9-.]{2,}\b"
        )
        obfuscated = re.findall(obfuscated_pattern, raw_text)

        # Convert obfuscated emails to standard format
        for email in obfuscated:
            cleaned = email.replace(" ", "").replace("(at)", "@").replace("(dot)", ".")
            candidates.append(cleaned)

        # Sometimes emails are split with HTML tags to prevent scraping
        # Look for patterns like "example@<span>domain</span>.com"
        email_parts = []
        for tag in soup.find_all(string=re.compile(r"@|email|mail|contact")):
            parent = tag.parent
            if parent:
                context = parent.get_text()
                if "@" in context:
                    parts = re.findall(r"[\w\.-]+@[\w\.-]+", context)
                    email_parts.extend(parts)

        # Add email parts to candidates
        candidates.extend(email_parts)

        # Filter out common false positives
        valid_emails = []
        for email in candidates:
            email = email.strip().lower()

            # Skip invalid emails
            if (
                # File extensions
                not email.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg"))
                # Example domains
                and not any(
                    domain in email
                    for domain in [
                        "@example.com",
                        "@domain.com",
                        "@yourdomain.com",
                        "@email.com",
                        "@yourcompany",
                        "@your-email",
                        "@your-domain",
                        "@website.com",
                    ]
                )
                # Invalid format
                and not email.startswith(".")
                and "@." not in email
                and email.count("@") == 1
                # Valid domain
                and "." in email.split("@")[1]
                # Minimum length
                and len(email) >= 6
            ):
                valid_emails.append(email)

        return list(set(valid_emails))
    except Exception as e:
        print(f"Error extracting emails from HTML: {e}")
        return []


def extract_emails_from_url(url):
    """
    Extract emails from a URL with improved extraction methods.
    Returns tuple: (emails_list, soup_object, error_message)
    """
    session = get_session()
    try:
        # More comprehensive headers to appear like a real browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        # Handle both http and https
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        # Use session with retry logic
        response = session.get(url, headers=headers, timeout=15, allow_redirects=True)

        if response.status_code == 200:
            # Check content type to make sure it's HTML
            content_type = response.headers.get("Content-Type", "").lower()
            if (
                "text/html" not in content_type
                and "application/xhtml+xml" not in content_type
            ):
                return [], None, f"Non-HTML content: {content_type}"

            try:
                html = response.text
                soup = BeautifulSoup(html, "html.parser")

                # Extract emails from text content
                text_emails = get_emails_from_html(html)

                # Extract emails from mailto links
                mailto_emails = []
                for a in soup.find_all("a", href=True):
                    href = a.get("href", "").strip().lower()
                    if href.startswith("mailto:"):
                        email = href.replace("mailto:", "").split("?")[0].strip()
                        if email and "@" in email and "." in email:
                            mailto_emails.append(email)

                # Extract emails from meta tags
                meta_emails = []
                for meta in soup.find_all("meta"):
                    content = meta.get("content", "")
                    if "@" in content and "." in content:
                        possible_emails = re.findall(
                            r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]{2,}",
                            content,
                        )
                        meta_emails.extend(possible_emails)

                # Extract from JSON-LD structured data
                script_emails = []
                for script in soup.find_all("script", type="application/ld+json"):
                    if script.string:
                        try:
                            data = json.loads(script.string)
                            if isinstance(data, dict):
                                # Look for email in standard schema.org structures
                                email = data.get("email") or data.get(
                                    "contactPoint", {}
                                ).get("email")
                                if email and "@" in email:
                                    script_emails.append(email)

                                # Look deeper in the structure
                                if "contactPoint" in data and isinstance(
                                    data["contactPoint"], list
                                ):
                                    for contact in data["contactPoint"]:
                                        if (
                                            isinstance(contact, dict)
                                            and "email" in contact
                                        ):
                                            script_emails.append(contact["email"])
                        except:
                            pass

                # Check image alt texts and titles for emails (sometimes used to avoid scrapers)
                img_emails = []
                for img in soup.find_all("img", alt=True):
                    alt_text = img.get("alt", "")
                    if "@" in alt_text and "." in alt_text:
                        possible_emails = re.findall(
                            r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]{2,}",
                            alt_text,
                        )
                        img_emails.extend(possible_emails)

                # Check for emails in data attributes (sometimes used for contact forms)
                data_emails = []
                for tag in soup.find_all(attrs={"data-email": True}):
                    email = tag.get("data-email", "")
                    if "@" in email and "." in email:
                        data_emails.append(email)

                # Combine all found emails
                all_emails = (
                    text_emails
                    + mailto_emails
                    + meta_emails
                    + script_emails
                    + img_emails
                    + data_emails
                )

                # Clean and deduplicate emails
                cleaned_emails = []
                for email in all_emails:
                    email = email.strip().lower()
                    if email and "@" in email and "." in email.split("@")[1]:
                        cleaned_emails.append(email)

                unique_emails = list(set(cleaned_emails))
                return unique_emails, soup, None

            except Exception as e:
                return [], None, f"HTML parsing error: {str(e)}"
        else:
            return (
                [],
                None,
                f"Failed to access URL. Status code: {response.status_code}",
            )

    except requests.exceptions.Timeout:
        return [], None, "Request timed out"
    except requests.exceptions.TooManyRedirects:
        return [], None, "Too many redirects"
    except requests.exceptions.SSLError:
        # Try again with http if https failed
        if url.startswith("https://"):
            try:
                return extract_emails_from_url(url.replace("https://", "http://"))
            except:
                return [], None, "SSL Error and HTTP fallback failed"
        return [], None, "SSL Error"
    except requests.exceptions.RequestException as e:
        return [], None, f"Request error: {str(e)}"
    except Exception as e:
        return [], None, f"Error processing URL: {str(e)}"


def get_subpages(base_url, soup, max_links=20):
    """Get potentially useful subpages for email extraction with improved targeting."""
    subpages = []
    try:
        base_domain = urllib.parse.urlparse(base_url).netloc

        # Keywords that suggest contact information might be present
        contact_keywords = [
            "contact",
            "about",
            "team",
            "staff",
            "people",
            "directory",
            "connect",
            "reach",
            "email",
            "mail",
            "info",
            "get-in-touch",
            "get_in_touch",
            "getintouch",
            "about-us",
            "about_us",
            "aboutus",
            "our-team",
            "our_team",
            "ourteam",
            "meet",
            "who-we-are",
            "location",
            "book",
            "reserve",
            "feedback",
            "inquiry",
            "contact-us",
            "contactus",
            "reservation",
        ]

        # First look for links with contact-suggesting text or paths
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            text = a.get_text().strip().lower()

            # Skip empty, javascript, or anchor links
            if not href or href.startswith(
                ("javascript:", "#", "tel:", "mailto:", "sms:")
            ):
                continue

            # Make relative URLs absolute
            full_url = urllib.parse.urljoin(base_url, href)
            parsed_url = urllib.parse.urlparse(full_url)

            # Only include links from the same domain
            if parsed_url.netloc != base_domain:
                continue

            # Check if the URL or link text suggests contact information
            url_path = parsed_url.path.lower()
            if any(
                keyword in url_path or keyword in text for keyword in contact_keywords
            ):
                if full_url not in subpages:
                    subpages.append(full_url)

            # Prioritize paths that are likely contact pages
            if parsed_url.path.lower() in [
                "/contact",
                "/about",
                "/team",
                "/contact-us",
                "/about-us",
            ]:
                if full_url not in subpages:
                    subpages.insert(0, full_url)  # Add to beginning for priority

            # Stop once we have enough links
            if len(subpages) >= max_links:
                break

        # If we didn't find any contact pages, look more broadly
        if not subpages:
            for a in soup.find_all("a", href=True):
                href = a.get("href", "").strip()

                # Skip problematic links
                if not href or href.startswith(
                    ("javascript:", "#", "tel:", "mailto:", "sms:")
                ):
                    continue

                # Make relative URLs absolute
                full_url = urllib.parse.urljoin(base_url, href)
                parsed_url = urllib.parse.urlparse(full_url)

                # Only include links from the same domain with short paths
                if parsed_url.netloc != base_domain:
                    continue

                # Look for short direct paths which might be main pages
                path_parts = [p for p in parsed_url.path.split("/") if p]
                if len(path_parts) == 1 and len(path_parts[0]) < 20:
                    if full_url not in subpages:
                        subpages.append(full_url)

                if len(subpages) >= max_links:
                    break
    except Exception as e:
        print(f"Error finding subpages: {e}")

    return subpages


def enhanced_email_scraper(base_url, deep_scrape=True):
    """
    Enhanced email scraper with improved email detection.
    Returns tuple: (emails_list, error_message)
    """
    found_emails = set()
    visited = set()
    errors = []

    # Handle cases where the URL doesn't have http/https
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url

    try:
        # First try: Extract emails from the main URL
        base_emails, soup, error = extract_emails_from_url(base_url)
        if error:
            errors.append(f"Base URL error: {error}")

        found_emails.update(base_emails)
        visited.add(base_url)

        # Check if "www." version gives different results (some sites redirect differently)
        if not base_url.startswith("https://www.") and "www." not in base_url:
            try:
                www_url = base_url.replace("https://", "https://www.")
                if www_url not in visited:
                    www_emails, _, www_error = extract_emails_from_url(www_url)
                    found_emails.update(www_emails)
                    visited.add(www_url)
            except:
                pass

        # Deep scrape: look at subpages for more emails
        if deep_scrape and soup:
            contact_urls = get_subpages(base_url, soup)
            if not contact_urls:
                errors.append("No contact or about pages found for deep scraping")

            # Visit each subpage to find emails
            for sub_url in contact_urls:
                if sub_url not in visited:
                    sub_emails, _, sub_error = extract_emails_from_url(sub_url)
                    if sub_error:
                        errors.append(f"Subpage error ({sub_url}): {sub_error}")

                    found_emails.update(sub_emails)
                    visited.add(sub_url)
                    # Add small delay between requests
                    time.sleep(0.5)

        # Try to find Facebook or Twitter pages that might have emails
        if soup and len(found_emails) == 0:
            social_links = []
            for a in soup.find_all("a", href=True):
                href = a.get("href", "").lower()
                if (
                    "facebook.com" in href
                    or "twitter.com" in href
                    or "instagram.com" in href
                ):
                    social_links.append(a["href"])

            # Visit up to 2 social media pages
            for social_url in social_links[:2]:
                if social_url not in visited:
                    social_url = urllib.parse.urljoin(base_url, social_url)
                    social_emails, _, social_error = extract_emails_from_url(social_url)
                    found_emails.update(social_emails)
                    visited.add(social_url)

        # Final step: Pattern cleanup and domain-based email inference
        if len(found_emails) == 0:
            # Try to infer emails based on domain name
            domain = urllib.parse.urlparse(base_url).netloc
            if domain.startswith("www."):
                domain = domain[4:]

            # Common patterns for business emails
            potential_emails = [
                f"info@{domain}",
                f"contact@{domain}",
                f"hello@{domain}",
                f"support@{domain}",
                f"reservations@{domain}",
            ]

            # Add these as potential emails (they'll be marked as "inferred")
            for email in potential_emails:
                found_emails.add(f"{email} [INFERRED]")

        email_list = list(found_emails)

        if not email_list:
            if errors:
                error_message = "; ".join(errors)
            else:
                error_message = "No email addresses found on website or subpages"
            return email_list, error_message

        return email_list, None

    except Exception as e:
        return list(found_emails), f"Email scraping error: {str(e)}"


def scrape_website_url_with_google(business_name, location):
    """
    Attempt to find a business website using Google search.
    Returns tuple: (url, error_message)
    """
    error_message = None
    try:
        query = f"{business_name} {location} site:.com"
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"

        # Use a session with retry logic
        session = get_session()

        # More realistic headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
        }

        # Add a random delay
        time.sleep(2 + random.random() * 2)

        response = session.get(search_url, headers=headers, timeout=15)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # Look for result links
            for cite in soup.find_all("cite"):
                href = cite.get_text()
                if "yelp.com" not in href and re.match(r"https?://", href):
                    # Verify this is a real website URL
                    if "." in href.split("//")[1]:
                        return href, None

            # Try another method - look for search result links
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                # Google search results have hrefs that start with /url?q=
                if href.startswith("/url?q="):
                    url_param = re.search(r"q=([^&]+)", href)
                    if url_param:
                        extracted_url = urllib.parse.unquote(url_param.group(1))
                        # Make sure it's a real URL and not a Google link
                        if (
                            re.match(r"https?://", extracted_url)
                            and "google" not in extracted_url
                            and "yelp" not in extracted_url
                        ):
                            return extracted_url, None

            error_message = "No suitable results found in Google search"
        else:
            error_message = (
                f"Google search failed with status code {response.status_code}"
            )
    except Exception as e:
        error_message = f"Google fallback failed: {str(e)}"

    return "", error_message


def extract_business_info(businesses, api_key):
    """Extract business information with minimal print statements."""
    business_info = []
    businesses_with_emails = 0

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

        # Print only the business name being processed
        print(f"Processing: {business_name}")

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


def save_to_csv(data, filename=None):
    """Save business data to a CSV file with specific column order."""
    if not os.path.exists("dat"):
        os.makedirs("dat")

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dat/happy_hour_businesses_{timestamp}.csv"
    else:
        filename = os.path.join("dat", filename)

    # Define the exact order of columns as specified
    ordered_columns = [
        "name",
        "website",
        "emails",
        "price",
        "zip_code",
        "city",
        "rating",
        "address",
        "review_count",
        "dogs_allowed",
        "phone",
        "categories",
        "good_for_kids",
    ]

    # Exclude error columns and yelp_url
    excluded_fields = ["website_error", "email_error", "yelp_url"]

    # Flatten any list fields (like emails)
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ordered_columns)
        writer.writeheader()
        for row in data:
            # Create a new dict with only the fields we want
            cleaned_row = {}
            for field in ordered_columns:
                if field in row:
                    # Flatten lists (like emails and categories)
                    if isinstance(row[field], list):
                        cleaned_row[field] = ", ".join(row[field])
                    else:
                        cleaned_row[field] = row[field]
                else:
                    cleaned_row[field] = ""  # Empty string for missing fields

            writer.writerow(cleaned_row)

    return filename


def main():
    # Start timing the script execution
    start_time = time.time()

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
        "--radius", type=int, default=20, help="Search radius in miles (max 24.85)"
    )
    parser.add_argument("--term", default="happy hour", help="Search term")
    parser.add_argument("--output", help="Output filename")
    parser.add_argument(
        "--limit", type=int, default=50, help="Number of results per API call (max 50)"
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=240,
        help="Maximum total number of businesses to fetch (Yelp limits to 240)",
    )

    args = parser.parse_args()

    print(f"Searching for '{args.term}' businesses within {args.radius} miles...")
    businesses = search_businesses(
        args.api_key,
        args.latitude,
        args.longitude,
        args.radius,
        args.term,
        args.limit,
        args.max_results,
    )

    print(f"Found {len(businesses)} businesses. Processing...")

    business_info, businesses_with_emails = extract_business_info(
        businesses, args.api_key
    )

    filename = save_to_csv(business_info, args.output)

    # Calculate execution time
    end_time = time.time()
    execution_time = end_time - start_time

    # Format the time
    if execution_time < 60:
        time_str = f"{execution_time:.2f} seconds"
    elif execution_time < 3600:
        minutes = int(execution_time // 60)
        seconds = execution_time % 60
        time_str = f"{minutes} minutes and {seconds:.2f} seconds"
    else:
        hours = int(execution_time // 3600)
        minutes = int((execution_time % 3600) // 60)
        seconds = execution_time % 60
        time_str = f"{hours} hours, {minutes} minutes and {seconds:.2f} seconds"

    print(f"\nResults summary:")
    print(f"- Total businesses processed: {len(businesses)}")
    print(
        f"- Businesses with websites: {sum(1 for b in business_info if b.get('website'))}"
    )
    print(f"- Businesses with email addresses: {businesses_with_emails}")
    print(f"- Data saved to: {filename}")
    print(f"- Total runtime: {time_str}")


if __name__ == "__main__":
    main()
