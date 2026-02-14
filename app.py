from flask import Flask, jsonify, request, session, redirect, url_for, render_template_string
import os
import json
import threading
from functools import wraps
from werkzeug.security import check_password_hash
from database import get_session, CompanyAnalysis, User
from llm_service import LLMService
from logic import AIScreener
import markdown
import frontmatter
from datetime import datetime

# Version mise à jour pour Railway deployment
APP_VERSION = "3.1.0"

# Import pour la prédiction EUR/USD
try:
    from eurgbpredict import EurUsdPredictor
except ImportError:
    EurUsdPredictor = None
    print("Module eurgbpredict non disponible - veuillez installer les dépendances")

app = Flask(__name__)
app.secret_key = "ai_quant_screener_secret_ultra_key" # In production, use env variable
llm_service = LLMService()

# Blog content directory
BLOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'content', 'blog')

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

# --- BLOG ROUTES ---

@app.route('/blog')
def blog_index():
    posts = []
    if os.path.exists(BLOG_DIR):
        for filename in os.listdir(BLOG_DIR):
            if filename.endswith('.md'):
                filepath = os.path.join(BLOG_DIR, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    post = frontmatter.load(f)
                    
                    # Extract date from filename if not in frontmatter
                    # Format: YYYY-MM-DD-slug.md
                    slug = filename.replace('.md', '')
                    date_str = str(post.get('date', ''))
                    
                    if not date_str and len(filename) > 10:
                         try:
                             date_part = filename[:10]
                             datetime.strptime(date_part, '%Y-%m-%d')
                             date_str = date_part
                         except:
                             date_str = datetime.now().strftime('%Y-%m-%d')

                    posts.append({
                        'title': post.get('title', 'Untitled'),
                        'date': date_str,
                        'category': post.get('category', 'Analysis'),
                        'description': post.get('description', ''),
                        'tags': post.get('tags', []),
                        'slug': slug
                    })
    
    # Sort by date descending
    posts.sort(key=lambda x: x['date'], reverse=True)
    
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'blog.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        return render_template_string(f.read(), posts=posts)

@app.route('/blog/<path:slug>')
def blog_post(slug):
    # Security check to prevent directory traversal
    if '..' in slug or slug.startswith('/'):
        return "Invalid path", 400
        
    filename = f"{slug}.md"
    filepath = os.path.join(BLOG_DIR, filename)
    
    if not os.path.exists(filepath):
        # Try to find file that matches the slug (ignoring date prefix if user provided just slug)
        # But here we assume slug is the full filename without extension as generated in list
        return "Post not found", 404
        
    with open(filepath, 'r', encoding='utf-8') as f:
        post_obj = frontmatter.load(f)
        html_content = markdown.markdown(post_obj.content, extensions=['fenced_code', 'tables'])
        
        post_data = {
            'title': post_obj.get('title', 'Untitled'),
            'date': post_obj.get('date', datetime.now().strftime('%Y-%m-%d')),
            'author': post_obj.get('author', 'AI Quant'),
            'category': post_obj.get('category', 'Analysis'),
            'content': html_content,
            'tags': post_obj.get('tags', [])
        }
        
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'blog_post.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        return render_template_string(f.read(), post=post_data)

# --- END BLOG ROUTES ---

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
    html_content = \"\"\"
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>EUR/USD Prediction Dashboard - Professional Hedge Fund Grade</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
            .container { max-width: 1400px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .controls { margin: 20px 0; padding: 15px; background: #f9f9f9; border-radius: 5px; }
            .control-group { margin: 10px 0; }
            label { display: inline-block; width: 200px; }
            input { padding: 5px; margin: 5px; width: 100px; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin: 5px; }
            button:hover { background: #0056b3; }
            button:disabled { background: #cccccc; cursor: not-allowed; }
            .results { margin-top: 20px; }
            #chart { width: 100%; height: 600px; }
            .loading { display: none; text-align: center; padding: 20px; }
            .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #007bff; border-radius: 50%; width: 40px; height: 40px; animation: spin 2s linear infinite; margin: 0 auto; }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            .training-progress { margin: 10px 0; padding: 10px; background: #e7f3ff; border-radius: 4px; display: none; }
            .model-results { margin-top: 20px; padding: 15px; background: #f0f8ff; border-radius: 5px; display: none; }
            .interpretation { margin-top: 15px; padding: 10px; background: #fff8dc; border-left: 4px solid #ffa500; border-radius: 4px; }
            .risk-factors { margin-top: 10px; padding: 10px; background: #ffe6e6; border-left: 4px solid #ff0000; border-radius: 4px; }
            .recommendations { margin-top: 10px; padding: 10px; background: #e6ffe6; border-left: 4px solid #00aa00; border-radius: 4px; }
            .robustness { margin-top: 10px; padding: 10px; background: #f0f0ff; border-left: 4px solid #6666ff; border-radius: 4px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>EUR/USD Prediction Dashboard - Professional Grade</h1>
            <p>This dashboard predicts EUR/USD movements using futures data and carry factors. Professional-grade analysis for hedge fund applications.</p>
            
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
                <button id="trainBtn" onclick="trainModel()">Train Model</button>
                <button onclick="predictNext()">Predict Next Movement</button>
            </div>
            
            <div class="loading" id="loadingDiv">
                <div class="spinner"></div>
                <p id="loadingText">Initializing...</p>
            </div>
            
            <div class="training-progress" id="progressDiv">
                <p id="progressText">Training progress will appear here...</p>
            </div>
            
            <div class="results">
                <h3>Market Regime Visualization</h3>
                <div id="chart"></div>
                
                <div class="model-results" id="modelResults">
                    <h3>Model Performance Metrics</h3>
                    <div id="metricsDisplay"></div>
                    <div id="interpretationSection"></div>
                </div>
                
                <div id="predictionResult"></div>
            </div>
        </div>

        <script>
            let chartData = null;
            
            async function fetchEurUsdData() {
                showLoading(true, 'Fetching EUR/USD data...');
                
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
                    showLoading(false);
                } catch (error) {
                    console.error('Error fetching EUR/USD data:', error);
                    alert('Error fetching data: ' + error.message);
                    showLoading(false);
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
                
                // Disable button and show loading
                document.getElementById('trainBtn').disabled = true;
                showLoading(true, 'Starting model training...');
                showProgress(true, 'Initializing training pipeline...');
                
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
                        showLoading(false);
                        showProgress(false);
                        document.getElementById('trainBtn').disabled = false;
                        return;
                    }
                    
                    // Display detailed results
                    displayModelResults(result);
                    
                    showLoading(false);
                    showProgress(false);
                    document.getElementById('trainBtn').disabled = false;
                    
                } catch (error) {
                    console.error('Error training model:', error);
                    alert('Error training model: ' + error.message);
                    showLoading(false);
                    showProgress(false);
                    document.getElementById('trainBtn').disabled = false;
                }
            }
            
            function displayModelResults(result) {
                document.getElementById('modelResults').style.display = 'block';
                
                // Fonction utilitaire pour formater les nombres de manière sécurisée
                function safeToFixed(value, digits = 3) {
                    if (value === undefined || value === null) {
                        return 'N/A';
                    }
                    return Number(value).toFixed(digits);
                }
                
                // Fonction utilitaire pour gérer les objets potentiellement undefined
                function safeGet(obj, prop, defaultValue = '') {
                    if (obj && obj[prop] !== undefined) {
                        return obj[prop];
                    }
                    return defaultValue;
                }
                
                // Format metrics display
                const metricsHtml = `
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="border: 1px solid #ddd; padding: 8px;"><strong>Accuracy:</strong></td>
                            <td style="border: 1px solid #ddd; padding: 8px;">${safeToFixed(result.accuracy)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">Ratio de prédictions correctes</td>
                        </tr>
                        <tr>
                            <td style="border: 1px solid #ddd; padding: 8px;"><strong>Precision:</strong></td>
                            <td style="border: 1px solid #ddd; padding: 8px;">${safeToFixed(result.precision)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">Fiabilité des signaux haussiers</td>
                        </tr>
                        <tr>
                            <td style="border: 1px solid #ddd; padding: 8px;"><strong>Recall:</strong></td>
                            <td style="border: 1px solid #ddd; padding: 8px;">${safeToFixed(result.recall)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">Capacité à capturer les mouvements haussiers</td>
                        </tr>
                        <tr>
                            <td style="border: 1px solid #ddd; padding: 8px;"><strong>F1-Score:</strong></td>
                            <td style="border: 1px solid #ddd; padding: 8px;">${safeToFixed(result.f1_score)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">Équilibre entre précision et rappel</td>
                        </tr>
                        <tr>
                            <td style="border: 1px solid #ddd; padding: 8px;"><strong>AUC-ROC:</strong></td>
                            <td style="border: 1px solid #ddd; padding: 8px;">${safeToFixed(result.auc_roc)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">Capacité de discrimination</td>
                        </tr>
                    </table>
                `;
                
                document.getElementById('metricsDisplay').innerHTML = metricsHtml;
                
                // Display interpretation with safety checks
                let interpretationHtml = '';
                
                // Model quality and performance assessment
                const perfAssessment = safeGet(result.interpretation, 'performance_assessment', 'Performance assessment not available');
                interpretationHtml += `<div class="interpretation"><h4>Performance Assessment</h4><p>${perfAssessment}</p>`;
                
                // Risk factors
                const riskFactors = safeGet(result.interpretation, 'risk_factors', []);
                if (riskFactors && riskFactors.length > 0) {
                    interpretationHtml += `<div class="risk-factors"><h4>Risk Factors</h4><ul>`;
                    riskFactors.forEach(factor => {
                        interpretationHtml += `<li>${factor}</li>`;
                    });
                    interpretationHtml += `</ul></div>`;
                }
                
                // Recommendations
                const recommendations = safeGet(result.interpretation, 'recommendations', []);
                if (recommendations && recommendations.length > 0) {
                    interpretationHtml += `<div class="recommendations"><h4>Recommendations</h4><ul>`;
                    recommendations.forEach(rec => {
                        interpretationHtml += `<li>${rec}</li>`;
                    });
                    interpretationHtml += `</ul></div>`;
                }
                
                // Robustness indicators
                const robustnessIndicators = safeGet(result.interpretation, 'robustness_indicators', []);
                if (robustnessIndicators && robustnessIndicators.length > 0) {
                    interpretationHtml += `<div class="robustness"><h4>Robustness Indicators</h4><ul>`;
                    robustnessIndicators.forEach(indicator => {
                        interpretationHtml += `<li>${indicator}</li>`;
                    });
                    interpretationHtml += `</ul></div>`;
                }
                
                interpretationHtml += `</div>`;
                
                document.getElementById('interpretationSection').innerHTML = interpretationHtml;
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
            
            function showLoading(show, message = '') {
                const loadingDiv = document.getElementById('loadingDiv');
                const loadingText = document.getElementById('loadingText');
                
                if (show) {
                    loadingText.textContent = message || 'Processing...';
                    loadingDiv.style.display = 'block';
                } else {
                    loadingDiv.style.display = 'none';
                }
            }
            
            function showProgress(show, message = '') {
                const progressDiv = document.getElementById('progressDiv');
                const progressText = document.getElementById('progressText');
                
                if (show) {
                    progressText.textContent = message;
                    progressDiv.style.display = 'block';
                } else {
                    progressDiv.style.display = 'none';
                }
            }
            
            // Auto-verify deployment after 5 minutes
            setTimeout(async function() {
                try {
                    const response = await fetch('/api/verify_deployment');
                    const result = await response.json();
                    console.log('Deployment verification result:', result);
                } catch (error) {
                    console.error('Error verifying deployment:', error);
                }
            }, 300000); // 5 minutes = 300000 ms
        </script>
    </body>
    </html>
    \"\"\"
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
        
        # Stocker les données dans l'instance pour une utilisation ultérieure
        predictor.data = data
        
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
        # Forcer le rechargement des données avec les paramètres spécifiés
        results = predictor.train_model(bull_threshold, bear_threshold, vol_threshold, force_reload=True)
        
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

@app.route('/api/verify_deployment')
@login_required
def verify_deployment():
    """Endpoint pour vérifier le déploiement sur Railway"""
    try:
        import subprocess
        import sys
        
        # Récupérer l'URL du site courant
        from urllib.parse import urlparse
        host_url = request.host_url  # Cela donne l'URL complète avec http://
        
        # Pour un déploiement Railway, vérifier que le site répond
        import requests
        response = requests.get(host_url, timeout=10)
        
        return jsonify({
            "status": "success",
            "deployment_url": host_url,
            "status_code": response.status_code,
            "timestamp": datetime.now().isoformat(),
            "message": f"Déploiement vérifié avec succès - Status: {response.status_code}"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "message": "Erreur lors de la vérification du déploiement"
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)
