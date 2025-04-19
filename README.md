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
│   │   └── csv_export.py       # Excel/CSV export functions
│   └── business/               # Business data processing
│       └── processor.py        # Business info extraction
├── dat/                        # Output folder (created by the script)
└── requirements.txt            # Project dependencies
```

## Installation

### Prerequisites

1. **Python**: Install Python 3.8 or later

   - Download from [python.org](https://www.python.org/downloads/)
   - During installation, ensure you check "Add Python to PATH"
   - Verify installation by opening a command prompt/terminal and typing: `python --version`

2. **Git**: Install Git for your operating system
   - Download from [git-scm.com](https://git-scm.com/downloads)
   - Verify installation by opening a command prompt/terminal and typing: `git --version`

### Project Setup

1. Clone this repository:

   ```bash
   git clone https://github.com/yourname/HHQueenYelp.git
   cd HHQueenYelp
   ```

2. Install the required packages:

   ```bash
   pip install -r requirements.txt
   ```

3. Get a Yelp API key from the [Yelp Fusion API](https://www.yelp.com/developers/documentation/v3/authentication)

## Usage

### Basic Usage

Run the script with your Yelp API key and a city name:

```bash
python main.py --api-key YOUR_YELP_API_KEY --city-name "San Francisco:CA"
```

### Search Multiple Locations

You can search for multiple specific locations (neighborhoods, districts, etc.) within a city:

```bash
python main.py --api-key YOUR_YELP_API_KEY --city-name "Los Angeles:CA" --locations "Santa Monica,Hollywood,Downtown LA,Beverly Hills,Venice"
```

### Command-line Arguments

- `--api-key`: Yelp Fusion API key (required)
- `--city-name`: Name of the city to search, with optional state code (e.g., "Los Angeles:CA") (required)
- `--locations`: Comma-separated list of sub-locations within the city (optional)
- `--radius`: Fallback search radius in miles if auto-calculation fails (default: 5)
- `--term`: Search term (default: "happy hour")
- `--batch-size`: Number of results per API call (default: 40, max: 50)
- `--max-results`: Maximum total businesses to fetch per location (default: 240)

## Features

### Smart Search Radius

The tool automatically calculates an appropriate search radius for each location based on its geographical size:

- Small neighborhoods like Venice or Downtown LA get smaller radii (around 3 miles)
- Medium-sized areas like Beverly Hills and Santa Monica get moderate radii (around 4 miles)
- Larger areas like full cities get larger radii (8+ miles)

### State Integration

Specify the state once with the main city name using the format `"City Name:State"` (e.g., `"Los Angeles:CA"`), and it will be applied to all sub-locations and included in the output data.

### Dynamic Email Column Creation

The tool will automatically create the appropriate number of email columns based on the maximum number of email addresses found for any business:

- If no business has more than one email, only one email column will appear
- If some businesses have multiple emails, the tool will create additional columns (email_1, email_2, etc.)

### Multi-Location Searches

When searching multiple locations:

- Each location gets its own sheet in the Excel file
- The Excel file is named after the main city

### City-Only Searches

If no specific sub-locations are provided, the tool will search the entire city:

```bash
python main.py --api-key YOUR_YELP_API_KEY --city-name "Chicago:IL"
```

## Output

The script creates an Excel file in the `dat/` directory with the following information for each business:

- Name
- Website
- Email columns (dynamically created based on the data)
- City
- State
- Zip code
- Phone
- Happy Hour tag

When multiple locations are searched, each location will have its own sheet in the Excel file.

## Examples

### Search entire city of Chicago:

```bash
python main.py --api-key YOUR_YELP_API_KEY --city-name "Chicago:IL"
```

### Search specific neighborhoods in Los Angeles:

```bash
python main.py --api-key YOUR_YELP_API_KEY --city-name "Los Angeles:CA" --locations "Santa Monica,Hollywood,Downtown LA,Beverly Hills,Venice"
```

### Search for sports bars in San Francisco:

```bash
python main.py --api-key YOUR_YELP_API_KEY --city-name "San Francisco:CA" --term "sports bar"
```
