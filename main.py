import argparse
import time
from datetime import datetime

from src.api.yelp import search_businesses
from src.business.processor import extract_business_info
from src.utils.csv_export import save_to_csv


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
        "--batch-size",
        type=int,
        default=40,
        help="Number of results per API call (max 50, recommend 40 for 240 max results)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=240,
        help="Maximum total number of businesses to fetch (Yelp limits to 240)",
    )

    args = parser.parse_args()

    print(f"Searching for '{args.term}' businesses within {args.radius} miles...")
    print(f"Using batch size of {args.batch_size} to avoid cutoff issues")

    businesses = search_businesses(
        args.api_key,
        args.latitude,
        args.longitude,
        args.radius,
        args.term,
        args.batch_size,
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
