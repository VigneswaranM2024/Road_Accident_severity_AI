"""
Flask backend for AI-Based Road Accident Severity Prediction
Endpoints:
 - GET / -> index
 - POST /predict -> returns severity predictions
 - GET /detect-weather?city= -> attempts to detect weather using OpenWeather or Open-Meteo
 - GET /monthly-trends -> returns Jan-Jun counts
"""
import os
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file
import logging
from config import get_config
from services.weather_service import WeatherService
from services.prediction_service import PredictionService
import joblib
import csv
import datetime
import json
import traceback
import threading
from models import db, PredictionLog
from flask_socketio import SocketIO, emit

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import pyttsx3 for server-side voice (optional). If unavailable, voice functionality will be disabled.
voice_available = False
voice_engine = None
voice_lock = threading.Lock()
try:
    import pyttsx3
    try:
        voice_engine = pyttsx3.init()
        # set a pleasant, clear speaking rate and volume
        try:
            voice_engine.setProperty('rate', 160)
            voice_engine.setProperty('volume', 0.9)
        except Exception:
            pass
        voice_available = True
    except Exception:
        voice_available = False
except Exception:
    voice_available = False


config = get_config()
ROOT = Path(__file__).parent
MODEL_DIR = ROOT / 'model'
MODEL_PATH = MODEL_DIR / 'model.pkl'
PERF_PATH = MODEL_DIR / 'perf.json'
PRED_LOG = ROOT / 'predictions_log.csv'
DATA_PATH = ROOT / 'data' / 'accident_data.csv'

app = Flask(__name__)
app.config.from_object(config)

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")

with app.app_context():
    db.create_all()

# Initialize prediction service
prediction_service = PredictionService(str(MODEL_PATH))

# Load performance summary for dashboard
model_perf = {}
dt_model = None
rf_model = None
perf_summary = {}

if PERF_PATH.exists():
    try:
        with open(PERF_PATH, 'r') as f:
            model_perf = json.load(f)
    except Exception as e:
        logger.error(f"Error loading perf json: {e}")

# Load classifier artifacts for comparison/dashboard
DT_PATH = MODEL_DIR / 'decision_tree.joblib'
RF_PATH = MODEL_DIR / 'random_forest.joblib'
PERF_SUM_PATH = MODEL_DIR / 'perf_summary.json'
if DT_PATH.exists():
    try:
        dt_model = joblib.load(DT_PATH)
    except Exception:
        dt_model = None
if RF_PATH.exists():
    try:
        rf_model = joblib.load(RF_PATH)
    except Exception:
        rf_model = None
if PERF_SUM_PATH.exists():
    try:
        with open(PERF_SUM_PATH,'r') as f:
            perf_summary = json.load(f)
    except Exception:
        perf_summary = {}

@app.route('/')
def index():
    # read monthly sample data counts Jan-Jun
    months = ['Jan','Feb','Mar','Apr','May','Jun']
    counts = {m:0 for m in months}
    if DATA_PATH.exists():
        import pandas as pd
        df = pd.read_csv(DATA_PATH)
        for m in months:
            # simple count by Month column
            counts[m] = int(df[df['Month']==m].shape[0])
    return render_template('index.html', model_perf=model_perf, monthly=counts)


@app.route('/dashboard')
def dashboard():
    # Render the same index which contains the dashboard area; frontend will request /dashboard-data
    months = ['Jan','Feb','Mar','Apr','May','Jun']
    counts = {m:0 for m in months}
    if DATA_PATH.exists():
        import pandas as pd
        df = pd.read_csv(DATA_PATH)
        for m in months:
            counts[m] = int(df[df['Month']==m].shape[0])
    return render_template('index.html', model_perf=model_perf, monthly=counts)


def _speak_async(text):
    if not voice_available or voice_engine is None:
        return False
    def _worker(msg):
        try:
            with voice_lock:
                voice_engine.say(msg)
                voice_engine.runAndWait()
        except Exception:
            pass
    t = threading.Thread(target=_worker, args=(text,), daemon=True)
    t.start()
    return True


def speak_alert(message):
    """Public helper used to speak a short alert message in a background thread."""
    if not voice_available or voice_engine is None:
        return False
    def _run():
        try:
            with voice_lock:
                voice_engine.say(message)
                voice_engine.runAndWait()
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()
    return True

@app.route('/detect-weather')
def detect_weather():
    city = request.args.get('city')
    if not city:
        return jsonify({'status': 'error', 'message': 'city required', 'code': 400}), 400

    # Always use OpenWeather
    ow = WeatherService.fetch_openweather(city)
    if isinstance(ow, dict) and 'error' not in ow:
        return jsonify(ow)
    else:
        err_msg = ow.get('error', 'Weather fetch failed') if isinstance(ow, dict) else 'Weather fetch failed'
        return jsonify({'status': 'error', 'message': err_msg, 'code': 500}), 500

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()
        # expected fields: speed, road_type, surface, weather_mode, manual_weather, city_name, time_of_day, vehicle_type
        speed = float(data.get('speed', 50))
        road_type = data.get('road_type','City')
        surface = data.get('surface','Dry')
        time_of_day = data.get('time_of_day','Morning')
        vehicle_type = data.get('vehicle_type','Car')
        weather_mode = data.get('weather_mode','manual')
        manual_weather = data.get('manual_weather','Sunny')
        city = data.get('city_name','')

        detected_weather = manual_weather
        if weather_mode == 'auto' and city:
            detected_weather = WeatherService.get_weather_for_city(city, manual_weather)
            
        features = {
            'Weather': detected_weather,
            'Road_Type': road_type,
            'Vehicle_Type': vehicle_type,
            'Time_of_Day': time_of_day,
            'Speed': speed,
            'Surface': surface
        }

        try:
            pred, label, advice, shap_explanation = prediction_service.get_prediction(features)
        except Exception as e:
            logger.error(f"Prediction error: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e), 'code': 500}), 500

        # Save to database
        new_log = PredictionLog(
            speed=speed,
            road_type=road_type,
            surface=surface,
            time_of_day=time_of_day,
            vehicle_type=vehicle_type,
            weather_mode=weather_mode,
            city=city,
            detected_weather=detected_weather,
            severity_percent=pred,
            severity_label=label
        )
        db.session.add(new_log)
        db.session.commit()

        # Trigger Celery asynchronous retraining if criteria are met
        try:
            count = PredictionLog.query.count()
            if count > 0 and count % 50 == 0:
                from tasks import run_retrain
                run_retrain.delay()
                logger.info(f"Triggered background retraining at {count} records.")
        except Exception as e:
            logger.error(f"Failed to trigger retraining: {str(e)}")

        # Emit real-time update
        try:
            socketio.emit('new_prediction', new_log.to_dict())
        except Exception as e:
            logger.error(f"Socket emit error: {e}")

        res = {
            'severity_percent': pred,
            'severity_label': label,
            'advice_text': advice,
            'shap_explanation': shap_explanation,
            'detected_weather': detected_weather,
            'model_perf': model_perf,
            'voice_available': voice_available
        }
        # Prepare voice message (non-blocking)
        try:
            if label == 'High':
                msg = 'Warning! Dangerous conditions detected. Please slow down immediately.'
            elif label == 'Medium':
                msg = 'Drive carefully. Road might be slippery.'
            else:
                msg = 'All clear. Maintain safe speed.'
            # append weather detail
            if detected_weather:
                msg = f"{msg} Current weather: {detected_weather}."
            # Start async speak if available
            if voice_available:
                _speak_async(msg)
        except Exception:
            pass

        return jsonify(res)
    except Exception as e:
        logger.error(f"Error in /predict: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e), 'code': 500}), 500

@app.route('/monthly-trends')
def monthly_trends():
    months = ['Jan','Feb','Mar','Apr','May','Jun']
    counts = {m:0 for m in months}
    if DATA_PATH.exists():
        import pandas as pd
        df = pd.read_csv(DATA_PATH)
        for m in months:
            counts[m] = int(df[df['Month']==m].shape[0])
    return jsonify(counts)

@app.route('/metrics')
def metrics():
    """Prometheus compatible metrics endpoint."""
    try:
        count = PredictionLog.query.count()
        lines = [
            "# HELP road_accident_predictions_total Total predictions made",
            "# TYPE road_accident_predictions_total counter",
            f"road_accident_predictions_total {count}"
        ]
        return "\\n".join(lines), 200, {'Content-Type': 'text/plain; version=0.0.4'}
    except Exception as e:
        logger.error(f"Metrics generation failed: {e}")
        return "Internal Server Error", 500


@app.route('/dashboard-data')
def dashboard_data():
    # Return JSON for dashboard charts: speed_vs_severity, weather_vs_severity, model_perf_summary
    speed_buckets = [(0,30),(31,60),(61,90),(91,120),(121,1000)]
    bucket_labels = ['0-30','31-60','61-90','91-120','121+']
    sev_bands = ['Low','Medium','High']
    speed_vs_severity = {b: {s:0 for s in sev_bands} for b in bucket_labels}
    weather_vs_severity = {}

    # Prefer database, else fallback to predictions_log, else accident_data
    import pandas as pd
    db_has_data = False
    try:
        if PredictionLog.query.count() > 0:
            df = pd.DataFrame([l.to_dict() for l in PredictionLog.query.all()])
            db_has_data = True
    except:
        pass

    if db_has_data or PRED_LOG.exists():
        if not db_has_data:
            df = pd.read_csv(PRED_LOG)
        # Ensure column names consistency
        if 'severity_percent' in df.columns:
            df['severity_percent'] = pd.to_numeric(df['severity_percent'], errors='coerce').fillna(0)
        else:
            df['severity_percent'] = 0
        # Map to labels
        def map_sev(p):
            p = float(p)
            if p >= 85: return 'High'
            if p >= 50: return 'Medium'
            return 'Low'
        df['sev_label'] = df['severity_percent'].apply(map_sev)
        # Speed buckets
        for _, r in df.iterrows():
            sp = float(r.get('speed') or 0)
            sev = r.get('sev_label','Low')
            # find bucket
            for (lo,hi),lab in zip(speed_buckets, bucket_labels):
                if lo <= sp <= hi or (lab=='121+' and sp>120):
                    speed_vs_severity[lab][sev] += 1
                    break
            w = r.get('detected_weather') or r.get('weather') or 'Unknown'
            weather_vs_severity.setdefault(w, {s:0 for s in sev_bands})
            weather_vs_severity[w][sev] += 1
    elif DATA_PATH.exists():
        df = pd.read_csv(DATA_PATH)
        # assume SeverityPercent present in df
        df['SeverityPercent'] = pd.to_numeric(df.get('SeverityPercent', 0), errors='coerce').fillna(0)
        def map_sev2(p):
            p = float(p)
            if p >= 85: return 'High'
            if p >= 50: return 'Medium'
            return 'Low'
        for _, r in df.iterrows():
            sp = float(r.get('Speed') or 0)
            sev = map_sev2(r.get('SeverityPercent',0))
            for (lo,hi),lab in zip(speed_buckets, bucket_labels):
                if lo <= sp <= hi or (lab=='121+' and sp>120):
                    speed_vs_severity[lab][sev] += 1
                    break
            w = r.get('Weather') or 'Unknown'
            weather_vs_severity.setdefault(w, {s:0 for s in sev_bands})
            weather_vs_severity[w][sev] += 1

    result = {
        'speed_vs_severity': speed_vs_severity,
        'weather_vs_severity': weather_vs_severity,
        'model_perf_summary': perf_summary
    }
    return jsonify(result)

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)

