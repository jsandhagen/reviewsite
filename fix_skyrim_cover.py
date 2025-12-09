from database import get_db

with get_db() as conn:
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
    c.execute("SELECT game_id, name, cover_path FROM games WHERE name LIKE %s", ('%Skyrim%',))
    for row in c.fetchall():
        print(f"ID: {row['game_id']}, Name: {row['name']}, Cover: {row['cover_path']}")
