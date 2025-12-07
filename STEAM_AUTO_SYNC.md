# Steam Auto-Sync Feature

## New Features Added

### 1. Steam Link During Registration
- New users can optionally link their Steam profile when creating an account
- Steam library import happens in the background (non-blocking)
- Register page updated with Steam URL input field

### 2. Automatic Library Updates
- Background service runs continuously checking for updates every hour
- Syncs each user's Steam library once every 24 hours
- Updates include:
  - New games added to backlog
  - Playtime updates for existing games
  - Game metadata refreshes

### 3. Manual Sync Button
- Users can manually trigger a sync from their profile page
- "Sync Now" button immediately updates their library
- Shows last sync timestamp on profile

## How It Works

### Background Updater (`steam_updater.py`)
- Runs as a daemon thread when the Flask app starts
- Checks every hour for users needing updates
- Only updates each user once per 24 hours
- Logs all updates to `steam_update_log` table
- Rate-limited to avoid Steam API throttling

### Database Changes
- New table: `steam_update_log`
  - `user_id` - User being tracked
  - `last_update` - Timestamp of last sync

### Registration Flow
1. User enters username, password, and optional Steam URL
2. Account is created immediately
3. If Steam URL provided:
   - Steam profile is validated and linked
   - Library import starts in background thread
   - User can start using the app immediately

### Auto-Update Flow
1. Background service checks hourly
2. Finds users with linked Steam profiles
3. Skips users updated in last 23 hours
4. For each user:
   - Fetches current library from Steam
   - Compares with existing games
   - Adds new games to backlog
   - Updates playtime for all games
   - Logs update timestamp

## Benefits

- **Set and forget**: Users link once, library stays current
- **New game notifications**: Automatically adds new purchases
- **Accurate playtime**: Always shows current hours played
- **Low maintenance**: Runs automatically in background
- **Rate-limited**: Respects Steam API limits

## Configuration

Update interval can be changed in `steam_updater.py`:
```python
UPDATE_INTERVAL = 24 * 60 * 60  # Currently 24 hours
```

## Manual Sync

Users can force an immediate sync by:
1. Going to their profile page
2. Clicking "Sync Now (Re-import Games)"
3. Waiting for completion message

## Monitoring

Check console output for sync activity:
```
Steam updater started
[2025-12-05 13:45:00] Updating Steam libraries for 3 users...
  Updating user1's Steam library...
    Added 2 new games, updated 15 playtimes
```
