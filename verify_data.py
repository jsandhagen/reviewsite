#!/usr/bin/env python3
"""
Verify migrated data in PostgreSQL
"""
from dotenv import load_dotenv
import psycopg2.extras

load_dotenv()

from database import get_db

print("Verifying PostgreSQL data on Render...")
print("=" * 60)

with get_db() as conn:
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Test 1: Check users
    print("\n1. Users:")
    c.execute('SELECT id, username, user_type FROM users ORDER BY id')
    users = c.fetchall()
    for user in users:
        print(f"   ID: {user['id']}, Username: {user['username']}, Type: {user['user_type']}")

    # Test 2: Check games (sample)
    print("\n2. Sample Games (first 5):")
    c.execute('SELECT game_id, name, num_ratings, average_enjoyment_score FROM games ORDER BY game_id LIMIT 5')
    games = c.fetchall()
    for game in games:
        print(f"   ID: {game['game_id']}, Name: {game['name'][:40]}, Ratings: {game['num_ratings']}, Avg: {game['average_enjoyment_score']}")

    # Test 3: Check user scores
    print("\n3. User Scores Count:")
    c.execute('SELECT COUNT(*) as count FROM user_scores')
    count = c.fetchone()['count']
    print(f"   Total user scores: {count}")

    # Test 4: Check superlatives
    print("\n4. Superlatives:")
    c.execute('SELECT COUNT(*) as count, category FROM superlatives GROUP BY category')
    categories = c.fetchall()
    for cat in categories:
        print(f"   {cat['category']}: {cat['count']} superlatives")

    # Test 5: Test a join query (verify foreign keys work)
    print("\n5. Sample User Scores (verify joins work):")
    c.execute('''
        SELECT u.username, g.name, us.enjoyment_score
        FROM user_scores us
        JOIN users u ON us.user_id = u.id
        JOIN games g ON us.game_id = g.game_id
        WHERE us.enjoyment_score IS NOT NULL
        ORDER BY us.enjoyment_score DESC
        LIMIT 3
    ''')
    scores = c.fetchall()
    for score in scores:
        print(f"   {score['username']}: {score['name'][:35]} - Score: {score['enjoyment_score']}")

print("\n" + "=" * 60)
print("Verification complete! All queries successful.")
print("=" * 60)
