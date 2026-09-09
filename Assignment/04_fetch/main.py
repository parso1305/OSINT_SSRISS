import os
import json
from pathlib import Path
from parser import parse_events
from retriving_html import fetch_url

# ==============================================================================
# IIT BOMBAY CONFIGURATION (FOR REAL EXTRACTION LATER)
# ==============================================================================
# IMPORTANT: Provide the real IIT Bombay URL here when you are ready.
# Do not run the real extraction until this is set.
REAL_URL = "https://www.iitb.ac.in/news" # e.g., "https://www.iitb.ac.in/en/events"

# TODO: After inspecting the real IIT Bombay HTML, you will need to replace the 
# selectors in parser.py to match the actual structure of the IITB website.
#
# Examples of things you'll need to find and replace in parser.py:
# - Event container class: 'event-container' -> 'views-row' or similar
# - Title class: 'title' -> 'field-title'
# - Link class: 'item-link' -> 'event-url'
# - Date class: 'date' -> 'date-display-single'
# - Speaker class: 'speaker' -> 'field-speaker'
# - Location class: 'location' -> 'field-location'
# ==============================================================================

def run_local_fixture():
    print("STEP 1: Reading and parsing the local iitb_real_response.html fixture...")
    fixture_path = Path(__file__).parent / 'fixtures' / 'iitb_real_response.html'
    
    if not fixture_path.exists():
        print(f"Fixture not found at {fixture_path}")
        return
        
    with open(fixture_path, 'r', encoding='utf-8') as f:
        html = f.read()
        
    base_url = "https://www.iitb.ac.in"
    events = parse_events(html, base_url)
    
    print("\nSTEP 2: Parsed fixture events:")
    # Pretty print the JSON output
    print(json.dumps(events, indent=4))

def run_real_extraction():
    if not REAL_URL:
        print("\nSTEP 3/4: Real extraction skipped. Provide REAL_URL to run.")
        return
        
    print(f"\nSTEP 4: Fetching real URL: {REAL_URL}")
    try:
        real_html = fetch_url(REAL_URL)
        
        # Save real HTML response locally
        fixtures_dir = Path(__file__).parent / 'fixtures'
        fixtures_dir.mkdir(exist_ok=True)
        
        output_path = fixtures_dir / 'iitb_news_response.html'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(real_html)
            
        print(f"Saved real HTML response to: {output_path}")
        
        print("\nSTEP 5: Real extraction next steps:")
        print("1. Open 'fixtures/iitb_news_response.html' and inspect the HTML structure.")
        print("2. Find the CSS selectors for the event containers and fields.")
        print("3. Update parser.py to use these new selectors.")
        print("4. Call parse_events() with the downloaded HTML and print the extracted events.")
        
        # Uncomment this once selectors are updated to parse only 5-10 records
        # events = parse_events(real_html, REAL_URL)
        # print(json.dumps(events[:10], indent=4)) 
        
    except Exception as e:
        print(f"Failed to fetch real URL: {e}")

if __name__ == "__main__":
    run_local_fixture()
    run_real_extraction()
