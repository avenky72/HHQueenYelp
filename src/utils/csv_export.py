import csv
import os
from datetime import datetime


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
