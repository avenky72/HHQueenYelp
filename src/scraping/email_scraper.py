import json
import re
import time
import urllib.parse
from typing import List, Tuple

import requests
from bs4 import BeautifulSoup

from src.utils.session import get_session


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
