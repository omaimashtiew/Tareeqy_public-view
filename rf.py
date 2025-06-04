# tareeqy/ai_prediction/train_xgboost_model.py

import os
import sys
import time
import json
import warnings
import pandas as pd
import numpy as np
from datetime import datetime
import mysql.connector
from sklearn.model_selection import train_test_split # No longer need RandomizedSearchCV here
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, median_absolute_error, r2_score
import joblib
# from scipy.stats import randint # No longer needed for this version

from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
import matplotlib.pyplot as plt
import seaborn as sns

# --- Configuration Import ---
try:
    from . import config as ai_config
    print("Loaded config via relative import.")
except ImportError:
    try:
        import config as ai_config
        print("Loaded config via direct import.")
    except ImportError:
        print("CRITICAL: Could not import ai_prediction.config. Using fallback.")
        class FallbackConfig: # Minimal fallback
            ARTIFACTS_DIR = 'ai_artifacts'
            MODEL_PATH = os.path.join(ARTIFACTS_DIR, 'wait_time_model.pkl')
            SCALER_PATH = os.path.join(ARTIFACTS_DIR, 'scaler.pkl')
            KMEANS_PATH = os.path.join(ARTIFACTS_DIR, 'kmeans_model.pkl')
            LE_STATUS_PATH = os.path.join(ARTIFACTS_DIR, 'le_status.pkl')
            LE_CITY_PATH = os.path.join(ARTIFACTS_DIR, 'le_city.pkl')
            LE_DAY_PART_PATH = os.path.join(ARTIFACTS_DIR, 'le_day_part.pkl')
            FEATURE_COLUMNS_PATH = os.path.join(ARTIFACTS_DIR, 'feature_columns.json')
            RUSH_HOURS_MORNING = (7, 9); RUSH_HOURS_EVENING = (16, 18)
            WAIT_TIME_DEFAULT_FILL = 10; WAIT_TIME_CLIP_LOWER = 5; WAIT_TIME_CLIP_UPPER = 120
            KMEANS_N_CLUSTERS = 3; APP_NAME = 'tareeqy'
        ai_config = FallbackConfig()

# --- Database Connection ---
DB_CONFIG = {
    "host": "yamabiko.proxy.rlwy.net", "port": 26213, "user": "root",
    "password": "sbKIFwBCaymbcggetPSaFpblUvThYNSX", "database": "railway",
    "charset": 'utf8mb4', "connect_timeout": 10
}
def get_db_connection(max_retries=3): # (Same as before)
    for attempt in range(max_retries):
        try: return mysql.connector.connect(**DB_CONFIG)
        except Exception as e:
            print(f"DB Connection attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1: raise e; time.sleep(2)

DATA_CACHE_FILE = os.path.join(ai_config.ARTIFACTS_DIR, 'training_data_cache.pkl')
def fetch_data(use_cache=True): # (Same as before)
    if use_cache and os.path.exists(DATA_CACHE_FILE):
        try:
            print(f"Loading data from cache: {DATA_CACHE_FILE}")
            df_cache = joblib.load(DATA_CACHE_FILE)
            if isinstance(df_cache,dict) and 'fences' in df_cache and 'status' in df_cache:
                print("Cache data loaded successfully."); return df_cache['fences'], df_cache['status']
            else: print("Cache structure invalid. Fetching fresh data.")
        except Exception as e: print(f"Error loading cache: {e}. Fetching fresh data.")
    print("Fetching data from database...")
    conn = None
    try:
        conn = get_db_connection()
        if not conn: print("Failed to get DB connection."); return pd.DataFrame(), pd.DataFrame()
        app_name = getattr(ai_config, 'APP_NAME', 'tareeqy')
        fences_df = pd.read_sql(f"SELECT id, name, latitude, longitude, city FROM {app_name}_fence", conn)
        status_df = pd.read_sql(f"SELECT id AS status_record_id, fence_id, status, message_time FROM {app_name}_fencestatus WHERE message_time >= NOW() - INTERVAL 6 MONTH", conn)
        print(f"Fetched {len(fences_df)} fences and {len(status_df)} status records.")
        os.makedirs(ai_config.ARTIFACTS_DIR, exist_ok=True)
        joblib.dump({'fences': fences_df, 'status': status_df}, DATA_CACHE_FILE)
        print(f"Data cached to {DATA_CACHE_FILE}"); return fences_df, status_df
    except Exception as e: print(f"Error fetching data: {e}"); return pd.DataFrame(), pd.DataFrame()
    finally:
        if conn and conn.is_connected(): conn.close()

def calculate_geo_features(fences_df): # (Same as before)
    print("Calculating geo features...")
    fences_df['geo_cluster'] = 0; coords = fences_df[['latitude', 'longitude']].dropna()
    target_k = getattr(ai_config, 'KMEANS_N_CLUSTERS', 3)
    if len(coords) >= target_k:
        try:
            optimal_k = coords.drop_duplicates().shape[0] if coords.drop_duplicates().shape[0] < target_k else target_k
            if optimal_k == 0: print("Warning: No unique coords for KMeans."); joblib.dump(None, ai_config.KMEANS_PATH); return fences_df
            if optimal_k < target_k : print(f"Reduced KMeans clusters to {optimal_k}.")
            kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init='auto')
            valid_mask = fences_df[['latitude', 'longitude']].notna().all(axis=1)
            if valid_mask.sum() >= optimal_k:
                fences_df.loc[valid_mask, 'geo_cluster'] = kmeans.fit_predict(fences_df.loc[valid_mask, ['latitude', 'longitude']])
                joblib.dump(kmeans, ai_config.KMEANS_PATH); print(f"KMeans model saved.")
            else: print(f"Warning: Not enough valid points for KMeans."); joblib.dump(None, ai_config.KMEANS_PATH)
        except Exception as e: print(f"KMeans Error: {e}"); joblib.dump(None, ai_config.KMEANS_PATH)
    else: print("Warning: Not enough data for KMeans."); joblib.dump(None, ai_config.KMEANS_PATH)
    return fences_df

def preprocess_data(fences_df, status_df): # (Same robust version as before)
    print("Preprocessing data...")
    fences_df['city'] = fences_df['city'].fillna('unknown')
    for city_val in fences_df['city'].unique():
        mask = (fences_df['city'] == city_val)
        for col in ['latitude', 'longitude']:
            median_val = fences_df.loc[mask, col].median()
            if not pd.isna(median_val): fences_df.loc[mask & fences_df[col].isna(), col] = median_val
    for col in ['latitude', 'longitude']:
        fences_df[col] = fences_df[col].fillna(fences_df[col].dropna().mean())

    fences_df = calculate_geo_features(fences_df)
    df = pd.merge(status_df, fences_df, left_on='fence_id', right_on='id', how='left')
    df.drop(columns=['id'], inplace=True, errors='ignore')

    df['message_time'] = pd.to_datetime(df['message_time'])
    df['hour_orig'] = df['message_time'].dt.hour
    df['day_of_week_orig'] = df['message_time'].dt.dayofweek
    df['month_orig'] = df['message_time'].dt.month

    for period, col_prefix in [(24,'hour'), (7,'day_of_week'), (12,'month')]:
        original_col = f'{col_prefix}_orig'
        df[f'{col_prefix}_sin'] = np.sin(2 * np.pi * df[original_col] / period)
        df[f'{col_prefix}_cos'] = np.cos(2 * np.pi * df[original_col] / period)
    df['is_weekend'] = df['day_of_week_orig'].isin([5, 6]).astype(int)

    m_rush=getattr(ai_config,'RUSH_HOURS_MORNING',(7,9)); e_rush=getattr(ai_config,'RUSH_HOURS_EVENING',(16,18))
    df['is_rush_hour']=df['hour_orig'].apply(lambda x:1 if(m_rush[0]<=x<m_rush[1])or(e_rush[0]<=x<e_rush[1])else 0)
    df['day_part']=pd.cut(df['hour_orig'],bins=[0,6,12,18,24],labels=['night','morning','afternoon','evening'],include_lowest=True,right=True)

    for col, path_suffix in [('status','status'),('city','city'),('day_part','day_part')]:
        le=LabelEncoder(); df[f'{col}_encoded']=le.fit_transform(df[col].astype(str))
        joblib.dump(le, getattr(ai_config, f'LE_{path_suffix.upper()}_PATH')); print(f"LE {col} saved.")

    df = df.sort_values(by=['fence_id', 'message_time'])
    df['time_diff_seconds'] = df.groupby('fence_id')['message_time'].diff().dt.total_seconds()

    def calc_median_diff(group): pos_diff=group[group>0]; return pos_diff.median() if not pos_diff.empty else np.nan
    group_cols = ['fence_id', 'status', 'hour_orig', 'day_of_week_orig']
    wait_agg = df.groupby(group_cols)['time_diff_seconds'].apply(calc_median_diff).reset_index(name='wait_time_seconds')
    df = pd.merge(df, wait_agg, on=group_cols, how='left')

    df['wait_time_minutes'] = df['wait_time_seconds'] / 60
    fill=getattr(ai_config,'WAIT_TIME_DEFAULT_FILL',10); clip_l=getattr(ai_config,'WAIT_TIME_CLIP_LOWER',5); clip_u=getattr(ai_config,'WAIT_TIME_CLIP_UPPER',120)
    df['wait_time_minutes'] = df['wait_time_minutes'].fillna(fill)
    df['wait_time'] = df['wait_time_minutes'].clip(lower=clip_l, upper=clip_u)

    cols_to_drop=['time_diff_seconds','wait_time_seconds','wait_time_minutes','hour_orig','day_of_week_orig','month_orig']
    df.drop(columns=[col for col in cols_to_drop if col in df.columns], inplace=True)
    
    final_dropna_cols = [
        'latitude','longitude','city_encoded','geo_cluster','day_part_encoded','wait_time',
        'hour_sin','hour_cos','day_of_week_sin','day_of_week_cos','month_sin','month_cos',
        'is_weekend','status_encoded','fence_id'
    ]
    df.dropna(subset=[col for col in final_dropna_cols if col in df.columns], inplace=True)
    print(f"Preprocessing complete. Shape: {df.shape}"); return df

def prepare_training_data_and_save_artifacts(df): # (Same robust version as before)
    print("Preparing training data...")
    feature_cols = [
        'fence_id','latitude','longitude','is_weekend','status_encoded','city_encoded',
        'geo_cluster','is_rush_hour','day_part_encoded',
        'hour_sin','hour_cos','day_of_week_sin','day_of_week_cos','month_sin','month_cos'
    ]
    missing = [col for col in feature_cols if col not in df.columns]
    if missing: raise ValueError(f"Missing features for training: {missing}")
    if df.empty: print("Warning: DF empty for training prep."); return None,None,[]
    X = df[feature_cols]; y = df['wait_time']; f_names = X.columns.tolist()
    os.makedirs(ai_config.ARTIFACTS_DIR, exist_ok=True)
    with open(ai_config.FEATURE_COLUMNS_PATH, 'w') as f: json.dump(f_names, f)
    print(f"Feature columns saved ({len(f_names)}).")
    scaler = StandardScaler(); X_scaled = scaler.fit_transform(X)
    joblib.dump(scaler, ai_config.SCALER_PATH); print(f"Scaler saved.")
    return X_scaled, y, f_names

def evaluate_model(model, X_test, y_test, feature_names, model_name="Model", save_plots=True): # (Same as before)
    if X_test.shape[0] == 0: print(f"Evaluation skipped for {model_name} (test set empty)."); return
    print(f"\n--- Evaluating: {model_name} ---")
    y_pred = model.predict(X_test); residuals = y_test - y_pred
    mae=mean_absolute_error(y_test,y_pred); medae=median_absolute_error(y_test,y_pred); r2=r2_score(y_test,y_pred)
    print(f"  Test MAE: {mae:.2f} min | Test MedianAE: {medae:.2f} min | Test R2: {r2:.2f}")
    if not save_plots: return
    fill_eval=getattr(ai_config,'WAIT_TIME_DEFAULT_FILL',10)
    plot_suffix=model_name.lower().replace(" ","_").replace("(","").replace(")","").replace(":","").replace("=","_")
    print("\n--- Binned CM ---")
    try:
        bins=[-float('inf'),10,30,60,float('inf')]; labels=["S","M","L","VL"]
        y_t_np=y_test.to_numpy(na_value=fill_eval)if hasattr(y_test,'to_numpy')else np.nan_to_num(np.array(y_test),nan=fill_eval)
        y_p_np=np.nan_to_num(np.array(y_pred),nan=fill_eval)
        y_tb=pd.cut(y_t_np,bins=bins,labels=labels,right=True,include_lowest=True).astype(str)
        y_pb=pd.cut(y_p_np,bins=bins,labels=labels,right=True,include_lowest=True).astype(str)
        cm=confusion_matrix(y_tb,y_pb,labels=labels)
        print(f"Categories for Binned CM ({model_name}): {labels}\n{cm}")
        disp=ConfusionMatrixDisplay(confusion_matrix=cm,display_labels=labels)
        fig,ax=plt.subplots(figsize=(6,5));disp.plot(cmap=plt.cm.Blues,ax=ax,xticks_rotation='horizontal')
        plt.title(f"Binned Preds ({model_name})");plt.tight_layout();plt.savefig(os.path.join(ai_config.ARTIFACTS_DIR,f'binned_cm_{plot_suffix}.png'));plt.close(fig)
        print(f"Binned CM plot for {model_name} saved.")
    except Exception as e: print(f"CM Err for {model_name}: {e}")
    if hasattr(model,'feature_importances_') and feature_names:
        print("\n--- Feat Imp ---")
        try:
            imp=model.feature_importances_;s_idx=np.argsort(imp)[::-1];n=np.array(feature_names)[s_idx]
            plt.figure(figsize=(10,max(5,len(n)*0.3)));plt.title(f"Feat Imps ({model_name})");
            plt.bar(range(len(imp)),imp[s_idx],align='center');plt.xticks(range(len(imp)),n,rotation=90)
            plt.tight_layout();plt.savefig(os.path.join(ai_config.ARTIFACTS_DIR,f'feat_imp_{plot_suffix}.png'));plt.close()
            print(f"Feat Imp plot for {model_name} saved.")
        except Exception as e: print(f"FI Err for {model_name}: {e}")
    print("\n--- Res Plots ---")
    try:
        plt.figure(figsize=(10,5));sns.histplot(residuals,kde=True);plt.title(f'Res Hist ({model_name})')
        plt.xlabel('Res(min)');plt.ylabel('Freq');plt.tight_layout();plt.savefig(os.path.join(ai_config.ARTIFACTS_DIR,f'res_hist_{plot_suffix}.png'));plt.close();print(f"Res Hist for {model_name} saved.")
        plt.figure(figsize=(10,5));plt.scatter(y_pred,residuals,alpha=0.3,s=10);plt.axhline(y=0,c='r',ls='--')
        plt.title(f'Res vs Pred ({model_name})');plt.xlabel('Pred(min)');plt.ylabel('Res(min)');plt.tight_layout()
        plt.savefig(os.path.join(ai_config.ARTIFACTS_DIR,f'res_vs_pred_{plot_suffix}.png'));plt.close();print(f"Res vs Pred for {model_name} saved.")
    except Exception as e: print(f"Res Plot Err for {model_name}: {e}")

def train_and_save_model(X, y, feature_names):
    print("Training RandomForestRegressor model directly with best known parameters...")
    if X is None or y is None or X.shape[0]==0: print("No training data."); return None
    X_train,X_test,y_train,y_test = train_test_split(X,y,test_size=0.2,random_state=42)
    if X_train.shape[0]<1: print("Train set empty."); return None

    # --- Using the BEST parameters found from your R²=0.776 run ---
    # Best params from RSCV (n_iter=40) that gave R2=0.776:
    # {'bootstrap': True, 'max_depth': 30, 'max_features': 0.7, 
    #  'min_samples_leaf': 1, 'min_samples_split': 2, 'n_estimators': 158}
    
    best_known_params = {
        'n_estimators': 158,
        'max_depth': 30,
        'min_samples_leaf': 1,
        'min_samples_split': 2,
        'max_features': 0.7, # This was a float percentage
        'bootstrap': True,    # This was explicitly in param_dist, assuming it was picked or True is fine
        'random_state': 42,
        'n_jobs': -1
    }
    print(f"\nTraining model with pre-defined best parameters: {best_known_params}")
    
    model = RandomForestRegressor(**best_known_params)
    
    start_t = time.time()
    model.fit(X_train, y_train)
    end_t = time.time()
    print(f"Direct model training took {(end_t - start_t):.2f}s.")
    
    evaluate_model(model, X_test, y_test, feature_names, model_name="Best Known Params Model")
    
    joblib.dump(model, ai_config.MODEL_PATH)
    print(f"\nModel with best known parameters saved as main model: {ai_config.MODEL_PATH}")

    return model

# --- Main Execution ---
def main():
    title = "--- RF Model Training (Using Best Known Params Directly) ---"
    print(title); os.makedirs(ai_config.ARTIFACTS_DIR, exist_ok=True)
    fdf,sdf=fetch_data(use_cache=True)
    if fdf.empty or sdf.empty: print("No data. Exit."); return
    pdf=preprocess_data(fdf,sdf)
    if pdf is None or pdf.empty: print("Preprocessing failed or resulted in empty df. Exit."); return
    print(f"Post-proc shape: {pdf.shape}. Wait: Min={pdf['wait_time'].min():.1f},Max={pdf['wait_time'].max():.1f},Mean={pdf['wait_time'].mean():.1f}")
    if 'wait_time' not in pdf.columns: print("'wait_time' missing. Exit."); return
    Xs,yt,fns=prepare_training_data_and_save_artifacts(pdf)
    if Xs is None or yt is None or Xs.shape[0]==0: print("Data prep failed. Exit."); return
    
    final_model = train_and_save_model(Xs,yt,fns)
    
    if final_model: print(f"\n{title} Training with best known params COMPLETED.")
    else: print(f"\n{title} Training with best known params FAILED.")

if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=UserWarning, module="sklearn.cluster._kmeans")
    warnings.filterwarnings("ignore", category=FutureWarning)
    if os.environ.get('DISPLAY','') == '':
        print('No display found. Using non-interactive Agg backend for Matplotlib.')
        plt.switch_backend('Agg')
    main()