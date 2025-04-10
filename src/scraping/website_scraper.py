import random
import re
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup

from src.utils.session import get_session


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
