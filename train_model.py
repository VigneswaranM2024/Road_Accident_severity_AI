"""
Train a RandomForestRegressor on /data/accident_data.csv and save artifacts to /model
Produces:
 - model/model.pkl
 - model/encoders.joblib
 - model/perf.json
 - static/images/confusion_matrix.png (derived from discretized labels)

Run: python train_model.py
"""
import os
import json
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, VotingRegressor
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error, confusion_matrix, accuracy_score
import joblib
import matplotlib.pyplot as plt

ROOT = Path(__file__).parent
DATA_PATH = ROOT / 'data' / 'accident_data.csv'
MODEL_DIR = ROOT / 'model'
MODEL_DIR.mkdir(exist_ok=True)
STATIC_IMG_DIR = ROOT / 'static' / 'images'
STATIC_IMG_DIR.mkdir(parents=True, exist_ok=True)

# Read sample data
print('Loading data from', DATA_PATH)
df = pd.read_csv(DATA_PATH)
print('Samples:', len(df))

# Simple preprocessing
categorical_cols = ['Weather', 'Road_Type', 'Vehicle_Type', 'Time_of_Day', 'Surface']
encoders = {}
for col in categorical_cols:
    le = LabelEncoder()
    df[col] = df[col].fillna('Unknown')
    df[col] = le.fit_transform(df[col])
    encoders[col] = le

# Target
y = df['SeverityPercent'].fillna(0).astype(float)
# Features
X = df[['Weather','Road_Type','Vehicle_Type','Time_of_Day','Speed','Surface']]

# Scale numeric
scaler = StandardScaler()
X['Speed'] = scaler.fit_transform(X[['Speed']])

# Train/test
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# --- Implement Ensemble Regressor
rf_base = RandomForestRegressor(n_estimators=100, random_state=42)
gb_base = GradientBoostingRegressor(n_estimators=100, random_state=42)
model = VotingRegressor(estimators=[('rf', rf_base), ('gb', gb_base)])
model.fit(X_train, y_train)

# For SHAP explanations reliably across different ensemble methods, we save the RF component or a separate explainer
explainer_model = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)
explainer_model.fit(X_train, y_train)

# Predict
y_pred = model.predict(X_test)

r2 = r2_score(y_test, y_pred)
mse = mean_squared_error(y_test, y_pred)
print(f'R2: {r2:.3f}, MSE: {mse:.3f}')

# For confusion matrix, discretize into Low/Medium/High using same thresholds
bins = [0,50,85,101]
labels = ['Low','Medium','High']
y_test_cat = pd.cut(y_test, bins=bins, labels=labels, right=False)
y_pred_cat = pd.cut(np.clip(y_pred,0,100), bins=bins, labels=labels, right=False)

acc = accuracy_score(y_test_cat, y_pred_cat)
cm = confusion_matrix(y_test_cat, y_pred_cat, labels=labels)

# Save confusion matrix image (regressor discretized)
fig, ax = plt.subplots(figsize=(4,3))
ax.imshow(cm, cmap='Blues')
ax.set_xticks(range(len(labels)))
ax.set_yticks(range(len(labels)))
ax.set_xticklabels(labels)
ax.set_yticklabels(labels)
ax.set_ylabel('True')
ax.set_xlabel('Predicted')
for i in range(cm.shape[0]):
    for j in range(cm.shape[1]):
        ax.text(j, i, cm[i, j], ha='center', va='center', color='black')
plt.title('Confusion Matrix (regressor discretized)')
plt.tight_layout()
plt.savefig(STATIC_IMG_DIR / 'confusion_matrix.png')
plt.close()

# Save regressor artifacts (preserve existing behavior)
joblib.dump(model, MODEL_DIR / 'model.pkl')
joblib.dump(encoders, MODEL_DIR / 'encoders.joblib')
joblib.dump(scaler, MODEL_DIR / 'scaler.joblib')
joblib.dump(explainer_model, MODEL_DIR / 'explainer_model.joblib')

perf = {
    'r2': float(r2),
    'mse': float(mse),
    'accuracy_cat': float(acc)
}
with open(MODEL_DIR / 'perf.json', 'w') as f:
    json.dump(perf, f, indent=2)

print('Regressor model and artifacts saved to', MODEL_DIR)
print('Confusion matrix image:', STATIC_IMG_DIR / 'confusion_matrix.png')

# --- Now train classification models for model comparison dashboard
print('Training classification models (Decision Tree and Random Forest)...')
# Prepare classification labels
y_class = pd.cut(df['SeverityPercent'].fillna(0).astype(float), bins=bins, labels=labels, right=False)

# Use same feature set X but rebuild/encode with encoders used earlier
X_cls = X.copy()

Xc_train, Xc_test, yc_train, yc_test = train_test_split(X_cls, y_class, test_size=0.2, random_state=42)

dt = DecisionTreeClassifier(random_state=42)
rf_clf = RandomForestClassifier(n_estimators=150, random_state=42)

dt.fit(Xc_train, yc_train)
rf_clf.fit(Xc_train, yc_train)

dt_pred = dt.predict(Xc_test)
rf_pred = rf_clf.predict(Xc_test)

dt_acc = accuracy_score(yc_test, dt_pred)
rf_acc = accuracy_score(yc_test, rf_pred)

dt_cm = confusion_matrix(yc_test, dt_pred, labels=labels)
rf_cm = confusion_matrix(yc_test, rf_pred, labels=labels)

# Save confusion matrices images
def save_cm_image(cm_array, labels, out_path, title='Confusion Matrix'):
    fig, ax = plt.subplots(figsize=(4,3))
    ax.imshow(cm_array, cmap='Blues')
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_yticklabels(labels)
    ax.set_ylabel('True')
    ax.set_xlabel('Predicted')
    for i in range(cm_array.shape[0]):
        for j in range(cm_array.shape[1]):
            ax.text(j, i, cm_array[i, j], ha='center', va='center', color='black')
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()

save_cm_image(dt_cm, labels, STATIC_IMG_DIR / 'confusion_matrix_dt.png', title='Decision Tree CM')
save_cm_image(rf_cm, labels, STATIC_IMG_DIR / 'confusion_matrix_rf.png', title='Random Forest CM')

# Save classification models
joblib.dump(dt, MODEL_DIR / 'decision_tree.joblib')
joblib.dump(rf_clf, MODEL_DIR / 'random_forest.joblib')

# Save perf summary json
perf_summary = {
    'decision_tree': {'accuracy': float(dt_acc), 'cm': 'static/images/confusion_matrix_dt.png'},
    'random_forest': {'accuracy': float(rf_acc), 'cm': 'static/images/confusion_matrix_rf.png'}
}
with open(MODEL_DIR / 'perf_summary.json', 'w') as f:
    json.dump(perf_summary, f, indent=2)

print('Classification models saved and perf_summary.json written')
