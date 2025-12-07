"""Update all games with aggregate scores and PV ratio."""
import sqlite3
from database import get_db

def update_all_game_aggregates():
    """Calculate and update aggregate scores for all games."""
    with get_db() as conn:
        c = conn.cursor()
        
        # Get all games
        c.execute("SELECT game_id, price FROM games")
        games = c.fetchall()
        
        print(f"Updating aggregates for {len(games)} games...")
        
        for game in games:
            game_id = game['game_id']
            price = game['price']
            
            # Calculate aggregate scores
            c.execute('''
                SELECT 
                    AVG(enjoyment_score) as avg_enjoyment,
                    AVG(gameplay_score) as avg_gameplay,
                    AVG(music_score) as avg_music,
                    AVG(narrative_score) as avg_narrative,
                    AVG(hours_played) as avg_hours,
                    COUNT(*) as num_ratings
                FROM user_scores 
                WHERE game_id = ? AND enjoyment_score IS NOT NULL
            ''', (game_id,))
            result = c.fetchone()
            
            avg_enjoyment = result['avg_enjoyment'] if result and result['avg_enjoyment'] else 0
            avg_gameplay = result['avg_gameplay'] if result and result['avg_gameplay'] else None
            avg_music = result['avg_music'] if result and result['avg_music'] else None
            avg_narrative = result['avg_narrative'] if result and result['avg_narrative'] else None
            avg_hours = result['avg_hours'] if result and result['avg_hours'] else None
            num_ratings = result['num_ratings'] if result else 0
            
            # Calculate PV ratio
            pv_ratio = None
            if price and avg_hours and avg_hours > 0:
                pv_ratio = price / avg_hours
            
            # Update the game
            c.execute('''
                UPDATE games 
                SET average_enjoyment_score = ?, 
                    average_gameplay_score = ?,
                    average_music_score = ?,
                    average_narrative_score = ?,
                    pv_ratio = ?,
                    num_ratings = ?, 
                    updated_at = CURRENT_TIMESTAMP
                WHERE game_id = ?
            ''', (avg_enjoyment, avg_gameplay, avg_music, avg_narrative, pv_ratio, num_ratings, game_id))
        
        conn.commit()
        print("Done! All game aggregates updated.")

if __name__ == "__main__":
    update_all_game_aggregates()
