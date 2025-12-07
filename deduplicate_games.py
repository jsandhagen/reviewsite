#!/usr/bin/env python3
"""
Remove duplicate games from the database, keeping the one with more ratings
"""
import sqlite3
from pathlib import Path

project_dir = Path(__file__).parent
db_path = project_dir / "ratings.db"

def deduplicate():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Find duplicates (case-insensitive)
    c.execute('''
        SELECT name, COUNT(*) as count
        FROM games
        GROUP BY LOWER(name)
        HAVING count > 1
        ORDER BY count DESC
    ''')
    
    duplicates = c.fetchall()
    
    if not duplicates:
        print("✓ No duplicates found")
        conn.close()
        return
    
    print(f"Found {len(duplicates)} duplicate game names:\n")
    
    for dup in duplicates:
        print(f"Processing: '{dup['name']}' ({dup['count']} entries)")
        
        # Get all versions of this game
        c.execute('''
            SELECT game_id, name, num_ratings, average_enjoyment_score
            FROM games
            WHERE LOWER(name) = ?
            ORDER BY num_ratings DESC, game_id ASC
        ''', (dup['name'].lower(),))
        
        games = c.fetchall()
        print(f"  Versions found:")
        for game in games:
            print(f"    - ID {game['game_id']}: '{game['name']}' ({game['num_ratings']} ratings, avg {game['average_enjoyment_score'] or 'N/A'})")
        
        # Keep the one with most ratings
        keeper = games[0]
        duplicates_to_remove = games[1:]
        
        print(f"  → Keeping ID {keeper['game_id']}: '{keeper['name']}'")
        
        for dup_game in duplicates_to_remove:
            print(f"  → Removing ID {dup_game['game_id']}: '{dup_game['name']}'")
            
            # Merge scores: if duplicate has scores and keeper doesn't have that user's score, copy it
            c.execute('''
                SELECT user_id, enjoyment_score, gameplay_score, music_score, 
                       narrative_score, metacritic_score
                FROM user_scores
                WHERE game_id = ?
            ''', (dup_game['game_id'],))
            
            scores_to_merge = c.fetchall()
            for score in scores_to_merge:
                # Check if keeper already has a score from this user
                c.execute('''
                    SELECT id FROM user_scores 
                    WHERE game_id = ? AND user_id = ?
                ''', (keeper['game_id'], score['user_id']))
                
                if not c.fetchone():
                    # Transfer the score
                    c.execute('''
                        INSERT INTO user_scores 
                        (user_id, game_id, enjoyment_score, gameplay_score, music_score, narrative_score, metacritic_score)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (score['user_id'], keeper['game_id'], score['enjoyment_score'], 
                          score['gameplay_score'], score['music_score'], score['narrative_score'], 
                          score['metacritic_score']))
                    print(f"    ✓ Transferred score from user {score['user_id']}")
            
            # Delete duplicate game (scores will cascade delete)
            c.execute('DELETE FROM games WHERE game_id = ?', (dup_game['game_id'],))
            print(f"    ✓ Deleted duplicate")
        
        # Recalculate average for keeper
        c.execute('''
            SELECT AVG(enjoyment_score) as avg, COUNT(*) as cnt
            FROM user_scores
            WHERE game_id = ? AND enjoyment_score IS NOT NULL
        ''', (keeper['game_id'],))
        
        result = c.fetchone()
        avg_score = result['avg']
        count = result['cnt']
        
        if count > 0:
            c.execute('''
                UPDATE games
                SET average_enjoyment_score = ?, num_ratings = ?
                WHERE game_id = ?
            ''', (avg_score, count, keeper['game_id']))
            print(f"    ✓ Updated average: {avg_score:.1f}/10 from {count} ratings\n")
        else:
            c.execute('''
                UPDATE games
                SET average_enjoyment_score = NULL, num_ratings = 0
                WHERE game_id = ?
            ''', (keeper['game_id'],))
            print(f"    ✓ Cleared average (no ratings)\n")
    
    conn.commit()
    conn.close()
    
    print("✓ Deduplication complete!")

if __name__ == "__main__":
    deduplicate()
