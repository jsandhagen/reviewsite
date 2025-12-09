#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite to PostgreSQL Migration Script
Migrates all data from ratings.db to PostgreSQL while preserving IDs and relationships.
"""
import os
import sys
import sqlite3
import psycopg2
import psycopg2.extras
from datetime import datetime
from dotenv import load_dotenv

# Set encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

# SQLite source
SQLITE_DB = os.path.join(os.path.dirname(__file__), "ratings.db")

# PostgreSQL destination (from environment)
POSTGRES_URL = os.environ.get('DATABASE_URL')

if not POSTGRES_URL:
    print("ERROR: DATABASE_URL environment variable not set!")
    print("Please set DATABASE_URL in your .env file")
    exit(1)

# Tables to migrate in dependency order (important!)
TABLES = [
    'users',
    'games',
    'superlatives',
    'user_scores',
    'steam_update_log',
    'friends',
    'user_superlatives'
]


def connect_sqlite():
    """Connect to SQLite database"""
    if not os.path.exists(SQLITE_DB):
        raise FileNotFoundError(f"SQLite database not found: {SQLITE_DB}")

    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    return conn


def connect_postgres():
    """Connect to PostgreSQL database"""
    conn = psycopg2.connect(POSTGRES_URL)
    return conn


def migrate_table(sqlite_conn, postgres_conn, table_name):
    """Migrate a single table from SQLite to PostgreSQL"""
    print(f"\nMigrating table: {table_name}")

    sqlite_cursor = sqlite_conn.cursor()
    postgres_cursor = postgres_conn.cursor()

    # Get all rows from SQLite
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()

    if not rows:
        print(f"   No data to migrate")
        return 0

    # Get column names
    columns = [desc[0] for desc in sqlite_cursor.description]

    # Build INSERT query
    placeholders = ', '.join(['%s'] * len(columns))
    column_list = ', '.join(columns)
    insert_query = f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders})"

    # Insert all rows
    migrated_count = 0
    for row in rows:
        try:
            # Convert empty strings and 'None' strings to None for PostgreSQL compatibility
            cleaned_row = []
            for value in tuple(row):
                if value == '' or value == 'None':
                    cleaned_row.append(None)
                else:
                    cleaned_row.append(value)

            postgres_cursor.execute(insert_query, tuple(cleaned_row))
            migrated_count += 1
        except Exception as e:
            print(f"   ERROR inserting row: {e}")
            print(f"   Row data: {dict(row)}")
            raise

    postgres_conn.commit()
    print(f"   Migrated {migrated_count} rows")
    return migrated_count


def reset_sequences(postgres_conn):
    """Reset PostgreSQL sequences to match the max ID in each table"""
    print("\nResetting PostgreSQL sequences...")

    cursor = postgres_conn.cursor()

    # Tables with SERIAL primary keys
    sequences = {
        'users': 'users_id_seq',
        'games': 'games_game_id_seq',
        'user_scores': 'user_scores_id_seq',
        'friends': 'friends_id_seq',
        'superlatives': 'superlatives_id_seq',
        'user_superlatives': 'user_superlatives_id_seq'
    }

    for table, sequence in sequences.items():
        try:
            # Get the column name for the primary key
            if table == 'games':
                id_col = 'game_id'
            else:
                id_col = 'id'

            # Get max ID
            cursor.execute(f"SELECT MAX({id_col}) FROM {table}")
            max_id = cursor.fetchone()[0]

            if max_id is not None:
                # Reset sequence to max_id + 1
                cursor.execute(f"SELECT setval('{sequence}', %s, true)", (max_id,))
                print(f"   Reset {sequence} to {max_id}")
            else:
                print(f"   No data in {table}, skipping sequence reset")
        except Exception as e:
            print(f"   Could not reset {sequence}: {e}")

    postgres_conn.commit()


def verify_migration(sqlite_conn, postgres_conn):
    """Verify that all data was migrated correctly"""
    print("\nVerifying migration...")

    sqlite_cursor = sqlite_conn.cursor()
    postgres_cursor = postgres_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    all_good = True

    for table in TABLES:
        # Count rows in SQLite
        sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table}")
        sqlite_count = sqlite_cursor.fetchone()[0]

        # Count rows in PostgreSQL
        postgres_cursor.execute(f"SELECT COUNT(*) FROM {table}")
        postgres_count = postgres_cursor.fetchone()['count']

        if sqlite_count == postgres_count:
            print(f"   {table}: {sqlite_count} rows (match)")
        else:
            print(f"   {table}: SQLite has {sqlite_count}, PostgreSQL has {postgres_count} (MISMATCH!)")
            all_good = False

    return all_good


def main():
    """Main migration function"""
    print("=" * 70)
    print("SQLite to PostgreSQL Migration")
    print("=" * 70)

    print(f"\nSource (SQLite): {SQLITE_DB}")
    print(f"Destination (PostgreSQL): {POSTGRES_URL[:50]}...")

    # Confirm migration
    print("\nWARNING: This will migrate data to PostgreSQL.")
    print("WARNING: Make sure you have backed up your SQLite database!")
    response = input("\nProceed with migration? (yes/no): ").strip().lower()

    if response != 'yes':
        print("Migration cancelled")
        return

    try:
        # Connect to databases
        print("\nConnecting to databases...")
        sqlite_conn = connect_sqlite()
        postgres_conn = connect_postgres()
        print("   Connected to both databases")

        # Clear existing PostgreSQL data (optional - comment out if you want to preserve)
        print("\nClearing existing PostgreSQL data...")
        postgres_cursor = postgres_conn.cursor()
        for table in reversed(TABLES):  # Reverse order for foreign keys
            postgres_cursor.execute(f"DELETE FROM {table}")
        postgres_conn.commit()
        print("   Cleared all tables")

        # Migrate each table
        print("\nStarting data migration...")
        total_rows = 0
        for table in TABLES:
            rows = migrate_table(sqlite_conn, postgres_conn, table)
            total_rows += rows

        # Reset sequences
        reset_sequences(postgres_conn)

        # Verify migration
        if verify_migration(sqlite_conn, postgres_conn):
            print("\n" + "=" * 70)
            print("MIGRATION SUCCESSFUL!")
            print(f"Total rows migrated: {total_rows}")
            print("=" * 70)
        else:
            print("\n" + "=" * 70)
            print("MIGRATION HAD ERRORS!")
            print("Please review the output above")
            print("=" * 70)

        # Close connections
        sqlite_conn.close()
        postgres_conn.close()

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

    print("\nMigration Complete!")


if __name__ == '__main__':
    main()
