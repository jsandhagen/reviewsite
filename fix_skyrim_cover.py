import sqlite3

conn = sqlite3.connect('ratings.db')
c = conn.cursor()

# Update regular Skyrim to use the correct cover
c.execute("""
    UPDATE games 
    SET cover_path = '/static/covers/The Elder Scrolls V Skyrim.png'
    WHERE game_id = 225 AND name = 'The Elder Scrolls V: Skyrim'
""")

conn.commit()
print(f"Updated {c.rowcount} row(s)")

# Verify the change
c.execute("SELECT game_id, name, cover_path FROM games WHERE name LIKE '%Skyrim%'")
for row in c.fetchall():
    print(f"ID: {row[0]}, Name: {row[1]}, Cover: {row[2]}")

conn.close()
