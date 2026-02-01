import requests
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from dotenv import load_dotenv
from database import get_session, CompanyAnalysis
from llm_service import LLMService

# Load environment variables from .env
load_dotenv()

class AIScreener:
    def __init__(self):
        self.api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        # On ne lève plus d'erreur ici pour permettre l'utilisation hors-ligne (re-analyse DB)
        
        self.base_url = 'https://www.alphavantage.co/query'
        self.llm_service = LLMService()
        
        # Charger la liste du S&P 500 depuis le fichier JSON
        json_path = os.path.join(os.path.dirname(__file__), 'sp500.json')
        try:
            with open(json_path, 'r') as f:
                self.software_companies = json.load(f)
        except Exception as e:
            print(f"Erreur lors du chargement de sp500.json: {e}")
            self.software_companies = {}
    
    def get_company_overview(self, symbol: str) -> dict:
        """Récupère les données de base d'une entreprise via Alpha Vantage"""
        params = {
            'function': 'OVERVIEW',
            'symbol': symbol,
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params)
            data = response.json()
            if 'Symbol' in data:
                return data
            else:
                print(f"Erreur pour {symbol}: {data}")
                return {}
        except Exception as e:
            print(f"Erreur lors de la récupération des données pour {symbol}: {e}")
            return {}

    def get_stock_quote(self, symbol: str) -> float:
        """Récupère le prix actuel d'une action via Alpha Vantage GLOBAL_QUOTE"""
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol,
            'apikey': self.api_key
        }
        try:
            response = requests.get(self.base_url, params=params)
            data = response.json()
            if "Global Quote" in data:
                price_str = data["Global Quote"].get("05. price")
                return self._safe_float(price_str)
            return 0.0
        except Exception as e:
            print(f"Erreur lors de la récupération du prix pour {symbol}: {e}")
            return 0.0
    
    def _safe_float(self, value):
        if value is None or value == 'None' or value == '-':
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def update_database(self):
        """Met à jour la base de données : télécharge seulement si nécessaire"""
        session = get_session()
        
        # Charger le prompt actuel une fois
        current_prompt = self.llm_service.get_current_prompt()
        print("Using System Prompt for Analysis...")
        
        for i, (symbol, sector_desc) in enumerate(self.software_companies.items()):
            existing = session.query(CompanyAnalysis).filter_by(symbol=symbol).first()
            
            # Logique de mise à jour:
            # 1. Si pas de données, on fetch tout.
            # 2. Si données > 24h, on fetch tout.
            # 3. Si on demande explicitement un 're-run' (via un flag, à implémenter plus tard), sinon on update juste l'analyse si le prompt a changé
            
            should_fetch_api = True
            if existing and existing.last_updated:
                 last_updated = existing.last_updated.replace(tzinfo=None) if existing.last_updated else None
                 if last_updated and datetime.now() - last_updated < timedelta(hours=24):
                     should_fetch_api = False

            company_data = {}
            if should_fetch_api:
                print(f"Fetching API data for {symbol}...")
                company_data = self.get_company_overview(symbol)
                if not company_data:
                    print(f"Skipping {symbol} due to API error")
                    continue
                # Respecter le quota API
                print("Sleeping 12s for API limit...")
                time.sleep(12)
            else:
                # Si les données sont fraîches (<24h), on ne fait rien dans le cycle automatique
                # L'utilisateur peut forcer une ré-analyse via /api/reanalyze qui utilise reanalyze_existing_data
                print(f"Data fresh for {symbol}. Skipping API fetch.")
                continue

            # Si on est ici, c'est qu'on a fetched des nouvelles données API
            if company_data:
                # Fetch price separately since OVERVIEW doesn't have it
                print(f"Fetching Price for {symbol}...")
                current_price = self.get_stock_quote(symbol)
                time.sleep(12) # Wait for another API slot

                print(f"Analyzing {symbol} with LLM...")
                # Inject correct price into company_data for LLM
                company_data['Price'] = current_price
                llm_result = self.llm_service.analyze_company(company_data, current_prompt)
                
                if llm_result:
                    new_data = {
                        'symbol': symbol,
                        'company_name': company_data.get('Name', symbol),
                        'sector': sector_desc,
                        'current_price': current_price,
                        'market_cap': self._safe_float(company_data.get('MarketCapitalization')),
                        'pe_ratio': self._safe_float(company_data.get('PERatio')),
                        'roe': self._safe_float(company_data.get('ReturnOnEquityTTM')),
                        'eps_growth': self._safe_float(company_data.get('EPSGrowthPast5Years')),
                        'debt_to_equity': self._safe_float(company_data.get('DebtToEquityRatio')),
                        
                        'ai_impact_score': llm_result.get('score', 50),
                        'recommendation': llm_result.get('recommendation', 'NEUTRAL'),
                        'reasoning': llm_result.get('reasoning', 'Analysis failed'),
                        'analysis_json': llm_result
                    }
                    
                    if existing:
                        for key, value in new_data.items():
                            setattr(existing, key, value)
                    else:
                        new_record = CompanyAnalysis(**new_data)
                        session.add(new_record)
                    session.commit()
                    print(f"Updated {symbol} in DB.")

        session.close()
        print("Database update cycle complete.")

    def reanalyze_existing_data(self):
        """Ré-analyse toutes les entreprises en base avec le prompt actuel (sans fetch API)"""
        session = get_session()
        companies = session.query(CompanyAnalysis).all()
        
        current_prompt = self.llm_service.get_current_prompt()
        print(f"Re-analyzing {len(companies)} companies with updated prompt...")
        
        for i, company in enumerate(companies):
            # Reconstruire un objet pseudo-data pour l'LLM
            # Note: C'est une approximation car on n'a pas gardé tout le JSON raw d'Alpha Vantage
            # Mais on a les métriques clés stockées en colonnes.
            company_data = {
                'Symbol': company.symbol,
                'Name': company.company_name,
                'Sector': company.sector,
                # Description n'était pas stockée dans les colonnes principales, mais peut-être dans analysis_json ?
                # Pour l'instant on fait sans description ou on la récupère si possible.
                'Description': company.sector, # Fallback
                'Price': company.current_price,
                'PERatio': company.pe_ratio,
                'MarketCapitalization': company.market_cap,
                'ReturnOnEquityTTM': company.roe,
                'EPSGrowthPast5Years': company.eps_growth,
                'DebtToEquityRatio': company.debt_to_equity
            }
            
            # Essayer de récupérer la description depuis le json stocké si dispo
            if company.analysis_json and isinstance(company.analysis_json, dict):
                 # Ce dictionnaire contient le résultat de l'LLM précédent, pas les données brutes AV
                 pass

            print(f"[{i+1}/{len(companies)}] Re-analyzing {company.symbol} ({self.llm_service.provider})...")
            llm_result = self.llm_service.analyze_company(company_data, current_prompt)
            
            if llm_result and 'score' in llm_result:
                print(f"  ✅ SUCCESS: {company.symbol} | Score: {llm_result.get('score')} | Rec: {llm_result.get('recommendation')}")
                company.ai_impact_score = llm_result.get('score')
                company.recommendation = llm_result.get('recommendation')
                company.reasoning = llm_result.get('reasoning')
                company.analysis_json = llm_result
                
                # Commit immediately to database after each success
                session.commit()
                print(f"  💾 Saved {company.symbol} to database.")
            else:
                print(f"  ❌ FAILED: {company.symbol} - No valid result from LLM.")
            
            # Rate limiting
            time.sleep(1)
        
        session.close()
        print("Re-analysis cycle complete.")

def main():
    screener = AIScreener()
    screener.update_database()

if __name__ == "__main__":
    main()