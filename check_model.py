from pathlib import Path
import sys

import joblib


metadata_path = Path("artifacts") / "leave_forecasting_metadata.pkl"

if not metadata_path.exists():
	print(f"ERROR: metadata file not found at {metadata_path}")
	sys.exit(1)

try:
	metadata = joblib.load(metadata_path)
except Exception as exc:
	print(f"ERROR: failed to load metadata: {exc}")
	sys.exit(1)

if not isinstance(metadata, dict):
	print("ERROR: metadata is not a dictionary. Artifact may be corrupted.")
	sys.exit(1)

required_keys = ["best_model_name", "training_end_date", "test_metrics", "feature_columns"]
missing_keys = [key for key in required_keys if key not in metadata]

print("MODEL TRAINING SUMMARY")
print("=" * 70)
if missing_keys:
	print(f"WARNING: missing metadata keys: {missing_keys}")

print(f"Best Model: {metadata.get('best_model_name', 'n/a')}")
print(f"Training Period: {metadata.get('training_start_date', 'n/a')} -> {metadata.get('training_end_date', 'n/a')}")
print(f"Test Period: {metadata.get('test_start_date', 'n/a')} -> {metadata.get('test_end_date', 'n/a')}")
print(f"Features: {len(metadata.get('feature_columns', []))} engineered features")

test_metrics = metadata.get("test_metrics", [{}])
test_metrics_first = test_metrics[0] if test_metrics else {}
print(f"Test WAPE: {test_metrics_first.get('WAPE', 0):.2%}")

balance = metadata.get("model_balance", {})
print(f"Overfitting Signal: {balance.get('Overfitting_Signal', 0):.4f}")
print(f"Generalization Gap: {balance.get('Generalization_Gap_WAPE', 0):.4f}")
print(f"Stability Score: {balance.get('Stability_Score', 0):.3f}")
forecast_horizon = metadata.get("forecast_horizon", len(metadata.get("next_30_days_forecast", [])))
print(f"Next {forecast_horizon}-Day Forecast: generated ({len(metadata.get('next_30_days_forecast', []))} days)")
print("=" * 70)
