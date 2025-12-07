# Game Ratings Database - Setup & Usage

## Quick Start

### 1. Initialize the Database

```bash
python init_db.py
```

This will:
- Create the SQLite database with the new schema
- Create a default admin account (username: `admin`, password: `password`)
- Display setup instructions

### 2. Start the Application

```bash
python app.py
```

Visit `http://localhost:5000`

### 3. Login

**Default credentials:**
- Username: `admin`
- Password: `password`

⚠️ **Change password after first login!**

---

## Database Schema

### Games Table
Central repository of all games with:
- **game_id** - Unique sequential ID (1, 2, 3...)
- **app_id** - Steam App ID (for Steam integration)
- **name** - Game title
- **release_date** - Release year or date
- **description** - Game description
- **genres** - Game genres
- **price** - Purchase price
- **cover_path** - Path to cover image
- **average_enjoyment_score** - Average enjoyment rating from all users
- **num_ratings** - Number of users who rated this game

### User_Scores Table
Individual user ratings:
- Links users to games (many-to-many)
- Stores enjoyment, gameplay, music, narrative, and MetaCritic scores
- One row per user per game

### Users Table
User accounts with username and password

---

## Uploading Your CSV

### CSV Format

Your `data.csv` should have these columns:

```
Game,Release Year,Cover Path,Enjoyment Score,Gameplay Score,Music Score,Narrative Score,MetaCritic Score
```

**Supported columns:**
- `Game` (required) - Game title
- `Release Year` - Year game was released
- `AppID` - Steam App ID (optional)
- `Description` - Game description (optional)
- `Genres` - Game genres (optional)
- `Price` - Game price (optional)
- `Cover Path` - Path to cover image
- `Enjoyment Score` - 0-10 rating
- `Gameplay Score` - 0-10 rating
- `Music Score` - 0-10 rating
- `Narrative Score` - 0-10 rating
- `MetaCritic Score` - MetaCritic score

### Uploading

1. Login to the app
2. Click "Upload CSV"
3. Select your CSV file
4. Click "Upload"

**What happens:**
- Games are added to the master database (if not already there)
- Your scores are linked to your account
- Average enjoyment scores are calculated
- Duplicate games (by name) reuse existing game_id

---

## Cover Images

### Option 1: Local Cover Images

1. Place PNG/JPG files in `static/covers/` directory
2. When editing a game, set Cover Path to `/static/covers/filename.png`

### Option 2: Auto-Download from Wikipedia/RAWG.io

1. Login to the app
2. Click "Full Reviews"
3. Click the "Autofill Covers" button (or visit `/autofill_covers`)
4. Covers will be automatically downloaded

### Option 3: Manual URLs

Set Cover Path to full URLs like:
- `https://steamcdn-a.akamaihd.net/steam/apps/...`
- `https://example.com/image.png`

---

## Features

### Multi-User Support
- Each user has their own account
- Each user can rate the same game
- Scores are kept separate per user

### Global Game Database
- All games stored in master database
- Shared across all users
- No duplicate game entries

### Average Enjoyment Scores
- Automatically calculated from all users' ratings
- Updated every time a user scores a game
- Shows community consensus
- Visible on game cards and in Full Reviews

### Data Export
- Download your personal ratings as CSV
- Includes all your scores and game metadata
- Keep backup or share with others

### Inline Editing
- Double-click any score in Full Reviews table to edit
- Press Enter to save, Escape to cancel

---

## Multi-User Workflow

### User 1: Import Their Library
1. Login as User 1
2. Upload their CSV
3. Add/edit ratings
4. Logout

### User 2: Import Their Library
1. Register new account (User 2)
2. Upload their CSV
3. Same games are reused from database
4. User 2's scores are separate from User 1

### View Combined Stats
- Each game shows average enjoyment from all users
- See which games are community favorites
- Compare your ratings to the average

---

## API Endpoints

### Authentication
- `POST /login` - User login
- `POST /register` - Register new account
- `GET /logout` - Logout

### Games (Require Login)
- `GET /` - View your games (card view)
- `GET /full` - View your games (table view)
- `GET/POST /edit/<game_id>` - Edit game and scores
- `POST /delete/<game_id>` - Remove game from your library
- `POST /upload` - Import CSV
- `GET /download` - Export your ratings as CSV
- `GET /autofill_covers` - Auto-download cover images
- `POST /api/update_score` - Update score via AJAX

---

## Troubleshooting

### "Database locked" error
```bash
# Delete the database and reinitialize
rm ratings.db
python init_db.py
python app.py
```

### Port 5000 already in use
```bash
# Use a different port
python app.py --port 5001
# Then visit http://localhost:5001
```

### Cover images not showing
- Make sure files are in `static/covers/`
- Check file paths are correct in database
- Try `/autofill_covers` to download automatically

### Can't login after creating account
- Check username and password spelling
- Make sure "Confirm Password" matches
- Try registering again

### CSV import errors
- Check for extra spaces in column headers
- Make sure "Game" column has values
- Empty cells are OK (treated as null)
- Dashes (-) are treated as null

---

## CSV Export Format

When you download your data, it includes:

```
GameID,AppID,Game,Release Year,Description,Genres,Price,Cover Path,Enjoyment Score,...
```

**Columns:**
- GameID - Unique game identifier from database
- AppID - Steam App ID
- Game - Game name
- Release Year - Release date
- Description - Game description
- Genres - Game genres
- Price - Game price
- Cover Path - Path to cover image
- Enjoyment Score - Your enjoyment rating
- (plus Gameplay, Music, Narrative, MetaCritic scores)

---

## Advanced: SQL Queries

You can inspect the database directly:

```bash
sqlite3 ratings.db

# See all games
sqlite> SELECT game_id, name, average_enjoyment_score, num_ratings FROM games;

# See all users
sqlite> SELECT id, username FROM users;

# See all scores for a game
sqlite> SELECT u.username, us.enjoyment_score, us.gameplay_score FROM user_scores us
        JOIN users u ON us.user_id = u.id
        WHERE us.game_id = 1;

# Find top-rated games
sqlite> SELECT * FROM games WHERE num_ratings > 0 ORDER BY average_enjoyment_score DESC;
```

---

## Best Practices

1. **Backup Your Data**
   - Download CSV regularly: `GET /download`
   - Keep backups before database resets

2. **Password Security**
   - Change admin password immediately after setup
   - Use unique passwords per user
   - (For production: use bcrypt password hashing)

3. **Game Metadata**
   - Edit game details while adding ratings
   - Add descriptions and genres for better organization
   - Set Steam App IDs for game linking

4. **Cover Images**
   - Keep cover files under 500KB
   - Use consistent naming in `static/covers/`
   - Save as PNG or JPG for web

5. **Data Consistency**
   - Don't edit `ratings.db` directly
   - Use the web interface for all changes
   - Use CSV import/export for bulk operations

---

## Common Tasks

### Add a New User
1. Click logout (or use new browser session)
2. Click "Register here"
3. Enter username and password
4. Click Register

### Add Games
1. Upload CSV, OR
2. Edit page → enter game info manually

### Change Password
- Currently: Create new account with new credentials
- Future: Add password reset functionality

### Delete a Game
1. Click "Delete" on game card or table row
2. This removes YOUR rating
3. Game stays in database for other users

### See Average Scores
- View on main index page (under game title)
- Shows average enjoyment and number of ratings
- Updated real-time as users rate games

---

## Future Enhancements

- Password hashing (bcrypt)
- User profiles with statistics
- Social features (compare ratings, follow users)
- Game recommendations based on ratings
- API integration (IGDB, Steam)
- Mobile app
- Dark/light theme toggle
- Advanced filtering and sorting

---

## Support

Check these files for more information:
- `SCHEMA_UPDATED.md` - Database schema details
- `README.md` - General application documentation
- `QUICKSTART.md` - Quick reference guide

For issues:
1. Check error message carefully
2. Review CSV format if importing
3. Delete database and reinitialize if corrupted
4. Check terminal output for detailed error logs
