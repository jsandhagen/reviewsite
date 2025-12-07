"""Test script for Steam integration"""
from steam_integration import extract_steamid64, import_steam_games

# Test Steam ID extraction
test_urls = [
    "https://steamcommunity.com/profiles/76561198000000000",
    "https://steamcommunity.com/id/customname",
    "76561198000000000"
]

print("Testing Steam ID extraction:")
for url in test_urls:
    steam_id = extract_steamid64(url)
    print(f"  {url} -> {steam_id}")

print("\nSteam integration is ready!")
print("\nTo test the full import, you need a valid Steam profile URL.")
print("The games will be:")
print("  1. Added to the games database (if not already present)")
print("  2. Added to the user's backlog")
print("  3. Sorted by most hours played")
print("  4. Include playtime data from Steam")
