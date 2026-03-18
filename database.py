import sqlite3
import os
import pickle
from datetime import datetime

import os
DB_PATH = os.environ.get('DB_PATH', 'nutrition_enhanced.db')

def init_db():
    """Initialize database only if it doesn't already exist."""

    # ── KEY FIX: skip entirely if DB already exists ──
    if os.path.exists(DB_PATH):
        print("✅ Database already exists — skipping initialization.")
        return

    print("🛠️  Creating fresh database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_keys = ON")

    # ── Users ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_admin INTEGER DEFAULT 0,
            age INTEGER DEFAULT 30,
            gender TEXT DEFAULT 'prefer_not_to_say',
            weight_kg REAL DEFAULT 70.0,
            height_cm REAL DEFAULT 170.0,
            activity_level TEXT DEFAULT 'moderate',
            health_goal TEXT DEFAULT 'general_wellness',
            daily_calorie_target INTEGER DEFAULT 2000,
            daily_sugar_limit_g INTEGER DEFAULT 50,
            daily_sodium_limit_mg INTEGER DEFAULT 2300,
            daily_fat_limit_g INTEGER DEFAULT 78,
            daily_protein_target_g INTEGER DEFAULT 50,
            daily_fiber_target_g INTEGER DEFAULT 28,
            bp_systolic INTEGER DEFAULT 120,
            bp_diastolic INTEGER DEFAULT 80,
            fasting_blood_sugar_mg REAL DEFAULT 100,
            hba1c_pct REAL,
            total_cholesterol_mg REAL DEFAULT 180,
            ldl_mg REAL,
            hdl_mg REAL,
            triglycerides_mg REAL,
            resting_heart_rate INTEGER,
            is_pregnant INTEGER DEFAULT 0,
            is_breastfeeding INTEGER DEFAULT 0,
            medications TEXT,
            profile_complete INTEGER DEFAULT 0,
            profile_saved_at TEXT
        )
    ''')

    # ── Health conditions reference ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            critical_nutrients TEXT,
            recommended_actions TEXT,
            severity_level TEXT,
            is_chronic INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── User health conditions ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_health_conditions (
            user_id INTEGER NOT NULL,
            condition_id INTEGER NOT NULL,
            diagnosed_date DATE DEFAULT CURRENT_DATE,
            severity TEXT,
            is_managed INTEGER DEFAULT 0,
            medication TEXT,
            notes TEXT,
            last_checked DATE,
            PRIMARY KEY (user_id, condition_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (condition_id) REFERENCES health_conditions(id) ON DELETE CASCADE
        )
    ''')

    # ── Categories ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            parent_category_id INTEGER DEFAULT NULL,
            icon_class TEXT DEFAULT 'bi-box',
            color_code TEXT DEFAULT '#6c757d',
            is_active INTEGER DEFAULT 1
        )
    ''')

    # ── Products ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            barcode TEXT UNIQUE,
            name TEXT NOT NULL,
            brand TEXT,
            category_id INTEGER,
            description TEXT,
            serving_size_g REAL DEFAULT 100,
            serving_size_ml REAL,
            servings_per_container REAL DEFAULT 1,
            calories REAL DEFAULT 0,
            protein_g REAL DEFAULT 0,
            carbohydrates_g REAL DEFAULT 0,
            sugar_g REAL DEFAULT 0,
            added_sugar_g REAL DEFAULT 0,
            fiber_g REAL DEFAULT 0,
            fat_g REAL DEFAULT 0,
            saturated_fat_g REAL DEFAULT 0,
            trans_fat_g REAL DEFAULT 0,
            cholesterol_mg REAL DEFAULT 0,
            sodium_mg REAL DEFAULT 0,
            potassium_mg REAL DEFAULT 0,
            calcium_mg REAL DEFAULT 0,
            iron_mg REAL DEFAULT 0,
            vitamin_a_iu REAL DEFAULT 0,
            vitamin_c_mg REAL DEFAULT 0,
            vitamin_d_iu REAL DEFAULT 0,
            caffeine_mg REAL DEFAULT 0,
            glycemic_index INTEGER,
            ingredients TEXT,
            allergen_info TEXT,
            is_gluten_free INTEGER DEFAULT 0,
            is_vegan INTEGER DEFAULT 0,
            is_vegetarian INTEGER DEFAULT 0,
            is_organic INTEGER DEFAULT 0,
            is_non_gmo INTEGER DEFAULT 0,
            health_score INTEGER DEFAULT 50,
            is_healthy INTEGER DEFAULT 0,
            manufacturer TEXT,
            country_of_origin TEXT,
            storage_instructions TEXT,
            expiry_days INTEGER,
            image_url TEXT,
            qr_code_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')

    # ── Allergens ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS allergens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            common_names TEXT,
            description TEXT,
            severity TEXT,
            icon_class TEXT DEFAULT 'bi-exclamation-triangle',
            is_common INTEGER DEFAULT 1
        )
    ''')

    # ── Product allergens ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_allergens (
            product_id TEXT NOT NULL,
            allergen_id INTEGER NOT NULL,
            contains_traces INTEGER DEFAULT 0,
            warning_level TEXT,
            PRIMARY KEY (product_id, allergen_id),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (allergen_id) REFERENCES allergens(id) ON DELETE CASCADE
        )
    ''')

    # ── User allergies ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_allergies (
            user_id INTEGER NOT NULL,
            allergen_id INTEGER NOT NULL,
            reaction_severity TEXT,
            first_experienced DATE,
            last_reaction DATE,
            epipen_required INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, allergen_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (allergen_id) REFERENCES allergens(id) ON DELETE CASCADE
        )
    ''')

    # ── Dietary preferences ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dietary_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            restrictions TEXT,
            icon_class TEXT DEFAULT 'bi-heart',
            is_popular INTEGER DEFAULT 1
        )
    ''')

    # ── User dietary preferences ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_dietary_preferences (
            user_id INTEGER NOT NULL,
            preference_id INTEGER NOT NULL,
            adherence_level TEXT,
            start_date DATE DEFAULT CURRENT_DATE,
            notes TEXT,
            PRIMARY KEY (user_id, preference_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (preference_id) REFERENCES dietary_preferences(id) ON DELETE CASCADE
        )
    ''')

    # ── Nutrition rules ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nutrition_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT UNIQUE NOT NULL,
            rule_type TEXT,
            target_condition_id INTEGER,
            target_preference_id INTEGER,
            target_gender TEXT,
            min_age INTEGER DEFAULT 0,
            max_age INTEGER DEFAULT 150,
            nutrient_field TEXT,
            comparison_operator TEXT,
            threshold_value REAL,
            custom_logic TEXT,
            severity TEXT,
            message_template TEXT NOT NULL,
            alternative_suggestion TEXT,
            learn_more_url TEXT,
            recommend_category_id INTEGER,
            recommend_max_nutrient TEXT,
            recommend_max_value REAL,
            priority INTEGER DEFAULT 5,
            is_active INTEGER DEFAULT 1,
            created_by TEXT DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Scan history ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_decision TEXT,
            consumption_amount REAL,
            consumption_time TEXT,
            assistant_advice_given TEXT,
            user_response TEXT,
            feedback_rating INTEGER,
            feedback_comment TEXT,
            location_lat REAL,
            location_lng REAL,
            device_type TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # ── Chatbot conversations ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chatbot_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            user_message TEXT NOT NULL,
            assistant_response TEXT NOT NULL,
            context_product_id TEXT,
            intent TEXT,
            entities_extracted TEXT,
            confidence_score REAL DEFAULT 1.0,
            rule_applied_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # ── User favourites ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_favourites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            saved_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, product_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # ── Contact messages ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            sent_at TEXT DEFAULT (datetime('now'))
        )
    ''')

    # ══ SAMPLE DATA ══

    # Categories
    cursor.executemany('INSERT OR IGNORE INTO categories VALUES (?,?,?,?,?,?,?)', [
        (1,'Beverages','Drinks',None,'bi-cup','#3498db',1),
        (2,'Snacks','Small meals',None,'bi-basket','#e74c3c',1),
        (3,'Dairy','Milk products',None,'bi-droplet','#f1c40f',1),
        (4,'Bakery','Bread and pastries',None,'bi-slash-circle','#27ae60',1),
        (5,'Produce','Fruits and vegetables',None,'bi-apple','#2ecc71',1),
    ])

    # Health conditions
    cursor.executemany('INSERT OR IGNORE INTO health_conditions VALUES (?,?,?,?,?,?,?,?)', [
        (1,'Diabetes','High blood sugar','{"sugar":"limit"}','Monitor carbs','moderate',1,datetime.now().isoformat()),
        (2,'Hypertension','High blood pressure','{"sodium":"limit"}','Reduce salt','moderate',1,datetime.now().isoformat()),
        (3,'High Cholesterol','Elevated cholesterol','{"fat":"limit"}','Reduce sat fats','moderate',1,datetime.now().isoformat()),
        (4,'Heart Disease','Cardiovascular issues','{"sodium":"strict","fat":"strict"}','Low sodium low fat','severe',1,datetime.now().isoformat()),
        (5,'Kidney Disease','CKD','{"sodium":"strict","protein":"limit"}','Limit sodium & protein','severe',1,datetime.now().isoformat()),
        (6,'GERD / Acid Reflux','Acid reflux','{"caffeine":"avoid"}','Avoid caffeine & fat','moderate',1,datetime.now().isoformat()),
        (7,'PCOS','Polycystic ovary','{"sugar":"limit"}','Low GI diet','moderate',1,datetime.now().isoformat()),
        (8,'Gout','High uric acid','{"fructose":"limit"}','Limit fructose','moderate',1,datetime.now().isoformat()),
        (9,'Celiac Disease','Gluten intolerance','{"gluten":"strict"}','No gluten','severe',1,datetime.now().isoformat()),
        (10,'Thyroid Disorder','Thyroid issues','{"iodine":"monitor"}','Monitor iodine','moderate',1,datetime.now().isoformat()),
    ])

    # Allergens
    cursor.executemany('INSERT OR IGNORE INTO allergens VALUES (?,?,?,?,?,?,?)', [
        (1,'Peanuts','Ground nuts','Peanut allergy','severe','bi-exclamation-triangle-fill',1),
        (2,'Milk','Dairy','Lactose intolerance','moderate','bi-droplet',1),
        (3,'Gluten','Wheat, barley','Celiac disease','severe','bi-slash-circle',1),
        (4,'Shellfish','Shrimp, crab','Shellfish allergy','life_threatening','bi-exclamation-octagon',1),
        (5,'Eggs','Egg whites','Egg allergy','moderate','bi-egg',1),
        (6,'Soy','Soybean','Soy allergy','moderate','bi-exclamation-triangle',1),
        (7,'Tree Nuts','Almonds, cashews','Tree nut allergy','severe','bi-exclamation-triangle-fill',1),
        (8,'Fish','Finfish','Fish allergy','severe','bi-exclamation-triangle-fill',1),
        (9,'Wheat','Wheat products','Wheat allergy','moderate','bi-slash-circle',1),
        (10,'Sesame','Sesame seeds','Sesame allergy','moderate','bi-exclamation-triangle',1),
    ])

    # Dietary preferences
    cursor.executemany('INSERT OR IGNORE INTO dietary_preferences VALUES (?,?,?,?,?,?)', [
        (1,'Vegetarian','No meat','{"meat":"exclude"}','bi-carrot',1),
        (2,'Vegan','No animal products','{"meat":"exclude","dairy":"exclude"}','bi-leaf',1),
        (3,'Gluten-Free','No gluten','{"gluten":"exclude"}','bi-ban',1),
        (4,'Low-Sodium','Reduced salt','{"sodium":"limit_1500"}','bi-droplet-half',1),
        (5,'Keto','High fat low carb','{"carbs":"limit_20"}','bi-lightning',1),
        (6,'Low-Sugar','Reduced sugar','{"sugar":"limit_25"}','bi-heart',1),
        (7,'High-Protein','Protein-focused','{"protein":"high"}','bi-activity',1),
        (8,'Low-Calorie','Calorie-restricted','{"calories":"limit_1500"}','bi-fire',1),
    ])

    # Sample products
    now = datetime.now().isoformat()
    for p in [
        ('PROD001','123456789001','Apple','Nature Fresh',5,'Fresh red apple',182,None,1,95,0.5,25,19,0,4.4,0.3,0.1,0,0,1,195,5,6,100,10,0,0,38,'Apple','None',1,1,1,1,0,85,1,'Apple Farms','USA','Cool place',30,'https://images.unsplash.com/photo-1568702846914-96b305d2aaeb?w=400',None,now,now,1),
        ('PROD002','123456789002','Whole Wheat Bread','Nature Own',4,'100% whole wheat',45,None,20,110,5,20,2,0,3,1.5,0.3,0,0,180,100,0,20,0,0,0,0,69,'Whole Wheat Flour, Water, Yeast, Salt','Contains Wheat',0,1,1,1,1,80,1,'Nature Own','USA','Cool dry place',7,'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400',None,now,now,1),
        ('PROD003','123456789003','Greek Yogurt','Chobani',3,'High protein yogurt',150,150,1,100,17,6,4,0,0,0,10,0,0,65,240,200,20,0,0,0,0,11,'Cultured Nonfat Milk','Contains Milk',1,0,0,1,0,85,1,'Chobani','USA','Refrigerate',21,'https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=400',None,now,now,1),
        ('PROD004','123456789004','Potato Chips','Lays',2,'Classic potato chips',28,None,8,160,2,15,1,0,1,10,1,0,0,170,350,0,0,0,0,0,0,75,'Potatoes, Vegetable Oil, Salt','None',1,1,1,1,0,40,0,'Frito-Lay','USA','Cool dry place',90,'https://images.unsplash.com/photo-1566478989037-eec170784d0b?w=400',None,now,now,1),
        ('PROD005','123456789005','Pepsi Regular','PepsiCo',1,'Carbonated soft drink',330,330,1,150,0,41,41,41,0,0,0,0,0,30,0,0,0,0,0,0,38,63,'Carbonated Water, HFCS, Caramel Color, Phosphoric Acid, Caffeine','None',1,0,0,0,0,20,0,'PepsiCo Inc.','USA','Cool place',180,'https://images.unsplash.com/photo-1629203851122-3726ecdf080e?w=400',None,now,now,1),
        ('PROD006','123456789006','Pepsi Zero Sugar','PepsiCo',1,'Zero sugar cola',330,330,1,0,0,0,0,0,0,0,0,0,0,40,0,0,0,0,0,0,38,0,'Carbonated Water, Caramel Color, Aspartame, Caffeine','Contains Phenylalanine',1,0,0,0,0,75,1,'PepsiCo Inc.','USA','Cool place',180,'https://images.unsplash.com/photo-1629203851252-3448c5e0c6f9?w=400',None,now,now,1),
        ('PROD007','123456789007','Dark Chocolate','Lindt',2,'Premium 85% dark chocolate',25,None,4,150,2,8,3,3,3,12,7,0,0,5,200,0,0,0,0,0,12,23,'Cocoa Mass, Sugar, Cocoa Butter, Vanilla','None',1,1,1,1,0,65,1,'Lindt','Switzerland','Cool dry place',365,'https://images.unsplash.com/photo-1511381939415-e44015466834?w=400',None,now,now,1),
        ('PROD008','123456789008','Mixed Nuts','Planters',2,'Salted mixed nuts',50,None,10,300,10,10,2,0,3,27,4,0,0,120,400,0,0,0,0,0,0,15,'Peanuts, Almonds, Cashews, Salt','Contains Peanuts, Tree Nuts',1,1,1,1,0,70,1,'Planters','USA','Cool dry place',180,'https://images.unsplash.com/photo-1533090161767-e6ffed986c88?w=400',None,now,now,1),
        ('PROD009','123456789009','Orange Juice','Tropicana',1,'100% pure orange juice',240,240,1,110,2,26,22,0,0,0,0,0,0,0,450,20,120,0,0,0,0,52,'Orange Juice','None',1,1,1,1,0,75,1,'Tropicana','USA','Refrigerate after opening',30,'https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?w=400',None,now,now,1),
        ('PROD010','123456789010','Mineral Water','Evian',1,'Natural spring water',500,500,1,0,0,0,0,0,0,0,0,0,0,5,0,80,20,0,0,0,0,0,'Natural Spring Water','None',1,1,1,1,1,95,1,'Evian','France','Cool place',730,'https://images.unsplash.com/photo-1523362628745-0c100150b504?w=400',None,now,now,1),
    ]:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO products (
                    id,barcode,name,brand,category_id,description,
                    serving_size_g,serving_size_ml,servings_per_container,
                    calories,protein_g,carbohydrates_g,sugar_g,added_sugar_g,fiber_g,
                    fat_g,saturated_fat_g,trans_fat_g,cholesterol_mg,sodium_mg,
                    potassium_mg,calcium_mg,iron_mg,vitamin_a_iu,vitamin_c_mg,vitamin_d_iu,
                    caffeine_mg,glycemic_index,
                    ingredients,allergen_info,
                    is_gluten_free,is_vegan,is_vegetarian,is_organic,is_non_gmo,
                    health_score,is_healthy,manufacturer,country_of_origin,
                    storage_instructions,expiry_days,image_url,qr_code_url,
                    created_at,last_updated,is_active
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', p)
        except Exception as e:
            print(f"  [product insert] {e}")

    # Admin user
    import hashlib
    cursor.execute('''
        INSERT OR IGNORE INTO users (email,password_hash,first_name,last_name,is_admin)
        VALUES (?,?,?,?,?)
    ''', ('admin@nutriscan.com', hashlib.sha256('admin123'.encode()).hexdigest(), 'Admin', 'User', 1))

    # Demo user
    cursor.execute('''
        INSERT OR IGNORE INTO users (email,password_hash,first_name,last_name,is_admin,age,gender,weight_kg,height_cm,activity_level,health_goal)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    ''', ('demo@example.com', hashlib.sha256('demo123'.encode()).hexdigest(), 'Demo', 'User', 0, 30, 'male', 70, 170, 'moderate', 'general_wellness'))

    conn.commit()
    conn.close()

    print("✅ Database initialized successfully!")
    print("📊 10 sample products added")
    print("👤 Admin: admin@nutriscan.com / admin123")
    print("👤 Demo:  demo@example.com / demo123")


def train_ml_model():
    """Simple rule-based model — only trains if model file missing."""
    if os.path.exists('health_model.pkl'):
        return _load_model()

    print("🤖 Training health prediction model...")
    model_rules = {
        'sugar_threshold':    25,
        'fat_threshold':      20,
        'sodium_threshold':   400,
        'calorie_threshold':  300,
        'protein_threshold':  10,
    }
    with open('health_model.pkl', 'wb') as f:
        pickle.dump(model_rules, f)
    print("✅ Model trained and saved as health_model.pkl")
    return model_rules


def _load_model():
    with open('health_model.pkl', 'rb') as f:
        return pickle.load(f)


def get_product_stats():
    if not os.path.exists(DB_PATH):
        return {}
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products WHERE is_active=1")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM products WHERE is_healthy=1 AND is_active=1")
    healthy = cursor.fetchone()[0]
    conn.close()
    return {'total_products': total, 'healthy_products': healthy}


if __name__ == '__main__':
    init_db()