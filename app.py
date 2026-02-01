from flask import Flask, jsonify, request, session, redirect, url_for
import os
import json
import threading
from functools import wraps
from werkzeug.security import check_password_hash
from database import get_session, CompanyAnalysis, User
from llm_service import LLMService
from logic import AIScreener

# Version mise à jour pour Railway deployment
APP_VERSION = "3.0.0"

app = Flask(__name__)
app.secret_key = "ai_quant_screener_secret_ultra_key" # In production, use env variable
llm_service = LLMService()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('landing'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def landing():
    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'landing.html')
    if not os.path.exists(filepath):
        # Fallback if I haven't created it yet
        return "Landing Page Coming Soon... Click <a href='/web'>here</a> to enter."
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/login', methods=['POST'])
def login():
    import time
    start_time = time.time()
    
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    db_session = get_session()
    session_time = time.time()
    print(f"DEBUG: Session created in {session_time - start_time:.4f}s")
    
    user = db_session.query(User).filter_by(email=email).first()
    query_time = time.time()
    print(f"DEBUG: User query executed in {query_time - session_time:.4f}s")
    
    if user and check_password_hash(user.password_hash, password):
        hash_time = time.time()
        print(f"DEBUG: Password hash checked in {hash_time - query_time:.4f}s")
        session['user_email'] = user.email
        db_session.close()
        return jsonify({"status": "success", "redirect": "/web"})
    
    hash_time = time.time()
    print(f"DEBUG: Password hash failed in {hash_time - query_time:.4f}s")
    db_session.close()
    return jsonify({"status": "error", "message": "Invalid email or password"}), 401

@app.route('/logout')
def logout():
    session.pop('user_email', None)
    return redirect(url_for('landing'))

@app.route('/web')
@login_required
def index():
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

@app.route('/api/stats')
def get_stats():
    """Endpoint pour récupérer les statistiques globales"""
    session = get_session()
    try:
        db_count = session.query(CompanyAnalysis).count()
        
        # Load SP500 count
        json_path = os.path.join(os.path.dirname(__file__), 'sp500.json')
        with open(json_path, 'r') as f:
            all_companies = json.load(f)
        
        return jsonify({
            "analyzed": db_count,
            "total": len(all_companies)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

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
