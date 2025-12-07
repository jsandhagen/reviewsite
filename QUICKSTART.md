# Quick Start Guide

## 1. Install & Run

```powershell
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000` in your browser.

## 2. Create Your First Account

- Click **Register here**
- Enter username and password
- You're logged in automatically

## 3. Add Games

### Option A: Upload CSV
1. Click **Upload CSV**
2. Select a CSV file with these columns:
   ```
   Game,Release Year,Cover Path,Enjoyment Score,Gameplay Score,Music Score,Narrative Score,MetaCritic Score
   ```
3. Games are added to the database
4. Your scores are saved

### Option B: Manual Entry
1. Use the Edit page to add new games
2. Enter game info and scores

## 4. View & Edit

- **Index** - See games as cards
- **Full Reviews** - Detailed table with sorting
- Double-click scores to edit inline
- Click **Edit** for full edit page
- Click **Delete** to remove from your library

## 5. Switch Users

- Click **Logout** (top-right, red button)
- Login or register as a different user
- Each user sees only their own games

## 6. Download Your Data

- Click **Download CSV** to export all your ratings
- File format matches the import format

## Logout Button Location

The **Logout** button is in the top-right corner of the page:
- Red colored to stand out
- Shows your username next to it
- Available on every page after login

## File Structure

```
RatingsProject/
├── app.py              # Main Flask app
├── database.py         # Database models
├── templates/
│   ├── login.html      # Login page
│   ├── register.html   # Registration
│   ├── index.html      # Card view
│   ├── full.html       # Table view
│   └── edit.html       # Edit form
└── static/
    ├── style.css       # Styling
    └── covers/         # Game cover images
```

## Common Tasks

### Upload Multiple Games
Prepare a CSV with all your games and upload it. Existing games will be updated, new ones added.

### Change User
1. Click **Logout**
2. Login as different user
3. Only that user's games appear

### Auto-Fill Cover Art
Visit `http://localhost:5000/autofill_covers`
Automatically downloads covers from Wikipedia/RAWG.io

### Export All Ratings
Click **Download CSV** to get all your ratings in CSV format

## Troubleshooting

**Can't login after registering?**
- Make sure you typed the same password twice
- Try logging in with that username and password

**Games not appearing?**
- Make sure you're logged in (check username in top-right)
- Try uploading a CSV file
- Clear browser cache if needed

**Download CSV is empty?**
- You haven't added any games yet
- Try uploading a CSV or adding games manually

**Cover images not showing?**
- Click `/autofill_covers` to download them
- Or manually set the "Cover Path" field when editing

## Tips

- All games are shared across users (same global database)
- You only see YOUR scores for those games
- Other users won't see your ratings
- Upload a CSV to quickly add multiple games
- Use sort by clicking column headers in Full Reviews
- Search by game name on the Index page

---

That's it! You're ready to start tracking your game ratings!
