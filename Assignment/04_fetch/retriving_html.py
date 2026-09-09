import requests
from requests.exceptions import RequestException, Timeout, HTTPError

def fetch_url(url: str) -> str:
    """
    Fetches the HTML content of the given URL.
    Returns the HTML response as text.
    
    Args:
        url: The website URL to fetch.
        
    Raises:
        RuntimeError: If the fetch fails due to timeout, HTTP error, or network error.
    """
    headers = {
        # A descriptive User-Agent helps identify our requests to the server
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    timeout_seconds = 10
    
    try:
        response = requests.get(url, headers=headers, timeout=timeout_seconds)
        # Check for HTTP errors (like 404 Not Found or 500 Internal Server Error)
        response.raise_for_status()
        return response.text
        
    except Timeout as e:
        raise RuntimeError(f"Request to {url} timed out after {timeout_seconds} seconds.") from e
        
    except HTTPError as e:
        raise RuntimeError(f"HTTP error occurred while fetching {url}: {e.response.status_code} {e.response.reason}") from e
        
    except RequestException as e:
        raise RuntimeError(f"A general network error occurred while fetching {url}: {e}") from e
