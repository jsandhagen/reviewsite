#!/usr/bin/env python3
"""
Flask App Runner - Loads .env and starts the Flask application
"""
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

# Now import and run the app
from app import app

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
