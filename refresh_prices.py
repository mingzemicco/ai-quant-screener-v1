from logic import AIScreener
from database import get_session, CompanyAnalysis
import time
import os
from dotenv import load_dotenv

load_dotenv()

def refresh_all_prices():
    screener = AIScreener()
    session = get_session()
    
    companies = session.query(CompanyAnalysis).all()
    print(f"Refraichissement des prix pour {len(companies)} entreprises...")
    
    for i, company in enumerate(companies):
        print(f"[{i+1}/{len(companies)}] Récupération du prix pour {company.symbol}...")
        price = screener.get_stock_quote(company.symbol)
        
        if price > 0:
            company.current_price = price
            session.commit()
            print(f"  ✅ Prix mis à jour : ${price}")
        else:
            print(f"  ❌ Impossible de récupérer le prix pour {company.symbol}")
            
        # Respecter le quota Alpha Vantage (5 requêtes par minute)
        # 60 / 5 = 12 secondes
        print("  Attente de 12s...")
        time.sleep(12)
        
    session.close()
    print("Mise à jour des prix terminée.")

if __name__ == "__main__":
    refresh_all_prices()
