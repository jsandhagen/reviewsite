import os
from dotenv import load_dotenv
import psycopg2.extras

# Load environment variables
load_dotenv()

from database import get_db

with get_db() as conn:
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get all tables from PostgreSQL
    c.execute("""
        SELECT tablename FROM pg_tables
        WHERE schemaname='public'
        ORDER BY tablename
    """)
    tables = c.fetchall()

    for table in tables:
        table_name = table['tablename']
        print(f"\n{'='*60}")
        print(f"TABLE: {table_name}")
        print(f"{'='*60}")

        # Get column information from information_schema
        c.execute(f'''
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
        ''', (table_name,))
        cols = c.fetchall()

        for col in cols:
            col_name = col['column_name']
            col_type = col['data_type']
            nullable = col['is_nullable']
            default = col['column_default']

            pk_marker = " [PRIMARY KEY]" if default and 'nextval' in str(default) else ""
            null_marker = "" if nullable == 'YES' else " NOT NULL"
            print(f"  {col_name:<25} {col_type:<15}{null_marker}{pk_marker}")

        # Show row count
        c.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = c.fetchone()['count']
        print(f"\nRow count: {count}")
