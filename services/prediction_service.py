import logging
from typing import Dict, Any, Tuple
import joblib
from pathlib import Path
from utils import encode_features, get_shap_explanation

logger = logging.getLogger(__name__)

class PredictionService:
    """Service class for encapsulating ML model prediction logic."""
    
    def __init__(self, model_path: str):
        self.model = None
        self.load_model(model_path)

    def load_model(self, model_path: str):
        """Loads the serialized machine learning model."""
        path = Path(model_path)
        if path.exists():
            try:
                self.model = joblib.load(path)
                logger.info(f"Successfully loaded model from {model_path}")
            except Exception as e:
                logger.error(f"Failed to load model from {model_path}: {str(e)}")
        else:
            logger.warning(f"Model path {model_path} does not exist.")

    def get_prediction(self, features: Dict[str, Any]) -> Tuple[float, str, str, str]:
        """
        Runs the ML model and returns prediction details.
        
        Args:
            features (dict): Dictionary mapping of all expected ML input features.
            
        Returns:
            tuple: (severity_percent, severity_label, advice_text, shap_explanation)
            
        Raises:
            ValueError: If the underlying model has not been loaded.
        """
        if not self.model:
            raise ValueError("Model not loaded. Please train the model first.")
            
        encoded_features = encode_features(features)
        pred = self.model.predict(encoded_features)[0]
        # Clamp prediction percentage
        pred = float(max(0, min(100, pred)))
        
        try:
            shap_explanation = get_shap_explanation(encoded_features)
        except Exception as e:
            logger.error(f"SHAP explanation failed: {str(e)}")
            shap_explanation = "Explanation unavailable"
            
        if pred >= 85:
            label = 'High'
        elif pred >= 50:
            label = 'Medium'
        else:
            label = 'Low'

        speed = float(features.get('Speed', 50))
        recommended_speed = max(30, round(speed * (100 - pred) / 100))
        advice = f'Recommended safe speed: {recommended_speed} km/h. Keep safe distance and drive cautiously.'

        return pred, label, advice, shap_explanation
