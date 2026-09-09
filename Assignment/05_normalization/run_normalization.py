import json
from pathlib import Path
from normalizer import normalize_all

def run():
    # 1. Read raw.json safely using json
    raw_path = Path(__file__).parent / 'raw.json'
    if not raw_path.exists():
        print(f"Error: {raw_path} not found.")
        return

    if raw_path.stat().st_size == 0:
        print(f"Error: {raw_path} is empty. Run the fetch/scraping step first to populate it.")
        return
        
    with open(raw_path, 'r', encoding='utf-8') as f:
        raw_items = json.load(f)
        
    print(f"Read {len(raw_items)} items from raw.json.")
    
    # 2. Normalize
    base_url = "https://www.iitb.ac.in"
    normalized_items = normalize_all(raw_items, base_url)
    
    # 3. Save to iit_bombay_normalized.json
    out_path = Path(__file__).parent / 'iit_bombay_normalized.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(normalized_items, f, indent=4, ensure_ascii=False)
        
    print(f"Successfully normalized and saved to {out_path}.")

if __name__ == "__main__":
    run()
