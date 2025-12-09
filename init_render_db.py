#!/usr/bin/env python3
"""
Initialize PostgreSQL schema on Render
"""
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Verify DATABASE_URL is loaded
db_url = os.environ.get('DATABASE_URL')
print(f"DATABASE_URL loaded: {db_url[:50]}..." if db_url else "ERROR: DATABASE_URL not found")

# Initialize the database
from database import init_db

print("\nInitializing PostgreSQL schema...")
init_db()
print("Schema initialized successfully!")
