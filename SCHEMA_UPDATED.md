# Enhanced Database Schema - Implementation Complete

## Database Schema Updated

Your database now includes the following enhanced structure:

### Games Table (Master Game Database)
```sql
game_id (INTEGER PRIMARY KEY) - Unique sequential ID for each game
app_id (TEXT) - Steam App ID
name (TEXT) - Game title
release_date (TEXT) - Release date/year
description (TEXT) - Game description
genres (TEXT) - Game genres
price (REAL) - Price of game
cover_path (TEXT) - Path to cover image
average_enjoyment_score (REAL) - Average enjoyment score across all users
num_ratings (INTEGER) - Number of user ratings for this game
created_at (TIMESTAMP) - When game was added to database
updated_at (TIMESTAMP) - Last update timestamp
```

### User_Scores Table (Individual User Ratings)
```sql
id (INTEGER PRIMARY KEY)
user_id (FOREIGN KEY) - References users table
game_id (FOREIGN KEY) - References games table (with CASCADE delete)
enjoyment_score (REAL) - User's enjoyment rating
gameplay_score (REAL) - User's gameplay rating
music_score (REAL) - User's music rating
narrative_score (REAL) - User's narrative rating
metacritic_score (REAL) - MetaCritic score
updated_at (TIMESTAMP)
UNIQUE(user_id, game_id) - Ensures one rating per user per game
```

### Users Table (Unchanged)
```sql
id (INTEGER PRIMARY KEY)
username (TEXT UNIQUE)
password (TEXT)
created_at (TIMESTAMP)
```

## Key Features

### 1. Unique Sequential Game IDs
- Each game gets a unique `game_id` (autoincrement)
- Games are stored in a master database accessible to all users
- Multiple users can rate the same game

### 2. Steam App ID Support
- Store Steam App IDs for easy linking to Steam store
- Helps with game identification and external API integration

### 3. Enhanced Game Metadata
- Release date for sorting and filtering
- Description for detailed game information
- Genres for categorization
- Price tracking

### 4. Average Enjoyment Score
- Automatically calculated when user scores are updated
- Aggregates enjoyment scores from all users
- Shows community consensus on game enjoyment
- Updated every time a user rates a game

### 5. Cover Image Management
- Centralized cover path storage
- Auto-fill covers from Wikipedia/RAWG.io
- Support for both local and remote image paths

## Updated Functions

### Database Functions in `database.py`

**`add_or_get_game()`**
- Now accepts: name, app_id, release_date, description, genres, price, cover_path
- Creates or retrieves game by name
- Returns game_id

**`set_user_score()`**
- Automatically updates average_enjoyment_score for the game
- Recalculates num_ratings across all users
- Maintains data integrity with transactions

**`import_csv_data(user_id, csv_content)`** - NEW
- Imports entire CSV file into database
- Associates all games with specified user
- Handles empty fields and dashes gracefully
- Returns count of imported games

**`update_game_info()`**
- Now updates all new fields: app_id, release_date, description, genres, price
- Updates modified timestamp

**`get_user_games(user_id)`**
- Returns user's games with their scores
- Includes average_enjoyment_score for each game
- Full game metadata available

## CSV Import Format

Your data.csv will be automatically imported with this structure:

```
Game,Release Year,Cover Path,Enjoyment Score,Gameplay Score,Music Score,Narrative Score,MetaCritic Score
```

**Supported columns** (case-insensitive):
- Game (required)
- AppID (optional)
- Release Year → release_date
- Description (optional)
- Genres (optional)
- Price (optional)
- Cover Path
- Enjoyment Score
- Gameplay Score
- Music Score
- Narrative Score
- MetaCritic Score

**Features:**
- Empty fields handled gracefully
- Dashes (-) treated as null
- Duplicate games (by name) reuse existing game_id
- One entry per user per game

## CSV Export Format

When you download data, you get:

```
GameID,AppID,Game,Release Year,Description,Genres,Price,Cover Path,Enjoyment Score,...
```

Includes all game metadata plus your personal scores.

## Migration Path

1. **Run migration script** (coming next step):
   ```bash
   python migrate.py
   ```

2. **Script will:**
   - Create new database with enhanced schema
   - Create default admin user (admin/password)
   - Import all games from data.csv
   - Calculate average enjoyment scores
   - Report any issues

3. **After migration:**
   - Delete or backup old data.csv
   - Start the app: `python app.py`
   - Login as admin
   - Change password
   - Start using with new multi-user setup

## Usage Scenarios

### Scenario 1: Adding a New Game
```
User A adds "Game X" with enjoyment score 8
- Game created in database with game_id = 42
- average_enjoyment_score = 8
- num_ratings = 1

User B adds same "Game X" with enjoyment score 9
- Reuses game_id = 42
- average_enjoyment_score = 8.5
- num_ratings = 2
```

### Scenario 2: Viewing Game Statistics
```
Game Overview (available to all users):
- Game name, cover, AppID
- Release date, description, genres, price
- Average enjoyment score (8.5/10 from 2 ratings)

User's Personal View:
- Their own scores (8, 9, 8, 7.5, 85)
- Can edit or delete their ratings
```

### Scenario 3: Bulk Import
Upload CSV → All games added to master database → Your scores linked to your account

## Performance Notes

- **Indexing**: Game lookups by name are optimized for single user CSV imports
- **Aggregation**: Average scores calculated on-demand during scoring
- **Scalability**: Schema supports unlimited users and games
- **Data Isolation**: Users only see/modify their own scores

## Security Considerations

- ⚠️ Passwords still in plaintext (use bcrypt for production)
- Games table is shared, but scores are user-private
- Foreign key constraints prevent orphaned records
- ON DELETE CASCADE keeps data consistent

## Next Steps

1. Copy PNG cover images to `static/covers/` (optional)
   - Or use `/autofill_covers` to auto-download from Wikipedia/RAWG.io

2. Run migration:
   ```bash
   python migrate.py
   ```

3. Start app:
   ```bash
   python app.py
   ```

4. Login with admin/password

5. Change admin password immediately

6. Add more users as needed

7. Each user can now:
   - Upload their own CSV
   - Rate existing games
   - See average scores from all users
   - Download their personal data

## Database Queries (Reference)

**Get all games with average scores:**
```sql
SELECT game_id, name, app_id, price, cover_path, 
       average_enjoyment_score, num_ratings
FROM games
ORDER BY average_enjoyment_score DESC
```

**Get user's games they haven't rated yet:**
```sql
SELECT g.* FROM games g
LEFT JOIN user_scores us ON g.game_id = us.game_id 
  AND us.user_id = ?
WHERE us.id IS NULL
```

**Games with most ratings:**
```sql
SELECT * FROM games 
ORDER BY num_ratings DESC
```

**Top-rated games (minimum 2 ratings):**
```sql
SELECT * FROM games
WHERE num_ratings >= 2
ORDER BY average_enjoyment_score DESC
```
