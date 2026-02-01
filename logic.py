import requests
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple

class AIScreener:
    def __init__(self):
        # Charger la clé API Alpha Vantage
        try:
            with open('../../credentials/alpha_vantage.json', 'r') as f:
                creds = json.load(f)
                self.api_key = creds['api_key']
        except FileNotFoundError:
            # Si le fichier n'existe pas, essayer d'autres sources
            self.api_key = os.getenv('ALPHA_VANTAGE_API_KEY', 'AAF5VV7X7707GCMP')
        
        self.base_url = 'https://www.alphavantage.co/query'
        self.software_companies = {
            'SALESFORCE': 'CRM',
            'ORACLE': 'ERP/Database',
            'ADOBE': 'Creative/Creative Cloud',
            'WORKDAY': 'HR Software',
            'SNOWFLAKE': 'Cloud Data Platform',
            'PALANTIR': 'Data Analytics',
            'COGNIZANT': 'IT Services',
            'ACCENTURE': 'Consulting/IT Services',
            'INTUIT': 'Accounting Software',
            'ANAPLAN': 'Business Planning'
        }
    
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
            
            # Vérifier si la requête a réussi
            if 'Symbol' in data:
                return data
            else:
                print(f"Erreur pour {symbol}: {data}")
                return {}
        except Exception as e:
            print(f"Erreur lors de la récupération des données pour {symbol}: {e}")
            return {}
    
    def calculate_ai_impact_score(self, company_data: dict) -> Tuple[float, dict]:
        """Calcule le score d'impact IA basé sur notre modèle d'analyse"""
        if not company_data:
            return 0.0, {"reasoning": "Aucune donnée disponible pour cette entreprise."}
        
        symbol = company_data.get('Symbol', 'UNKNOWN')
        
        # Extraire les données pertinentes
        pe_ratio = float(company_data.get('PERatio', 0) or 0)
        market_cap = float(company_data.get('MarketCapitalization', 0) or 0)
        roe = float(company_data.get('ReturnOnEquityTTM', 0) or 0)
        debt_to_equity = float(company_data.get('DebtToEquityRatio', 0) or 0)
        eps_growth = float(company_data.get('EPSGrowthPast5Years', 0) or 0)
        
        # Logique d'analyse
        score = 50  # Score de base
        reasoning = []
        
        # Analyse Short (risques)
        if pe_ratio > 50:
            score -= 15
            reasoning.append(f"Ratio P/E élevé ({pe_ratio:.2f}), valorisation potentiellement excessive")
        elif pe_ratio > 30:
            score -= 7
            reasoning.append(f"Ratio P/E élevé ({pe_ratio:.2f})")
        else:
            reasoning.append(f"Ratio P/E raisonnable ({pe_ratio:.2f})")
        
        # Secteur vulnérable à l'IA (HR, comptabilité, ERP traditionnels)
        sector = company_data.get('Sector', '').lower()
        if any(sector_keyword in sector for sector_keyword in ['human resources', 'accounting', 'erp']):
            score -= 10
            reasoning.append("Secteur potentiellement vulnérable à l'automatisation par l'IA")
        
        # Analyse Long (opportunités)
        if market_cap > 50000000000:  # Plus de 50 milliards
            score += 5
            reasoning.append("Grande capitalisation, ressources pour investir dans l'IA")
        
        if roe > 0.15:  # ROE > 15%
            score += 10
            reasoning.append(f"Bonne rentabilité (ROE: {roe:.2%})")
        elif roe > 0.10:
            score += 5
            reasoning.append(f"Rentabilité satisfaisante (ROE: {roe:.2%})")
        
        if eps_growth > 0.15:  # EPS Growth > 15%
            score += 10
            reasoning.append(f"Bonne croissance des bénéfices (EPS Growth: {eps_growth:.2%})")
        elif eps_growth > 0.10:
            score += 5
            reasoning.append(f"Croissance des bénéfices solide (EPS Growth: {eps_growth:.2%})")
        
        # Vérifier si l'entreprise est active dans l'IA
        description = company_data.get('Description', '').lower()
        if any(ai_keyword in description for ai_keyword in ['artificial intelligence', 'machine learning', 'ai ', 'ai,', 'ai.', 'ai-', 'deep learning', 'neural network']):
            score += 15
            reasoning.append("Actif dans l'IA/intelligence artificielle")
        else:
            reasoning.append("Moins d'activité apparente dans l'IA")
        
        # Ajustement pour la dette
        if debt_to_equity > 1.0:
            score -= 5
            reasoning.append(f"Niveau d'endettement élevé (D/E: {debt_to_equity:.2f})")
        
        # Normaliser le score entre 0 et 100
        score = max(0, min(100, score))
        
        return score, {
            "reasoning": "; ".join(reasoning),
            "metrics": {
                "P/E Ratio": pe_ratio,
                "Market Cap": market_cap,
                "ROE": roe,
                "EPS Growth": eps_growth,
                "Debt/Equity": debt_to_equity
            }
        }
    
    def screen_companies(self) -> List[Dict]:
        """Analyse toutes les entreprises du secteur logiciel"""
        import time
        results = []
        
        for i, (symbol, sector) in enumerate(self.software_companies.items()):
            print(f"Analyse de {symbol}...")
            company_data = self.get_company_overview(symbol)
            
            if company_data:
                score, analysis = self.calculate_ai_impact_score(company_data)
                
                results.append({
                    "symbol": symbol,
                    "company_name": company_data.get('Name', symbol),
                    "sector": sector,
                    "current_price": float(company_data.get('Price', 0) or 0),
                    "market_cap": float(company_data.get('MarketCapitalization', 0) or 0),
                    "ai_impact_score": round(score, 2),
                    "analysis": analysis
                })
            
            # Ajouter un délai de 5 secondes entre les requêtes pour éviter les limitations de débit
            if i < len(self.software_companies) - 1:  # Ne pas attendre après la dernière requête
                print(f"Attente de 5 secondes avant la prochaine requête...")
                time.sleep(5)
        
        # Trier par score d'impact IA (du plus haut au plus bas)
        results.sort(key=lambda x: x['ai_impact_score'], reverse=True)
        
        return results

def main():
    screener = AIScreener()
    results = screener.screen_companies()
    
    # Sauvegarder les résultats
    with open('screener_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("\nRésultats de l'analyse :")
    for result in results:
        print(f"{result['symbol']} ({result['company_name']}): Score IA = {result['ai_impact_score']}")
    
    return results

if __name__ == "__main__":
    main()