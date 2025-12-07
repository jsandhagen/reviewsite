"""
Standalone script to autofill cover images for the RatingsProject.
Downloads thumbnails from Wikipedia (when available) into static/covers/
and updates the Cover Path column in data.csv.

Usage:
    python scripts\autofill_covers.py

This script requires the `requests` package.
"""
import csv
import os
import urllib.parse
import re
import sys

try:
    import requests
except ImportError:
    print("The 'requests' package is required. Install with:\n    python -m pip install requests")
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_CSV = os.path.join(ROOT, 'data.csv')
COVERS_DIR = os.path.join(ROOT, 'static', 'covers')

os.makedirs(COVERS_DIR, exist_ok=True)


def slugify(name):
    s = name.strip().lower()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    return s


def fetch_wikipedia_thumbnail(title):
    api = 'https://en.wikipedia.org/w/api.php'
    try:
        # Try direct lookup first
        params = {
            'action': 'query',
            'titles': title,
            'prop': 'pageimages',
            'pithumbsize': 500,
            'format': 'json',
            'redirects': 1,
            'formatversion': 2
        }
        r = requests.get(api, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        pages = data.get('query', {}).get('pages', [])
        for p in pages:
            if not p:
                continue
            thumb = p.get('thumbnail', {}).get('source') if p else None
            if thumb:
                return thumb

        # Fallback: search for the best matching page title
        params_search = {
            'action': 'query',
            'list': 'search',
            'srsearch': title,
            'srlimit': 1,
            'format': 'json',
            'formatversion': 2
        }
        r2 = requests.get(api, params=params_search, timeout=10)
        r2.raise_for_status()
        data2 = r2.json()
        results = data2.get('query', {}).get('search', [])
        if not results:
            return None
        best_title = results[0].get('title')
        if not best_title:
            return None

        # Query pageimages for the found title
        params3 = {
            'action': 'query',
            'titles': best_title,
            'prop': 'pageimages',
            'pithumbsize': 500,
            'format': 'json',
            'redirects': 1,
            'formatversion': 2
        }
        r3 = requests.get(api, params=params3, timeout=10)
        r3.raise_for_status()
        data3 = r3.json()
        pages3 = data3.get('query', {}).get('pages', [])
        for p in pages3:
            thumb = p.get('thumbnail', {}).get('source') if p else None
            if thumb:
                print(f"  Matched page: {best_title}")
                print(f"  Thumbnail URL: {thumb}")
                return thumb
    except Exception:
        return None
    return None


def fetch_image_via_commons(query):
    """Try Wikimedia Commons for game cover images."""
    try:
        api = 'https://commons.wikimedia.org/w/api.php'
        params = {
            'action': 'query',
            'list': 'allimages',
            'aisearch': query + ' cover',
            'ailimit': 1,
            'format': 'json'
        }
        r = requests.get(api, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        images = data.get('query', {}).get('allimages', [])
        if images:
            file_title = images[0].get('name', '')
            if file_title:
                file_params = {
                    'action': 'query',
                    'titles': f'File:{file_title}',
                    'prop': 'imageinfo',
                    'iiprop': 'url',
                    'format': 'json'
                }
                r2 = requests.get(api, params=file_params, timeout=10)
                r2.raise_for_status()
                file_data = r2.json()
                pages = file_data.get('query', {}).get('pages', {})
                for page in pages.values():
                    imageinfo = page.get('imageinfo', [])
                    if imageinfo:
                        return imageinfo[0].get('url')
    except Exception:
        pass
    return None


def fetch_image_via_rawg(query):
    """Try RAWG.io API (free tier, no key needed for basic search)."""
    try:
        api = 'https://api.rawg.io/api/games'
        params = {
            'search': query,
            'page_size': 1
        }
        r = requests.get(api, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        results = data.get('results', [])
        print(f"  RAWG query '{query}': got {len(results)} results")
        if results:
            result = results[0]
            print(f"    First result: {result.get('name', 'N/A')}")
            cover_url = result.get('background_image') or result.get('image_background')
            if cover_url:
                print(f"    Found image: {cover_url[:80]}")
                return cover_url
    except Exception as e:
        print(f"  RAWG error: {e}")
    return None


def fetch_image_via_google(query):
    """Try OpenAI DALL-E or a free game database. For now, returns None."""
    # This was unreliable; we'll skip web scraping
    return None


def fetch_image_via_ddg(query):
    """Placeholder for future implementation."""
    return None


def main():
    if not os.path.exists(DATA_CSV):
        print(f"data.csv not found at {DATA_CSV}")
        return

    with open(DATA_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    changed = False
    found = 0
    skipped = 0
    failed = 0

    for i, row in enumerate(rows):
        title = row.get('Game','').strip()
        cur = row.get('Cover Path','').strip()
        # skip if already has a local static cover
        if cur and cur.startswith('/static/'):
            local_fp = os.path.join(ROOT, cur.lstrip('/\\'))
            if os.path.exists(local_fp):
                skipped += 1
                continue
        if not title:
            failed += 1
            continue
        print(f"[{i+1}/{len(rows)}] Searching for: {title}")
        thumb = fetch_wikipedia_thumbnail(title)
        if not thumb:
            print("  No wikipedia thumbnail, trying RAWG.io...")
            thumb = fetch_image_via_rawg(title)
        if not thumb:
            print("  No thumbnail found")
            failed += 1
            continue
        try:
            r = requests.get(thumb, timeout=15)
            r.raise_for_status()
            ext = os.path.splitext(urllib.parse.urlparse(thumb).path)[1] or '.jpg'
            base = slugify(title)
            fname = f"{base}{ext}"
            outpath = os.path.join(COVERS_DIR, fname)
            # avoid overwrite: if exists, append index
            if os.path.exists(outpath):
                fname = f"{base}_{i}{ext}"
                outpath = os.path.join(COVERS_DIR, fname)
            with open(outpath, 'wb') as out:
                out.write(r.content)
            row['Cover Path'] = f"/static/covers/{fname}"
            changed = True
            found += 1
            print(f"  Saved: {fname}")
        except Exception as e:
            print(f"  Failed to download: {e}")
            failed += 1

    if changed:
        # write back CSV preserving headers
        with open(DATA_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)

    print('\nSummary:')
    print(f'  Found and saved: {found}')
    print(f'  Skipped (already present): {skipped}')
    print(f'  Failed/no thumbnail: {failed}')
    print('\nRun the web app and open /full to see updated covers.')


if __name__ == '__main__':
    main()
