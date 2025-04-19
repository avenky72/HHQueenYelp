# Happy Hour Queen Yelp Finder

## What is this?

This tool helps you find bars and restaurants with happy hours in any city or neighborhood. It searches Yelp for businesses, collects their information, and creates an organized Excel spreadsheet with all the results.

## Before You Start

You'll need:

1. Python installed on your computer (version 3.7 or newer)
2. A Yelp API key (explained below)
3. Basic familiarity with running commands in a terminal/command prompt

### Getting a Yelp API Key

1. Go to [https://www.yelp.com/developers](https://www.yelp.com/developers)
2. Sign up for a free account or log in
3. Create a new app to get your API key
4. Save this key somewhere safe - you'll need it to run the tool

## Setting Up (First Time Only)

1. Download all the files from this project
2. Open a terminal/command prompt
3. Navigate to the folder where you saved the files
4. Install required packages by typing:
   ```
   pip install requests pandas openpyxl
   ```

## How to Use

### Basic Example:

To search for happy hours in Chicago:

1. Open terminal/command prompt
2. Navigate to the project folder
3. Type this command (replace YOUR_API_KEY with your actual Yelp API key):

```
python main.py --api-key YOUR_API_KEY --city-name "Chicago:IL"
```

### Searching Multiple Neighborhoods:

To search specific neighborhoods in Los Angeles:

```
python main.py --api-key YOUR_API_KEY --city-name "Los Angeles:CA" --locations "Downtown,Hollywood,Santa Monica"
```

### Looking for Something Besides Happy Hours:

To search for sports bars instead:

```
python main.py --api-key YOUR_API_KEY --city-name "Miami:FL" --term "sports bar"
```

## Understanding the Results

After running the command:

1. The tool will start searching Yelp
2. You'll see progress updates in the terminal
3. When finished, it creates an Excel file in a folder called "dat"
4. The filename will be the city name plus the current date/time
5. Open this Excel file to see all the businesses found

Each business listing includes:

- Name and address
- Phone number
- Rating and number of reviews
- Price level
- Categories
- Website (if available)
- And more...

If you searched multiple neighborhoods, each will have its own sheet in the Excel file.

## Helpful Tips

- **Not getting results?** Try a different search term or increase the search radius
- **Want to search a specific area?** Use the `--locations` option with neighborhood names
- **Want to change how far it searches?** Use `--radius` followed by a number (in miles)
- **Need more results?** The tool is limited to 240 results per location (Yelp's limit)

## Common Questions

**Q: How long does it take to run?**  
A: It depends on how many locations you search, but typically a few minutes per location.

**Q: Why does it pause sometimes?**  
A: The tool waits between searches to avoid hitting Yelp's rate limits.

**Q: Can I search outside the US?**  
A: Yes, but you should include the country name in your search, like "London, UK".
