# Assignment 04: Fetching and Parsing HTML

This assignment demonstrates how to fetch HTML from a webpage and parse it locally using `requests` and `BeautifulSoup`. It is designed with clear separation of concerns (fetching vs. parsing) and resilient data extraction techniques.

## 1. How to install dependencies

Make sure you have Python installed, then install the required libraries:

```bash
pip install requests beautifulsoup4
```

## 2. How to run the local fixture parser

To parse the local `file.html` fixture and see the extracted events in beautifully formatted JSON, run:

```bash
python main.py
```

## 3. How to run the checkpoint test

To verify that the parser works correctly and can handle missing fields (like missing speaker or location) and absolute/relative URLs without crashing, run:

```bash
python test_parser.py
```

## 4. How to configure the real IIT Bombay URL

1. Open `main.py`.
2. Locate the `REAL_URL` constant near the top of the file.
3. Replace `None` with the actual IIT Bombay URL (e.g., `"https://www.iitb.ac.in/en/events"`).
4. Run `python main.py` again. The HTML will be downloaded and saved to `fixtures/iitb_real_response.html`.

## 5. How to inspect HTML and replace selectors

After fetching the real HTML:
1. Open `fixtures/iitb_real_response.html` in your editor or browser.
2. Inspect the HTML to find the correct classes or IDs of the repeating event records and their inner fields.
3. Open `parser.py`.
4. Replace the sample selectors (e.g., `div.event-container`, `.title`, `.date`) with the ones you found in the real HTML.
5. Uncomment the parsing lines at the bottom of `main.py` in the `run_real_extraction` function to extract and print the first 5-10 real events.

## 6. The difference between fetch_url() and parse_events()

- **`fetch_url()`** (in `retriving_html.py`): Strictly responsible for network operations. It makes the HTTP request, handles timeouts/errors, and returns the raw HTML string. It has no idea what is inside the HTML.
- **`parse_events()`** (in `parser.py`): Strictly responsible for data extraction. It takes a raw HTML string and a base URL, and uses BeautifulSoup to find and extract the desired fields. It never touches the network.

Keeping these separate ensures the code is clean, easily testable (as seen in `test_parser.py` which only tests parsing), and maintainable.
