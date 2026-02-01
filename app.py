from flask import Flask, render_template_string, send_from_directory, jsonify
import json
import os

app = Flask(__name__)

# Charger les données simulées pour la démonstration
def get_mock_data():
    with open('screener_results.json', 'r', encoding='utf-8') as f:
        return json.load(f)

@app.route('/')
def index():
    with open('index.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/api/companies')
def get_companies():
    """Endpoint pour récupérer les données des entreprises analysées"""
    try:
        # Essayer d'abord les données réelles
        with open('screener_results.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        # Si les données réelles ne sont pas disponibles, utiliser les données simulées
        return jsonify([
            {
                "symbol": "SALESFORCE",
                "company_name": "Salesforce Inc.",
                "sector": "CRM",
                "current_price": 250.45,
                "market_cap": 230000000000,
                "ai_impact_score": 87.5,
                "analysis": {
                    "reasoning": "Actif dans l'IA avec Einstein AI; forte croissance des bénéfices (EPS Growth: 25%); bonne rentabilité (ROE: 18%); ratio P/E raisonnable (28.5); grand capitalisation permettant investissements IA",
                    "metrics": {
                        "P/E Ratio": 28.5,
                        "Market Cap": 230000000000,
                        "ROE": 0.18,
                        "EPS Growth": 0.25,
                        "Debt/Equity": 0.35
                    }
                }
            },
            {
                "symbol": "ADOBE",
                "company_name": "Adobe Inc.",
                "sector": "Creative Cloud",
                "current_price": 480.20,
                "market_cap": 220000000000,
                "ai_impact_score": 92.3,
                "analysis": {
                    "reasoning": "Leader dans l'intégration de l'IA dans Creative Cloud avec Firefly; excellente rentabilité (ROE: 22%); croissance soutenue (EPS Growth: 30%); possède des données massives servant de barrière à l'entrée; valorisation adéquate",
                    "metrics": {
                        "P/E Ratio": 32.1,
                        "Market Cap": 220000000000,
                        "ROE": 0.22,
                        "EPS Growth": 0.30,
                        "Debt/Equity": 0.15
                    }
                }
            },
            {
                "symbol": "ORACLE",
                "company_name": "Oracle Corporation",
                "sector": "ERP/Database",
                "current_price": 195.80,
                "market_cap": 280000000000,
                "ai_impact_score": 78.9,
                "analysis": {
                    "reasoning": "Investissements massifs dans l'IA et cloud; bases de données Oracle constituent une barrière à l'entrée; bonnes perspectives de croissance (EPS Growth: 18%); ROE solide (15%); secteur traditionnellement résistant aux disruptions",
                    "metrics": {
                        "P/E Ratio": 35.2,
                        "Market Cap": 280000000000,
                        "ROE": 0.15,
                        "EPS Growth": 0.18,
                        "Debt/Equity": 0.85
                    }
                }
            },
            {
                "symbol": "WORKDAY",
                "company_name": "Workday Inc.",
                "sector": "HR Software",
                "current_price": 310.60,
                "market_cap": 75000000000,
                "ai_impact_score": 75.4,
                "analysis": {
                    "reasoning": "Solution RH leader avec intégration IA croissante; bonnes perspectives dans le cloud RH; ROE solide (14%); mais secteur vulnérable à l'automatisation des tâches RH; valorisation élevée (P/E: 45.2)",
                    "metrics": {
                        "P/E Ratio": 45.2,
                        "Market Cap": 75000000000,
                        "ROE": 0.14,
                        "EPS Growth": 0.20,
                        "Debt/Equity": 0.10
                    }
                }
            },
            {
                "symbol": "SNOWFLAKE",
                "company_name": "Snowflake Inc.",
                "sector": "Cloud Data Platform",
                "current_price": 280.50,
                "market_cap": 85000000000,
                "ai_impact_score": 85.7,
                "analysis": {
                    "reasoning": "Plateforme de données cloud avec forte barrière à l'entrée; données constituent actif stratégique pour l'IA; forte croissance (EPS Growth: 35%); excellent positionnement pour l'ère de l'IA; mais valorisation élevée (P/E: 58.7)",
                    "metrics": {
                        "P/E Ratio": 58.7,
                        "Market Cap": 85000000000,
                        "ROE": 0.12,
                        "EPS Growth": 0.35,
                        "Debt/Equity": 0.05
                    }
                }
            },
            {
                "symbol": "PALANTIR",
                "company_name": "Palantir Technologies",
                "sector": "Data Analytics",
                "current_price": 18.90,
                "market_cap": 40000000000,
                "ai_impact_score": 80.2,
                "analysis": {
                    "reasoning": "Spécialiste de l'analyse de données pour gouvernement et entreprises; position unique dans l'analyse sémantique et IA; barrière à l'entrée élevée; mais valorisation incertaine; EPS Growth limité",
                    "metrics": {
                        "P/E Ratio": 0, # Pas de profit
                        "Market Cap": 40000000000,
                        "ROE": -0.05, # Perte
                        "EPS Growth": 0.05,
                        "Debt/Equity": 0.02
                    }
                }
            }
        ])

@app.route('/api/run_analysis')
def run_analysis():
    """Endpoint pour exécuter une nouvelle analyse"""
    # Pour l'instant, retourner un message d'information
    # L'analyse réelle nécessiterait la configuration de l'API Alpha Vantage
    return jsonify({"status": "info", "message": "L'analyse complète nécessite la configuration de l'API Alpha Vantage et la gestion des quotas API"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))