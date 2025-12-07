"""Verify aggregate data in games table."""
import sqlite3

conn = sqlite3.connect('ratings.db')
c = conn.cursor()

# Check top 5 best value games
rows = c.execute('''
    SELECT name, average_enjoyment_score, average_gameplay_score, 
           average_music_score, average_narrative_score, pv_ratio 
    FROM games 
    WHERE pv_ratio IS NOT NULL 
    ORDER BY pv_ratio 
    LIMIT 5
''').fetchall()

print('Top 5 Games by Value (lowest $/hr):\n')
for row in rows:
    name, enjoy, gameplay, music, narrative, pv = row
    print(f'{name}:')
    print(f'  Enjoyment: {enjoy:.1f}' if enjoy else '  Enjoyment: N/A')
    print(f'  Gameplay: {gameplay:.1f}' if gameplay else '  Gameplay: N/A')
    print(f'  Music: {music:.1f}' if music else '  Music: N/A')
    print(f'  Narrative: {narrative:.1f}' if narrative else '  Narrative: N/A')
    print(f'  PV Ratio: ${pv:.2f}/hr')
    print()

conn.close()
