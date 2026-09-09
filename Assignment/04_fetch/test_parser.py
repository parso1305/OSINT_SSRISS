import os
from parser import parse_events

def test_parse_events():
    """
    Checkpoint test for the local HTML fixture parser.
    """
    # 1. Resolve path to the fixture file
    current_dir = os.path.dirname(__file__)
    fixture_path = os.path.join(current_dir, 'file.html')
    
    with open(fixture_path, 'r', encoding='utf-8') as f:
        html = f.read()
        
    base_url = "http://localhost:8000"
    
    # 2. Parse the events
    events = parse_events(html, base_url)
    
    # Verify we got all expected 10 events
    assert len(events) == 10, f"Expected 10 events, but got {len(events)}."
    
    # Check that we correctly handled missing speakers
    missing_speaker_events = [e for e in events if e["speaker_raw"] is None]
    assert len(missing_speaker_events) > 0, "Expected at least one event with a missing speaker."
    
    # Check that we correctly handled missing locations
    missing_location_events = [e for e in events if e["location_raw"] is None]
    assert len(missing_location_events) > 0, "Expected at least one event with a missing location."
    
    # Check absolute URL parsing
    absolute_url_events = [e for e in events if e["item_url"] and "http" in e["item_url"]]
    assert len(absolute_url_events) > 0, "Expected at least one event with an absolute URL."
    
    print("All tests passed successfully! The parser is robust.")

if __name__ == "__main__":
    test_parse_events()
