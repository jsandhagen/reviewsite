# Steam Integration Feature

## Overview
Added Steam profile linking functionality that allows users to import their Steam library directly into their backlog, sorted by most hours played.

## Changes Made

### 1. Database Schema Updates (`database.py`)
- Added `steam_profile_url` column to the `users` table
- Added `backlog_order` column to the `user_scores` table
- Created `set_user_steam_profile()` function to save Steam profile URL

### 2. Steam Integration Module (`steam_integration.py`)
Created a new module that handles all Steam API interactions:
- `extract_steamid64()` - Extracts Steam ID from various profile URL formats
- `get_owned_games()` - Fetches all owned games with playtime from Steam API
- `get_store_details()` - Fetches game metadata from Steam Store API
- `import_steam_games()` - Main function that imports and sorts games by playtime

Features:
- Supports multiple Steam URL formats (profiles/, id/, direct numeric IDs)
- Handles rate limiting with automatic retries
- Sorts games by playtime (most played first)
- Fetches comprehensive game metadata (description, genres, price, release date)

### 3. User Interface (`templates/profile.html`)
Added a new Steam Integration section with:
- Input field for Steam profile URL
- "Link Steam Profile" button
- Status display showing linked profile
- "Re-import Games" button to refresh library
- "Unlink Steam" button to remove connection
- Helpful instructions for users

### 4. Flask Routes (`app.py`)
Added three new routes:

**`/link_steam`** (POST)
- Validates Steam profile URL
- Extracts Steam ID
- Saves profile URL to user account
- Imports all games from Steam
- Adds games to database and user's backlog
- Sets playtime and backlog order

**`/import_steam`** (POST)
- Re-imports games from already-linked Steam profile
- Updates library with new games
- Refreshes playtime data

**`/unlink_steam`** (POST)
- Removes Steam profile link
- Keeps imported games in backlog

### 5. Backlog Display (`templates/backlog.html`)
- Added "Hours" column to show playtime from Steam
- Games imported from Steam are ordered by playtime (descending)

## How It Works

1. **User links Steam profile**: Enter Steam profile URL on the profile page
2. **System validates URL**: Extracts Steam ID and validates profile
3. **Import process begins**: 
   - Fetches all owned games from Steam API
   - Sorts by playtime (most played first)
   - For each game:
     - Fetches additional metadata from Steam Store
     - Adds game to master games table (if not exists)
     - Creates user_score entry with playtime
     - Sets backlog_order based on playtime ranking
4. **Games appear in backlog**: Sorted by hours played, ready to review

## API Key
Uses Steam Web API key: `EF41FB111ABBA588DDAE7EBEF933D669`
(Note: This is hardcoded in `steam_integration.py` - consider moving to environment variable for production)

## Requirements
- `requests` library (already in requirements.txt)
- Public Steam profile with visible game details

## Testing
Run `test_steam.py` to verify Steam ID extraction works correctly.

## Future Enhancements
- Download and save cover images locally
- Add progress indicator for import process
- Allow selective import of games
- Import wishlist games as well
- Cache Steam data to reduce API calls
