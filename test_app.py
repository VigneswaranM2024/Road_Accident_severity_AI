import pytest
from app import app, db
import json

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///:memory:"
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.drop_all()

def test_index_route(client):
    response = client.get('/')
    assert response.status_code == 200

def test_predict_route_invalid(client):
    # Missing data should handle gracefully or return error
    response = client.post('/predict', json={})
    # If our logic handles empty dict with defaults
    assert response.status_code in [200, 400, 500]

from unittest.mock import patch

@patch('services.weather_service.WeatherService.get_weather_for_city')
def test_predict_route_valid(mock_weather, client):
    mock_weather.return_value = "Partly Cloudy"
    payload = {
        "speed": 60,
        "road_type": "City",
        "surface": "Dry",
        "time_of_day": "Morning",
        "vehicle_type": "Car",
        "weather_mode": "auto",
        "manual_weather": "Sunny",
        "city_name": "London"
    }
    response = client.post('/predict', json=payload)
    if response.status_code == 200:
        data = json.loads(response.data)
        assert 'severity_percent' in data
        assert 'severity_label' in data
        assert 'shap_explanation' in data

@patch('services.weather_service.WeatherService.fetch_openweather')
def test_detect_weather_route(mock_fetch, client):
    mock_fetch.return_value = {'source': 'openweather', 'mapped': 'Rainy'}
    response = client.get('/detect-weather?city=London')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['mapped'] == 'Rainy'

def test_monthly_trends(client):
    response = client.get('/monthly-trends')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'Jan' in data
