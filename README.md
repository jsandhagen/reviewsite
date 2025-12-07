# Game Scoreboard with Multi-User Support

A Flask-based web application for managing game reviews with individual user accounts and a centralized game database.

## Quick Start

### Installation

1. Install Python dependencies:
```powershell
pip install -r requirements.txt
```

2. Run the application:
```powershell
python app.py
```

3. Open `http://localhost:5000` in your browser

### First-Time Setup

1. Click the **Register** link and create an account
2. Login with your credentials
3. Upload a CSV file with your game ratings
4. View, edit, and manage your ratings

## Features

✨ **Multi-User Support**
- Individual user accounts with login
- Each user maintains their own ratings
- Global game database shared across all users

📊 **Game Management**
- Upload ratings from CSV files
- View games as cards or detailed table
- Edit scores inline in the table view
- Download your ratings as CSV

🖼️ **Cover Art Management**
- Automatic cover art download from Wikipedia and RAWG.io
- Auto-fill feature to populate missing covers

🎯 **Sorting & Filtering**
- Sort by any score column
- Search across your game library
- Quick view of average scores

🎵 **Utilities**
- Quick links to game soundtracks on YouTube
- Toggle between card view and table view

## CSV Format

### Import Format

Upload a CSV with these columns:

```
Game,Release Year,Cover Path,Enjoyment Score,Gameplay Score,Music Score,Narrative Score,MetaCritic Score
Elden Ring,2022,,9,9,8,8,96
Baldur's Gate 3,2023,,10,10,9,9,96
```

**Column Descriptions:**
- **Game**: Game title (required)
- **Release Year**: Year of release
- **Cover Path**: Path to cover image (e.g., `/static/covers/game.jpg`)
- **Enjoyment Score**: Your enjoyment rating (0-10)
- **Gameplay Score**: Gameplay quality (0-10)
- **Music Score**: Music/soundtrack (0-10)
- **Narrative Score**: Story quality (0-10)
- **MetaCritic Score**: MetaCritic score (usually 0-100)

### Export Format

Click **Download CSV** to export your ratings in the same format

## Architecture

### Database

The application uses SQLite with three tables:

**users**
- Stores user accounts with username and password

**games**
- Master list of all games (name, year, cover path)
- Shared across all users

**user_scores**
- Individual ratings per user per game
- Links users to games with one-to-many relationship

### Project Structure

```
RatingsProject/
├── app.py                 # Main Flask application
├── database.py           # SQLite database models
├── requirements.txt      # Python dependencies
├── ratings.db           # SQLite database (auto-created)
├── templates/
│   ├── login.html       # Login/auth page
│   ├── register.html    # Registration page
│   ├── index.html       # Card view of games
│   ├── full.html        # Table view with sorting
│   └── edit.html        # Edit game scores page
└── static/
    ├── style.css        # Styling
    └── covers/          # Downloaded cover images
```

## Usage Guide

### Login & Registration

1. Visit `http://localhost:5000`
2. You'll be redirected to login
3. Click "Register here" to create a new account
4. After creating an account, you're automatically logged in

### Adding Games

1. Click **Upload CSV**
2. Select a CSV file with the format shown above
3. Games are added to the global database
4. Your scores are saved under your account

### Viewing & Editing

**Index Page** - Card view of your games:
- Search for games using the search box
- Click **Edit** to modify a game or your scores
- Click **Delete** to remove a game from your library
- Click **Music** to search for OST on YouTube

**Full Reviews** - Detailed table view:
- Click column headers to sort
- Double-click any score cell to edit inline
- Search across all columns

### Switching Users

Click **Logout** in the top-right corner to logout
Then login with a different account to see their library

## Configuration

### Secret Key

Change the Flask secret key in `app.py` for production:

```python
app.secret_key = 'your-production-secret-key'
```

### Security Notes

- Passwords are stored in plaintext (use bcrypt for production)
- Add HTTPS in production
- Add CSRF protection for form submissions
- Use environment variables for secrets

## API Routes

### Authentication
- `GET/POST /login` - User login
- `GET/POST /register` - User registration
- `GET /logout` - Logout and clear session

### Games (all require login)
- `GET /` - View user's games (card view)
- `GET /full` - View user's games (table view)
- `GET/POST /edit/<game_id>` - Edit game and scores
- `POST /delete/<game_id>` - Delete user's rating

### Data
- `POST /upload` - Import games from CSV
- `GET /download` - Export ratings as CSV
- `POST /api/update_score` - Update score via AJAX
- `GET /autofill_covers` - Auto-download cover art

## Troubleshooting

**"requests library not installed"**
```powershell
pip install requests
```

**Port 5000 already in use**
```powershell
python app.py --port 5001
```

**Database locked**
- Close all Flask instances
- Delete `ratings.db`
- Restart the application

**CSS/styles not loading**
- Make sure you're using `http://localhost:5000` (not 127.0.0.1)
- Refresh the page or clear browser cache

## Development Setup

Using PowerShell with venv:
```powershell
python -m venv .\venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Using Conda:
```powershell
conda create -n ratings python=3.10 -y
conda activate ratings
pip install -r requirements.txt
python app.py
```

---

**Ready to get started?** Follow the Quick Start section above!
