"""Test script to refresh a game from Steam directly."""
import requests

# Configuration
BASE_URL = "http://127.0.0.1:5000"
GAME_ID = 281  # Balatro

# Create a session to maintain cookies
session = requests.Session()

# Login
print("Logging in...")
login_response = session.post(f"{BASE_URL}/login", data={
    'username': 'admin',
    'password': 'admin'  # Update with your actual password
})

if login_response.status_code == 200:
    print("✓ Logged in successfully")
    
    # Trigger refresh
    print(f"\nRefreshing game ID {GAME_ID}...")
    refresh_response = session.post(f"{BASE_URL}/admin/refresh_game/{GAME_ID}")
    
    if refresh_response.status_code == 200 or refresh_response.status_code == 302:
        print("✓ Refresh request sent successfully")
        print(f"Response status: {refresh_response.status_code}")
        print("\nCheck the Flask terminal for [ADMIN REFRESH] log messages")
    else:
        print(f"✗ Refresh failed with status {refresh_response.status_code}")
else:
    print(f"✗ Login failed with status {login_response.status_code}")
