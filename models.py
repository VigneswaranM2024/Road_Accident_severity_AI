from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class PredictionLog(db.Model):
    __tablename__ = 'prediction_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Input Parameters
    speed = db.Column(db.Float, nullable=False)
    road_type = db.Column(db.String(50), nullable=False)
    surface = db.Column(db.String(50), nullable=False)
    time_of_day = db.Column(db.String(50), nullable=False)
    vehicle_type = db.Column(db.String(50), nullable=False)
    
    # Weather Context
    weather_mode = db.Column(db.String(20), default='manual')
    city = db.Column(db.String(100), nullable=True)
    detected_weather = db.Column(db.String(50), nullable=False)
    
    # Model Output
    severity_percent = db.Column(db.Float, nullable=False)
    severity_label = db.Column(db.String(20), nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() + 'Z',
            'speed': self.speed,
            'road_type': self.road_type,
            'surface': self.surface,
            'time_of_day': self.time_of_day,
            'vehicle_type': self.vehicle_type,
            'weather_mode': self.weather_mode,
            'city': self.city,
            'detected_weather': self.detected_weather,
            'severity_percent': self.severity_percent,
            'severity_label': self.severity_label
        }
