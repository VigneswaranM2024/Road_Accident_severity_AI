import os
from celery import Celery
from retrain import retrain_pipeline
import logging

logger = logging.getLogger(__name__)

# Configure Celery to use Redis as broker and backend
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)

@celery_app.task(bind=True)
def run_retrain(self):
    """
    Background Celery task to run the automated machine learning retraining pipeline.
    This prevents the main Flask thread from blocking during heavy computation.
    """
    logger.info("Executing background retraining task...")
    try:
        retrain_pipeline()
        logger.info("Background retraining completed successfully.")
        return "Success"
    except Exception as e:
        logger.error(f"Error during background retraining: {str(e)}", exc_info=True)
        # Re-raise to let Celery handle failure state
        raise
