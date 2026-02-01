import requests
import csv
import io
import os

def get_all_listings():
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    url = f'https://www.alphavantage.co/query?function=LISTING_STATUS&apikey={api_key}'
    
    print("Récupération de la liste complète des actions...")
    response = requests.get(url)
    
    if response.status_code == 200:
        csv_content = response.content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        all_symbols = list(csv_reader)
        us_stocks = [s for s in all_symbols if s['assetType'] == 'Stock' and s['exchange'] in ['NASDAQ', 'NYSE', 'AMEX']]
        
        print(f"Total symboles trouvés : {len(all_symbols)}")
        print(f"Actions US (NASDAQ, NYSE, AMEX) : {len(us_stocks)}")
        
        # Afficher un aperçu
        print("\nExemple de 5 symboles :")
        for s in us_stocks[:5]:
            print(s)
            
        return us_stocks
    else:
        print("Erreur lors de la récupération :", response.text)
        return []

if __name__ == "__main__":
    get_all_listings()
