# Happy Hour Business Finder

This tool searches for businesses related to "happy hour" using the Yelp API, extracts their websites, and scrapes email addresses from those websites.

## Project Structure

```
project_root/
├── main.py                     # Main entry point script
├── src/
│   ├── api/                    # API-related functions
│   │   └── yelp.py             # Yelp API interaction
│   ├── scraping/               # Web scraping functionality
│   │   ├── email_scraper.py    # Email extraction
│   │   └── website_scraper.py  # Website URL scraping
│   ├── utils/                  # Utility functions
│   │   ├── session.py          # HTTP session configuration
│   │   └── csv_export.py       # CSV export functions
│   └── business/               # Business data processing
│       └── processor.py        # Business info extraction
├── dat/                        # Output folder (created by the script)
└── requirements.txt            # Project dependencies
```

## Installation

1. Clone this repository
2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```
3. Get a Yelp API key from the [Yelp Fusion API](https://www.yelp.com/developers/documentation/v3/authentication)

## Usage

Run the script with your Yelp API key and location parameters:

```bash
python main.py --api-key eGU2qoxtM-LNjwtaQEdBE4NOgqRz1Se5s2iCZWovw-RCh8gA8bHYlLc4Iy1T2QsX7TKe1xALV3gcVDclIgEhf2Kb785gcoYUpe_8_OkwO4I2ieGvXomtekp3EnHcZ3Yx --latitude 37.7749 --longitude -122.4194
```

### Command-line Arguments

- `--api-key`: Yelp Fusion API key (required)
- `--latitude`: Latitude of the center point (required)
- `--longitude`: Longitude of the center point (required)
- `--radius`: Search radius in miles (default: 20)
- `--term`: Search term (default: "happy hour")
- `--output`: Output filename (default: generated with timestamp)
- `--batch-size`: Number of results per API call (default: 40, max: 50)
- `--max-results`: Maximum total businesses to fetch (default: 240)

## Output

The script creates a CSV file in the `dat/` directory with the following information for each business:

- Name
- Website
- Emails
- Price
- Zip code
- City
- Rating
- Address
- Review count
- Dogs allowed
- Phone
- Categories
- Good for kids

## Example

```bash
python main.py --api-key YOUR_YELP_API_KEY --latitude 34.0522 --longitude -118.2437 --radius 15 --term "sports bar"
```
