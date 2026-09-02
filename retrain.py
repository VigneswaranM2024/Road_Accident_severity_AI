import os
from pathlib import Path
import pandas as pd
import joblib
from sqlalchemy import create_engine
from train_model import X, y, scaler, encoders, model, explainer_model, DATA_PATH, MODEL_DIR
import numpy as np

ROOT = Path(__file__).parent
DB_PATH = ROOT / 'data' / 'predictions.db'
ENGINE_URL = f"sqlite:///{DB_PATH}"

def retrain_pipeline():
    print("Initiating automated retraining pipeline...")
    
    # Check if database exists
    if not DB_PATH.exists():
        print("Database not found, no new predictions to retrain on.")
        return

    # Load new predictions
    try:
        engine = create_engine(ENGINE_URL)
        new_df = pd.read_sql_table('prediction_logs', con=engine)
    except ValueError:
        print("Prediction logs table not found.")
        return

    if len(new_df) < 50:
        print(f"Only {len(new_df)} new records found. Waiting for more data (min 50 required).")
        return

    print(f"Loaded {len(new_df)} new records for retraining.")

    # Load original dataset to combine (simulating a full retrain strategy)
    orig_df = pd.read_csv(DATA_PATH)
    
    # Process new records to match expected structure
    # We map back `detected_weather` -> `Weather` etc.
    new_df = new_df.rename(columns={
        'detected_weather': 'Weather',
        'road_type': 'Road_Type',
        'vehicle_type': 'Vehicle_Type',
        'time_of_day': 'Time_of_Day',
        'speed': 'Speed',
        'surface': 'Surface',
        'severity_percent': 'SeverityPercent'
    })
    
    combined_df = pd.concat([orig_df, new_df], ignore_index=True)
    print(f"Combined dataset size: {len(combined_df)}")

    # Preprocessing
    categorical_cols = ['Weather', 'Road_Type', 'Vehicle_Type', 'Time_of_Day', 'Surface']
    for col in categorical_cols:
        combined_df[col] = combined_df[col].fillna('Unknown')
        
    X_new = combined_df[['Weather','Road_Type','Vehicle_Type','Time_of_Day','Speed','Surface']]
    y_new = combined_df['SeverityPercent'].fillna(0).astype(float)

    # Use existing encoders to transform new data, to prevent mismatch
    # If a new category appears, we might need logic to handle it, but for now we ignore errors
    # A robust system would use fit_transform and save new encoders.
    for col in categorical_cols:
        le = encoders[col]
        # handle unseen labels
        valid_mask = X_new[col].isin(le.classes_)
        X_new.loc[~valid_mask, col] = 'Unknown'
        # if 'Unknown' not in classes_, we have to append it or use a default class
        if 'Unknown' not in le.classes_:
            le.classes_ = np.append(le.classes_, 'Unknown')
        
        X_new.loc[:, col] = le.transform(X_new[col])
        
    # Scale Speed
    X_new['Speed'] = scaler.fit_transform(X_new[['Speed']])
    
    # Retrain
    print("Refitting ensemble model...")
    model.fit(X_new, y_new)
    
    # Refit explainer
    print("Refitting explainer model...")
    explainer_model.fit(X_new, y_new)

    # Save
    joblib.dump(model, MODEL_DIR / 'model.pkl')
    joblib.dump(explainer_model, MODEL_DIR / 'explainer_model.joblib')
    joblib.dump(scaler, MODEL_DIR / 'scaler.joblib')
    # Save encoders in case classes_ was updated
    joblib.dump(encoders, MODEL_DIR / 'encoders.joblib')

    print("Retraining completed. New artifacts saved.")

if __name__ == '__main__':
    retrain_pipeline()
