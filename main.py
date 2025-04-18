import argparse
import os
import time
from datetime import datetime

from src.api.yelp import get_location_coordinates, search_businesses
from src.business.processor import extract_business_info
from src.utils.csv_export import add_sheet_to_excel, save_to_excel


def main():
    # Start timing the script execution
    start_time = time.time()

    parser = argparse.ArgumentParser(
        description="Search Yelp for specific locations and save to sheets in one Excel file"
    )
    parser.add_argument("--api-key", required=True, help="Yelp Fusion API key")
    parser.add_argument(
        "--city-name",
        required=True,
        help="Name for the output Excel file with optional state (e.g., 'Los Angeles:CA')",
    )
    parser.add_argument(
        "--locations",
        required=False,
        help="Comma-separated list of sub-locations to search (e.g., 'Santa Monica,Hollywood'). "
        "If not provided, will just search the city itself.",
    )
    parser.add_argument(
        "--radius",
        type=int,
        default=5,
        help="Search radius in miles for each location (max 24.85). Usually auto-calculated.",
    )
    parser.add_argument("--term", default="happy hour", help="Search term")
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
        help="Maximum total businesses to fetch per location (Yelp limits to 240)",
    )

    args = parser.parse_args()

    # Parse city name and state
    if ":" in args.city_name:
        city_name, state = args.city_name.split(":", 1)
        city_name = city_name.strip()
        state = state.strip()
    else:
        city_name = args.city_name.strip()
        state = ""  # No state provided

    # Parse locations (sub-locations) if provided
    location_data = []
    if args.locations:
        # Multiple sub-locations provided
        for loc in args.locations.split(","):
            loc_name = loc.strip()
            location_data.append({"name": loc_name, "state": state})
    else:
        # No sub-locations provided, just search the main city
        location_data = [{"name": city_name, "state": state}]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    total_businesses_processed_all_locations = 0

    # Define the output filename based on the city name
    safe_city_name = city_name.replace(" ", "_").replace("/", "_")
    output_filename = f"{safe_city_name}_{timestamp}.xlsx"
    print(f"Output will be saved to: {output_filename}")

    # Process each location
    first_location = True
    successful_locations = 0

    for location in location_data:
        location_name = location["name"]
        location_state = location["state"]

        try:
            # Format search name with state if provided
            search_name = (
                f"{location_name}, {location_state}"
                if location_state
                else location_name
            )
            display_name = (
                f"{location_name}, {location_state}"
                if location_state
                else location_name
            )

            print(f"\n--- Processing Location: {display_name} ---")
            coordinates = get_location_coordinates(search_name)

            if not coordinates:
                print(f"Skipping {display_name} due to geocoding failure.")
                continue

            # Use the calculated radius if available, otherwise use the command-line radius
            location_radius = coordinates.get("radius", args.radius)

            print(
                f"Searching Yelp for '{args.term}' near {display_name} (Radius: {location_radius:.1f} miles)"
            )

            businesses = search_businesses(
                args.api_key,
                coordinates["latitude"],
                coordinates["longitude"],
                location_radius,
                args.term,
                args.batch_size,
                args.max_results,
            )

            if not businesses:
                print(f"No businesses found for {display_name}.")
                continue

            print(
                f"Found {len(businesses)} businesses for {display_name}. Processing..."
            )
            total_businesses_processed_all_locations += len(businesses)

            business_info, businesses_with_emails = extract_business_info(
                businesses, args.api_key
            )

            if not business_info:
                print(f"No business information extracted for {display_name}.")
                continue

            print(
                f"Extracted information for {len(business_info)} businesses from {display_name}"
            )

            # Set state if not already defined in business data
            if location_state:
                for business in business_info:
                    if not business.get("state"):
                        business["state"] = location_state

            # Save to Excel file
            sheet_name = location_name

            if first_location:
                # Create new file with first sheet
                result = save_to_excel(business_info, output_filename, sheet_name)
                if result:
                    print(f"Created Excel file with data for {display_name}")
                    first_location = False
                    successful_locations += 1
                else:
                    print(f"Failed to create Excel file for {display_name}")
            else:
                # Add sheet to existing file
                full_path = os.path.join("dat", output_filename)
                result = add_sheet_to_excel(full_path, business_info, sheet_name)
                if result:
                    print(f"Added data for {display_name} to Excel file")
                    successful_locations += 1
                else:
                    print(f"Failed to add data for {display_name} to Excel file")

        except Exception as location_error:
            print(f"Error processing location {display_name}: {str(location_error)}")
            print("Continuing with next location...")
            continue

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

    # Final summary
    print(f"\n--- Finished --- ")

    # Check results
    dat_file_path = os.path.join("dat", output_filename)
    if os.path.exists(dat_file_path) and successful_locations > 0:
        print(f"Output saved to: {dat_file_path}")
        print(
            f"Successfully processed {successful_locations} out of {len(location_data)} locations"
        )
    else:
        print(f"No data was saved to {dat_file_path}")

    print(f"Total businesses processed: {total_businesses_processed_all_locations}")
    print(f"Total runtime: {time_str}")


if __name__ == "__main__":
    main()
