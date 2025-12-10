"""Steam API integration for importing user games."""
import requests
import time
import os
import re
from urllib.parse import urlparse
from PIL import Image
from io import BytesIO
import cloudflare_storage

# Use your Steam API key here
API_KEY = "EF41FB111ABBA588DDAE7EBEF933D669"


def extract_steamid64(profile_url):
    """Extract Steam ID from various profile URL formats."""
    parsed = urlparse(profile_url)
    path = parsed.path.strip("/")

    # Handle wishlist URLs
    if path.startswith("wishlist/profiles/"):
        parts = path.split("/")
        if len(parts) >= 3:
            return parts[2]
        return None

    # Handle /profiles/STEAMID64
    if path.startswith("profiles/"):
        return path.split("/")[1]
    
    # Handle /id/customURL
    elif path.startswith("id/"):
        customid = path.split("/")[1]
        url = f"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key={API_KEY}&vanityurl={customid}"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json().get("response", {})
            if data.get("success") == 1:
                return data.get("steamid")
            else:
                return None
        except Exception:
            return None
    
    # Handle direct numeric ID
    else:
        if path.isdigit():
            return path
        else:
            return None


def get_owned_games(steam_id):
    """Fetch all owned games for a Steam user including playtime."""
    url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    params = {
        "key": API_KEY,
        "steamid": steam_id,
        "include_appinfo": True,
        "include_played_free_games": True
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("response", {}).get("games", [])
    except Exception as e:
        print(f"Error fetching owned games: {e}")
        return []


def get_store_details(appid, retries=3):
    """Fetch game details from Steam Store API."""
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=us"
    
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 429:
                # Rate limited, wait and retry
                time.sleep(0.5 + attempt * 0.5)
                continue
            
            resp.raise_for_status()
            info = resp.json().get(str(appid), {})
            
            if not info.get("success"):
                return None
            
            return info.get("data", {})
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(0.5)
            else:
                print(f"Error fetching store details for appid {appid}: {e}")
                return None
    
    return None


def safe_text(text):
    """Clean and normalize text from Steam API."""
    if text is None:
        return ""
    import html
    import unicodedata
    text = html.unescape(str(text))
    return unicodedata.normalize('NFC', text)


def clean_filename(name):
    """Clean a string to be safe for use as a filename."""
    # Remove invalid filename characters
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    # Replace spaces and special chars with underscores
    name = re.sub(r'[^\w\-_]', '_', name)
    # Collapse multiple underscores
    name = re.sub(r'_+', '_', name)
    # Limit length
    return name[:100]


def download_cover_art(app_id, game_name, covers_dir, existing_etag=None):
    """
    Download cover art from Steam CDN if it doesn't exist or has changed.
    Uploads to Cloudflare R2 and saves locally as backup.

    Args:
        app_id: Steam app ID
        game_name: Name of the game
        covers_dir: Directory to save covers
        existing_etag: ETag from previous download (if any)

    Returns:
        tuple: (cover_path, etag) or (None, None) if download failed
    """
    url = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg"
    filename = f"{app_id}_{clean_filename(game_name)}.png"
    filepath = os.path.join(covers_dir, filename)
    r2_key = f"covers/{filename}"

    # Set headers to avoid 403 errors from Steam CDN
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        # First, do a HEAD request to check ETag
        head_response = requests.head(url, headers=headers, timeout=10)
        if head_response.status_code != 200:
            return None, None

        new_etag = head_response.headers.get('ETag', '')

        # Check if file exists in R2 with matching ETag
        r2_exists = cloudflare_storage.file_exists(r2_key)
        if r2_exists and existing_etag and new_etag == existing_etag:
            # Cover exists in R2 and hasn't changed, return R2 URL
            return cloudflare_storage.get_public_url(r2_key), existing_etag

        # Also check local file
        if os.path.exists(filepath) and existing_etag and new_etag == existing_etag:
            # Cover hasn't changed locally, but upload to R2 if missing
            if not r2_exists:
                r2_url = cloudflare_storage.upload_file(filepath, r2_key, 'image/png')
                if r2_url:
                    return r2_url, existing_etag
            return cloudflare_storage.get_public_url(r2_key), existing_etag

        # Download the image
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return None, None

        # Convert to PNG and save locally
        image = Image.open(BytesIO(response.content))
        image = image.convert("RGB")
        image.save(filepath, "PNG")

        # Upload to Cloudflare R2
        r2_url = cloudflare_storage.upload_file(filepath, r2_key, 'image/png')

        if r2_url:
            return r2_url, new_etag
        else:
            # Fallback to local path if R2 upload fails
            return f"/static/covers/{filename}", new_etag

    except Exception as e:
        print(f"Error downloading cover for {game_name} (appid {app_id}): {e}")
        return None, None


def import_steam_games(steam_id, progress_callback=None, skip_complete_games=False, existing_games_dict=None, download_covers=False, covers_dir=None):
    """
    Import games from Steam profile.
    
    Args:
        steam_id: Steam ID or profile URL
        progress_callback: Optional function(current, total, message) to report progress
        skip_complete_games: If True, skip fetching store details for games with complete metadata
        existing_games_dict: Dict of {app_id: game_data} to check which games already have complete info
        download_covers: If True, download cover art from Steam
        covers_dir: Directory to save cover images (required if download_covers=True)
    
    Returns:
        List of game dictionaries with metadata including cover_path and cover_etag
    """
    # If steam_id looks like a URL, extract the ID
    if steam_id.startswith("http"):
        steam_id = extract_steamid64(steam_id)
        if not steam_id:
            return []
    
    # Fetch owned games
    owned_games = get_owned_games(steam_id)
    if not owned_games:
        return []
    
    # Sort by playtime descending
    owned_games.sort(key=lambda g: g.get("playtime_forever", 0), reverse=True)
    
    results = []
    total = len(owned_games)
    
    for idx, game in enumerate(owned_games):
        appid = game.get("appid")
        if not appid:
            continue
        
        name = safe_text(game.get("name", "Unknown"))
        playtime_minutes = game.get("playtime_forever", 0)
        playtime_hours = round(playtime_minutes / 60, 2)
        
        # Report progress
        if progress_callback:
            progress_callback(idx + 1, total, f"Processing {name}")
        
        # Check if this game already has complete metadata
        skip_api_call = False
        if skip_complete_games and existing_games_dict and str(appid) in existing_games_dict:
            existing = existing_games_dict[str(appid)]
            # Consider game complete if it has description, genres, and developer
            if (existing.get('description') and existing.get('genres') and 
                existing.get('developer')):
                skip_api_call = True
                # Use existing data, just update playtime
                game_info = {
                    "app_id": str(appid),
                    "name": name,
                    "playtime_hours": playtime_hours,
                    "release_date": existing.get('release_date', ''),
                    "description": existing.get('description', ''),
                    "genres": existing.get('genres', ''),
                    "price": existing.get('price'),
                    "original_price": existing.get('original_price'),
                    "sale_price": existing.get('sale_price'),
                    "developer": existing.get('developer', ''),
                    "publisher": existing.get('publisher', ''),
                    "cover_url": f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg",
                    "cover_path": existing.get('cover_path'),
                    "cover_etag": existing.get('cover_etag')
                }
                
                # Download cover if requested (will check ETag and R2 existence)
                if download_covers and covers_dir:
                    cover_path, cover_etag = download_cover_art(
                        appid, name, covers_dir, existing.get('cover_etag')
                    )
                    if cover_path:
                        game_info["cover_path"] = cover_path
                        game_info["cover_etag"] = cover_etag
                
                results.append(game_info)
                continue
        
        # Fetch additional details from store (with rate limiting)
        store_data = get_store_details(appid)
        time.sleep(0.2)  # Rate limit: 5 requests per second
        
        game_info = {
            "app_id": str(appid),
            "name": name,
            "playtime_hours": playtime_hours,
            "release_date": "",
            "description": "",
            "genres": "",
            "price": None,
            "original_price": None,
            "sale_price": None,
            "developer": "",
            "publisher": "",
            "cover_url": f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg"
        }
        
        if store_data:
            # Extract release date
            release_info = store_data.get("release_date", {})
            if release_info.get("date"):
                game_info["release_date"] = release_info["date"]
            
            # Extract description
            game_info["description"] = safe_text(store_data.get("short_description", ""))
            
            # Extract genres
            genres_list = store_data.get("genres", [])
            if genres_list:
                game_info["genres"] = ", ".join([safe_text(g.get("description", "")) for g in genres_list])
            
            # Extract developer and publisher
            developers = store_data.get("developers", [])
            if developers:
                game_info["developer"] = ", ".join([safe_text(d) for d in developers])
            
            publishers = store_data.get("publishers", [])
            if publishers:
                game_info["publisher"] = ", ".join([safe_text(p) for p in publishers])
            
            # Extract price information
            price_data = store_data.get("price_overview")
            if price_data:
                # Original price (before discount)
                if price_data.get("initial"):
                    game_info["original_price"] = price_data["initial"] / 100.0
                
                # Final price (current price, could be on sale)
                if price_data.get("final"):
                    game_info["price"] = price_data["final"] / 100.0
                    
                    # If there's a discount, the final is the sale price
                    if price_data.get("discount_percent", 0) > 0:
                        game_info["sale_price"] = price_data["final"] / 100.0
                    
                    # If no original price but has final, set original = final
                    if not game_info["original_price"]:
                        game_info["original_price"] = game_info["price"]
            elif store_data.get("is_free"):
                game_info["price"] = 0.0
                game_info["original_price"] = 0.0
        
        # Download cover art if requested
        if download_covers and covers_dir:
            existing_etag = None
            if existing_games_dict and str(appid) in existing_games_dict:
                existing_etag = existing_games_dict[str(appid)].get('cover_etag')
            
            cover_path, cover_etag = download_cover_art(appid, name, covers_dir, existing_etag)
            if cover_path:
                game_info["cover_path"] = cover_path
                game_info["cover_etag"] = cover_etag
            else:
                game_info["cover_path"] = None
                game_info["cover_etag"] = None
        else:
            game_info["cover_path"] = None
            game_info["cover_etag"] = None
        
        results.append(game_info)
    
    return results
