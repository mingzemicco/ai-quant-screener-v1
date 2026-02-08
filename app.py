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

# Import pour la prédiction EUR/USD
try:
    from eurgbpredict import EurUsdPredictor
except ImportError:
    EurUsdPredictor = None
    print("Module eurgbpredict non disponible - veuillez installer les dépendances")

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

# Routes pour la prédiction EUR/USD
@app.route('/eurusd')
@login_required
def eurusd_page():
    """Page pour la prédiction EUR/USD"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>EUR/USD Prediction Dashboard</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .controls { margin: 20px 0; padding: 15px; background: #f9f9f9; border-radius: 5px; }
            .control-group { margin: 10px 0; }
            label { display: inline-block; width: 200px; }
            input { padding: 5px; margin: 5px; width: 100px; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin: 5px; }
            button:hover { background: #0056b3; }
            .results { margin-top: 20px; }
            #chart { width: 100%; height: 600px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>EUR/USD Prediction Dashboard</h1>
            <p>This dashboard predicts EUR/USD movements using futures data and carry factors.</p>
            
            <div class="controls">
                <h3>Market Regime Parameters</h3>
                <div class="control-group">
                    <label for="bullThreshold">Bull Threshold (%):</label>
                    <input type="number" id="bullThreshold" value="0.1" step="0.01" min="-10" max="10">
                </div>
                <div class="control-group">
                    <label for="bearThreshold">Bear Threshold (%):</label>
                    <input type="number" id="bearThreshold" value="-0.1" step="0.01" min="-10" max="10">
                </div>
                <div class="control-group">
                    <label for="volThreshold">Volatility Threshold:</label>
                    <input type="number" id="volThreshold" value="" placeholder="Auto calculated">
                </div>
                <button onclick="fetchEurUsdData()">Fetch & Analyze Data</button>
                <button onclick="trainModel()">Train Model</button>
                <button onclick="predictNext()">Predict Next Movement</button>
            </div>
            
            <div class="results">
                <h3>Market Regime Visualization</h3>
                <div id="chart"></div>
                <div id="predictionResult"></div>
            </div>
        </div>

        <script>
            let chartData = null;
            
            async function fetchEurUsdData() {
                const params = {
                    bull_threshold: parseFloat(document.getElementById('bullThreshold').value) / 100,
                    bear_threshold: parseFloat(document.getElementById('bearThreshold').value) / 100
                };
                
                if (document.getElementById('volThreshold').value) {
                    params.vol_threshold = parseFloat(document.getElementById('volThreshold').value);
                }
                
                const queryString = new URLSearchParams(params).toString();
                
                try {
                    const response = await fetch(`/api/eurusd/data?${queryString}`);
                    const data = await response.json();
                    
                    if (data.error) {
                        alert('Error: ' + data.error);
                        return;
                    }
                    
                    chartData = data;
                    plotChart(data);
                } catch (error) {
                    console.error('Error fetching EUR/USD data:', error);
                    alert('Error fetching data: ' + error.message);
                }
            }
            
            function plotChart(data) {
                // Format data for Plotly
                const trace1 = {
                    x: data.dates,
                    y: data.prices,
                    type: 'scatter',
                    mode: 'lines',
                    name: 'EUR/USD Price',
                    yaxis: 'y'
                };
                
                const layout = {
                    title: 'EUR/USD Market Regimes',
                    xaxis: { title: 'Date' },
                    yaxis: { title: 'Price', side: 'left' },
                    yaxis2: { title: 'Regime', side: 'right', overlaying: 'y' },
                    height: 600
                };
                
                Plotly.newPlot('chart', [trace1], layout);
            }
            
            async function trainModel() {
                if (!chartData) {
                    alert('Please fetch data first');
                    return;
                }
                
                try {
                    const response = await fetch('/api/eurusd/train', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            bull_threshold: parseFloat(document.getElementById('bullThreshold').value) / 100,
                            bear_threshold: parseFloat(document.getElementById('bearThreshold').value) / 100
                        })
                    });
                    const result = await response.json();
                    
                    if (result.error) {
                        alert('Training error: ' + result.error);
                        return;
                    }
                    
                    alert(`Model trained successfully!\\nAccuracy: ${result.accuracy.toFixed(3)}\\nPrecision: ${result.precision.toFixed(3)}\\nRecall: ${result.recall.toFixed(3)}`);
                } catch (error) {
                    console.error('Error training model:', error);
                    alert('Error training model: ' + error.message);
                }
            }
            
            async function predictNext() {
                try {
                    const response = await fetch('/api/eurusd/predict');
                    const result = await response.json();
                    
                    if (result.error) {
                        alert('Prediction error: ' + result.error);
                        return;
                    }
                    
                    document.getElementById('predictionResult').innerHTML = 
                        '<h3>Prediction Result</h3>' +
                        '<p><strong>Direction:</strong> ' + result.direction + '</p>' +
                        '<p><strong>Probability:</strong> ' + (result.probability * 100).toFixed(2) + '%</p>';
                } catch (error) {
                    console.error('Error making prediction:', error);
                    alert('Error making prediction: ' + error.message);
                }
            }
        </script>
    </body>
    </html>
    """
    return html_content

@app.route('/api/eurusd/data')
@login_required
def get_eurusd_data():
    """Endpoint pour récupérer les données EUR/USD et les régimes de marché"""
    if not EurUsdPredictor:
        return jsonify({"error": "EurUsdPredictor module not available"}), 500
    
    try:
        # Récupérer les paramètres de la requête
        bull_threshold = float(request.args.get('bull_threshold', 0.001))
        bear_threshold = float(request.args.get('bear_threshold', -0.001))
        vol_threshold = request.args.get('vol_threshold')
        if vol_threshold:
            vol_threshold = float(vol_threshold)
        
        predictor = EurUsdPredictor()
        data = predictor.get_eurusd_futures_data()
        
        if data is None:
            return jsonify({"error": "Could not fetch EUR/USD data"}), 500
        
        # Identifier les régimes
        data = predictor.identify_regimes(data, bull_threshold, bear_threshold, vol_threshold)
        
        # Retourner les données formatées
        result = {
            "dates": data.index.strftime('%Y-%m-%d').tolist(),
            "prices": data['close'].tolist(),
            "regimes": data['regime'].tolist(),
            "volatilities": data['volatility'].tolist()
        }
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/eurusd/train', methods=['POST'])
@login_required
def train_eurusd_model():
    """Endpoint pour entraîner le modèle de prédiction EUR/USD"""
    if not EurUsdPredictor:
        return jsonify({"error": "EurUsdPredictor module not available"}), 500
    
    try:
        data = request.json
        bull_threshold = data.get('bull_threshold', 0.001)
        bear_threshold = data.get('bear_threshold', -0.001)
        vol_threshold = data.get('vol_threshold')
        
        predictor = EurUsdPredictor()
        results = predictor.train_model(bull_threshold, bear_threshold, vol_threshold)
        
        return jsonify({
            "status": "success",
            "accuracy": results['accuracy'],
            "precision": results['precision'],
            "recall": results['recall']
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/eurusd/predict')
@login_required
def predict_eurusd():
    """Endpoint pour prédire le prochain mouvement EUR/USD"""
    if not EurUsdPredictor:
        return jsonify({"error": "EurUsdPredictor module not available"}), 500
    
    try:
        predictor = EurUsdPredictor()
        
        # On ne peut pas entraîner dans cet endpoint, donc on suppose que le modèle est déjà entraîné
        # dans un contexte réel, le modèle serait chargé depuis un fichier ou une base de données
        # Pour cette implémentation, on lance une analyse rapide
        data = predictor.get_eurusd_futures_data()
        if data is not None:
            # On entraîne rapidement le modèle
            results = predictor.train_model()
            prediction = predictor.predict_next_movement()
            return jsonify(prediction)
        else:
            return jsonify({"error": "Could not fetch data for prediction"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)
