"""项目全局配置：品类、市场、路径、模型参数。"""

from __future__ import annotations

import os
import pathlib

# 项目根目录（src 的上一级）
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

# 加载根目录 .env（可选）：存在则生效，缺失/未装依赖时静默回退默认值。
# 必须早于本模块任何 os.environ 读取（首个读取在第 190 行附近），使 BACKEND_*/AI_* 等可统一写入 .env。
try:  # pragma: no cover - python-dotenv 为可选依赖，未安装时回退纯环境变量
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:  # pragma: no cover
    pass

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DEMO_DIR = DATA_DIR / "demo"
MODEL_DIR = PROJECT_ROOT / "models"
DOCS_DIR = PROJECT_ROOT / "docs"
OUTPUT_DIR = PROJECT_ROOT / "output"

for _d in (RAW_DIR, PROCESSED_DIR, DEMO_DIR, MODEL_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# 统一文件
RAW_CSV = RAW_DIR / "market_data_raw.csv"
PROCESSED_CSV = PROCESSED_DIR / "clean_data.csv"
DEMO_CSV = DEMO_DIR / "demo_market_data.csv"
REAL_TRAINING_CSV = PROCESSED_DIR / "clean_data_real.csv"
REAL_FEATURE_BANK_CSV = PROCESSED_DIR / "real_feature_bank.csv"
DB_PATH = PROCESSED_DIR / "market_data.db"
FORECAST_CSV = MODEL_DIR / "forecast.csv"
RECOMMEND_CSV = MODEL_DIR / "recommendations.csv"
METRICS_JSON = MODEL_DIR / "metrics.json"
REAL_PROXY_MODEL = MODEL_DIR / "real_demand_proxy.joblib"
REAL_PROXY_META = MODEL_DIR / "real_demand_proxy_meta.json"
REAL_PROXY_EVIDENCE_WEIGHT = 0.4

# 每日联网更新相关产物
DATA_STATUS_JSON = OUTPUT_DIR / "data_status.json"
DAILY_SNAPSHOT_DIR = OUTPUT_DIR / "daily_snapshots"
CONTROL_OUTPUT_DIR = OUTPUT_DIR / "control"
CONTROL_METRICS_JSON = CONTROL_OUTPUT_DIR / "control_metrics.json"
SYSTEM_EVAL_JSON = CONTROL_OUTPUT_DIR / "system_eval.json"
ENG_STATUS_JSON = OUTPUT_DIR / "eng_status.json"

# GitHub public dataset signal layer (does not change training data)
GITHUB_DATA_DIR = DATA_DIR / "external" / "github"
GITHUB_SOURCES_MD = GITHUB_DATA_DIR / "SOURCES.md"
HARMONIZED_SYSTEM_CSV = GITHUB_DATA_DIR / "hs" / "data" / "harmonized-system.csv"
GITHUB_SIGNALS_JSON = CONTROL_OUTPUT_DIR / "github_signals.json"
GITHUB_REAL_RESULTS_CSV = CONTROL_OUTPUT_DIR / "github_real_results.csv"
GITHUB_MAX_ROWS_PER_PROVIDER = 500
GITHUB_PROMPT_SIGNAL_ROWS_LITE = 40
GITHUB_PROMPT_SIGNAL_ROWS_FULL = 80

# Hugging Face public dataset signal layer (does not change training data)
HF_DATA_DIR = DATA_DIR / "external" / "hf"
HF_SOURCES_MD = HF_DATA_DIR / "SOURCES.md"
HF_SIGNALS_JSON = CONTROL_OUTPUT_DIR / "hf_signals.json"
HF_REAL_RESULTS_CSV = CONTROL_OUTPUT_DIR / "hf_real_results.csv"
HF_MAX_ROWS_PER_PROVIDER = 200
HF_PROMPT_SIGNAL_ROWS_LITE = 40
HF_PROMPT_SIGNAL_ROWS_FULL = 80
CONTROL_RETRY_LIMIT = 3
DEMO_DATA_JSON = OUTPUT_DIR / "dashboard-data.json"

# 品类统一目录：名称、联网关键词、合成参数、默认 HS4 与关税基线。
# 食品品类统一目录（依据源代码文档 V1.0，食品口径为权威）
# MAJOR_CATEGORIES = 12 大类食品；CATEGORY_CATALOG = 132 个食品 SKU；其余从 CATEGORY_CATALOG 派生。
MAJOR_CATEGORIES: dict[str, dict] = {
    'staple': {
        'name_cn': '谷物主食', 'name_en': 'Grain Staples',
        'hs4_default': '1902', 'hs_description': '米、面制食品', 'tariff_base': 0.1,
        'logistics': {
            'transport_type': ['常温集装箱', '冷藏（冷冻主食）'],
            'storage_type': '常温/阴凉干燥；冷冻主食 -18°C',
            'temperature_range_c': '0~30（冷冻 -18）',
            'shelf_life_months': 12,
            'cold_chain_required': False,
            'perishability': 'low',
            'fragility': 'low',
            'weight_density': '重货',
            'import_clearance': '标签/成分表；谷物类农残与检疫',
        },
    },
    'meat_egg': {
        'name_cn': '肉禽蛋奶', 'name_en': 'Meat, Egg & Dairy',
        'hs4_default': '1602', 'hs_description': '肉及食用杂碎制品', 'tariff_base': 0.12,
        'logistics': {
            'transport_type': ['冷链冷藏', '冷链冷冻'],
            'storage_type': '冷藏 0~4°C；冷冻 -18°C',
            'temperature_range_c': '-18~4',
            'shelf_life_months': 6,
            'cold_chain_required': True,
            'perishability': 'high',
            'fragility': 'low',
            'weight_density': '重货',
            'import_clearance': 'FDA/EFSA、动物检疫、产地证明、标签与成分表',
        },
    },
    'seafood': {
        'name_cn': '海鲜水产', 'name_en': 'Seafood & Aquatic',
        'hs4_default': '1604', 'hs_description': '制作或保藏的水产品', 'tariff_base': 0.12,
        'logistics': {
            'transport_type': ['冷链冷冻', '冷链冷藏', '干冰'],
            'storage_type': '冷冻 -18°C；冷藏 0~4°C；干制常温',
            'temperature_range_c': '-18~4（干制 0~30）',
            'shelf_life_months': 6,
            'cold_chain_required': True,
            'perishability': 'high',
            'fragility': 'low',
            'weight_density': '重货',
            'import_clearance': '水产检疫、捕捞/养殖证明、汞含量与标签',
        },
    },
    'produce': {
        'name_cn': '果蔬生鲜', 'name_en': 'Fresh Produce',
        'hs4_default': '0710', 'hs_description': '冷冻蔬菜', 'tariff_base': 0.08,
        'logistics': {
            'transport_type': ['冷链冷藏', '常温（耐储）', '航空'],
            'storage_type': '冷藏 0~10°C；部分常温',
            'temperature_range_c': '0~25',
            'shelf_life_months': 1,
            'cold_chain_required': True,
            'perishability': 'high',
            'fragility': 'medium',
            'weight_density': '重货（含水）/轻抛（部分）',
            'import_clearance': '植物检疫、农药残留、冷链到港时效',
        },
    },
    'snack': {
        'name_cn': '中式零食', 'name_en': 'Chinese Snacks',
        'hs4_default': '1905', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1,
        'logistics': {
            'transport_type': ['常温集装箱'],
            'storage_type': '常温/阴凉干燥',
            'temperature_range_c': '0~30',
            'shelf_life_months': 12,
            'cold_chain_required': False,
            'perishability': 'low',
            'fragility': 'low',
            'weight_density': '轻抛',
            'import_clearance': '标签/成分、添加剂与过敏原',
        },
    },
    'nuts': {
        'name_cn': '坚果果干', 'name_en': 'Nuts & Dried Fruits',
        'hs4_default': '0802', 'hs_description': '其他坚果', 'tariff_base': 0.08,
        'logistics': {
            'transport_type': ['常温集装箱'],
            'storage_type': '常温/阴凉干燥',
            'temperature_range_c': '0~30',
            'shelf_life_months': 12,
            'cold_chain_required': False,
            'perishability': 'low',
            'fragility': 'medium',
            'weight_density': '轻抛',
            'import_clearance': '黄曲霉/农残、标签与过敏原',
        },
    },
    'sauce': {
        'name_cn': '调味酱料', 'name_en': 'Sauces & Condiments',
        'hs4_default': '2103', 'hs_description': '调味汁及其制品', 'tariff_base': 0.1,
        'logistics': {
            'transport_type': ['常温集装箱'],
            'storage_type': '常温/阴凉干燥；开瓶后部分冷藏',
            'temperature_range_c': '0~30',
            'shelf_life_months': 18,
            'cold_chain_required': False,
            'perishability': 'low',
            'fragility': 'medium',
            'weight_density': '重货',
            'import_clearance': '标签/成分/添加剂/微生物限量',
        },
    },
    'beverage': {
        'name_cn': '茶饮酒水', 'name_en': 'Tea, Beverages & Alcohol',
        'hs4_default': '0902', 'hs_description': '茶', 'tariff_base': 0.07,
        'logistics': {
            'transport_type': ['常温集装箱', '保温'],
            'storage_type': '常温/阴凉干燥；酒类避光',
            'temperature_range_c': '0~30',
            'shelf_life_months': 24,
            'cold_chain_required': False,
            'perishability': 'low',
            'fragility': 'medium',
            'weight_density': '重货',
            'import_clearance': '标签、酒类进口许可、茶叶农残检疫、成分表',
        },
    },
    'bakery': {
        'name_cn': '烘焙甜点', 'name_en': 'Bakery & Desserts',
        'hs4_default': '1905', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1,
        'logistics': {
            'transport_type': ['常温（短保）', '冷链冷藏', '冷冻半成品'],
            'storage_type': '常温/阴凉干燥；冷藏/冷冻短保',
            'temperature_range_c': '0~30（冷藏 0~4 / 冷冻 -18）',
            'shelf_life_months': 3,
            'cold_chain_required': False,
            'perishability': 'medium',
            'fragility': 'high',
            'weight_density': '轻抛',
            'import_clearance': '标签/过敏原/保质期、进口烘焙食品检验',
        },
    },
    'instant': {
        'name_cn': '方便速食', 'name_en': 'Instant & Ready-to-Eat',
        'hs4_default': '1902', 'hs_description': '面食', 'tariff_base': 0.1,
        'logistics': {
            'transport_type': ['常温集装箱', '冷冻调理'],
            'storage_type': '常温/阴凉干燥；冷冻 -18°C',
            'temperature_range_c': '0~30（冷冻 -18）',
            'shelf_life_months': 12,
            'cold_chain_required': False,
            'perishability': 'low',
            'fragility': 'medium',
            'weight_density': '重货（自热含料包）',
            'import_clearance': '标签/成分/添加剂、自热包航空禁运风险',
        },
    },
    'wellness': {
        'name_cn': '滋补保健', 'name_en': 'Tonic & Wellness Foods',
        'hs4_default': '1211', 'hs_description': '主要用作香料、药料或杀虫、杀菌的植物', 'tariff_base': 0.06,
        'logistics': {
            'transport_type': ['常温集装箱'],
            'storage_type': '常温/阴凉干燥',
            'temperature_range_c': '0~30',
            'shelf_life_months': 24,
            'cold_chain_required': False,
            'perishability': 'low',
            'fragility': 'medium',
            'weight_density': '轻抛',
            'import_clearance': '药食同源目录、保健食品注册/备案、成分与功效宣称合规',
        },
    },
    'vegetarian': {
        'name_cn': '素食清真', 'name_en': 'Plant-Based & Halal',
        'hs4_default': '2106', 'hs_description': '其他税号未列名食品', 'tariff_base': 0.09,
        'logistics': {
            'transport_type': ['常温集装箱', '冷藏/冷冻'],
            'storage_type': '常温/阴凉干燥；冷藏/冷冻',
            'temperature_range_c': '0~30（冷冻 -18）',
            'shelf_life_months': 12,
            'cold_chain_required': False,
            'perishability': 'medium',
            'fragility': 'low',
            'weight_density': '轻抛/重货混合',
            'import_clearance': '标签/过敏原（大豆、麸质）、清真认证（Halal）、植物蛋白进口检验',
        },
    },
}

CATEGORY_CATALOG: dict[str, dict] = {
    'cn_changsha_mifen': {'name_cn': '长沙米粉', 'name_en': 'Changsha Rice Noodles', 'category': 'staple', 'mid_category': 'rice_noodle', 'culture_group': 'cn', 'keyword': 'changsha rice noodles', 'base_sales': 86, 'price': 9, 'peak_month': 11, 'competition': 58, 'hs4': '1902', 'hs_description': '米、面制食品', 'tariff_base': 0.1, 'nutrition_score': 72, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_guilin_mifen': {'name_cn': '桂林米粉', 'name_en': 'Guilin Rice Noodles', 'category': 'staple', 'mid_category': 'rice_noodle', 'culture_group': 'cn', 'keyword': 'guilin rice noodles', 'base_sales': 84, 'price': 9, 'peak_month': 11, 'competition': 58, 'hs4': '1902', 'hs_description': '米、面制食品', 'tariff_base': 0.1, 'nutrition_score': 72, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_handmade_noodles': {'name_cn': '手工挂面', 'name_en': 'Handmade Noodles', 'category': 'staple', 'mid_category': 'rice_noodle', 'culture_group': 'cn', 'keyword': 'handmade wheat noodles china', 'base_sales': 78, 'price': 8, 'peak_month': 9, 'competition': 52, 'hs4': '1902', 'hs_description': '米、面制食品', 'tariff_base': 0.1, 'nutrition_score': 70, 'shelf_life_months': 18, 'storage_type': '常温'},
    'cn_bajiang_mian': {'name_cn': '八宝粥', 'name_en': 'Eight Treasure Congee', 'category': 'staple', 'mid_category': 'grain_porridge', 'culture_group': 'cn', 'keyword': 'eight treasure congee', 'base_sales': 72, 'price': 10, 'peak_month': 12, 'competition': 50, 'hs4': '1904', 'hs_description': '米、面制食品', 'tariff_base': 0.1, 'nutrition_score': 78, 'shelf_life_months': 18, 'storage_type': '常温'},
    'cn_xiaomi_zhou': {'name_cn': '小米粥', 'name_en': 'Millet Porridge', 'category': 'staple', 'mid_category': 'grain_porridge', 'culture_group': 'cn', 'keyword': 'millet porridge instant', 'base_sales': 70, 'price': 8, 'peak_month': 1, 'competition': 48, 'hs4': '1104', 'hs_description': '米、面制食品', 'tariff_base': 0.1, 'nutrition_score': 80, 'shelf_life_months': 18, 'storage_type': '常温'},
    'cn_frozen_dumplings': {'name_cn': '速冻水饺', 'name_en': 'Frozen Dumplings', 'category': 'staple', 'mid_category': 'frozen_staple', 'culture_group': 'cn', 'keyword': 'frozen chinese dumplings', 'base_sales': 95, 'price': 14, 'peak_month': 12, 'competition': 62, 'hs4': '1902', 'hs_description': '米、面制食品', 'tariff_base': 0.1, 'nutrition_score': 68, 'shelf_life_months': 9, 'storage_type': '冷冻'},
    'intl_ramen_japan': {'name_cn': '日式拉面', 'name_en': 'Japanese Ramen Noodles', 'category': 'staple', 'mid_category': 'rice_noodle', 'culture_group': 'intl', 'keyword': 'japanese ramen noodles', 'base_sales': 88, 'price': 12, 'peak_month': 12, 'competition': 60, 'hs4': '1902', 'hs_description': '米、面制食品', 'tariff_base': 0.1, 'nutrition_score': 68, 'shelf_life_months': 12, 'storage_type': '常温'},
    'intl_pasta': {'name_cn': '意大利面', 'name_en': 'Pasta', 'category': 'staple', 'mid_category': 'rice_noodle', 'culture_group': 'intl', 'keyword': 'pasta italian', 'base_sales': 90, 'price': 7, 'peak_month': 11, 'competition': 55, 'hs4': '1902', 'hs_description': '米、面制食品', 'tariff_base': 0.1, 'nutrition_score': 74, 'shelf_life_months': 24, 'storage_type': '常温'},
    'intl_oats': {'name_cn': '燕麦片', 'name_en': 'Rolled Oats', 'category': 'staple', 'mid_category': 'grain_porridge', 'culture_group': 'intl', 'keyword': 'rolled oats', 'base_sales': 76, 'price': 8, 'peak_month': 1, 'competition': 50, 'hs4': '1104', 'hs_description': '米、面制食品', 'tariff_base': 0.1, 'nutrition_score': 82, 'shelf_life_months': 18, 'storage_type': '常温'},
    'intl_quinoa': {'name_cn': '藜麦', 'name_en': 'Quinoa', 'category': 'staple', 'mid_category': 'grain_porridge', 'culture_group': 'intl', 'keyword': 'quinoa grain', 'base_sales': 62, 'price': 12, 'peak_month': 3, 'competition': 48, 'hs4': '1008', 'hs_description': '米、面制食品', 'tariff_base': 0.1, 'nutrition_score': 85, 'shelf_life_months': 24, 'storage_type': '常温'},
    'intl_frozen_pizza': {'name_cn': '冷冻披萨', 'name_en': 'Frozen Pizza', 'category': 'staple', 'mid_category': 'frozen_staple', 'culture_group': 'intl', 'keyword': 'frozen pizza', 'base_sales': 84, 'price': 11, 'peak_month': 12, 'competition': 60, 'hs4': '1905', 'hs_description': '米、面制食品', 'tariff_base': 0.1, 'nutrition_score': 60, 'shelf_life_months': 9, 'storage_type': '冷冻'},
    'cn_beef_jerky': {'name_cn': '麻辣牛肉干', 'name_en': 'Sichuan Spicy Beef Jerky', 'category': 'meat_egg', 'mid_category': 'cured', 'culture_group': 'cn', 'keyword': 'sichuan spicy beef jerky', 'base_sales': 82, 'price': 16, 'peak_month': 12, 'competition': 64, 'hs4': '1602', 'hs_description': '肉及食用杂碎制品', 'tariff_base': 0.12, 'nutrition_score': 66, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_tea_egg': {'name_cn': '茶叶蛋', 'name_en': 'Marinated Tea Eggs', 'category': 'meat_egg', 'mid_category': 'egg_dairy', 'culture_group': 'cn', 'keyword': 'chinese tea egg', 'base_sales': 68, 'price': 3, 'peak_month': 3, 'competition': 50, 'hs4': '0407', 'hs_description': '肉及食用杂碎制品', 'tariff_base': 0.12, 'nutrition_score': 74, 'shelf_life_months': 1, 'storage_type': '冷藏'},
    'cn_salted_duck_egg': {'name_cn': '咸鸭蛋', 'name_en': 'Salted Duck Eggs', 'category': 'meat_egg', 'mid_category': 'egg_dairy', 'culture_group': 'cn', 'keyword': 'salted duck egg', 'base_sales': 70, 'price': 5, 'peak_month': 2, 'competition': 48, 'hs4': '0407', 'hs_description': '肉及食用杂碎制品', 'tariff_base': 0.12, 'nutrition_score': 70, 'shelf_life_months': 6, 'storage_type': '常温'},
    'cn_sichuan_sausage': {'name_cn': '川味香肠', 'name_en': 'Sichuan Cured Sausage', 'category': 'meat_egg', 'mid_category': 'cured', 'culture_group': 'cn', 'keyword': 'sichuan sausage', 'base_sales': 78, 'price': 15, 'peak_month': 12, 'competition': 58, 'hs4': '1601', 'hs_description': '肉及食用杂碎制品', 'tariff_base': 0.12, 'nutrition_score': 64, 'shelf_life_months': 9, 'storage_type': '冷藏'},
    'cn_century_egg': {'name_cn': '松花蛋', 'name_en': 'Preserved Century Eggs', 'category': 'meat_egg', 'mid_category': 'egg_dairy', 'culture_group': 'cn', 'keyword': 'century egg chinese', 'base_sales': 66, 'price': 6, 'peak_month': 2, 'competition': 46, 'hs4': '0407', 'hs_description': '肉及食用杂碎制品', 'tariff_base': 0.12, 'nutrition_score': 68, 'shelf_life_months': 6, 'storage_type': '常温'},
    'intl_beef_jerky': {'name_cn': '美式牛肉干', 'name_en': 'American Beef Jerky', 'category': 'meat_egg', 'mid_category': 'meat', 'culture_group': 'intl', 'keyword': 'beef jerky', 'base_sales': 88, 'price': 14, 'peak_month': 11, 'competition': 60, 'hs4': '1602', 'hs_description': '肉及食用杂碎制品', 'tariff_base': 0.12, 'nutrition_score': 70, 'shelf_life_months': 12, 'storage_type': '常温'},
    'intl_pepperoni': {'name_cn': '意式萨拉米', 'name_en': 'Pepperoni', 'category': 'meat_egg', 'mid_category': 'meat', 'culture_group': 'intl', 'keyword': 'pepperoni salami', 'base_sales': 74, 'price': 12, 'peak_month': 12, 'competition': 56, 'hs4': '1601', 'hs_description': '肉及食用杂碎制品', 'tariff_base': 0.12, 'nutrition_score': 62, 'shelf_life_months': 12, 'storage_type': '冷藏'},
    'intl_cheddar': {'name_cn': '切达奶酪', 'name_en': 'Cheddar Cheese', 'category': 'meat_egg', 'mid_category': 'egg_dairy', 'culture_group': 'intl', 'keyword': 'cheddar cheese block', 'base_sales': 80, 'price': 18, 'peak_month': 12, 'competition': 58, 'hs4': '0406', 'hs_description': '肉及食用杂碎制品', 'tariff_base': 0.12, 'nutrition_score': 72, 'shelf_life_months': 8, 'storage_type': '冷藏'},
    'intl_greek_yogurt': {'name_cn': '希腊酸奶', 'name_en': 'Greek Yogurt', 'category': 'meat_egg', 'mid_category': 'egg_dairy', 'culture_group': 'intl', 'keyword': 'greek yogurt', 'base_sales': 72, 'price': 6, 'peak_month': 3, 'competition': 54, 'hs4': '0403', 'hs_description': '肉及食用杂碎制品', 'tariff_base': 0.12, 'nutrition_score': 76, 'shelf_life_months': 1, 'storage_type': '冷藏'},
    'intl_prosciutto': {'name_cn': '帕尔玛火腿', 'name_en': 'Prosciutto', 'category': 'meat_egg', 'mid_category': 'cured', 'culture_group': 'intl', 'keyword': 'prosciutto ham', 'base_sales': 62, 'price': 22, 'peak_month': 12, 'competition': 56, 'hs4': '1602', 'hs_description': '肉及食用杂碎制品', 'tariff_base': 0.12, 'nutrition_score': 64, 'shelf_life_months': 10, 'storage_type': '冷藏'},
    'intl_mozzarella': {'name_cn': '马苏里拉奶酪', 'name_en': 'Mozzarella', 'category': 'meat_egg', 'mid_category': 'egg_dairy', 'culture_group': 'intl', 'keyword': 'mozzarella cheese', 'base_sales': 78, 'price': 16, 'peak_month': 12, 'competition': 58, 'hs4': '0406', 'hs_description': '肉及食用杂碎制品', 'tariff_base': 0.12, 'nutrition_score': 70, 'shelf_life_months': 6, 'storage_type': '冷藏'},
    'cn_shrimp_paste': {'name_cn': '虾酱', 'name_en': 'Shrimp Paste', 'category': 'seafood', 'mid_category': 'dried_seafood', 'culture_group': 'cn', 'keyword': 'chinese shrimp paste', 'base_sales': 64, 'price': 9, 'peak_month': 1, 'competition': 48, 'hs4': '1605', 'hs_description': '制作或保藏的水产品', 'tariff_base': 0.12, 'nutrition_score': 62, 'shelf_life_months': 18, 'storage_type': '常温'},
    'cn_dried_seaweed': {'name_cn': '紫菜干', 'name_en': 'Dried Seaweed', 'category': 'seafood', 'mid_category': 'dried_seafood', 'culture_group': 'cn', 'keyword': 'dried seaweed sheets china', 'base_sales': 74, 'price': 8, 'peak_month': 1, 'competition': 46, 'hs4': '1212', 'hs_description': '制作或保藏的水产品', 'tariff_base': 0.12, 'nutrition_score': 80, 'shelf_life_months': 24, 'storage_type': '常温'},
    'cn_fish_balls': {'name_cn': '潮汕鱼丸', 'name_en': 'Chaoshan Fish Balls', 'category': 'seafood', 'mid_category': 'fresh_seafood', 'culture_group': 'cn', 'keyword': 'chaoshan fish balls', 'base_sales': 82, 'price': 14, 'peak_month': 12, 'competition': 55, 'hs4': '1604', 'hs_description': '制作或保藏的水产品', 'tariff_base': 0.12, 'nutrition_score': 70, 'shelf_life_months': 9, 'storage_type': '冷冻'},
    'cn_crispy_fish': {'name_cn': '香酥小黄鱼', 'name_en': 'Crispy Fried Yellow Croaker', 'category': 'seafood', 'mid_category': 'canned_seafood', 'culture_group': 'cn', 'keyword': 'crispy fish snack', 'base_sales': 76, 'price': 12, 'peak_month': 12, 'competition': 52, 'hs4': '1604', 'hs_description': '制作或保藏的水产品', 'tariff_base': 0.12, 'nutrition_score': 64, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_oyster_sauce': {'name_cn': '蚝油', 'name_en': 'Oyster Sauce', 'category': 'seafood', 'mid_category': 'dried_seafood', 'culture_group': 'cn', 'keyword': 'oyster sauce', 'base_sales': 88, 'price': 6, 'peak_month': 12, 'competition': 50, 'hs4': '2103', 'hs_description': '制作或保藏的水产品', 'tariff_base': 0.12, 'nutrition_score': 60, 'shelf_life_months': 18, 'storage_type': '常温'},
    'intl_canned_tuna': {'name_cn': '金枪鱼罐头', 'name_en': 'Canned Tuna', 'category': 'seafood', 'mid_category': 'canned_seafood', 'culture_group': 'intl', 'keyword': 'canned tuna', 'base_sales': 90, 'price': 8, 'peak_month': 12, 'competition': 56, 'hs4': '1604', 'hs_description': '制作或保藏的水产品', 'tariff_base': 0.12, 'nutrition_score': 74, 'shelf_life_months': 24, 'storage_type': '常温'},
    'intl_salmon_fillet': {'name_cn': '三文鱼柳', 'name_en': 'Salmon Fillet', 'category': 'seafood', 'mid_category': 'fresh_seafood', 'culture_group': 'intl', 'keyword': 'salmon fillet fresh', 'base_sales': 78, 'price': 24, 'peak_month': 12, 'competition': 60, 'hs4': '0304', 'hs_description': '制作或保藏的水产品', 'tariff_base': 0.12, 'nutrition_score': 78, 'shelf_life_months': 1, 'storage_type': '冷冻'},
    'intl_dried_shrimp': {'name_cn': '干虾米', 'name_en': 'Dried Shrimp', 'category': 'seafood', 'mid_category': 'dried_seafood', 'culture_group': 'intl', 'keyword': 'dried shrimp', 'base_sales': 66, 'price': 14, 'peak_month': 2, 'competition': 50, 'hs4': '0305', 'hs_description': '制作或保藏的水产品', 'tariff_base': 0.12, 'nutrition_score': 68, 'shelf_life_months': 18, 'storage_type': '常温'},
    'intl_crab_sticks': {'name_cn': '蟹柳', 'name_en': 'Crab Sticks', 'category': 'seafood', 'mid_category': 'fresh_seafood', 'culture_group': 'intl', 'keyword': 'crab sticks imitation', 'base_sales': 72, 'price': 8, 'peak_month': 12, 'competition': 52, 'hs4': '1605', 'hs_description': '制作或保藏的水产品', 'tariff_base': 0.12, 'nutrition_score': 60, 'shelf_life_months': 6, 'storage_type': '冷藏'},
    'intl_anchovy_snack': {'name_cn': '鳀鱼脆条', 'name_en': 'Anchovy Snacks', 'category': 'seafood', 'mid_category': 'canned_seafood', 'culture_group': 'intl', 'keyword': 'anchovy snacks', 'base_sales': 70, 'price': 10, 'peak_month': 12, 'competition': 54, 'hs4': '1604', 'hs_description': '制作或保藏的水产品', 'tariff_base': 0.12, 'nutrition_score': 66, 'shelf_life_months': 12, 'storage_type': '常温'},
    'intl_seaweed_snack': {'name_cn': '海苔脆片', 'name_en': 'Roasted Seaweed Snack', 'category': 'seafood', 'mid_category': 'dried_seafood', 'culture_group': 'intl', 'keyword': 'roasted seaweed snack', 'base_sales': 80, 'price': 6, 'peak_month': 12, 'competition': 50, 'hs4': '1212', 'hs_description': '制作或保藏的水产品', 'tariff_base': 0.12, 'nutrition_score': 78, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_dried_shitake': {'name_cn': '干香菇', 'name_en': 'Dried Shiitake Mushrooms', 'category': 'produce', 'mid_category': 'preserved', 'culture_group': 'cn', 'keyword': 'dried shiitake mushrooms', 'base_sales': 74, 'price': 12, 'peak_month': 1, 'competition': 48, 'hs4': '0712', 'hs_description': '冷冻蔬菜', 'tariff_base': 0.08, 'nutrition_score': 78, 'shelf_life_months': 24, 'storage_type': '常温'},
    'cn_pickled_cabbage': {'name_cn': '酸菜', 'name_en': 'Pickled Cabbage', 'category': 'produce', 'mid_category': 'preserved', 'culture_group': 'cn', 'keyword': 'chinese pickled cabbage suancai', 'base_sales': 80, 'price': 7, 'peak_month': 1, 'competition': 46, 'hs4': '2005', 'hs_description': '冷冻蔬菜', 'tariff_base': 0.08, 'nutrition_score': 64, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_dried_chili': {'name_cn': '干辣椒', 'name_en': 'Dried Chili Peppers', 'category': 'produce', 'mid_category': 'preserved', 'culture_group': 'cn', 'keyword': 'dried chili peppers', 'base_sales': 84, 'price': 10, 'peak_month': 1, 'competition': 50, 'hs4': '0904', 'hs_description': '冷冻蔬菜', 'tariff_base': 0.08, 'nutrition_score': 68, 'shelf_life_months': 24, 'storage_type': '常温'},
    'cn_baby_bok_choy': {'name_cn': '娃娃菜', 'name_en': 'Baby Bok Choy', 'category': 'produce', 'mid_category': 'fresh_veg', 'culture_group': 'cn', 'keyword': 'baby bok choy', 'base_sales': 62, 'price': 6, 'peak_month': 3, 'competition': 44, 'hs4': '0704', 'hs_description': '冷冻蔬菜', 'tariff_base': 0.08, 'nutrition_score': 82, 'shelf_life_months': 0.5, 'storage_type': '冷藏'},
    'cn_dried_persimmon': {'name_cn': '柿饼', 'name_en': 'Dried Persimmon', 'category': 'produce', 'mid_category': 'preserved', 'culture_group': 'cn', 'keyword': 'dried persimmon', 'base_sales': 70, 'price': 14, 'peak_month': 12, 'competition': 46, 'hs4': '0813', 'hs_description': '冷冻蔬菜', 'tariff_base': 0.08, 'nutrition_score': 74, 'shelf_life_months': 9, 'storage_type': '常温'},
    'intl_avocado': {'name_cn': '牛油果', 'name_en': 'Avocado', 'category': 'produce', 'mid_category': 'fresh_fruit', 'culture_group': 'intl', 'keyword': 'avocado', 'base_sales': 82, 'price': 14, 'peak_month': 6, 'competition': 58, 'hs4': '0804', 'hs_description': '冷冻蔬菜', 'tariff_base': 0.08, 'nutrition_score': 80, 'shelf_life_months': 1, 'storage_type': '冷藏'},
    'intl_blueberry': {'name_cn': '蓝莓', 'name_en': 'Blueberries', 'category': 'produce', 'mid_category': 'fresh_fruit', 'culture_group': 'intl', 'keyword': 'blueberries fresh', 'base_sales': 78, 'price': 12, 'peak_month': 5, 'competition': 56, 'hs4': '0810', 'hs_description': '冷冻蔬菜', 'tariff_base': 0.08, 'nutrition_score': 84, 'shelf_life_months': 1, 'storage_type': '冷藏'},
    'intl_sun_dried_tomato': {'name_cn': '番茄干', 'name_en': 'Sun-Dried Tomatoes', 'category': 'produce', 'mid_category': 'preserved', 'culture_group': 'intl', 'keyword': 'sun dried tomatoes', 'base_sales': 70, 'price': 10, 'peak_month': 6, 'competition': 50, 'hs4': '0712', 'hs_description': '冷冻蔬菜', 'tariff_base': 0.08, 'nutrition_score': 72, 'shelf_life_months': 12, 'storage_type': '常温'},
    'intl_olives': {'name_cn': '橄榄罐装', 'name_en': 'Canned Olives', 'category': 'produce', 'mid_category': 'preserved', 'culture_group': 'intl', 'keyword': 'canned olives', 'base_sales': 74, 'price': 7, 'peak_month': 12, 'competition': 52, 'hs4': '2005', 'hs_description': '冷冻蔬菜', 'tariff_base': 0.08, 'nutrition_score': 64, 'shelf_life_months': 24, 'storage_type': '常温'},
    'intl_sweet_potato_chips': {'name_cn': '红薯脆片', 'name_en': 'Sweet Potato Chips', 'category': 'produce', 'mid_category': 'preserved', 'culture_group': 'intl', 'keyword': 'sweet potato chips', 'base_sales': 72, 'price': 8, 'peak_month': 12, 'competition': 54, 'hs4': '2005', 'hs_description': '冷冻蔬菜', 'tariff_base': 0.08, 'nutrition_score': 70, 'shelf_life_months': 9, 'storage_type': '常温'},
    'intl_frozen_broccoli': {'name_cn': '冷冻西兰花', 'name_en': 'Frozen Broccoli', 'category': 'produce', 'mid_category': 'fresh_veg', 'culture_group': 'intl', 'keyword': 'frozen broccoli', 'base_sales': 68, 'price': 7, 'peak_month': 6, 'competition': 48, 'hs4': '0710', 'hs_description': '冷冻蔬菜', 'tariff_base': 0.08, 'nutrition_score': 80, 'shelf_life_months': 12, 'storage_type': '冷冻'},
    'cn_latiao': {'name_cn': '辣条', 'name_en': 'Spicy Wheat Strips', 'category': 'snack', 'mid_category': 'spicy', 'culture_group': 'cn', 'keyword': 'latiao spicy snack', 'base_sales': 92, 'price': 4, 'peak_month': 12, 'competition': 66, 'hs4': '1905', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 52, 'shelf_life_months': 9, 'storage_type': '常温'},
    'cn_guaiwei_dou': {'name_cn': '怪味豆', 'name_en': 'Spiced Peas', 'category': 'snack', 'mid_category': 'savory', 'culture_group': 'cn', 'keyword': 'guaiwei beans', 'base_sales': 78, 'price': 6, 'peak_month': 12, 'competition': 54, 'hs4': '2008', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 68, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_wuxiang_guazi': {'name_cn': '五香瓜子', 'name_en': 'Five-Spice Sunflower Seeds', 'category': 'snack', 'mid_category': 'savory', 'culture_group': 'cn', 'keyword': 'five spice sunflower seeds', 'base_sales': 84, 'price': 7, 'peak_month': 12, 'competition': 56, 'hs4': '1202', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 64, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_tanghulu': {'name_cn': '糖葫芦', 'name_en': 'Candied Hawthorn Skewers', 'category': 'snack', 'mid_category': 'sweet', 'culture_group': 'cn', 'keyword': 'tanghulu candied hawthorn', 'base_sales': 62, 'price': 8, 'peak_month': 12, 'competition': 48, 'hs4': '1704', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 70, 'shelf_life_months': 6, 'storage_type': '常温'},
    'cn_youzha_sanzi': {'name_cn': '油炸馓子', 'name_en': 'Fried Dough Twists', 'category': 'snack', 'mid_category': 'savory', 'culture_group': 'cn', 'keyword': 'chinese fried dough twists', 'base_sales': 68, 'price': 6, 'peak_month': 12, 'competition': 50, 'hs4': '1905', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 56, 'shelf_life_months': 9, 'storage_type': '常温'},
    'cn_pork_floss': {'name_cn': '猪肉松', 'name_en': 'Pork Floss', 'category': 'snack', 'mid_category': 'jerky', 'culture_group': 'cn', 'keyword': 'pork floss', 'base_sales': 76, 'price': 12, 'peak_month': 12, 'competition': 52, 'hs4': '1602', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 62, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_donggua_tang': {'name_cn': '冬瓜糖', 'name_en': 'Candied Winter Melon', 'category': 'snack', 'mid_category': 'sweet', 'culture_group': 'cn', 'keyword': 'candied winter melon', 'base_sales': 60, 'price': 7, 'peak_month': 12, 'competition': 46, 'hs4': '1704', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 66, 'shelf_life_months': 12, 'storage_type': '常温'},
    'intl_popcorn': {'name_cn': '爆米花', 'name_en': 'Popcorn', 'category': 'snack', 'mid_category': 'savory', 'culture_group': 'intl', 'keyword': 'popcorn kernels', 'base_sales': 82, 'price': 5, 'peak_month': 11, 'competition': 54, 'hs4': '1904', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 62, 'shelf_life_months': 12, 'storage_type': '常温'},
    'intl_chocolate_bar': {'name_cn': '巧克力棒', 'name_en': 'Chocolate Bar', 'category': 'snack', 'mid_category': 'sweet', 'culture_group': 'intl', 'keyword': 'chocolate bar', 'base_sales': 88, 'price': 6, 'peak_month': 12, 'competition': 64, 'hs4': '1806', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 58, 'shelf_life_months': 18, 'storage_type': '常温'},
    'intl_gummy_bears': {'name_cn': '小熊软糖', 'name_en': 'Gummy Bears', 'category': 'snack', 'mid_category': 'sweet', 'culture_group': 'intl', 'keyword': 'gummy bears', 'base_sales': 74, 'price': 5, 'peak_month': 12, 'competition': 58, 'hs4': '1704', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 50, 'shelf_life_months': 24, 'storage_type': '常温'},
    'intl_meat_sticks': {'name_cn': '肉干棒', 'name_en': 'Meat Snack Sticks', 'category': 'snack', 'mid_category': 'jerky', 'culture_group': 'intl', 'keyword': 'meat snack sticks', 'base_sales': 80, 'price': 9, 'peak_month': 12, 'competition': 56, 'hs4': '1602', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 64, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_hickory_nuts': {'name_cn': '临安山核桃', 'name_en': "Lin'an Hickory Nuts", 'category': 'nuts', 'mid_category': 'nut', 'culture_group': 'cn', 'keyword': 'linan hickory nuts', 'base_sales': 76, 'price': 22, 'peak_month': 12, 'competition': 56, 'hs4': '0802', 'hs_description': '其他坚果', 'tariff_base': 0.08, 'nutrition_score': 78, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_snake_gourd_seeds': {'name_cn': '吊瓜子', 'name_en': 'Snake Gourd Seeds', 'category': 'nuts', 'mid_category': 'seed', 'culture_group': 'cn', 'keyword': 'snake gourd seeds', 'base_sales': 66, 'price': 12, 'peak_month': 1, 'competition': 50, 'hs4': '1202', 'hs_description': '其他坚果', 'tariff_base': 0.08, 'nutrition_score': 70, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_xinjiang_dates': {'name_cn': '新疆红枣', 'name_en': 'Xinjiang Red Dates', 'category': 'nuts', 'mid_category': 'dried_fruit', 'culture_group': 'cn', 'keyword': 'xinjiang red dates', 'base_sales': 86, 'price': 9, 'peak_month': 12, 'competition': 50, 'hs4': '0813', 'hs_description': '其他坚果', 'tariff_base': 0.08, 'nutrition_score': 82, 'shelf_life_months': 18, 'storage_type': '常温'},
    'cn_candied_jujube': {'name_cn': '金丝蜜枣', 'name_en': 'Candied Jujube', 'category': 'nuts', 'mid_category': 'dried_fruit', 'culture_group': 'cn', 'keyword': 'candied jujube', 'base_sales': 72, 'price': 10, 'peak_month': 12, 'competition': 48, 'hs4': '1704', 'hs_description': '其他坚果', 'tariff_base': 0.08, 'nutrition_score': 72, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_pine_nuts': {'name_cn': '松子', 'name_en': 'Pine Nuts', 'category': 'nuts', 'mid_category': 'seed', 'culture_group': 'cn', 'keyword': 'pine nuts', 'base_sales': 70, 'price': 28, 'peak_month': 12, 'competition': 54, 'hs4': '0802', 'hs_description': '其他坚果', 'tariff_base': 0.08, 'nutrition_score': 76, 'shelf_life_months': 12, 'storage_type': '常温'},
    'intl_almonds': {'name_cn': '巴旦木', 'name_en': 'Almonds', 'category': 'nuts', 'mid_category': 'nut', 'culture_group': 'intl', 'keyword': 'almonds raw', 'base_sales': 90, 'price': 14, 'peak_month': 12, 'competition': 58, 'hs4': '0802', 'hs_description': '其他坚果', 'tariff_base': 0.08, 'nutrition_score': 80, 'shelf_life_months': 18, 'storage_type': '常温'},
    'intl_cashews': {'name_cn': '腰果', 'name_en': 'Cashews', 'category': 'nuts', 'mid_category': 'nut', 'culture_group': 'intl', 'keyword': 'cashews roasted', 'base_sales': 84, 'price': 16, 'peak_month': 12, 'competition': 56, 'hs4': '0802', 'hs_description': '其他坚果', 'tariff_base': 0.08, 'nutrition_score': 76, 'shelf_life_months': 12, 'storage_type': '常温'},
    'intl_walnuts': {'name_cn': '核桃', 'name_en': 'Walnuts', 'category': 'nuts', 'mid_category': 'nut', 'culture_group': 'intl', 'keyword': 'walnuts', 'base_sales': 82, 'price': 15, 'peak_month': 11, 'competition': 54, 'hs4': '0802', 'hs_description': '其他坚果', 'tariff_base': 0.08, 'nutrition_score': 78, 'shelf_life_months': 18, 'storage_type': '常温'},
    'intl_raisins': {'name_cn': '葡萄干', 'name_en': 'Raisins', 'category': 'nuts', 'mid_category': 'dried_fruit', 'culture_group': 'intl', 'keyword': 'raisins', 'base_sales': 80, 'price': 7, 'peak_month': 12, 'competition': 52, 'hs4': '0806', 'hs_description': '其他坚果', 'tariff_base': 0.08, 'nutrition_score': 72, 'shelf_life_months': 18, 'storage_type': '常温'},
    'intl_dried_mango': {'name_cn': '芒果干', 'name_en': 'Dried Mango', 'category': 'nuts', 'mid_category': 'dried_fruit', 'culture_group': 'intl', 'keyword': 'dried mango', 'base_sales': 76, 'price': 9, 'peak_month': 12, 'competition': 54, 'hs4': '0813', 'hs_description': '其他坚果', 'tariff_base': 0.08, 'nutrition_score': 70, 'shelf_life_months': 12, 'storage_type': '常温'},
    'intl_pumpkin_seeds': {'name_cn': '南瓜籽', 'name_en': 'Pumpkin Seeds', 'category': 'nuts', 'mid_category': 'seed', 'culture_group': 'intl', 'keyword': 'pumpkin seeds', 'base_sales': 78, 'price': 8, 'peak_month': 12, 'competition': 52, 'hs4': '1202', 'hs_description': '其他坚果', 'tariff_base': 0.08, 'nutrition_score': 74, 'shelf_life_months': 18, 'storage_type': '常温'},
    'cn_laoganma': {'name_cn': '老干妈辣椒酱', 'name_en': 'Lao Gan Ma Chili Crisp', 'category': 'sauce', 'mid_category': 'chili_spice', 'culture_group': 'cn', 'keyword': 'laoganma chili sauce', 'base_sales': 94, 'price': 7, 'peak_month': 12, 'competition': 66, 'hs4': '2103', 'hs_description': '调味汁及其制品', 'tariff_base': 0.1, 'nutrition_score': 56, 'shelf_life_months': 18, 'storage_type': '常温'},
    'cn_pixian_doubanjiang': {'name_cn': '郫县豆瓣酱', 'name_en': 'Pixian Doubanjiang', 'category': 'sauce', 'mid_category': 'soy_fermented', 'culture_group': 'cn', 'keyword': 'pixian doubanjiang', 'base_sales': 86, 'price': 8, 'peak_month': 12, 'competition': 56, 'hs4': '2103', 'hs_description': '调味汁及其制品', 'tariff_base': 0.1, 'nutrition_score': 62, 'shelf_life_months': 18, 'storage_type': '常温'},
    'cn_light_soy_sauce': {'name_cn': '生抽酱油', 'name_en': 'Light Soy Sauce', 'category': 'sauce', 'mid_category': 'soy_fermented', 'culture_group': 'cn', 'keyword': 'light soy sauce', 'base_sales': 90, 'price': 6, 'peak_month': 12, 'competition': 52, 'hs4': '2103', 'hs_description': '调味汁及其制品', 'tariff_base': 0.1, 'nutrition_score': 58, 'shelf_life_months': 24, 'storage_type': '常温'},
    'cn_chinkiang_vinegar': {'name_cn': '镇江香醋', 'name_en': 'Chinkiang Vinegar', 'category': 'sauce', 'mid_category': 'soy_fermented', 'culture_group': 'cn', 'keyword': 'chinkiang black vinegar', 'base_sales': 82, 'price': 7, 'peak_month': 11, 'competition': 50, 'hs4': '2209', 'hs_description': '调味汁及其制品', 'tariff_base': 0.1, 'nutrition_score': 64, 'shelf_life_months': 36, 'storage_type': '常温'},
    'cn_sesame_paste': {'name_cn': '芝麻酱', 'name_en': 'Sesame Paste', 'category': 'sauce', 'mid_category': 'cooking', 'culture_group': 'cn', 'keyword': 'chinese sesame paste', 'base_sales': 78, 'price': 10, 'peak_month': 11, 'competition': 52, 'hs4': '2008', 'hs_description': '调味汁及其制品', 'tariff_base': 0.1, 'nutrition_score': 72, 'shelf_life_months': 18, 'storage_type': '常温'},
    'cn_fuling_zhacai': {'name_cn': '涪陵榨菜', 'name_en': 'Fuling Zhacai', 'category': 'sauce', 'mid_category': 'dipping', 'culture_group': 'cn', 'keyword': 'zhacai pickled mustard', 'base_sales': 80, 'price': 5, 'peak_month': 1, 'competition': 48, 'hs4': '2005', 'hs_description': '调味汁及其制品', 'tariff_base': 0.1, 'nutrition_score': 66, 'shelf_life_months': 12, 'storage_type': '常温'},
    'intl_ketchup': {'name_cn': '番茄酱', 'name_en': 'Ketchup', 'category': 'sauce', 'mid_category': 'dipping', 'culture_group': 'intl', 'keyword': 'ketchup', 'base_sales': 86, 'price': 4, 'peak_month': 11, 'competition': 50, 'hs4': '2103', 'hs_description': '调味汁及其制品', 'tariff_base': 0.1, 'nutrition_score': 54, 'shelf_life_months': 18, 'storage_type': '常温'},
    'intl_dijon_mustard': {'name_cn': '第戎芥末酱', 'name_en': 'Dijon Mustard', 'category': 'sauce', 'mid_category': 'dipping', 'culture_group': 'intl', 'keyword': 'dijon mustard', 'base_sales': 70, 'price': 6, 'peak_month': 11, 'competition': 48, 'hs4': '2103', 'hs_description': '调味汁及其制品', 'tariff_base': 0.1, 'nutrition_score': 60, 'shelf_life_months': 18, 'storage_type': '常温'},
    'intl_japanese_soy_sauce': {'name_cn': '日本酱油', 'name_en': 'Japanese Soy Sauce', 'category': 'sauce', 'mid_category': 'soy_fermented', 'culture_group': 'intl', 'keyword': 'japanese soy sauce', 'base_sales': 84, 'price': 8, 'peak_month': 12, 'competition': 52, 'hs4': '2103', 'hs_description': '调味汁及其制品', 'tariff_base': 0.1, 'nutrition_score': 58, 'shelf_life_months': 24, 'storage_type': '常温'},
    'intl_pesto': {'name_cn': '青酱', 'name_en': 'Pesto Sauce', 'category': 'sauce', 'mid_category': 'cooking', 'culture_group': 'intl', 'keyword': 'pesto sauce jar', 'base_sales': 64, 'price': 12, 'peak_month': 6, 'competition': 50, 'hs4': '2103', 'hs_description': '调味汁及其制品', 'tariff_base': 0.1, 'nutrition_score': 62, 'shelf_life_months': 12, 'storage_type': '冷藏'},
    'intl_sriracha': {'name_cn': '是拉差辣酱', 'name_en': 'Sriracha', 'category': 'sauce', 'mid_category': 'chili_spice', 'culture_group': 'intl', 'keyword': 'sriracha hot sauce', 'base_sales': 82, 'price': 6, 'peak_month': 12, 'competition': 56, 'hs4': '2103', 'hs_description': '调味汁及其制品', 'tariff_base': 0.1, 'nutrition_score': 56, 'shelf_life_months': 18, 'storage_type': '常温'},
    'cn_longjing': {'name_cn': '西湖龙井', 'name_en': 'West Lake Longjing Tea', 'category': 'beverage', 'mid_category': 'tea', 'culture_group': 'cn', 'keyword': 'longjing green tea', 'base_sales': 70, 'price': 28, 'peak_month': 4, 'competition': 62, 'hs4': '0902', 'hs_description': '茶', 'tariff_base': 0.07, 'nutrition_score': 76, 'shelf_life_months': 24, 'storage_type': '常温'},
    'cn_tieguanyin': {'name_cn': '铁观音', 'name_en': 'Tieguanyin Oolong', 'category': 'beverage', 'mid_category': 'tea', 'culture_group': 'cn', 'keyword': 'tieguanyin oolong tea', 'base_sales': 68, 'price': 24, 'peak_month': 4, 'competition': 58, 'hs4': '0902', 'hs_description': '茶', 'tariff_base': 0.07, 'nutrition_score': 76, 'shelf_life_months': 24, 'storage_type': '常温'},
    'cn_puerh': {'name_cn': '普洱熟茶', 'name_en': "Pu'er Ripe Tea", 'category': 'beverage', 'mid_category': 'tea', 'culture_group': 'cn', 'keyword': 'puerh tea cake', 'base_sales': 72, 'price': 26, 'peak_month': 12, 'competition': 60, 'hs4': '0902', 'hs_description': '茶', 'tariff_base': 0.07, 'nutrition_score': 74, 'shelf_life_months': 36, 'storage_type': '常温'},
    'cn_osmanthus_oolong': {'name_cn': '桂花乌龙', 'name_en': 'Osmanthus Oolong', 'category': 'beverage', 'mid_category': 'herbal', 'culture_group': 'cn', 'keyword': 'osmanthus oolong tea', 'base_sales': 74, 'price': 16, 'peak_month': 4, 'competition': 54, 'hs4': '0902', 'hs_description': '茶', 'tariff_base': 0.07, 'nutrition_score': 78, 'shelf_life_months': 18, 'storage_type': '常温'},
    'cn_baijiu_mini': {'name_cn': '小瓶白酒', 'name_en': 'Baijiu Mini Bottles', 'category': 'beverage', 'mid_category': 'alcohol', 'culture_group': 'cn', 'keyword': 'baijiu liquor mini', 'base_sales': 66, 'price': 18, 'peak_month': 12, 'competition': 58, 'hs4': '2208', 'hs_description': '茶', 'tariff_base': 0.07, 'nutrition_score': 48, 'shelf_life_months': 36, 'storage_type': '常温'},
    'intl_earl_grey': {'name_cn': '伯爵红茶', 'name_en': 'Earl Grey Tea', 'category': 'beverage', 'mid_category': 'tea', 'culture_group': 'intl', 'keyword': 'earl grey tea', 'base_sales': 76, 'price': 14, 'peak_month': 12, 'competition': 54, 'hs4': '0902', 'hs_description': '茶', 'tariff_base': 0.07, 'nutrition_score': 74, 'shelf_life_months': 24, 'storage_type': '常温'},
    'intl_matcha': {'name_cn': '抹茶粉', 'name_en': 'Matcha Powder', 'category': 'beverage', 'mid_category': 'tea', 'culture_group': 'intl', 'keyword': 'matcha powder', 'base_sales': 78, 'price': 20, 'peak_month': 6, 'competition': 58, 'hs4': '0902', 'hs_description': '茶', 'tariff_base': 0.07, 'nutrition_score': 80, 'shelf_life_months': 18, 'storage_type': '常温'},
    'intl_instant_coffee': {'name_cn': '速溶咖啡', 'name_en': 'Instant Coffee', 'category': 'beverage', 'mid_category': 'drink', 'culture_group': 'intl', 'keyword': 'instant coffee', 'base_sales': 88, 'price': 9, 'peak_month': 12, 'competition': 62, 'hs4': '2101', 'hs_description': '茶', 'tariff_base': 0.07, 'nutrition_score': 60, 'shelf_life_months': 24, 'storage_type': '常温'},
    'intl_hot_chocolate': {'name_cn': '热巧克力粉', 'name_en': 'Hot Chocolate Mix', 'category': 'beverage', 'mid_category': 'drink', 'culture_group': 'intl', 'keyword': 'hot chocolate powder', 'base_sales': 74, 'price': 8, 'peak_month': 12, 'competition': 56, 'hs4': '1806', 'hs_description': '茶', 'tariff_base': 0.07, 'nutrition_score': 58, 'shelf_life_months': 18, 'storage_type': '常温'},
    'intl_sake': {'name_cn': '清酒', 'name_en': 'Sake', 'category': 'beverage', 'mid_category': 'alcohol', 'culture_group': 'intl', 'keyword': 'sake bottle', 'base_sales': 64, 'price': 18, 'peak_month': 12, 'competition': 54, 'hs4': '2206', 'hs_description': '茶', 'tariff_base': 0.07, 'nutrition_score': 52, 'shelf_life_months': 24, 'storage_type': '常温'},
    'intl_hibiscus_tea': {'name_cn': '洛神花茶', 'name_en': 'Hibiscus Tea', 'category': 'beverage', 'mid_category': 'herbal', 'culture_group': 'intl', 'keyword': 'hibiscus tea', 'base_sales': 70, 'price': 10, 'peak_month': 12, 'competition': 52, 'hs4': '0902', 'hs_description': '茶', 'tariff_base': 0.07, 'nutrition_score': 74, 'shelf_life_months': 18, 'storage_type': '常温'},
    'cn_egg_yolk_pastry': {'name_cn': '蛋黄酥', 'name_en': 'Egg Yolk Pastry', 'category': 'bakery', 'mid_category': 'cake', 'culture_group': 'cn', 'keyword': 'egg yolk pastry chinese', 'base_sales': 74, 'price': 14, 'peak_month': 9, 'competition': 56, 'hs4': '1905', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 64, 'shelf_life_months': 6, 'storage_type': '常温'},
    'cn_sesame_balls': {'name_cn': '麻球', 'name_en': 'Fried Sesame Balls', 'category': 'bakery', 'mid_category': 'cake', 'culture_group': 'cn', 'keyword': 'chinese sesame balls', 'base_sales': 66, 'price': 8, 'peak_month': 2, 'competition': 50, 'hs4': '1905', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 60, 'shelf_life_months': 3, 'storage_type': '常温'},
    'cn_green_bean_cake': {'name_cn': '绿豆糕', 'name_en': 'Green Bean Cake', 'category': 'bakery', 'mid_category': 'cake', 'culture_group': 'cn', 'keyword': 'green bean cake', 'base_sales': 70, 'price': 10, 'peak_month': 6, 'competition': 50, 'hs4': '1905', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 68, 'shelf_life_months': 3, 'storage_type': '常温'},
    'cn_almond_cookies': {'name_cn': '杏仁酥', 'name_en': 'Almond Cookies', 'category': 'bakery', 'mid_category': 'biscuit', 'culture_group': 'cn', 'keyword': 'chinese almond cookies', 'base_sales': 72, 'price': 12, 'peak_month': 12, 'competition': 52, 'hs4': '1905', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 66, 'shelf_life_months': 6, 'storage_type': '常温'},
    'cn_mooncake': {'name_cn': '广式月饼', 'name_en': 'Cantonese Mooncake', 'category': 'bakery', 'mid_category': 'mooncake', 'culture_group': 'cn', 'keyword': 'mooncake cantonese', 'base_sales': 78, 'price': 18, 'peak_month': 8, 'competition': 58, 'hs4': '1905', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 62, 'shelf_life_months': 4, 'storage_type': '常温'},
    'intl_croissant': {'name_cn': '牛角包', 'name_en': 'Croissant', 'category': 'bakery', 'mid_category': 'cake', 'culture_group': 'intl', 'keyword': 'croissant', 'base_sales': 72, 'price': 6, 'peak_month': 1, 'competition': 56, 'hs4': '1905', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 64, 'shelf_life_months': 0.3, 'storage_type': '冷藏'},
    'intl_macaron': {'name_cn': '马卡龙', 'name_en': 'Macarons', 'category': 'bakery', 'mid_category': 'cake', 'culture_group': 'intl', 'keyword': 'macarons', 'base_sales': 58, 'price': 16, 'peak_month': 12, 'competition': 50, 'hs4': '1905', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 58, 'shelf_life_months': 1, 'storage_type': '冷藏'},
    'intl_biscotti': {'name_cn': '意式杏仁饼', 'name_en': 'Biscotti', 'category': 'bakery', 'mid_category': 'biscuit', 'culture_group': 'intl', 'keyword': 'biscotti', 'base_sales': 66, 'price': 12, 'peak_month': 12, 'competition': 50, 'hs4': '1905', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 66, 'shelf_life_months': 12, 'storage_type': '常温'},
    'intl_cookie_jar': {'name_cn': '曲奇礼盒', 'name_en': 'Cookie Gift Jar', 'category': 'bakery', 'mid_category': 'biscuit', 'culture_group': 'intl', 'keyword': 'cookie gift jar', 'base_sales': 80, 'price': 11, 'peak_month': 12, 'competition': 56, 'hs4': '1905', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 62, 'shelf_life_months': 9, 'storage_type': '常温'},
    'intl_panettone': {'name_cn': '潘纳托尼', 'name_en': 'Panettone', 'category': 'bakery', 'mid_category': 'cake', 'culture_group': 'intl', 'keyword': 'panettone', 'base_sales': 60, 'price': 20, 'peak_month': 12, 'competition': 54, 'hs4': '1905', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 60, 'shelf_life_months': 6, 'storage_type': '常温'},
    'intl_frozen_croissant_dough': {'name_cn': '冷冻可颂面团', 'name_en': 'Frozen Croissant Dough', 'category': 'bakery', 'mid_category': 'cake', 'culture_group': 'intl', 'keyword': 'frozen croissant dough', 'base_sales': 68, 'price': 9, 'peak_month': 12, 'competition': 52, 'hs4': '1905', 'hs_description': '面包、糕点、饼干', 'tariff_base': 0.1, 'nutrition_score': 64, 'shelf_life_months': 9, 'storage_type': '冷冻'},
    'cn_self_heating_hotpot': {'name_cn': '自热火锅', 'name_en': 'Self-Heating Hot Pot', 'category': 'instant', 'mid_category': 'rice_dish', 'culture_group': 'cn', 'keyword': 'self heating hotpot', 'base_sales': 90, 'price': 18, 'peak_month': 12, 'competition': 64, 'hs4': '2104', 'hs_description': '面食', 'tariff_base': 0.1, 'nutrition_score': 58, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_beef_instant_noodles': {'name_cn': '红烧牛肉方便面', 'name_en': 'Braised Beef Instant Noodles', 'category': 'instant', 'mid_category': 'noodle', 'culture_group': 'cn', 'keyword': 'braised beef instant noodles', 'base_sales': 92, 'price': 5, 'peak_month': 12, 'competition': 60, 'hs4': '1902', 'hs_description': '面食', 'tariff_base': 0.1, 'nutrition_score': 54, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_chongqing_suanlafen': {'name_cn': '重庆酸辣粉', 'name_en': 'Chongqing Suan La Fen', 'category': 'instant', 'mid_category': 'noodle', 'culture_group': 'cn', 'keyword': 'chongqing hot sour noodles', 'base_sales': 84, 'price': 8, 'peak_month': 12, 'competition': 58, 'hs4': '1902', 'hs_description': '面食', 'tariff_base': 0.1, 'nutrition_score': 60, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_instant_congee': {'name_cn': '速食粥', 'name_en': 'Instant Congee', 'category': 'instant', 'mid_category': 'soup', 'culture_group': 'cn', 'keyword': 'instant congee', 'base_sales': 74, 'price': 6, 'peak_month': 1, 'competition': 50, 'hs4': '1904', 'hs_description': '面食', 'tariff_base': 0.1, 'nutrition_score': 68, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_self_heating_rice': {'name_cn': '自热米饭', 'name_en': 'Self-Heating Rice Bowl', 'category': 'instant', 'mid_category': 'rice_dish', 'culture_group': 'cn', 'keyword': 'self heating rice', 'base_sales': 86, 'price': 10, 'peak_month': 12, 'competition': 60, 'hs4': '2104', 'hs_description': '面食', 'tariff_base': 0.1, 'nutrition_score': 60, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_frozen_wontons': {'name_cn': '速冻小馄饨', 'name_en': 'Frozen Wontons', 'category': 'instant', 'mid_category': 'noodle', 'culture_group': 'cn', 'keyword': 'frozen wontons', 'base_sales': 80, 'price': 9, 'peak_month': 12, 'competition': 54, 'hs4': '1902', 'hs_description': '面食', 'tariff_base': 0.1, 'nutrition_score': 66, 'shelf_life_months': 9, 'storage_type': '冷冻'},
    'intl_cup_ramen': {'name_cn': '日式杯面', 'name_en': 'Instant Cup Ramen', 'category': 'instant', 'mid_category': 'noodle', 'culture_group': 'intl', 'keyword': 'cup ramen', 'base_sales': 86, 'price': 4, 'peak_month': 12, 'competition': 58, 'hs4': '1902', 'hs_description': '面食', 'tariff_base': 0.1, 'nutrition_score': 54, 'shelf_life_months': 12, 'storage_type': '常温'},
    'intl_canned_soup': {'name_cn': '浓汤罐头', 'name_en': 'Canned Cream Soup', 'category': 'instant', 'mid_category': 'soup', 'culture_group': 'intl', 'keyword': 'canned soup', 'base_sales': 72, 'price': 7, 'peak_month': 12, 'competition': 52, 'hs4': '2005', 'hs_description': '面食', 'tariff_base': 0.1, 'nutrition_score': 64, 'shelf_life_months': 24, 'storage_type': '常温'},
    'intl_mac_cheese': {'name_cn': '芝士通心粉', 'name_en': 'Mac & Cheese', 'category': 'instant', 'mid_category': 'noodle', 'culture_group': 'intl', 'keyword': 'mac and cheese box', 'base_sales': 78, 'price': 8, 'peak_month': 12, 'competition': 56, 'hs4': '1902', 'hs_description': '面食', 'tariff_base': 0.1, 'nutrition_score': 58, 'shelf_life_months': 12, 'storage_type': '常温'},
    'intl_canned_chili': {'name_cn': '辣椒豆罐头', 'name_en': 'Canned Chili Beans', 'category': 'instant', 'mid_category': 'canned_meals', 'culture_group': 'intl', 'keyword': 'canned chili beans', 'base_sales': 70, 'price': 7, 'peak_month': 12, 'competition': 52, 'hs4': '2005', 'hs_description': '面食', 'tariff_base': 0.1, 'nutrition_score': 66, 'shelf_life_months': 24, 'storage_type': '常温'},
    'intl_instant_oatmeal': {'name_cn': '即食燕麦粥', 'name_en': 'Instant Oatmeal Packets', 'category': 'instant', 'mid_category': 'soup', 'culture_group': 'intl', 'keyword': 'instant oatmeal packets', 'base_sales': 76, 'price': 7, 'peak_month': 1, 'competition': 52, 'hs4': '1904', 'hs_description': '面食', 'tariff_base': 0.1, 'nutrition_score': 76, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_ningxia_goji': {'name_cn': '宁夏枸杞', 'name_en': 'Ningxia Goji Berries', 'category': 'wellness', 'mid_category': 'supplement_food', 'culture_group': 'cn', 'keyword': 'ningxia goji berries', 'base_sales': 84, 'price': 14, 'peak_month': 12, 'competition': 54, 'hs4': '1211', 'hs_description': '主要用作香料、药料或杀虫、杀菌的植物', 'tariff_base': 0.06, 'nutrition_score': 82, 'shelf_life_months': 18, 'storage_type': '常温'},
    'cn_black_sesame_balls': {'name_cn': '黑芝麻丸', 'name_en': 'Black Sesame Balls', 'category': 'wellness', 'mid_category': 'supplement_food', 'culture_group': 'cn', 'keyword': 'black sesame balls', 'base_sales': 78, 'price': 16, 'peak_month': 12, 'competition': 56, 'hs4': '1806', 'hs_description': '主要用作香料、药料或杀虫、杀菌的植物', 'tariff_base': 0.06, 'nutrition_score': 76, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_ejiao_cake': {'name_cn': '阿胶糕', 'name_en': 'Ejiao Cake', 'category': 'wellness', 'mid_category': 'supplement_food', 'culture_group': 'cn', 'keyword': 'ejiao cake', 'base_sales': 62, 'price': 30, 'peak_month': 12, 'competition': 58, 'hs4': '2106', 'hs_description': '主要用作香料、药料或杀虫、杀菌的植物', 'tariff_base': 0.06, 'nutrition_score': 64, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_snow_fungus': {'name_cn': '银耳', 'name_en': 'Snow Fungus', 'category': 'wellness', 'mid_category': 'herb_soup', 'culture_group': 'cn', 'keyword': 'snow fungus', 'base_sales': 74, 'price': 9, 'peak_month': 1, 'competition': 50, 'hs4': '0712', 'hs_description': '主要用作香料、药料或杀虫、杀菌的植物', 'tariff_base': 0.06, 'nutrition_score': 80, 'shelf_life_months': 18, 'storage_type': '常温'},
    'cn_goji_honey': {'name_cn': '枸杞蜂蜜', 'name_en': 'Goji Honey', 'category': 'wellness', 'mid_category': 'honey', 'culture_group': 'cn', 'keyword': 'goji honey', 'base_sales': 70, 'price': 15, 'peak_month': 12, 'competition': 52, 'hs4': '0409', 'hs_description': '主要用作香料、药料或杀虫、杀菌的植物', 'tariff_base': 0.06, 'nutrition_score': 78, 'shelf_life_months': 24, 'storage_type': '常温'},
    'cn_chinese_yam': {'name_cn': '铁棍山药', 'name_en': 'Chinese Yam', 'category': 'wellness', 'mid_category': 'herb_soup', 'culture_group': 'cn', 'keyword': 'chinese yam dried', 'base_sales': 68, 'price': 11, 'peak_month': 1, 'competition': 50, 'hs4': '0714', 'hs_description': '主要用作香料、药料或杀虫、杀菌的植物', 'tariff_base': 0.06, 'nutrition_score': 78, 'shelf_life_months': 18, 'storage_type': '常温'},
    'cn_hawthorn_slices': {'name_cn': '山楂片', 'name_en': 'Dried Hawthorn Slices', 'category': 'wellness', 'mid_category': 'supplement_food', 'culture_group': 'cn', 'keyword': 'dried hawthorn slices', 'base_sales': 76, 'price': 8, 'peak_month': 12, 'competition': 50, 'hs4': '2008', 'hs_description': '主要用作香料、药料或杀虫、杀菌的植物', 'tariff_base': 0.06, 'nutrition_score': 76, 'shelf_life_months': 12, 'storage_type': '常温'},
    'intl_manuka_honey': {'name_cn': '麦卢卡蜂蜜', 'name_en': 'Manuka Honey', 'category': 'wellness', 'mid_category': 'honey', 'culture_group': 'intl', 'keyword': 'manuka honey', 'base_sales': 66, 'price': 34, 'peak_month': 12, 'competition': 58, 'hs4': '0409', 'hs_description': '主要用作香料、药料或杀虫、杀菌的植物', 'tariff_base': 0.06, 'nutrition_score': 74, 'shelf_life_months': 24, 'storage_type': '常温'},
    'intl_collagen_powder': {'name_cn': '胶原蛋白粉', 'name_en': 'Collagen Powder', 'category': 'wellness', 'mid_category': 'supplement_food', 'culture_group': 'intl', 'keyword': 'collagen powder', 'base_sales': 58, 'price': 26, 'peak_month': 12, 'competition': 56, 'hs4': '2106', 'hs_description': '主要用作香料、药料或杀虫、杀菌的植物', 'tariff_base': 0.06, 'nutrition_score': 62, 'shelf_life_months': 18, 'storage_type': '常温'},
    'intl_maca_powder': {'name_cn': '玛卡粉', 'name_en': 'Maca Powder', 'category': 'wellness', 'mid_category': 'supplement_food', 'culture_group': 'intl', 'keyword': 'maca powder', 'base_sales': 52, 'price': 18, 'peak_month': 12, 'competition': 50, 'hs4': '1211', 'hs_description': '主要用作香料、药料或杀虫、杀菌的植物', 'tariff_base': 0.06, 'nutrition_score': 66, 'shelf_life_months': 24, 'storage_type': '常温'},
    'intl_chia_seeds': {'name_cn': '奇亚籽', 'name_en': 'Chia Seeds', 'category': 'wellness', 'mid_category': 'supplement_food', 'culture_group': 'intl', 'keyword': 'chia seeds', 'base_sales': 70, 'price': 12, 'peak_month': 12, 'competition': 52, 'hs4': '1207', 'hs_description': '主要用作香料、药料或杀虫、杀菌的植物', 'tariff_base': 0.06, 'nutrition_score': 82, 'shelf_life_months': 24, 'storage_type': '常温'},
    'cn_spicy_gluten': {'name_cn': '麻辣面筋', 'name_en': 'Spicy Gluten Snack', 'category': 'vegetarian', 'mid_category': 'gluten', 'culture_group': 'cn', 'keyword': 'spicy gluten', 'base_sales': 74, 'price': 7, 'peak_month': 12, 'competition': 56, 'hs4': '1905', 'hs_description': '其他税号未列名食品', 'tariff_base': 0.09, 'nutrition_score': 58, 'shelf_life_months': 9, 'storage_type': '常温'},
    'cn_braised_gluten': {'name_cn': '红烧面筋', 'name_en': 'Braised Gluten Puffs', 'category': 'vegetarian', 'mid_category': 'gluten', 'culture_group': 'cn', 'keyword': 'braised gluten puffs', 'base_sales': 70, 'price': 9, 'peak_month': 12, 'competition': 52, 'hs4': '1905', 'hs_description': '其他税号未列名食品', 'tariff_base': 0.09, 'nutrition_score': 62, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_su_rou': {'name_cn': '素肉', 'name_en': 'Vegetarian Meat Snack', 'category': 'vegetarian', 'mid_category': 'plant_protein', 'culture_group': 'cn', 'keyword': 'vegetarian meat snack', 'base_sales': 72, 'price': 10, 'peak_month': 12, 'competition': 54, 'hs4': '2106', 'hs_description': '其他税号未列名食品', 'tariff_base': 0.09, 'nutrition_score': 64, 'shelf_life_months': 12, 'storage_type': '常温'},
    'cn_liangpi': {'name_cn': '凉皮', 'name_en': 'Cold Skin Noodles', 'category': 'vegetarian', 'mid_category': 'gluten', 'culture_group': 'cn', 'keyword': 'liangpi cold noodles', 'base_sales': 76, 'price': 6, 'peak_month': 6, 'competition': 52, 'hs4': '1902', 'hs_description': '其他税号未列名食品', 'tariff_base': 0.09, 'nutrition_score': 66, 'shelf_life_months': 1, 'storage_type': '冷藏'},
    'intl_firm_tofu': {'name_cn': '硬豆腐', 'name_en': 'Firm Tofu', 'category': 'vegetarian', 'mid_category': 'plant_protein', 'culture_group': 'intl', 'keyword': 'firm tofu', 'base_sales': 80, 'price': 5, 'peak_month': 3, 'competition': 50, 'hs4': '2008', 'hs_description': '其他税号未列名食品', 'tariff_base': 0.09, 'nutrition_score': 74, 'shelf_life_months': 1, 'storage_type': '冷藏'},
    'intl_tempeh': {'name_cn': '天贝', 'name_en': 'Tempeh', 'category': 'vegetarian', 'mid_category': 'plant_protein', 'culture_group': 'intl', 'keyword': 'tempeh', 'base_sales': 64, 'price': 9, 'peak_month': 6, 'competition': 48, 'hs4': '2106', 'hs_description': '其他税号未列名食品', 'tariff_base': 0.09, 'nutrition_score': 78, 'shelf_life_months': 1, 'storage_type': '冷藏'},
    'intl_seitan': {'name_cn': '素肉筋', 'name_en': 'Seitan', 'category': 'vegetarian', 'mid_category': 'gluten', 'culture_group': 'intl', 'keyword': 'seitan', 'base_sales': 62, 'price': 10, 'peak_month': 6, 'competition': 50, 'hs4': '2106', 'hs_description': '其他税号未列名食品', 'tariff_base': 0.09, 'nutrition_score': 70, 'shelf_life_months': 6, 'storage_type': '冷藏'},
    'intl_plant_burger': {'name_cn': '植物汉堡排', 'name_en': 'Plant-Based Burger Patties', 'category': 'vegetarian', 'mid_category': 'plant_protein', 'culture_group': 'intl', 'keyword': 'plant based burger patties', 'base_sales': 72, 'price': 14, 'peak_month': 6, 'competition': 56, 'hs4': '2106', 'hs_description': '其他税号未列名食品', 'tariff_base': 0.09, 'nutrition_score': 66, 'shelf_life_months': 6, 'storage_type': '冷冻'},
    'intl_hummus': {'name_cn': '鹰嘴豆泥', 'name_en': 'Hummus', 'category': 'vegetarian', 'mid_category': 'plant_protein', 'culture_group': 'intl', 'keyword': 'hummus', 'base_sales': 74, 'price': 6, 'peak_month': 6, 'competition': 52, 'hs4': '2008', 'hs_description': '其他税号未列名食品', 'tariff_base': 0.09, 'nutrition_score': 70, 'shelf_life_months': 0.5, 'storage_type': '冷藏'},
    'intl_halal_jerky': {'name_cn': '清真牛肉干', 'name_en': 'Halal Beef Jerky', 'category': 'vegetarian', 'mid_category': 'halal', 'culture_group': 'intl', 'keyword': 'halal beef jerky', 'base_sales': 76, 'price': 12, 'peak_month': 12, 'competition': 54, 'hs4': '1602', 'hs_description': '其他税号未列名食品', 'tariff_base': 0.09, 'nutrition_score': 64, 'shelf_life_months': 12, 'storage_type': '常温'},
    'intl_vegetable_chips': {'name_cn': '蔬菜脆片', 'name_en': 'Vegetable Chips', 'category': 'vegetarian', 'mid_category': 'plant_protein', 'culture_group': 'intl', 'keyword': 'vegetable chips', 'base_sales': 72, 'price': 8, 'peak_month': 12, 'competition': 54, 'hs4': '2005', 'hs_description': '其他税号未列名食品', 'tariff_base': 0.09, 'nutrition_score': 70, 'shelf_life_months': 9, 'storage_type': '常温'},
}

CATEGORIES = {
    code: meta["name_cn"]
    for code, meta in CATEGORY_CATALOG.items()
}

CATEGORY_HS_CODES = {
    code: {"code": meta["hs4"], "description": meta["hs_description"]}
    for code, meta in CATEGORY_CATALOG.items()
}

FOOD_KEYWORDS = {
    code: meta["keyword"]
    for code, meta in CATEGORY_CATALOG.items()
}

FOOD_LOGISTICS: dict[str, dict] = {
    code: {
        **MAJOR_CATEGORIES[meta["category"]]["logistics"],
        "storage_type": meta["storage_type"],
    }
    for code, meta in CATEGORY_CATALOG.items()
}

MARKETS = {
    "us": "美国",
    "eu": "欧洲",
    "sea": "东南亚",
    "jp": "日本",
    "ca": "加拿大",
    "au": "澳大利亚",
    "uk": "英国",
    "kr": "韩国",
    "de": "德国",
    "fr": "法国",
    "vn": "越南",
    "ru": "俄罗斯",
    "hu": "匈牙利",
    "ae": "中东",
    "mx": "墨西哥",
}

# 市场因子（用于合成数据）
# Crawler signal evidence layer (does not change training data)
CRAWLER_OUTPUT_DIR = OUTPUT_DIR / "crawler"
CRAWLER_CACHE_DIR = CRAWLER_OUTPUT_DIR / "cache"
CRAWLER_LATEST_JSON = CRAWLER_OUTPUT_DIR / "latest.json"
CRAWLER_CACHE_TTL_SECONDS = 30 * 60
CRAWLER_DEFAULT_COMBOS = 10

# Daily policy snapshot paths (foreign / domestic / global policy events)
POLICY_OUTPUT_DIR = OUTPUT_DIR / "policy"
POLICY_DAILY_DIR = POLICY_OUTPUT_DIR / "daily"
POLICY_LATEST_JSON = POLICY_OUTPUT_DIR / "latest.json"
POLICY_SOURCES = [
    item.strip()
    for item in os.environ.get(
        "POLICY_SOURCES", "gov_cn,federal_register,eu,uk"
    ).split(",")
    if item.strip()
]
POLICY_WATCH_INTERVAL_HOURS = int(
    os.environ.get("POLICY_WATCH_INTERVAL_HOURS", "6")
)
POLICY_WATCH_LOOKBACK_DAYS = int(
    os.environ.get("POLICY_WATCH_LOOKBACK_DAYS", "14")
)

# Google Trends / 平台榜单 / 市场日报
TRENDS_OUTPUT_DIR = OUTPUT_DIR / "trends"
TRENDS_LATEST_JSON = TRENDS_OUTPUT_DIR / "latest.json"
PLATFORM_RANKINGS_OUTPUT_DIR = OUTPUT_DIR / "platform_rankings"
PLATFORM_RANKINGS_LATEST_JSON = PLATFORM_RANKINGS_OUTPUT_DIR / "latest.json"
MARKET_DAILY_OUTPUT_DIR = OUTPUT_DIR / "market_daily"
CUSTOMS_OUTPUT_DIR = OUTPUT_DIR / "customs"
CUSTOMS_LATEST_JSON = CUSTOMS_OUTPUT_DIR / "latest.json"
OPEN_FOOD_FACTS_OUTPUT_DIR = OUTPUT_DIR / "open_food_facts"
OPEN_FOOD_FACTS_LATEST_JSON = OPEN_FOOD_FACTS_OUTPUT_DIR / "latest.json"
ANOMALIES_OUTPUT_DIR = OUTPUT_DIR / "anomalies"
ANOMALIES_LATEST_JSON = ANOMALIES_OUTPUT_DIR / "latest.json"
EDA_OUTPUT_DIR = OUTPUT_DIR / "eda"
SUPPLIER_OUTPUT_DIR = OUTPUT_DIR / "suppliers"
SUPPLIER_LATEST_JSON = SUPPLIER_OUTPUT_DIR / "latest.json"
REAL_TRAINING_STATUS_JSON = OUTPUT_DIR / "real_training" / "status.json"
REAL_PROXY_STATUS_JSON = OUTPUT_DIR / "real_training" / "proxy_status.json"

# 联网数据源开关（默认开启，无 Key / 断网时自动回退 mock）
GOOGLE_TRENDS_ENABLED = os.environ.get("GOOGLE_TRENDS_ENABLED", "1").lower() in (
    "1",
    "true",
    "yes",
)
GOOGLE_TRENDS_MAX_KEYWORDS = int(
    os.environ.get("GOOGLE_TRENDS_MAX_KEYWORDS", "10")
)
GOOGLE_TRENDS_PROXIES = [
    item.strip()
    for item in os.environ.get("GOOGLE_TRENDS_PROXIES", "").split(",")
    if item.strip()
]
GOOGLE_TRENDS_COOKIE = os.environ.get("GOOGLE_TRENDS_COOKIE", "").strip()
PLATFORM_RANKING_PROVIDERS = [
    item.strip()
    for item in os.environ.get(
        "PLATFORM_RANKING_PROVIDERS",
        "amazon_github,ebay_github,shopee_github,mock",
    ).split(",")
    if item.strip()
]
KEEPA_API_KEY = os.environ.get("KEEPA_API_KEY", "").strip()
EBAY_APP_ID = os.environ.get("EBAY_APP_ID", "").strip()
EBAY_DEV_ID = os.environ.get("EBAY_DEV_ID", "").strip()
EBAY_CERT_ID = os.environ.get("EBAY_CERT_ID", "").strip()
COMTRADE_SUBSCRIPTION_KEY = os.environ.get("COMTRADE_SUBSCRIPTION_KEY", "").strip()
OPEN_FOOD_FACTS_ENABLED = os.environ.get("OPEN_FOOD_FACTS_ENABLED", "1").lower() in (
    "1",
    "true",
    "yes",
)
OPEN_FOOD_FACTS_MAX_PRODUCTS = int(os.environ.get("OPEN_FOOD_FACTS_MAX_PRODUCTS", "20"))
MARKET_DAILY_PUSH_URL = os.environ.get("MARKET_DAILY_PUSH_URL", "").strip()
# 货源/供应商尽调：1688-cli 为可选外部 CLI（MIT，需 npm 安装并扫码登录）
SUPPLIER_SOURCE_PROVIDERS = [
    item.strip()
    for item in os.environ.get("SUPPLIER_SOURCE_PROVIDERS", "1688_cli,mock").split(",")
    if item.strip()
]
SUPPLIER_CLI_PATH = os.environ.get("SUPPLIER_CLI_PATH", "").strip() or None
SUPPLIER_CLI_TIMEOUT_SECONDS = int(
    os.environ.get("SUPPLIER_CLI_TIMEOUT_SECONDS", "90")
)
SUPPLIER_MAX_KEYWORDS = int(os.environ.get("SUPPLIER_MAX_KEYWORDS", "10"))

# =========================================================================
# 联网数据源统一注册表（SOURCES）
#
# 单一视图，便于：
#   1) 每日更新 / 状态接口按数据源统一迭代采集与展示；
#   2) 新增一个数据源只需在此追加一条；
#   3) 各数据源的 enabled / providers / 路径 / Key / 限额 一目了然。
#
# 注意：各扁平常量（GOOGLE_TRENDS_ENABLED / KEEPA_API_KEY / ...）仍是各模块
# 与测试的权威来源，本注册表只“引用”它们，不做二次 env 解析，避免两处漂移。
# =========================================================================

SOURCES: dict[str, dict] = {
    "crawler": {
        "label": "Wikimedia 公开爬虫",
        "enabled": True,
        "providers": ("crawler", "duckduckgo_html", "mock"),
        "output_dir": CRAWLER_OUTPUT_DIR,
        "latest_json": CRAWLER_LATEST_JSON,
        "cache_ttl_seconds": CRAWLER_CACHE_TTL_SECONDS,
        "default_combos": CRAWLER_DEFAULT_COMBOS,
    },
    "policy": {
        "label": "政策雷达（官方源优先）",
        "enabled": True,
        "providers": tuple(POLICY_SOURCES),
        "output_dir": POLICY_OUTPUT_DIR,
        "latest_json": POLICY_LATEST_JSON,
        "lookback_days": POLICY_WATCH_LOOKBACK_DAYS,
        "interval_hours": POLICY_WATCH_INTERVAL_HOURS,
    },
    "trends": {
        "label": "Google Trends",
        "enabled": GOOGLE_TRENDS_ENABLED,
        "providers": ("pytrends", "mock"),
        "output_dir": TRENDS_OUTPUT_DIR,
        "latest_json": TRENDS_LATEST_JSON,
        "max_keywords": GOOGLE_TRENDS_MAX_KEYWORDS,
    },
    "platform_rankings": {
        "label": "平台榜单（Amazon / eBay GitHub 免费样例，Keepa 可选）",
        "enabled": True,
        "providers": tuple(PLATFORM_RANKING_PROVIDERS),
        "output_dir": PLATFORM_RANKINGS_OUTPUT_DIR,
        "latest_json": PLATFORM_RANKINGS_LATEST_JSON,
        "keys": {
            "keepa": KEEPA_API_KEY,
            "ebay_app_id": EBAY_APP_ID,
        },
    },
    "customs": {
        "label": "海关出口（UN Comtrade / OTS）",
        "enabled": True,
        "providers": ("comtrade", "ots", "mock"),
        "output_dir": CUSTOMS_OUTPUT_DIR,
        "latest_json": CUSTOMS_LATEST_JSON,
        "keys": {"comtrade": COMTRADE_SUBSCRIPTION_KEY},
    },
    "open_food_facts": {
        "label": "Open Food Facts（开放商品数据库，ODbL）",
        "enabled": OPEN_FOOD_FACTS_ENABLED,
        "providers": ("open_food_facts", "mock"),
        "output_dir": OPEN_FOOD_FACTS_OUTPUT_DIR,
        "latest_json": OPEN_FOOD_FACTS_LATEST_JSON,
        "max_products": OPEN_FOOD_FACTS_MAX_PRODUCTS,
    },
    "suppliers": {
        "label": "货源/供应商（1688-cli）",
        "enabled": True,
        "providers": tuple(SUPPLIER_SOURCE_PROVIDERS),
        "output_dir": SUPPLIER_OUTPUT_DIR,
        "latest_json": SUPPLIER_LATEST_JSON,
        "max_keywords": SUPPLIER_MAX_KEYWORDS,
        "cli_timeout_seconds": SUPPLIER_CLI_TIMEOUT_SECONDS,
    },
    "market_daily": {
        "label": "市场日报",
        "enabled": True,
        "output_dir": MARKET_DAILY_OUTPUT_DIR,
        "push_url": MARKET_DAILY_PUSH_URL,
    },
}

# 搜索服务回退链与受支持 provider 的单一来源（brain_bridge / data_tools 引用这里）
SEARCH_PROVIDER_CHAIN = ("crawler", "duckduckgo_html", "mock")
SEARCH_PROVIDERS = {
    "mock",
    "crawler",
    "duckduckgo",
    "duckduckgo_html",
    "tavily",
    "serpapi",
    "generic",
}


def enabled_sources() -> list[str]:
    """返回当前启用的数据源名称（保持注册表顺序）。"""
    return [name for name, cfg in SOURCES.items() if cfg.get("enabled")]


MARKET_FACTOR = {
    "us": 1.00,
    "eu": 0.82,
    "sea": 0.65,
    "jp": 0.78,
    "ca": 0.95,
    "au": 0.88,
    "uk": 0.86,
    "kr": 0.76,
    "de": 0.80,
    "fr": 0.74,
    "vn": 0.60,
    "ru": 0.52,
    "hu": 0.42,
    "ae": 0.55,
    "mx": 0.58,
}

# 品类基准参数（用于合成数据：基础销量、基准价格、季节峰值月份、竞争基线）
CATEGORY_PARAMS = {
    code: {
        "base_sales": meta["base_sales"],
        "price": meta["price"],
        "peak_month": meta["peak_month"],
        "competition": meta["competition"],
    }
    for code, meta in CATEGORY_CATALOG.items()
}

# 数据与模型参数
# Representative English keyword per category for public data retrieval
CATEGORY_KEYWORDS = {
    code: meta["keyword"]
    for code, meta in CATEGORY_CATALOG.items()
}

WEEKS_HISTORY = 104          # 2 年周数据
FORECAST_HORIZON = 90        # 预测 90 天
TEST_WEEKS = 12              # 最近 12 周作为测试集
RANDOM_SEED = 42
TRAIN_WORKERS = int(os.environ.get("TRAIN_WORKERS", "4"))
TARGET_COL = "sales_volume"
REAL_FEATURE_COLS = [
    "real_price_median",
    "real_rating_median",
    "real_reviews_median",
    "real_demand_median",
    "real_trend_value",
    "real_rank_avg",
    "real_customs_export",
    "real_crawler_trend_pct",
    "real_evidence_score",
]

# 预测模型参数
PROPHET_PARAMS = {
    "weekly_seasonality": True,
    "yearly_seasonality": True,
    "daily_seasonality": False,
}

# Prophet external regressors carried into evaluation and 90-day forecast
PROPHET_REGRESSORS = [
    "search_index",
    "price_median",
    "competition_index",
    "review_growth",
    "export_value",
    "bestseller_rank",
    "real_trend_value",
    "real_customs_export",
    "real_crawler_trend_pct",
    "real_evidence_score",
]

LGBM_PARAMS = {
    "objective": "regression",
    "metric": "mae",
    "n_estimators": 900,
    "learning_rate": 0.034484844346092995,
    "num_leaves": 13,
    "max_depth": 3,
    "feature_fraction": 0.5924198110299715,
    "bagging_fraction": 0.6400737383507629,
    "bagging_freq": 4,
    "min_child_samples": 9,
    "reg_alpha": 0.2683791600359044,
    "reg_lambda": 1.8038425856614662,
    "verbose": -1,
    "random_state": RANDOM_SEED,
}

# LightGBM target transform: "raw" or "log1p" (selected by scripts/optimize_models.py)
LGBM_TARGET_TRANSFORM = "raw"

# 推荐引擎权重
RECOMMEND_WEIGHTS = {
    "forecast_growth": 0.35,
    "search_trend": 0.30,
    "competition": 0.25,
    "review_growth": 0.10,
}

# Go/No-Go 六维判定阈值
VERDICT_THRESHOLDS = {
    "go_min": 70.0,
    "conditional_min": 55.0,
    "dimension_min": 50.0,
    "conditional_dimension_min": 40.0,
}

# 3×3 对外主叙事（B-3 收敛落地，用户拍板：A 对外主叙事 US/SEA 版）
# 9 格 = 3 个食品 SKU × {US, SEA, DE}；其中 US/SEA 6 格走真实数据链路（达标），
# DE 3 格保留能力但对外标注"规划中"。
NARRATIVE_3X3 = {
    "label": "对外主叙事（US/SEA 版）",
    "categories": ("cn_latiao", "cn_longjing", "cn_frozen_dumplings"),
    "markets_real": ("us", "sea"),
    "markets_planned": ("de",),
    "real_ratio_threshold": 0.8,  # 真实来源占比验收线（≥80%）
    "note": "DE 列无真实销量代理，对外标注『规划中』；占比口径 mock_isolated（真实与 mock 分开统计）。",
}


def narrative_grid() -> list[dict]:
    """返回 9 格清单：每格带真实/规划中标记（B-3 供看板/API 标注）。"""
    grid: list[dict] = []
    for category in NARRATIVE_3X3["categories"]:
        for market in NARRATIVE_3X3["markets_real"] + NARRATIVE_3X3["markets_planned"]:
            grid.append(
                {
                    "category": category,
                    "market": market,
                    "status": (
                        "real"
                        if market in NARRATIVE_3X3["markets_real"]
                        else "planned"
                    ),
                }
            )
    return grid


def category_name(code: str) -> str:
    return CATEGORIES.get(code, code)


def market_name(code: str) -> str:
    return MARKETS.get(code, code)
