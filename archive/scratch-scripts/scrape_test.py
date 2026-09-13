import requests
from bs4 import BeautifulSoup
import pandas as pd

# Try to scrape EuroLeague stats from RealGM with better headers
url = 'https://basketball.realgm.com/international/leagues/1/Euroleague/2025/Advanced_Stats'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.google.com/',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}
try:
    response = requests.get(url, headers=headers)
    print(f'Status: {response.status_code}')
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        tables = pd.read_html(response.text)
        print(f'Found {len(tables)} tables')
        if tables:
            print('First table columns:', tables[0].columns.tolist())
            print('First table shape:', tables[0].shape)
            print(tables[0].head())
    else:
        print(f'Failed to fetch: {response.status_code}')
        print(f'Response headers: {response.headers}')
except Exception as e:
    print(f'Error: {e}')
