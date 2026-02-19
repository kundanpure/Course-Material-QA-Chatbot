import requests
import time

github_url = "https://github.com/kundanpure"

# Create a session to maintain cookies
session = requests.Session()

# Add browser-like headers
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

for i in range(1, 21):
    try:
        # Clear cookies between requests to simulate new visitors
        session.cookies.clear()
        
        response = session.get(github_url, headers=headers)
        print(f"Visit {i}: Status {response.status_code}")
        
        # Wait 2-5 seconds between requests (randomize it)
        time.sleep(3)
    except KeyboardInterrupt:
        print("\nStopped by user")
        break
    except Exception as e:
        print(f"Error on visit {i}: {e}")