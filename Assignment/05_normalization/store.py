import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

def init_db(db_path: str):
    """
    Initializes the SQLite database with the required schema.
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Create table with 'url' as the UNIQUE deduplication identity
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                published_at TEXT,
                image_url TEXT,
                image_alt TEXT,
                raw_text TEXT,
                content_hash TEXT,
                first_seen DATETIME NOT NULL,
                last_seen DATETIME NOT NULL
            )
        ''')
        conn.commit()

def generate_content_hash(item: dict) -> str:
    """
    Generates a hash based on the mutable content fields of the item.
    This allows us to detect if a record has been modified.
    """
    # We include fields that might change. 
    # We do NOT include volatile fields like first_seen, last_seen.
    content = f"{item.get('title')}|{item.get('published_at')}|{item.get('image_url')}|{item.get('image_alt')}|{item.get('raw_text')}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def get_item(db_path: str, url: str) -> dict:
    """
    Retrieves an item from the database by its unique url.
    Returns None if not found.
    """
    with sqlite3.connect(db_path) as conn:
        # Return results as dictionaries
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items WHERE url = ?", (url,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None

def upsert_item(db_path: str, item: dict) -> str:
    """
    Inserts or updates an item based on its canonical URL.
    Returns a status string: 'new', 'known', or 'updated'.
    """
    url = item.get("item_url")
    if not url:
        return "skipped" # Require URL for identity
        
    current_hash = generate_content_hash(item)
    now_str = datetime.utcnow().isoformat()
    
    # Check if item exists
    existing_item = get_item(db_path, url)
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        if not existing_item:
            # 1. New item -> Insert
            cursor.execute('''
                INSERT INTO items (url, title, published_at, image_url, image_alt, raw_text, content_hash, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                url,
                item.get("title"),
                item.get("published_at"),
                item.get("image_url"),
                item.get("image_alt"),
                item.get("raw_text"),
                current_hash,
                now_str, # first_seen
                now_str  # last_seen
            ))
            return "new"
            
        else:
            # Item exists. Check if content changed.
            if existing_item["content_hash"] == current_hash:
                # 2. Same content -> update last_seen only
                cursor.execute('''
                    UPDATE items SET last_seen = ? WHERE url = ?
                ''', (now_str, url))
                return "known"
            else:
                # 3. Content changed -> update content and last_seen
                cursor.execute('''
                    UPDATE items 
                    SET title = ?, published_at = ?, image_url = ?, image_alt = ?, raw_text = ?, content_hash = ?, last_seen = ?
                    WHERE url = ?
                ''', (
                    item.get("title"),
                    item.get("published_at"),
                    item.get("image_url"),
                    item.get("image_alt"),
                    item.get("raw_text"),
                    current_hash,
                    now_str, # update last_seen
                    url
                ))
                return "updated"
