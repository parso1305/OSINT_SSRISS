import sys 
import requests


def main():
    # Get the URl from user code
    if len(sys.argv) != 2:
        print("Usage: python http_headers.py <URL>")
        return
    
    
    # make the http requests
    requested_url = sys.argv[1]
    
    
    try:
        response = requests.get(
            requested_url,
            timeout=10
        )
    except requests.exception.RequestException as e:
        print(f"Error occurred while making the request: {e}")
        return
    
    # inspecting the response
    final_url = response.url
    status_code = response.status_code
    content_type = response.headers.get("Content-Type","")
    content_length = len(response.content)
    
    is_html = "text/html" in content_type.lower()
    
    if is_html:
        body_print = response.text[:2000]
    else:
        body_print = "[Non-HTML content not displayed]"
    
    
    # printing results 
    print(f"Final URL: {final_url}")
    print(f"Status Code: {status_code}")
    print(f"Content Type: {content_type}")
    print(f"Content Length: {content_length}")
    
    
    print("\nRedirect history:")
    
    if response.history:
        for redirect in response.history:
            print(f" {redirect.status_code} -> {redirect.url}")
    else:
        print("none")
    
    print("\n Response headers:")
    headers_show = [
        "content-type",
        "content-length",
        "server",
        "date",
        "location"
    ]
    
    for header in headers_show:
        print(f" {header}: {response.headers.get(header)}")
    
    print("\n body show")
    print(body_print)
    
    
if __name__ == "__main__":
    main()