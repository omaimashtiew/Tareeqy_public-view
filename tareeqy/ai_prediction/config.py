# tareeqy/ai_prediction/config.py
import os

# Directory where this config.py file is located
AI_PREDICTION_DIR = os.path.dirname(os.path.abspath(__file__))

# Sub-directory for storing/loading model artifacts
ARTIFACTS_DIR = os.path.join(AI_PREDICTION_DIR, 'artifacts')
os.makedirs(ARTIFACTS_DIR, exist_ok=True) # Ensure it exists

# --- Artifact Paths ---
# Model and related components
MODEL_PATH = os.path.join(ARTIFACTS_DIR, 'wait_time_model.pkl')
SCALER_PATH = os.path.join(ARTIFACTS_DIR, 'scaler.pkl')
KMEANS_PATH = os.path.join(ARTIFACTS_DIR, 'kmeans_model.pkl')

# Label Encoders
LE_STATUS_PATH = os.path.join(ARTIFACTS_DIR, 'label_encoder_status.pkl')
LE_CITY_PATH = os.path.join(ARTIFACTS_DIR, 'label_encoder_city.pkl')
LE_DAY_PART_PATH = os.path.join(ARTIFACTS_DIR, 'label_encoder_day_part.pkl')

# Feature columns (expected by the model)
FEATURE_COLUMNS_PATH = os.path.join(ARTIFACTS_DIR, 'feature_columns.json')

# --- Django Settings ---
DJANGO_SETTINGS_MODULE = 'tareeqy_tracker.settings' # تأكد من أن هذا صحيح لمشروعك
APP_NAME = 'tareeqy' # اسم تطبيق Django

# --- Prediction Defaults and Constants ---
DEFAULT_UNKNOWN_ENCODED_VALUE = 0 # القيمة الافتراضية للفئات غير المعروفة
RUSH_HOURS_MORNING = (7, 9)      # أوقات الذروة الصباحية: من 7 إلى 9 صباحًا
RUSH_HOURS_EVENING = (16, 18)    # أوقات الذروة المسائية: من 4 إلى 6 مساءً
DEFAULT_PREDICTION_ERROR_WAIT_TIME = 15 # الوقت الافتراضي في حالة فشل التنبؤ (بالدقائق)
WAIT_TIME_DEFAULT_FILL = 10      # القيمة الافتراضية لوقت الانتظار عند تعبئة القيم الفارغة
WAIT_TIME_CLIP_LOWER = 5         # الحد الأدنى لوقت الانتظار (بالدقائق)
WAIT_TIME_CLIP_UPPER = 120       # الحد الأعلى لوقت الانتظار (بالدقائق)
KMEANS_N_CLUSTERS = 3            # عدد العناقيد المستخدمة في KMeans

# Status strings that might have special handling (must match training data)
STATUS_OPEN = 'open'
STATUS_SEVERE_TRAFFIC = 'sever_traffic_jam' # يجب أن تتطابق مع القيمة المستخدمة في البيانات
STATUS_CLOSED = 'closed'