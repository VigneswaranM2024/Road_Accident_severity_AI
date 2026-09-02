import requests
import logging
from typing import Dict, Any, Optional, Tuple
from config import get_config

logger = logging.getLogger(__name__)
config = get_config()

class WeatherService:
    """Service class to handle external geocoding and weather API calls."""
    
    API_KEY = config.OPENWEATHER_API_KEY

    @staticmethod
    def fetch_openweather(city: str) -> Dict[str, Any]:
        """Fetch current weather from OpenWeather.
        
        Args:
            city (str): Name of the city.
            
        Returns:
            dict: Parsed weather details or an error dictionary.
        """
        try:
            url = 'https://api.openweathermap.org/data/2.5/weather'
            params = {'q': city, 'appid': WeatherService.API_KEY, 'units': 'metric'}
            r = requests.get(url, params=params, timeout=8)
            j = r.json()
            logger.debug(f"OpenWeather response for {city}: {r.status_code}")
            
            if r.status_code == 200 and 'weather' in j:
                main = j['weather'][0].get('main', '')
                desc = j['weather'][0].get('description', '')
                temp = j.get('main', {}).get('temp')
                
                # Map to categories with finer cloud handling
                mapped = 'Sunny'
                m = (main or '').lower()
                d = (desc or '').lower()
                
                if 'rain' in m or 'drizzle' in m:
                    mapped = 'Rainy'
                elif 'clear' in m:
                    mapped = 'Sunny'
                elif 'cloud' in m:
                    if 'few' in d:
                        mapped = 'Partly Cloudy'
                    elif 'overcast' in d:
                        mapped = 'Overcast'
                    elif 'scattered' in d:
                        mapped = 'Scattered Clouds'
                    else:
                        mapped = 'Cloudy'
                elif any(x in m for x in ['fog', 'mist', 'haze']):
                    mapped = 'Foggy'
                elif 'thunder' in m:
                    mapped = 'Thunderstorm'
                elif 'snow' in m:
                    mapped = 'Snow'

                return {'source': 'openweather', 'main': main, 'description': desc, 'temp': temp, 'mapped': mapped}
            else:
                return {'error': j}
        except Exception as e:
            logger.error(f"Error fetching OpenWeather for {city}: {str(e)}")
            return {'error': str(e)}

    @staticmethod
    def geocode_open_meteo(city: str) -> Optional[Tuple[float, float]]:
        """Geocode a city name to coordinates using Open-Meteo."""
        try:
            url = 'https://geocoding-api.open-meteo.com/v1/search'
            params = {'name': city, 'count': 1}
            r = requests.get(url, params=params, timeout=6)
            r.raise_for_status()
            j = r.json()
            if 'results' in j and len(j['results']) > 0:
                return j['results'][0]['latitude'], j['results'][0]['longitude']
            return None
        except Exception as e:
            logger.error(f"Error geocoding {city} via Open-Meteo: {str(e)}")
            return None

    @staticmethod
    def map_open_meteo_code(code: int) -> str:
        """Map WMO weather codes to categorical string values."""
        if code is None:
            return 'Unknown'
        if code == 0:
            return 'Sunny'
        if code in [1, 2, 3]:
            return 'Cloudy'
        if code in [45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]:
            return 'Rainy'
        if code in [71, 73, 75, 77, 85, 86]:
            return 'Snow'
        if code in [95, 96, 99]:
            return 'Thunderstorm'
        # Implicitly catching custom fog implementations or falling back
        return 'Cloudy'

    @staticmethod
    def fetch_open_meteo_by_coords(lat: float, lon: float) -> Dict[str, Any]:
        """Fetch weather data from Open-Meteo using coordinates."""
        try:
            url = 'https://api.open-meteo.com/v1/forecast'
            params = {'latitude': lat, 'longitude': lon, 'current_weather': True}
            r = requests.get(url, params=params, timeout=6)
            r.raise_for_status()
            j = r.json()
            
            cw = j.get('current_weather', {})
            code = cw.get('weathercode', None)
            temp = cw.get('temperature', None)
            mapped = WeatherService.map_open_meteo_code(code)
            
            return {'source': 'open-meteo', 'code': code, 'temp': temp, 'mapped': mapped}
        except Exception as e:
            logger.error(f"Error fetching Open-Meteo weather for coords ({lat},{lon}): {str(e)}")
            return {'error': str(e)}

    @staticmethod
    def get_weather_for_city(city: str, fallback_manual_weather: str = "Sunny") -> str:
        """
        Orchestrate the weather fetch logic with a fallback.
        Attempts OpenWeather first, falls back to Open-Meteo, defaults to fallback_manual_weather.
        """
        detected_weather = fallback_manual_weather
        if not city:
            return detected_weather

        # Primary attempt: OpenWeather
        ow = WeatherService.fetch_openweather(city)
        if isinstance(ow, dict) and 'mapped' in ow:
            detected_weather = ow.get('mapped', fallback_manual_weather)
        elif isinstance(ow, dict) and 'error' in ow:
            # Fallback attempt: Open-Meteo via Geocoding
            logger.warning(f"OpenWeather failed for {city}, falling back to Open-Meteo.")
            coords = WeatherService.geocode_open_meteo(city)
            if coords:
                om = WeatherService.fetch_open_meteo_by_coords(*coords)
                if 'error' not in om:
                    detected_weather = om.get('mapped', fallback_manual_weather)
        else:
            # Handle string responses (legacy safety mechanism)
            if isinstance(ow, str):
                detected_weather = ow
                
        return detected_weather
