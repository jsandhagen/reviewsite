# START HERE

## Quick Setup (3 steps)

### 1. Initialize Database
```bash
python init_db.py
```

### 2. Start Application
```bash
python app.py
```

### 3. Open Browser
```
http://localhost:5000
```

Login with:
- Username: `admin`
- Password: `password`

---

## Next Steps

1. **Change Password** - Don't use default password
2. **Upload CSV** - Click "Upload CSV" and select your data.csv
3. **Add More Users** - Register new accounts, upload their CSVs
4. **View Stats** - See average enjoyment scores calculated across all users

---

## Detailed Guides

- `DATABASE_GUIDE.md` - Complete setup and usage
- `IMPLEMENTATION_SUMMARY.md` - What was implemented
- `SCHEMA_UPDATED.md` - Database schema details
- `README.md` - General documentation

---

## Key Features

✅ Multi-user accounts
✅ Global game database (all games shared)
✅ Individual user ratings (scores separate per user)
✅ Average enjoyment scores (from all users)
✅ CSV import/export
✅ Cover image support
✅ Enhanced game metadata (AppID, description, genres, price)

---

## Database Info

- **Games Table**: Master list of all games with averages
- **User_Scores Table**: Individual user ratings
- **Users Table**: User accounts

Each game has a unique `game_id` (sequential: 1, 2, 3...)

---

## Troubleshooting

**Database locked?**
```bash
rm ratings.db
python init_db.py
```

**Port 5000 in use?**
```bash
python app.py --port 5001
# Then visit http://localhost:5001
```

**Cover images not showing?**
```
Click "Full Reviews" then "Autofill Covers"
```

---

That's it! You're ready to go. Start with `python init_db.py`
