from __future__ import annotations

import argparse
import ast
import json
import shutil
import warnings
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

try:
    from xgboost import XGBRegressor

    XGBOOST_AVAILABLE = True
except ImportError:  # pragma: no cover - environment dependent
    XGBRegressor = None
    XGBOOST_AVAILABLE = False


warnings.filterwarnings("ignore")


@dataclass
class RetrainConfig:
    project_dir: Path
    app_path: Path
    artifacts_dir: Path
    archive_dir: Path
    production_model_path: Path
    production_metadata_path: Path
    as_of_date: str
    forecast_horizon: int = 60
    validation_ratio: float = 0.15
    test_ratio: float = 0.15
    random_state: int = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrain and redeploy the leave forecasting model.")
    parser.add_argument(
        "--as-of-date",
        help="Cutoff date for training data in YYYY-MM-DD format. Defaults to min(today, latest approved leave date).",
    )
    parser.add_argument(
        "--forecast-horizon",
        type=int,
        default=60,
        help="Number of forward days to save into metadata after retraining.",
    )
    return parser.parse_args()


def load_forecasting_namespace(app_path: Path) -> dict[str, object]:
    source = app_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(app_path))
    keep_assignments = {
        "DATE_COLUMNS",
        "DROP_COLUMNS",
        "TEXT_FILL_COLUMNS",
        "TARGET_COLUMN",
        "MASTER_FORECAST_BUFFER_DAYS",
    }
    keep_functions = {
        "get_project_paths",
        "slugify_label",
        "build_holiday_calendar",
        "bucket_holiday_name",
        "is_long_weekend",
        "add_calendar_features",
        "add_history_features",
        "clean_leave_data",
        "read_employee_master_sheet",
        "prepare_employee_master",
        "build_active_headcount_series",
        "expand_leave_records",
        "expand_leave_records_full",
        "clip_leave_records_to_as_of_date",
        "align_feature_columns",
        "ensure_model_ready_features",
        "safe_model_predict",
        "build_feature_dataset",
        "iterative_forecast",
        "weighted_absolute_percentage_error",
        "mean_absolute_percentage_error_safe",
        "symmetric_mean_absolute_percentage_error",
    }
    selected_nodes = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            selected_nodes.append(node)
        elif isinstance(node, ast.Assign):
            target_names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            if target_names & keep_assignments:
                selected_nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in keep_functions:
            selected_nodes.append(node)
    module = ast.Module(body=selected_nodes, type_ignores=[])
    namespace: dict[str, object] = {}
    exec(compile(module, str(app_path), "exec"), namespace, namespace)
    return namespace


def infer_default_as_of_date(data_path: Path) -> str:
    raw = pd.read_csv(data_path, low_memory=False, usecols=["Status", "To Date"])
    approved = raw[raw["Status"].astype(str).str.strip().eq("Approved")].copy()
    approved["To Date"] = pd.to_datetime(approved["To Date"], errors="coerce", dayfirst=True)
    max_data_date = approved["To Date"].max()
    if pd.isna(max_data_date):
        raise ValueError(f"No approved leave dates found in {data_path}.")
    today_ts = pd.Timestamp(date.today()).normalize()
    inferred = min(today_ts, max_data_date.normalize())
    return str(inferred.date())


def evaluate_predictions(y_true, y_pred, model_name: str, ns: dict[str, object]) -> dict[str, object]:
    return {
        "Model": model_name,
        "MAE": mean_absolute_error(y_true, y_pred),
        "RMSE": mean_squared_error(y_true, y_pred) ** 0.5,
        "MAPE": ns["mean_absolute_percentage_error_safe"](y_true, y_pred),
        "R2": r2_score(y_true, y_pred),
        "WAPE": ns["weighted_absolute_percentage_error"](y_true, y_pred),
        "SMAPE": ns["symmetric_mean_absolute_percentage_error"](y_true, y_pred),
    }


def build_candidate_models(random_state: int) -> dict[str, object]:
    models: dict[str, object] = {
        "RandomForest": RandomForestRegressor(
            n_estimators=500,
            max_depth=14,
            min_samples_leaf=4,
            min_samples_split=8,
            max_features="sqrt",
            bootstrap=True,
            random_state=random_state,
            n_jobs=1,
        ),
        "GradientBoosting": GradientBoostingRegressor(
            loss="huber",
            learning_rate=0.035,
            n_estimators=450,
            max_depth=3,
            min_samples_leaf=4,
            min_samples_split=8,
            subsample=0.85,
            max_features="sqrt",
            validation_fraction=0.1,
            n_iter_no_change=30,
            random_state=random_state,
        ),
    }
    if XGBOOST_AVAILABLE:
        models["XGBoost"] = XGBRegressor(
            objective="reg:squarederror",
            booster="gbtree",
            n_estimators=1200,
            max_depth=4,
            learning_rate=0.03,
            subsample=0.85,
            colsample_bytree=0.80,
            colsample_bylevel=0.80,
            reg_alpha=0.8,
            reg_lambda=3.0,
            min_child_weight=4,
            gamma=0.05,
            random_state=random_state,
            n_jobs=1,
            eval_metric="rmse",
            early_stopping_rounds=60,
        )
    return models


def build_sample_weights(frame: pd.DataFrame, target_col: str) -> np.ndarray:
    target = frame[target_col].astype(float)
    weights = np.ones(len(frame), dtype=float)
    if len(frame) == 0:
        return weights

    high_leave_threshold = float(target.quantile(0.85))
    peak_leave_threshold = float(target.quantile(0.95))

    weights += np.where(target >= high_leave_threshold, 0.60, 0.0)
    weights += np.where(target >= peak_leave_threshold, 0.90, 0.0)
    weights += frame.get("is_holiday", 0).astype(float).to_numpy() * 0.35
    weights += frame.get("is_long_weekend", 0).astype(float).to_numpy() * 0.25
    weights += frame.get("is_month_end", 0).astype(float).to_numpy() * 0.10
    return np.clip(weights, 1.0, 3.0)


def build_walk_forward_splits(frame: pd.DataFrame, feature_cols: list[str], target_col: str, min_train_rows: int = 365, n_splits: int = 3) -> list[dict[str, object]]:
    splits: list[dict[str, object]] = []
    if len(frame) < (min_train_rows + 60):
        return splits

    effective_splits = min(n_splits, max(1, (len(frame) - min_train_rows) // 45))
    validation_window = max(30, int(round(len(frame) * 0.10)))
    step_size = max(30, validation_window // 2)

    for split_idx in range(effective_splits):
        valid_end = len(frame) - ((effective_splits - split_idx - 1) * step_size)
        valid_start = max(min_train_rows, valid_end - validation_window)
        train_end = valid_start
        if train_end < min_train_rows or valid_end <= valid_start:
            continue
        split_train = frame.iloc[:train_end].copy()
        split_valid = frame.iloc[valid_start:valid_end].copy()
        splits.append(
            {
                "name": f"fold_{split_idx + 1}",
                "X_train": split_train[feature_cols],
                "y_train": split_train[target_col],
                "X_valid": split_valid[feature_cols],
                "y_valid": split_valid[target_col],
                "sample_weight_train": build_sample_weights(split_train, target_col),
                "sample_weight_valid": build_sample_weights(split_valid, target_col),
            }
        )
    return splits


def fit_model(model_name: str, model, X_fit, y_fit, X_eval=None, y_eval=None, sample_weight_fit=None, sample_weight_eval=None):
    fit_kwargs: dict[str, object] = {}
    if sample_weight_fit is not None:
        fit_kwargs["sample_weight"] = sample_weight_fit
    if model_name == "XGBoost" and X_eval is not None and y_eval is not None:
        fit_kwargs["eval_set"] = [(X_eval, y_eval)]
        if sample_weight_eval is not None:
            fit_kwargs["sample_weight_eval_set"] = [sample_weight_eval]
        fit_kwargs["verbose"] = False
    model.fit(X_fit, y_fit, **fit_kwargs)
    return model


def make_json_safe(value):
    if isinstance(value, dict):
        return {str(key): make_json_safe(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [make_json_safe(inner) for inner in value]
    if isinstance(value, tuple):
        return [make_json_safe(inner) for inner in value]
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def main() -> None:
    args = parse_args()
    project_dir = Path(__file__).resolve().parent
    app_path = project_dir / "streamlit_app.py"
    paths = {
        "data_path": project_dir / "Data" / "Combined_All_Leave_Data.csv",
        "artifacts_dir": project_dir / "artifacts",
        "archive_dir": project_dir / "artifacts" / "archive",
        "production_model_path": project_dir / "artifacts" / "leave_forecasting_model.pkl",
        "production_metadata_path": project_dir / "artifacts" / "leave_forecasting_metadata.pkl",
    }
    as_of_date = args.as_of_date or infer_default_as_of_date(paths["data_path"])
    config = RetrainConfig(
        project_dir=project_dir,
        app_path=app_path,
        artifacts_dir=paths["artifacts_dir"],
        archive_dir=paths["archive_dir"],
        production_model_path=paths["production_model_path"],
        production_metadata_path=paths["production_metadata_path"],
        as_of_date=as_of_date,
        forecast_horizon=max(int(args.forecast_horizon), 1),
    )

    config.artifacts_dir.mkdir(parents=True, exist_ok=True)
    config.archive_dir.mkdir(parents=True, exist_ok=True)

    ns = load_forecasting_namespace(config.app_path)
    build_feature_dataset = ns["build_feature_dataset"]
    iterative_forecast = ns["iterative_forecast"]
    target_col = ns["TARGET_COLUMN"]

    print("=" * 72)
    print("RETRAINING LEAVE FORECAST MODEL")
    print("=" * 72)
    print(f"As-of date: {config.as_of_date}")
    print(f"Forecast horizon: {config.forecast_horizon} days")
    print(f"XGBoost available: {XGBOOST_AVAILABLE}")

    dataset_bundle = build_feature_dataset(config.project_dir, as_of_date=config.as_of_date)
    model_df = dataset_bundle["model_df"].sort_values("Date").reset_index(drop=True)
    feature_columns = dataset_bundle["feature_columns"]

    n_rows = len(model_df)
    test_size = max(30, int(round(n_rows * config.test_ratio)))
    valid_size = max(30, int(round(n_rows * config.validation_ratio)))
    train_size = n_rows - valid_size - test_size
    if train_size <= 0:
        raise ValueError("Not enough rows to build train/validation/test splits.")

    train_df = model_df.iloc[:train_size].copy()
    valid_df = model_df.iloc[train_size : train_size + valid_size].copy()
    test_df = model_df.iloc[train_size + valid_size :].copy()

    X_train = train_df[feature_columns]
    y_train = train_df[target_col]
    X_valid = valid_df[feature_columns]
    y_valid = valid_df[target_col]
    X_test = test_df[feature_columns]
    y_test = test_df[target_col]

    sample_weight_train = build_sample_weights(train_df, target_col)
    sample_weight_valid = build_sample_weights(valid_df, target_col)
    walk_forward_splits = build_walk_forward_splits(train_df, feature_columns, target_col)

    print(
        f"Train/valid/test rows: {len(train_df)}/{len(valid_df)}/{len(test_df)} | "
        f"Date ranges: {train_df['Date'].min().date()} -> {test_df['Date'].max().date()}"
    )

    candidate_models = build_candidate_models(config.random_state)
    validation_records: list[dict[str, object]] = []
    naive_valid = np.clip(valid_df["leave_lag_1"].to_numpy(), 0, None)
    validation_records.append(evaluate_predictions(y_valid, naive_valid, "Naive Lag-1 Baseline", ns))

    for model_name, model in candidate_models.items():
        cv_scores: list[dict[str, object]] = []
        for fold in walk_forward_splits:
            fold_model = build_candidate_models(config.random_state)[model_name]
            fold_model = fit_model(
                model_name,
                fold_model,
                fold["X_train"],
                fold["y_train"],
                X_eval=fold["X_valid"],
                y_eval=fold["y_valid"],
                sample_weight_fit=fold["sample_weight_train"],
                sample_weight_eval=fold["sample_weight_valid"],
            )
            fold_predictions = np.clip(fold_model.predict(fold["X_valid"]), 0, None)
            cv_scores.append(evaluate_predictions(fold["y_valid"], fold_predictions, fold["name"], ns))

        fitted_model = fit_model(
            model_name,
            model,
            X_train,
            y_train,
            X_eval=X_valid,
            y_eval=y_valid,
            sample_weight_fit=sample_weight_train,
            sample_weight_eval=sample_weight_valid,
        )
        valid_predictions = np.clip(fitted_model.predict(X_valid), 0, None)
        valid_metrics = evaluate_predictions(y_valid, valid_predictions, model_name, ns)
        cv_wape = float(np.mean([score["WAPE"] for score in cv_scores])) if cv_scores else float(valid_metrics["WAPE"])
        cv_mae = float(np.mean([score["MAE"] for score in cv_scores])) if cv_scores else float(valid_metrics["MAE"])
        stability_penalty = abs(float(valid_metrics["WAPE"]) - cv_wape)
        ranking_score = (0.65 * cv_wape) + (0.25 * float(valid_metrics["WAPE"])) + (0.10 * stability_penalty)
        valid_metrics["CV_WAPE"] = cv_wape
        valid_metrics["CV_MAE"] = cv_mae
        valid_metrics["Stability_Penalty"] = stability_penalty
        valid_metrics["Ranking_Score"] = ranking_score
        validation_records.append(valid_metrics)

    validation_results = pd.DataFrame(validation_records)
    validation_results["CV_WAPE"] = validation_results.get("CV_WAPE", np.nan)
    validation_results["Ranking_Score"] = validation_results.get("Ranking_Score", np.nan)
    validation_results = validation_results.sort_values(["Ranking_Score", "WAPE", "MAE", "RMSE"], na_position="last").reset_index(drop=True)
    best_model_name = validation_results.loc[validation_results["Model"].ne("Naive Lag-1 Baseline"), "Model"].iloc[0]

    print("\nValidation ranking:")
    print(validation_results[["Model", "WAPE", "MAE", "RMSE", "CV_WAPE", "Ranking_Score"]].to_string(index=False))
    print(f"\nSelected model: {best_model_name}")

    best_model = build_candidate_models(config.random_state)[best_model_name]
    train_valid_df = pd.concat([train_df, valid_df], ignore_index=True).sort_values("Date").reset_index(drop=True)
    train_valid_weights = build_sample_weights(train_valid_df, target_col)

    best_model = fit_model(
        best_model_name,
        best_model,
        train_valid_df[feature_columns],
        train_valid_df[target_col],
        X_eval=X_test,
        y_eval=y_test,
        sample_weight_fit=train_valid_weights,
    )

    if best_model_name == "XGBoost" and hasattr(best_model, "best_iteration") and best_model.best_iteration is not None:
        best_iteration = int(best_model.best_iteration) + 1
        best_model = XGBRegressor(
            **{**best_model.get_params(), "n_estimators": best_iteration, "early_stopping_rounds": None}
        )
        best_model.fit(
            train_valid_df[feature_columns],
            train_valid_df[target_col],
            sample_weight=train_valid_weights,
            verbose=False,
        )
    else:
        best_iteration = None

    test_predictions = np.clip(best_model.predict(X_test), 0, None)
    test_metrics = pd.DataFrame([evaluate_predictions(y_test, test_predictions, best_model_name, ns)])
    test_comparison = pd.DataFrame(
        {
            "Date": test_df["Date"].to_numpy(),
            "Actual_Leave_Count": y_test.to_numpy(),
            "Predicted_Leave_Count": test_predictions,
        }
    )
    test_comparison["Residual"] = test_comparison["Actual_Leave_Count"] - test_comparison["Predicted_Leave_Count"]
    test_comparison["Absolute_Error"] = test_comparison["Residual"].abs()

    feature_importance_df = pd.DataFrame(columns=["feature", "importance"])
    if hasattr(best_model, "feature_importances_"):
        feature_importance_df = pd.DataFrame(
            {"feature": feature_columns, "importance": best_model.feature_importances_}
        ).sort_values("importance", ascending=False).reset_index(drop=True)

    prediction_interval = {
        "residual_p05": float(test_comparison["Residual"].quantile(0.05)),
        "residual_p95": float(test_comparison["Residual"].quantile(0.95)),
        "absolute_error_p90": float(test_comparison["Absolute_Error"].quantile(0.90)),
    }

    train_predictions = np.clip(best_model.predict(X_train), 0, None)
    valid_predictions = np.clip(best_model.predict(X_valid), 0, None)
    train_metrics_dict = evaluate_predictions(y_train, train_predictions, "Train", ns)
    valid_metrics_dict = evaluate_predictions(y_valid, valid_predictions, "Validation", ns)
    test_metrics_dict = evaluate_predictions(y_test, test_predictions, "Test", ns)

    model_balance = {
        "Training_WAPE": train_metrics_dict["WAPE"],
        "Validation_WAPE": valid_metrics_dict["WAPE"],
        "Test_WAPE": test_metrics_dict["WAPE"],
        "Generalization_Gap_WAPE": abs(valid_metrics_dict["WAPE"] - test_metrics_dict["WAPE"]),
        "Overfitting_Signal": valid_metrics_dict["WAPE"] - train_metrics_dict["WAPE"],
        "Training_MAE": train_metrics_dict["MAE"],
        "Validation_MAE": valid_metrics_dict["MAE"],
        "Test_MAE": test_metrics_dict["MAE"],
        "MAE_Gap": abs(valid_metrics_dict["MAE"] - test_metrics_dict["MAE"]),
        "Training_R2": train_metrics_dict["R2"],
        "Validation_R2": valid_metrics_dict["R2"],
        "Test_R2": test_metrics_dict["R2"],
        "Stability_Score": max(
            0.0,
            1.0 - (abs(valid_metrics_dict["WAPE"] - test_metrics_dict["WAPE"]) / (test_metrics_dict["WAPE"] + 0.001)),
        ),
    }

    timestamp = pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S")
    version_prefix = f"leave_forecasting_{best_model_name.lower()}_{timestamp}"
    versioned_model_path = config.artifacts_dir / f"{version_prefix}.pkl"
    versioned_metadata_path = config.artifacts_dir / f"{version_prefix}_metadata.pkl"
    versioned_metrics_path = config.artifacts_dir / f"{version_prefix}_test_metrics.csv"
    versioned_predictions_path = config.artifacts_dir / f"{version_prefix}_test_predictions.csv"
    versioned_importance_path = config.artifacts_dir / f"{version_prefix}_feature_importance.csv"
    versioned_card_path = config.artifacts_dir / f"{version_prefix}_model_card.json"
    forecast_output_path = config.artifacts_dir / f"leave_forecast_next_{config.forecast_horizon}days_{timestamp}.csv"

    if config.production_model_path.exists():
        shutil.copy2(
            config.production_model_path,
            config.archive_dir / f"{config.production_model_path.stem}_{timestamp}{config.production_model_path.suffix}",
        )
    if config.production_metadata_path.exists():
        shutil.copy2(
            config.production_metadata_path,
            config.archive_dir / f"{config.production_metadata_path.stem}_{timestamp}{config.production_metadata_path.suffix}",
        )

    dataset_bundle["model"] = best_model
    dataset_bundle["metadata"] = {}
    dataset_bundle["feature_columns"] = feature_columns
    future_frame = iterative_forecast(dataset_bundle, config.forecast_horizon).copy()
    future_frame["Predicted_Leave_Count"] = future_frame["Predicted_Leave_Count"].round().clip(lower=0).astype(int)
    future_frame["Day_of_Week"] = pd.to_datetime(future_frame["Date"]).dt.day_name()
    future_frame["Lower_Bound"] = np.maximum(
        future_frame["Predicted_Leave_Count"] - prediction_interval["absolute_error_p90"],
        0,
    ).round().astype(int)
    future_frame["Upper_Bound"] = (
        future_frame["Predicted_Leave_Count"] + prediction_interval["absolute_error_p90"]
    ).round().astype(int)

    metadata = {
        "best_model_name": best_model_name,
        "training_timestamp_utc": timestamp,
        "as_of_date": config.as_of_date,
        "training_start_date": str(train_valid_df["Date"].min().date()),
        "training_end_date": str(train_valid_df["Date"].max().date()),
        "test_start_date": str(test_df["Date"].min().date()),
        "test_end_date": str(test_df["Date"].max().date()),
        "feature_columns": feature_columns,
        "forecast_horizon": config.forecast_horizon,
        "current_live_headcount_from_master": dataset_bundle["current_live_headcount"],
        "validation_results": validation_results.to_dict(orient="records"),
        "test_metrics": test_metrics.to_dict(orient="records"),
        "prediction_interval": prediction_interval,
        "model_balance": model_balance,
        "best_iteration": best_iteration,
        "walk_forward_folds": len(walk_forward_splits),
        "training_sample_weight_max": float(train_valid_weights.max()) if len(train_valid_weights) else 1.0,
        "versioned_model_path": str(versioned_model_path),
        "versioned_metadata_path": str(versioned_metadata_path),
        "next_30_days_forecast": future_frame[
            ["Date", "Day_of_Week", "Predicted_Leave_Count", "Lower_Bound", "Upper_Bound"]
        ].assign(Date=lambda frame: pd.to_datetime(frame["Date"]).dt.strftime("%Y-%m-%d")).to_dict(orient="records"),
    }

    safe_metadata = make_json_safe(metadata)
    joblib.dump(best_model, versioned_model_path)
    joblib.dump(safe_metadata, versioned_metadata_path)
    test_metrics.to_csv(versioned_metrics_path, index=False)
    test_comparison.to_csv(versioned_predictions_path, index=False)
    feature_importance_df.to_csv(versioned_importance_path, index=False)
    future_frame.to_csv(forecast_output_path, index=False)
    with open(versioned_card_path, "w", encoding="utf-8") as handle:
        json.dump(safe_metadata, handle, ensure_ascii=True, indent=2)

    shutil.copy2(versioned_model_path, config.production_model_path)
    shutil.copy2(versioned_metadata_path, config.production_metadata_path)

    print("\nTest metrics:")
    print(test_metrics.to_string(index=False))
    print("\nModel balance:")
    print(pd.DataFrame([model_balance]).T.rename(columns={0: "Value"}).to_string())
    print("\nArtifacts updated:")
    print(f"- Production model: {config.production_model_path}")
    print(f"- Production metadata: {config.production_metadata_path}")
    print(f"- Versioned model: {versioned_model_path}")
    print(f"- Versioned metadata: {versioned_metadata_path}")
    print(f"- Test metrics: {versioned_metrics_path}")
    print(f"- Test predictions: {versioned_predictions_path}")
    print(f"- Feature importance: {versioned_importance_path}")
    print(f"- Forecast export: {forecast_output_path}")


if __name__ == "__main__":
    main()
