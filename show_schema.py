import sqlite3

conn = sqlite3.connect('ratings.db')
c = conn.cursor()

# Get all tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()

for table in tables:
    table_name = table[0]
    print(f"\n{'='*60}")
    print(f"TABLE: {table_name}")
    print(f"{'='*60}")
    
    c.execute(f'PRAGMA table_info({table_name})')
    cols = c.fetchall()
    
    for col in cols:
        col_id, col_name, col_type, not_null, default, pk = col
        pk_marker = " [PRIMARY KEY]" if pk else ""
        print(f"  {col_name:<25} {col_type:<15}{pk_marker}")
    
    # Show row count
    c.execute(f'SELECT COUNT(*) FROM {table_name}')
    count = c.fetchone()[0]
    print(f"\nRow count: {count}")

conn.close()
