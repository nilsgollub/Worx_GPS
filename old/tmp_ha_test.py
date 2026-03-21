from web_ui.home_assistant_service import HomeAssistantService
import requests
import os
from dotenv import load_dotenv

def main():
    load_dotenv(override=True)
    ha = HomeAssistantService()
    
    print(f"URL: {ha.url}")
    print(f"Token (First 5): {ha.token[:5]}...")
    
    # 1. Versuche die Addon-Liste abzurufen
    r = requests.get(f"{ha.url.rstrip('/')}/api/hassio/addons", headers=ha.headers)
    print(f"\n--- ADDONS LIST (Code {r.status_code}) ---")
    if r.status_code == 200:
        data = r.json().get('data', {}).get('addons', [])
        for addon in data:
            print(f"- {addon.get('name')} (Slug: {addon.get('slug')})")
    else:
        print(r.text)

if __name__ == "__main__":
    main()
