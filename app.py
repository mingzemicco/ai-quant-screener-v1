from flask import Flask, jsonify, request
import os
import threading
from database import get_session, CompanyAnalysis
from llm_service import LLMService
from logic import AIScreener

# Version mise à jour pour Railway deployment
APP_VERSION = "2.1.0"

app = Flask(__name__)
llm_service = LLMService()

@app.route('/')
def index():
    import os
    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/api/prompt', methods=['GET'])
def get_prompt():
    prompt = llm_service.get_current_prompt()
    return jsonify({"prompt": prompt})

@app.route('/api/prompt', methods=['POST'])
def update_prompt():
    data = request.json
    new_prompt = data.get('prompt')
    if new_prompt:
        llm_service.update_prompt(new_prompt)
        return jsonify({"status": "success"})
    return jsonify({"error": "No prompt provided"}), 400

@app.route('/api/reanalyze', methods=['POST'])
def trigger_reanalysis():
    def run_screen():
        screener = AIScreener()
        screener.reanalyze_existing_data()
    
    thread = threading.Thread(target=run_screen)
    thread.start()
    
    return jsonify({"status": "started", "message": "Re-analysis started in background."})

@app.route('/api/companies')
def get_companies():
    """Endpoint pour récupérer les données des entreprises depuis la base de données"""
    session = get_session()
    try:
        companies = session.query(CompanyAnalysis).all()
        results = []
        for c in companies:
            # Reconstruire le format attendu par le frontend
            results.append({
                "symbol": c.symbol,
                "company_name": c.company_name,
                "sector": c.sector,
                "current_price": c.current_price,
                "market_cap": c.market_cap,
                "ai_impact_score": c.ai_impact_score,
                "analysis": {
                    "reasoning": c.reasoning,
                    "metrics": {
                        "P/E Ratio": c.pe_ratio,
                        "Market Cap": c.market_cap,
                        "ROE": c.roe,
                        "EPS Growth": c.eps_growth,
                        "Debt/Equity": c.debt_to_equity
                    },
                    "recommendation": c.recommendation
                }
            })
        return jsonify(results)
    except Exception as e:
        print(f"Erreur DB: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@app.route('/api/run_analysis')
def run_analysis():
    """Endpoint pour déclencher une mise à jour complète (Data + AI)"""
    def run_full_update():
        screener = AIScreener()
        screener.update_database()
        
    thread = threading.Thread(target=run_full_update)
    thread.start()
    return jsonify({"status": "started", "message": "Full update (Data + AI) started in background."})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)
