import os
import requests
from dotenv import load_dotenv

RIOT_API_BASE_URL = "https://americas.api.riotgames.com"

def get_puuid_from_riot_id(api_key: str, game_name: str, tag_line: str) -> str | None:
    """Looks up a PUUID using a Riot ID (game name + tag line)."""
    url = f"{RIOT_API_BASE_URL}/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    headers = {"X-Riot-Token": api_key}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        account_data = response.json()
        return account_data.get("puuid")
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        if e.response:
            print(f"Response content: {e.response.text}")
        return None

if __name__ == "__main__":
    load_dotenv()
    api_key = os.getenv("RIOT_API_KEY")
    
    if not api_key:
        print("Error: RIOT_API_KEY not found in .env file.")
    else:
        print("--- Riot PUUID Lookup Utility ---")
        game_name = input("Enter your Riot game name (the part before the #): ")
        tag_line = input("Enter your Riot tag line (the part after the #): ")
        
        if game_name and tag_line:
            puuid = get_puuid_from_riot_id(api_key, game_name, tag_line)
            if puuid:
                print(f"\\n[SUCCESS] Found PUUID: {puuid}")
                print("\\nPlease copy this PUUID and paste it into your .env file for the 'RIOT_PUUID' variable.")
            else:
                print("\\n[FAILURE] Could not retrieve the PUUID. Please check the game name, tag line, and API key.")
        else:
            print("Game name and tag line cannot be empty.") 