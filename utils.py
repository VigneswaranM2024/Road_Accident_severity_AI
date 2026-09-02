"""
Utility functions for the Flask app:
- encode_features: turn input dict into array matching training
- fetch_openweather: call OpenWeather API
- fetch_open_meteo: geocode then call open-meteo
- map_open_meteo_code: map weathercode -> category
"""
import os
import requests
from pathlib import Path
import joblib
import numpy as np

ROOT = Path(__file__).parent
MODEL_DIR = ROOT / 'model'
ENCODERS_PATH = MODEL_DIR / 'encoders.joblib'
SCALER_PATH = MODEL_DIR / 'scaler.joblib'

# Load encoders/scaler if present
encoders = None
scaler = None
if ENCODERS_PATH.exists():
    encoders = joblib.load(ENCODERS_PATH)
if SCALER_PATH.exists():
    scaler = joblib.load(SCALER_PATH)

import shap
EXPLAINER_PATH = MODEL_DIR / 'explainer_model.joblib'
explainer_model = None
if EXPLAINER_PATH.exists():
    try:
        explainer_model = joblib.load(EXPLAINER_PATH)
    except:
        pass

def encode_features(d):
    """Encode input dict to numpy array in the order used for training.
    Expects keys: Weather, Road_Type, Vehicle_Type, Time_of_Day, Speed, Surface
    Uses saved encoders and scaler if available; otherwise uses naive mapping.
    """
    features = []
    # Copy to avoid mutation
    Weather = d.get('Weather', 'Sunny')
    Road_Type = d.get('Road_Type', 'City')
    Vehicle_Type = d.get('Vehicle_Type', 'Car')
    Time_of_Day = d.get('Time_of_Day', 'Morning')
    Speed = float(d.get('Speed', 50))
    Surface = d.get('Surface', 'Dry')

    if encoders:
        w = encoders['Weather'].transform([Weather])[0] if Weather in encoders['Weather'].classes_ else 0
        r = encoders['Road_Type'].transform([Road_Type])[0] if Road_Type in encoders['Road_Type'].classes_ else 0
        v = encoders['Vehicle_Type'].transform([Vehicle_Type])[0] if Vehicle_Type in encoders['Vehicle_Type'].classes_ else 0
        t = encoders['Time_of_Day'].transform([Time_of_Day])[0] if Time_of_Day in encoders['Time_of_Day'].classes_ else 0
        s = encoders['Surface'].transform([Surface])[0] if Surface in encoders['Surface'].classes_ else 0
    else:
        # fallback simple mapping
        mapping = {'Sunny':0,'Rainy':1,'Foggy':2,'Cloudy':3,'Thunderstorm':4}
        w = mapping.get(Weather, 0)
        rtmap = {'City':0,'Highway':1,'Village':2}
        r = rtmap.get(Road_Type,0)
        vmap = {'Car':0,'Bike':1,'Truck':2}
        v = vmap.get(Vehicle_Type,0)
        tmap = {'Morning':0,'Noon':1,'Evening':2,'Night':3}
        t = tmap.get(Time_of_Day,0)
        smap = {'Dry':0,'Wet':1,'Slippery':2}
        s = smap.get(Surface,0)

    # scale speed
    if scaler:
        sp = scaler.transform([[Speed]])[0][0]
    else:
        sp = (Speed - 50)/15.0

    features = [w,r,v,t,sp,s]
    return np.array(features).reshape(1,-1)

def get_shap_explanation(features_array):
    if not explainer_model:
        return "Explanation not available."
    try:
        explainer = shap.TreeExplainer(explainer_model)
        shap_values = explainer.shap_values(features_array)
        
        feature_names = ['Weather','Road_Type','Vehicle_Type','Time_of_Day','Speed','Surface']
        vals = shap_values[0]
        
        contributions = list(zip(feature_names, vals))
        contributions.sort(key=lambda x: abs(x[1]), reverse=True)
        
        primary = contributions[0]
        secondary = contributions[1]
        
        def format_contrib(name, val):
            impact = "increased" if val > 0 else "decreased"
            return f"{name} {impact} risk"

        explanation = f"Top risk factors: {format_contrib(primary[0], primary[1])} and {format_contrib(secondary[0], secondary[1])}."
        return explanation
    except Exception as e:
        return f"Error explaining: {str(e)}"

