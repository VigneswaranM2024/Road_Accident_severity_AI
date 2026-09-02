import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration class with environment fallbacks."""
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "3aafe8c4e0b44cd0a75153905252210")
    
    # Database
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DEFAULT_DB_PATH = os.path.join(BASE_DIR, "data", "predictions.db")
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", f"sqlite:///{DEFAULT_DB_PATH}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Flask settings
    TESTING = False
    DEBUG = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "t")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

class TestConfig(Config):
    """Configuration for testing."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

def get_config():
    """Retrieve the appropriate configuration class."""
    if os.getenv("FLASK_ENV") == "testing":
        return TestConfig
    return Config
