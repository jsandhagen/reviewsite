# Game Scoreboard - Database & Login Implementation

## Changes Implemented

### 1. **Database Layer** (`database.py`)
- Created SQLite database with three main tables:
  - **users**: Stores username and password for each user
  - **games**: Maintains a master list of all games (name, release year, cover path)
  - **user_scores**: Tracks individual review scores per user per game (one-to-many relationship)
- Implemented database functions:
  - `create_user()` / `verify_user()` - User authentication
  - `add_or_get_game()` - Game management
  - `get_user_games()` - Retrieve games and scores for a specific user
  - `set_user_score()` - Update/create user scores
  - `update_game_info()` - Modify game metadata

### 2. **Authentication System** (`app.py`)
- Added `/login` route - User login with session management
- Added `/register` route - New user registration
- Added `/logout` route - Clear user session
- Added `@login_required` decorator - Protect routes that need authentication
- All game-related routes now require login

### 3. **Multi-User Support**
- Each user maintains their own game library and ratings
- Games are shared across all users (global game database)
- When uploading a CSV, games are added to the global database and scores are tied to the logged-in user
- Users can see their own scores and edit/delete only their own ratings

### 4. **Updated Templates**

#### `login.html` (NEW)
- Login form with username and password
- Registration link
- Error message display

#### `register.html` (NEW)
- Registration form with password confirmation
- Login link

#### `index.html`, `full.html`, `edit.html` (UPDATED)
- Added logout button in top-right corner
- Shows currently logged-in username
- Updated all field references from CSV names (Game, Release Year, etc.) to database column names
- Login button styled in red to distinguish from other buttons

### 5. **Updated Routes in `app.py`**
- **`/`** - Now requires login, shows user's games
- **`/full`** - Now requires login, shows full table of user's games
- **`/edit/<game_id>`** - Updated to use database IDs instead of array indices
- **`/delete/<game_id>`** - Deletes user's score for a game (game stays in global database)
- **`/upload`** - Imports CSV and creates/links games to current user
- **`/download`** - Exports user's games and scores as CSV
- **`/api/update_score`** - New AJAX endpoint for inline score editing
- **`/autofill_covers`** - Now requires login, uses database functions

### 6. **New Features**
- Session-based authentication (Flask sessions)
- User isolation - each user sees only their own data
- Global game database shared across all users
- Individual score tracking per user
- CSV import now associates data with current user
- CSV export downloads only current user's data

## Database Schema

### users table
```
id (PRIMARY KEY)
username (UNIQUE)
password
created_at
```

### games table
```
id (PRIMARY KEY)
name
release_year
cover_path
created_at
```

### user_scores table
```
id (PRIMARY KEY)
user_id (FOREIGN KEY → users.id)
game_id (FOREIGN KEY → games.id)
enjoyment_score
gameplay_score
music_score
narrative_score
metacritic_score
updated_at
UNIQUE(user_id, game_id)
```

## How to Use

1. **First Time**: Visit the app and create an account on the registration page
2. **Login**: Use your credentials to login
3. **Add Games**: Upload a CSV file with your game ratings
4. **View/Edit**: Browse your games and edit scores (click on score cells for inline editing)
5. **Switch Users**: Click "Logout" in top-right, then login with another account
6. **Download**: Download your ratings as a CSV file

## Security Notes
- Passwords are stored in plaintext (change for production)
- Session secret key should be changed in production
- Add proper password hashing (bcrypt) for production use
- Add CSRF protection for form submissions
