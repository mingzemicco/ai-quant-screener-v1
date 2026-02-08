"""
Module de prédiction EUR/USD basé sur les futures et le carry
"""
import os
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score
import warnings
warnings.filterwarnings('ignore')

class EurUsdPredictor:
    def __init__(self):
        self.api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        if not self.api_key:
            raise ValueError("La variable d'environnement ALPHA_VANTAGE_API_KEY n'est pas définie")
        self.data = None
        self.model = None
        self.train_data = None
        self.test_data = None
        
    def get_eurusd_futures_data(self):
        """
        Récupère les données futures EUR/USD via Alpha Vantage
        """
        print("Récupération des données EUR/USD futures...")
        
        # Pour l'instant, nous utiliserons les données FX disponibles
        # Le symbole pour EUR/USD sur Alpha Vantage est 'EURUSD'
        url = f'https://www.alphavantage.co/query'
        params = {
            'function': 'FX_DAILY',
            'from_symbol': 'EUR',
            'to_symbol': 'USD',
            'apikey': self.api_key,
            'outputsize': 'full'  # Pour obtenir les données historiques complètes
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            if 'Error Message' in data:
                print(f"Erreur: {data['Error Message']}")
                return None
            
            if 'Note' in data:
                print(f"Note: {data['Note']}")
                return None
                
            if 'Time Series FX (Daily)' not in data:
                print("Aucune série temporelle trouvée")
                print(f"Clés disponibles: {list(data.keys())}")
                return None
            
            # Convertir les données en DataFrame
            ts_data = data['Time Series FX (Daily)']
            df = pd.DataFrame(ts_data).T
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            
            # Renommer les colonnes
            df.columns = ['open', 'high', 'low', 'close', 'adjusted_close']
            df = df.astype(float)
            
            # Calculer les prix forward en incluant le carry (approximation)
            # Pour le carry, nous allons simuler en utilisant la différence de taux d'intérêt
            # Nous utiliserons les taux de change pour simuler le carry
            df['return'] = df['close'].pct_change()
            df['volatility'] = df['return'].rolling(window=20).std()
            
            # Créer des features techniques
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()
            df['rsi'] = self.calculate_rsi(df['close'])
            df['macd'], df['macd_signal'] = self.calculate_macd(df['close'])
            
            # Calculer une approximation du carry (différence de taux)
            # Pour simuler, nous allons créer une colonne carry basée sur la volatilité et les tendances
            df['carry_approx'] = df['close'].pct_change().rolling(window=5).mean() * 12  # Annualisé
            
            # Sélectionner les données à partir de 2010
            df = df[df.index.year >= 2010]
            
            print(f"Données récupérées: {len(df)} observations de {df.index.min()} à {df.index.max()}")
            self.data = df
            return df
            
        except Exception as e:
            print(f"Erreur lors de la récupération des données: {e}")
            return None
    
    def calculate_rsi(self, prices, period=14):
        """Calculer le RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """Calculer le MACD"""
        exp1 = prices.ewm(span=fast, adjust=False).mean()
        exp2 = prices.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        macd_signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd, macd_signal_line
    
    def identify_regimes(self, df, bull_threshold=0.02, bear_threshold=-0.02, volatility_threshold=None):
        """
        Identifier les régimes de marché (bull/bear) selon les paramètres définis
        """
        if volatility_threshold is None:
            volatility_threshold = df['volatility'].median()
        
        # Créer des signaux de régime
        df['regime'] = 'neutral'
        
        # Bull regime: hausse significative et volatilité relativement faible
        bull_condition = (df['return'] > bull_threshold) & (df['volatility'] <= volatility_threshold)
        df.loc[bull_condition, 'regime'] = 'bull'
        
        # Bear regime: baisse significative et volatilité relativement faible
        bear_condition = (df['return'] < bear_threshold) & (df['volatility'] <= volatility_threshold)
        df.loc[bear_condition, 'regime'] = 'bear'
        
        # High volatility regime
        high_vol_condition = df['volatility'] > volatility_threshold
        df.loc[high_vol_condition, 'regime'] = 'volatile'
        
        return df
    
    def prepare_features(self, df, regime_bull_threshold=0.02, regime_bear_threshold=-0.02, regime_volatility_threshold=None):
        """
        Préparer les features pour le modèle ML
        """
        df = df.copy()
        
        if regime_volatility_threshold is None:
            regime_volatility_threshold = df['volatility'].median()
        
        # Identifier les régimes
        df = self.identify_regimes(df, regime_bull_threshold, regime_bear_threshold, regime_volatility_threshold)
        
        # Créer des features pour le modèle
        df['price_change'] = df['close'].pct_change()
        df['price_change_lag1'] = df['price_change'].shift(1)
        df['price_change_lag2'] = df['price_change'].shift(2)
        df['volatility_lag1'] = df['volatility'].shift(1)
        df['rsi_lag1'] = df['rsi'].shift(1)
        df['macd_lag1'] = df['macd'].shift(1)
        df['carry_lag1'] = df['carry_approx'].shift(1)
        
        # Target: mouvement directionnel suivant
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)  # 1 si haussier, 0 si baissier
        
        # Sélectionner les lignes avec des valeurs valides
        feature_columns = [
            'price_change_lag1', 'price_change_lag2', 'volatility_lag1', 
            'rsi_lag1', 'macd_lag1', 'carry_lag1', 'sma_20', 'sma_50'
        ]
        
        # S'assurer que toutes les colonnes de features existent
        for col in feature_columns:
            if col not in df.columns:
                df[col] = 0  # Valeur par défaut si la colonne n'existe pas
        
        # Filtrer les lignes avec des NaN
        df = df.dropna(subset=feature_columns + ['target'])
        
        return df, feature_columns
    
    def train_model(self, regime_bull_threshold=0.02, regime_bear_threshold=-0.02, regime_volatility_threshold=None):
        """
        Entraîner le modèle LightGBM
        """
        if self.data is None:
            print("Aucune donnée disponible. Veuillez d'abord récupérer les données.")
            return
        
        # Préparer les données
        df, feature_cols = self.prepare_features(
            self.data, 
            regime_bull_threshold, 
            regime_bear_threshold, 
            regime_volatility_threshold
        )
        
        # Diviser les données en ensemble d'entraînement (jusqu'en 2020) et de test (après 2020)
        train_data = df[df.index.year <= 2020]
        test_data = df[df.index.year > 2020]
        
        print(f"Entraînement sur {len(train_data)} observations (jusqu'en 2020)")
        print(f"Test sur {len(test_data)} observations (après 2020)")
        
        X_train = train_data[feature_cols]
        y_train = train_data['target']
        
        X_test = test_data[feature_cols]
        y_test = test_data['target']
        
        # Entraîner le modèle LightGBM
        params = {
            'objective': 'binary',
            'metric': 'binary_logloss',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1
        }
        
        train_dataset = lgb.Dataset(X_train, label=y_train)
        test_dataset = lgb.Dataset(X_test, label=y_test, reference=train_dataset)
        
        self.model = lgb.train(
            params,
            train_dataset,
            valid_sets=[test_dataset],
            num_boost_round=100,
            callbacks=[lgb.early_stopping(stopping_rounds=10), lgb.log_evaluation(0)]
        )
        
        # Stocker les données d'entraînement et de test
        self.train_data = train_data
        self.test_data = test_data
        
        # Prédire sur l'ensemble de test
        y_pred = self.model.predict(X_test)
        y_pred_binary = (y_pred > 0.5).astype(int)
        
        # Calculer les métriques
        accuracy = accuracy_score(y_test, y_pred_binary)
        precision = precision_score(y_test, y_pred_binary, zero_division=0)
        recall = recall_score(y_test, y_pred_binary, zero_division=0)
        
        print(f"\nRésultats du modèle:")
        print(f"Précision: {accuracy:.3f}")
        print(f"Precision: {precision:.3f}")
        print(f"Recall: {recall:.3f}")
        
        return {
            'model': self.model,
            'train_data': train_data,
            'test_data': test_data,
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall
        }
    
    def plot_market_regimes(self, regime_bull_threshold=0.02, regime_bear_threshold=-0.02, regime_volatility_threshold=None):
        """
        Tracer les régimes de marché identifiés
        """
        if self.data is None:
            print("Aucune donnée disponible.")
            return
        
        df = self.data.copy()
        
        if regime_volatility_threshold is None:
            regime_volatility_threshold = df['volatility'].median()
        
        df = self.identify_regimes(df, regime_bull_threshold, regime_bear_threshold, regime_volatility_threshold)
        
        # Créer le graphique
        fig = make_subplots(rows=3, cols=1, 
                           subplot_titles=['Prix EUR/USD', 'Volatilité', 'Régimes de Marché'],
                           vertical_spacing=0.08,
                           row_heights=[0.4, 0.3, 0.3])
        
        # Prix EUR/USD
        fig.add_trace(go.Scatter(x=df.index, y=df['close'], 
                                 mode='lines', name='EUR/USD Close',
                                 line=dict(color='blue')), 
                      row=1, col=1)
        
        # Volatilité
        fig.add_trace(go.Scatter(x=df.index, y=df['volatility'], 
                                 mode='lines', name='Volatilité (20-jours)',
                                 line=dict(color='orange')), 
                      row=2, col=1)
        
        # Ligne horizontale pour le seuil de volatilité
        fig.add_hline(y=regime_volatility_threshold, line_dash="dash", 
                      line_color="red", row=2, col=1, 
                      annotation_text="Seuil Volatilité")
        
        # Régimes de marché
        # Créer des séries séparées pour chaque régime
        bull_mask = df['regime'] == 'bull'
        bear_mask = df['regime'] == 'bear'
        volatile_mask = df['regime'] == 'volatile'
        neutral_mask = df['regime'] == 'neutral'
        
        if bull_mask.any():
            fig.add_trace(go.Scatter(x=df[bull_mask].index, y=df[bull_mask]['close'],
                                     mode='markers', name='Régime Haussier',
                                     marker=dict(color='green', size=4)), 
                          row=1, col=1)
        
        if bear_mask.any():
            fig.add_trace(go.Scatter(x=df[bear_mask].index, y=df[bear_mask]['close'],
                                     mode='markers', name='Régime Baissier',
                                     marker=dict(color='red', size=4)), 
                          row=1, col=1)
        
        if volatile_mask.any():
            fig.add_trace(go.Scatter(x=df[volatile_mask].index, y=df[volatile_mask]['close'],
                                     mode='markers', name='Régime Volatile',
                                     marker=dict(color='yellow', size=4)), 
                          row=1, col=1)
        
        # Barres pour les régimes
        regime_colors = {'bull': 'green', 'bear': 'red', 'volatile': 'yellow', 'neutral': 'gray'}
        for regime, color in regime_colors.items():
            mask = df['regime'] == regime
            if mask.any():
                fig.add_trace(go.Bar(x=df[mask].index, y=[1]*mask.sum(), 
                                     name=f'Régime {regime}', 
                                     marker_color=color, 
                                     opacity=0.3,
                                     showlegend=False),
                              row=3, col=1)
        
        fig.update_layout(height=800, title_text="Analyse des Régimes de Marché EUR/USD",
                          xaxis_title="Date")
        
        fig.update_yaxes(title_text="EUR/USD", row=1, col=1)
        fig.update_yaxes(title_text="Volatilité", row=2, col=1)
        fig.update_yaxes(title_text="Régime", row=3, col=1)
        
        return fig
    
    def predict_next_movement(self):
        """
        Prédire le prochain mouvement de prix
        """
        if self.model is None:
            print("Le modèle n'est pas entraîné. Veuillez d'abord entraîner le modèle.")
            return None
        
        # Utiliser les dernières données pour prédire
        latest_data = self.test_data.iloc[-1:] if len(self.test_data) > 0 else self.train_data.iloc[-1:]
        feature_cols = [col for col in latest_data.columns if col not in ['target', 'regime']]
        
        X_latest = latest_data[feature_cols]
        prediction_proba = self.model.predict(X_latest)[0]
        prediction = int(prediction_proba > 0.5)
        
        return {
            'prediction': prediction,  # 1 pour haussier, 0 pour baissier
            'probability': prediction_proba,
            'direction': 'HAUSSIER' if prediction == 1 else 'BAISSIER'
        }

def main():
    predictor = EurUsdPredictor()
    
    # Récupérer les données
    data = predictor.get_eurusd_futures_data()
    
    if data is not None:
        print(f"Données chargées: {len(data)} observations")
        
        # Paramètres configurables pour les régimes
        bull_threshold = 0.001  # 0.1% de variation haussière pour bull regime
        bear_threshold = -0.001  # -0.1% de variation baissière pour bear regime
        volatility_threshold = None  # Utilisera la médiane par défaut
        
        # Tracer les régimes de marché
        fig = predictor.plot_market_regimes(bull_threshold, bear_threshold, volatility_threshold)
        fig.show()
        
        # Entraîner le modèle
        results = predictor.train_model(bull_threshold, bear_threshold, volatility_threshold)
        
        # Faire une prédiction
        prediction = predictor.predict_next_movement()
        if prediction:
            print(f"\nPrédiction du prochain mouvement: {prediction['direction']}")
            print(f"Probabilité: {prediction['probability']:.3f}")
    
    else:
        print("Impossible de récupérer les données.")

if __name__ == "__main__":
    main()