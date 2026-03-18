# create_nutrition_db.py
import sqlite3
import json
import hashlib
from datetime import datetime

def create_enhanced_database():
    """Create a complete nutrition_enhanced.db with sample data"""
    conn = sqlite3.connect('nutrition_enhanced.db')
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")
    
    # ========== CREATE TABLES ==========
    
    # Users table
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
            weight_kg REAL DEFAULT 70.0,
            height_cm REAL DEFAULT 170.0,
            gender TEXT DEFAULT 'prefer_not_to_say',
            activity_level TEXT DEFAULT 'moderate',
            health_goal TEXT DEFAULT 'general_wellness',
            daily_calorie_target INTEGER DEFAULT 2000,
            daily_sugar_limit_g INTEGER DEFAULT 36,
            daily_sodium_limit_mg INTEGER DEFAULT 2300,
            daily_fat_limit_g INTEGER DEFAULT 78,
            -- Vitals
            bp_systolic INTEGER DEFAULT 120,
            bp_diastolic INTEGER DEFAULT 80,
            fasting_blood_sugar REAL DEFAULT 100,
            hba1c REAL DEFAULT 5.4,
            total_cholesterol REAL DEFAULT 180,
            ldl_mg REAL DEFAULT 100,
            hdl_mg REAL DEFAULT 50,
            triglycerides_mg REAL DEFAULT 150,
            resting_heart_rate INTEGER DEFAULT 72,
            -- Special states
            is_pregnant INTEGER DEFAULT 0,
            is_breastfeeding INTEGER DEFAULT 0,
            -- Profile complete flag
            profile_complete INTEGER DEFAULT 0
        )
    ''')
    
    # Health conditions
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
    
    # User health conditions
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
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (condition_id) REFERENCES health_conditions (id) ON DELETE CASCADE
        )
    ''')
    
    # Categories
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
    
    # Products table - COUNTED COLUMNS = 45
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
            caffeine_mg REAL DEFAULT 0,
            glycemic_index INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Allergens
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS allergens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            common_names TEXT,
            description TEXT,
            severity TEXT CHECK(severity IN ('mild', 'moderate', 'severe', 'life_threatening')),
            icon_class TEXT DEFAULT 'bi-exclamation-triangle',
            is_common INTEGER DEFAULT 1
        )
    ''')
    
    # Product allergens
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_allergens (
            product_id TEXT NOT NULL,
            allergen_id INTEGER NOT NULL,
            contains_traces INTEGER DEFAULT 0,
            warning_level TEXT CHECK(warning_level IN ('contains', 'may_contain', 'processed_in_facility')),
            PRIMARY KEY (product_id, allergen_id),
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
            FOREIGN KEY (allergen_id) REFERENCES allergens (id) ON DELETE CASCADE
        )
    ''')
    
    # User allergies
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_allergies (
            user_id INTEGER NOT NULL,
            allergen_id INTEGER NOT NULL,
            reaction_severity TEXT CHECK(reaction_severity IN ('mild', 'moderate', 'severe', 'anaphylactic')),
            first_experienced DATE,
            last_reaction DATE,
            epipen_required INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, allergen_id),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (allergen_id) REFERENCES allergens (id) ON DELETE CASCADE
        )
    ''')

    # User medications
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            medication_name TEXT NOT NULL,
            dosage TEXT,
            frequency TEXT,
            condition_treated TEXT,
            interactions_flag TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    
    # Dietary preferences
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
    
    # User dietary preferences
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_dietary_preferences (
            user_id INTEGER NOT NULL,
            preference_id INTEGER NOT NULL,
            adherence_level TEXT CHECK(adherence_level IN ('strict', 'moderate', 'flexible', 'transitioning')),
            start_date DATE DEFAULT CURRENT_DATE,
            notes TEXT,
            PRIMARY KEY (user_id, preference_id),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (preference_id) REFERENCES dietary_preferences (id) ON DELETE CASCADE
        )
    ''')
    
    # Nutrition rules
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nutrition_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT UNIQUE NOT NULL,
            rule_type TEXT CHECK(rule_type IN ('warning', 'suggestion', 'recommendation', 'education')),
            target_condition_id INTEGER,
            target_preference_id INTEGER,
            target_gender TEXT,
            min_age INTEGER DEFAULT 0,
            max_age INTEGER DEFAULT 150,
            nutrient_field TEXT,
            comparison_operator TEXT CHECK(comparison_operator IN ('>', '<', '>=', '<=', '=', '!=')),
            threshold_value REAL,
            custom_logic TEXT,
            severity TEXT CHECK(severity IN ('info', 'warning', 'danger', 'critical')),
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
    
    # Scan history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_decision TEXT CHECK(user_decision IN ('consumed', 'avoided', 'saved_for_later', 'shared', 'rated')),
            consumption_amount REAL,
            consumption_time TEXT,
            assistant_advice_given TEXT,
            user_response TEXT CHECK(user_response IN ('followed', 'partially_followed', 'ignored', 'dismissed')),
            feedback_rating INTEGER CHECK(feedback_rating >= 1 AND feedback_rating <= 5),
            feedback_comment TEXT,
            location_lat REAL,
            location_lng REAL,
            device_type TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
        )
    ''')
    
    # Chatbot conversations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chatbot_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            user_message TEXT NOT NULL,
            assistant_response TEXT NOT NULL,
            context_product_id TEXT,
            intent TEXT CHECK(intent IN ('health_analysis', 'product_search', 'recipe_suggestion', 'general_question', 'allergy_check', 'diet_advice')),
            entities_extracted TEXT,
            confidence_score REAL DEFAULT 1.0,
            rule_applied_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (context_product_id) REFERENCES products (id),
            FOREIGN KEY (rule_applied_id) REFERENCES nutrition_rules (id)
        )
    ''')
    
    # ========== MIGRATE EXISTING DATABASE (safe ALTER TABLE) ==========
    # These run silently — they fail gracefully if columns already exist
    migrations = [
        "ALTER TABLE users ADD COLUMN bp_systolic INTEGER DEFAULT 120",
        "ALTER TABLE users ADD COLUMN bp_diastolic INTEGER DEFAULT 80",
        "ALTER TABLE users ADD COLUMN fasting_blood_sugar REAL DEFAULT 100",
        "ALTER TABLE users ADD COLUMN hba1c REAL DEFAULT 5.4",
        "ALTER TABLE users ADD COLUMN total_cholesterol REAL DEFAULT 180",
        "ALTER TABLE users ADD COLUMN ldl_mg REAL DEFAULT 100",
        "ALTER TABLE users ADD COLUMN hdl_mg REAL DEFAULT 50",
        "ALTER TABLE users ADD COLUMN triglycerides_mg REAL DEFAULT 150",
        "ALTER TABLE users ADD COLUMN resting_heart_rate INTEGER DEFAULT 72",
        "ALTER TABLE users ADD COLUMN is_pregnant INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN is_breastfeeding INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN profile_complete INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN caffeine_mg REAL DEFAULT 0",
        "ALTER TABLE products ADD COLUMN glycemic_index INTEGER DEFAULT 0",
    ]
    for sql in migrations:
        try:
            cursor.execute(sql)
        except Exception:
            pass  # Column already exists — that's fine

    # ========== INSERT SAMPLE DATA ==========
    
    print("Inserting sample data...")
    
    # Insert categories
    categories = [
        (1, 'Beverages', 'Drinks and liquids', None, 'bi-cup', '#3498db', 1),
        (2, 'Snacks', 'Small meals and treats', None, 'bi-basket', '#e74c3c', 1),
        (3, 'Dairy', 'Milk products', None, 'bi-droplet', '#f1c40f', 1),
        (4, 'Bakery', 'Bread and pastries', None, 'bi-wheat', '#27ae60', 1),
        (5, 'Produce', 'Fruits and vegetables', None, 'bi-apple', '#2ecc71', 1)
    ]
    cursor.executemany('INSERT OR IGNORE INTO categories VALUES (?, ?, ?, ?, ?, ?, ?)', categories)
    
    # Insert health conditions
    conditions = [
        (1, 'Diabetes', 'High blood sugar', '{"sugar": "limit"}', 'Monitor carb intake', 'moderate', 1, datetime.now().isoformat()),
        (2, 'Hypertension', 'High blood pressure', '{"sodium": "limit"}', 'Reduce salt intake', 'moderate', 1, datetime.now().isoformat()),
        (3, 'High Cholesterol', 'Elevated cholesterol', '{"fat": "limit"}', 'Reduce saturated fats', 'moderate', 1, datetime.now().isoformat()),
        (4, 'Heart Disease', 'Cardiovascular issues', '{"sodium": "strict", "fat": "strict"}', 'Low sodium, low fat diet', 'severe', 1, datetime.now().isoformat())
    ]
    cursor.executemany('INSERT OR IGNORE INTO health_conditions VALUES (?, ?, ?, ?, ?, ?, ?, ?)', conditions)
    
    # Insert allergens
    allergens = [
        (1, 'Peanuts', 'Ground nuts', 'Peanut allergy', 'severe', 'bi-exclamation-triangle-fill', 1),
        (2, 'Milk', 'Dairy', 'Lactose intolerance', 'moderate', 'bi-droplet', 1),
        (3, 'Gluten', 'Wheat products', 'Celiac disease', 'severe', 'bi-wheat', 1),
        (4, 'Shellfish', 'Shrimp, crab', 'Shellfish allergy', 'severe', 'bi-crab', 1)
    ]
    cursor.executemany('INSERT OR IGNORE INTO allergens VALUES (?, ?, ?, ?, ?, ?, ?)', allergens)
    
    # Insert dietary preferences
    preferences = [
        (1, 'Vegetarian', 'No meat', '{"meat": "exclude"}', 'bi-carrot', 1),
        (2, 'Vegan', 'No animal products', '{"meat": "exclude", "dairy": "exclude"}', 'bi-leaf', 1),
        (3, 'Gluten-Free', 'No gluten', '{"gluten": "exclude"}', 'bi-ban', 1),
        (4, 'Low-Sodium', 'Reduced salt', '{"sodium": "limit"}', 'bi-droplet-half', 1)
    ]
    cursor.executemany('INSERT OR IGNORE INTO dietary_preferences VALUES (?, ?, ?, ?, ?, ?)', preferences)
    
    # Insert nutrition rules
    rules = [
        (1, 'High Sugar Warning', 'warning', 1, None, None, 0, 150,
         'sugar_g', '>', 10, None, 'danger',
         'High sugar content ({value}g). Limit for diabetes management.',
         'Choose sugar-free alternatives', None, None, None, None, 8, 1, 'system', datetime.now().isoformat()),
        
        (2, 'High Sodium Warning', 'warning', 2, None, None, 0, 150,
         'sodium_mg', '>', 200, None, 'danger',
         'High sodium ({value}mg). Avoid for hypertension.',
         'Look for low-sodium options', None, None, None, None, 7, 1, 'system', datetime.now().isoformat()),
        
        (3, 'High Fat Warning', 'warning', 3, None, None, 0, 150,
         'fat_g', '>', 15, None, 'warning',
         'High fat content ({value}g). Not ideal for cholesterol.',
         'Choose low-fat alternatives', None, None, None, None, 6, 1, 'system', datetime.now().isoformat()),
        
        (4, 'Healthy Choice Praise', 'recommendation', None, None, None, 0, 150,
         'health_score', '>', 70, None, 'info',
         'Great choice! Healthy score: {value}/100',
         'Keep making healthy choices!', None, None, None, None, 3, 1, 'system', datetime.now().isoformat())
    ]
    cursor.executemany('''
        INSERT OR IGNORE INTO nutrition_rules 
        (id, rule_name, rule_type, target_condition_id, target_preference_id, target_gender, min_age, max_age,
         nutrient_field, comparison_operator, threshold_value, custom_logic, severity, message_template,
         alternative_suggestion, learn_more_url, recommend_category_id, recommend_max_nutrient, recommend_max_value,
         priority, is_active, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', rules)
    
    # Insert sample products - FIXED: Now with 45 values matching the 45 columns
    products = [
        # PROD001 - Apple  (caffeine=0, gi=39)
        ('PROD001', '123456789001', 'Apple', 'Nature Fresh', 5, 'Fresh red apple',
         182, None, 1, 95, 0.5, 25, 19, 0, 4.4, 0.3, 0.1, 0, 0, 1, 195, 5, 6, 100, 10, 0,
         'Apple', 'None', 1, 1, 1, 1, 0, 85, 1, 'Apple Farms', 'USA', 'Store in cool place', 30,
         'https://images.unsplash.com/photo-1568702846914-96b305d2aaeb?w=400', None,
         0, 39,
         datetime.now().isoformat(), datetime.now().isoformat(), 1),

        # PROD002 - Whole Wheat Bread  (caffeine=0, gi=74)
        ('PROD002', '123456789002', 'Whole Wheat Bread', 'Nature Own', 4, '100% whole wheat bread',
         45, None, 20, 110, 5, 20, 2, 0, 3, 1.5, 0.3, 0, 0, 180, 100, 0, 20, 0, 0, 0,
         'Whole Wheat Flour, Water, Yeast, Salt', 'Contains Wheat', 0, 1, 1, 1, 1, 80, 1,
         'Nature Own', 'USA', 'Store in cool dry place', 7,
         'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400', None,
         0, 74,
         datetime.now().isoformat(), datetime.now().isoformat(), 1),

        # PROD003 - Greek Yogurt  (caffeine=0, gi=11)
        ('PROD003', '123456789003', 'Greek Yogurt', 'Chobani', 3, 'High protein yogurt',
         150, 150, 1, 100, 17, 6, 4, 0, 0, 0, 10, 0, 0, 65, 240, 200, 20, 0, 0, 0,
         'Cultured Pasteurized Nonfat Milk, Live Active Cultures', 'Contains Milk', 1, 0, 0, 1, 0, 85, 1,
         'Chobani', 'USA', 'Refrigerate', 21,
         'https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=400', None,
         0, 11,
         datetime.now().isoformat(), datetime.now().isoformat(), 1),

        # PROD004 - Potato Chips  (caffeine=0, gi=56)
        ('PROD004', '123456789004', 'Potato Chips', 'Lays', 2, 'Classic potato chips',
         28, None, 8, 160, 2, 15, 1, 0, 1, 10, 1, 0, 0, 170, 350, 0, 0, 0, 0, 0,
         'Potatoes, Vegetable Oil, Salt', 'None', 1, 1, 1, 1, 0, 40, 0,
         'Frito-Lay', 'USA', 'Store in cool dry place', 90,
         'https://images.unsplash.com/photo-1566478989037-eec170784d0b?w=400', None,
         0, 56,
         datetime.now().isoformat(), datetime.now().isoformat(), 1),

        # PROD005 - Pepsi Regular  (caffeine=38mg/330ml, gi=63)
        ('PROD005', '123456789005', 'Pepsi Regular', 'PepsiCo', 1, 'Carbonated soft drink',
         330, 330, 1, 150, 0, 41, 41, 41, 0, 0, 0, 0, 0, 30, 0, 0, 0, 0, 0, 0,
         'Carbonated Water, High Fructose Corn Syrup, Caramel Color, Phosphoric Acid, Caffeine, Natural Flavors',
         'None', 1, 0, 0, 0, 0, 20, 0,
         'PepsiCo Inc.', 'USA', 'Store in cool place', 180,
         'https://images.unsplash.com/photo-1629203851122-3726ecdf080e?w=400', None,
         38, 63,
         datetime.now().isoformat(), datetime.now().isoformat(), 1),

        # PROD006 - Pepsi Zero Sugar  (caffeine=35mg, gi=0)
        ('PROD006', '123456789006', 'Pepsi Zero Sugar', 'PepsiCo', 1, 'Zero sugar cola',
         330, 330, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 40, 0, 0, 0, 0, 0, 0,
         'Carbonated Water, Caramel Color, Phosphoric Acid, Aspartame, Potassium Benzoate, Natural Flavors, Caffeine',
         'Contains Phenylalanine', 1, 0, 0, 0, 0, 75, 1,
         'PepsiCo Inc.', 'USA', 'Store in cool place', 180,
         'https://images.unsplash.com/photo-1629203851252-3448c5e0c6f9?w=400', None,
         35, 0,
         datetime.now().isoformat(), datetime.now().isoformat(), 1),

        # PROD007 - Dark Chocolate  (caffeine=12mg, gi=23)
        ('PROD007', '123456789007', 'Dark Chocolate', 'Lindt', 2, 'Premium dark chocolate',
         25, None, 4, 150, 2, 8, 3, 3, 3, 12, 7, 0, 0, 5, 200, 0, 0, 0, 0, 0,
         'Cocoa Mass, Sugar, Cocoa Butter, Vanilla', 'None', 1, 1, 1, 1, 0, 65, 1,
         'Lindt', 'Switzerland', 'Store in cool dry place', 365,
         'https://images.unsplash.com/photo-1511381939415-e44015466834?w=400', None,
         12, 23,
         datetime.now().isoformat(), datetime.now().isoformat(), 1),

        # PROD008 - Mixed Nuts  (caffeine=0, gi=15)
        ('PROD008', '123456789008', 'Mixed Nuts', 'Planters', 2, 'Salted mixed nuts',
         50, None, 10, 300, 10, 10, 2, 0, 3, 27, 4, 0, 0, 120, 400, 0, 0, 0, 0, 0,
         'Peanuts, Almonds, Cashews, Brazil Nuts, Salt', 'Contains Peanuts, Tree Nuts', 1, 1, 1, 1, 0, 70, 1,
         'Planters', 'USA', 'Store in cool dry place', 180,
         'https://images.unsplash.com/photo-1533090161767-e6ffed986c88?w=400', None,
         0, 15,
         datetime.now().isoformat(), datetime.now().isoformat(), 1),

        # PROD009 - Orange Juice  (caffeine=0, gi=52)
        ('PROD009', '123456789009', 'Orange Juice', 'Tropicana', 1, '100% pure orange juice',
         240, 240, 1, 110, 2, 26, 22, 0, 0, 0, 0, 0, 0, 0, 450, 20, 120, 0, 0, 0,
         'Orange Juice', 'None', 1, 1, 1, 1, 0, 75, 1,
         'Tropicana', 'USA', 'Refrigerate after opening', 30,
         'https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?w=400', None,
         0, 52,
         datetime.now().isoformat(), datetime.now().isoformat(), 1),

        # PROD010 - Mineral Water  (caffeine=0, gi=0)
        ('PROD010', '123456789010', 'Mineral Water', 'Evian', 1, 'Natural spring water',
         500, 500, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 0, 80, 20, 0, 0, 0,
         'Natural Spring Water', 'None', 1, 1, 1, 1, 1, 95, 1,
         'Evian', 'France', 'Store in cool place', 730,
         'https://images.unsplash.com/photo-1523362628745-0c100150b504?w=400', None,
         0, 0,
         datetime.now().isoformat(), datetime.now().isoformat(), 1)
    ]
    
    # Named-column INSERT so column count never mismatches existing DBs
    for p in products:
        cursor.execute('''
            INSERT OR IGNORE INTO products (
                id, barcode, name, brand, category_id, description,
                serving_size_g, serving_size_ml, servings_per_container,
                calories, protein_g, carbohydrates_g, sugar_g, added_sugar_g, fiber_g,
                fat_g, saturated_fat_g, trans_fat_g, cholesterol_mg, sodium_mg,
                potassium_mg, calcium_mg, iron_mg, vitamin_a_iu, vitamin_c_mg, vitamin_d_iu,
                caffeine_mg, glycemic_index,
                ingredients, allergen_info,
                is_gluten_free, is_vegan, is_vegetarian, is_organic, is_non_gmo,
                health_score, is_healthy, manufacturer, country_of_origin,
                storage_instructions, expiry_days, image_url, qr_code_url,
                created_at, last_updated, is_active
            ) VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                ?,?,?,?,?,?
            )
        ''', p)
    
    # Insert product allergens
    product_allergens = [
        ('PROD003', 2, 0, 'contains'),  # Yogurt contains milk
        ('PROD008', 1, 0, 'contains'),  # Nuts contains peanuts
        ('PROD002', 3, 0, 'contains'),  # Bread contains wheat
    ]
    cursor.executemany('INSERT OR IGNORE INTO product_allergens VALUES (?, ?, ?, ?)', product_allergens)
    
    # Create admin user
    admin_hash = hashlib.sha256('admin123'.encode()).hexdigest()
    cursor.execute('''
        INSERT OR IGNORE INTO users 
        (id, email, password_hash, first_name, last_name, is_admin)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (1, 'admin@nutrition.com', admin_hash, 'Admin', 'User', 1))
    
    # Create regular user
    user_hash = hashlib.sha256('password123'.encode()).hexdigest()
    cursor.execute('''
        INSERT OR IGNORE INTO users 
        (id, email, password_hash, first_name, last_name, is_admin,
         age, weight_kg, height_cm, gender, activity_level, health_goal,
         bp_systolic, bp_diastolic, fasting_blood_sugar, hba1c,
         total_cholesterol, ldl_mg, hdl_mg, triglycerides_mg,
         daily_calorie_target, daily_sugar_limit_g, daily_sodium_limit_mg, daily_fat_limit_g,
         profile_complete)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (2, 'john@example.com', user_hash, 'John', 'Doe', 0,
          45, 82, 175, 'male', 'moderate', 'weight_loss',
          138, 88, 145, 7.2,
          210, 130, 38, 180,
          1800, 25, 1500, 65,
          1))
    
    # Add health conditions for users
    user_conditions = [
        (2, 1, '2023-01-15', 'moderate', 1, 'Metformin', 'Diagnosed 2023', '2024-01-15'),
        (2, 2, '2023-03-20', 'mild', 1, 'Lisinopril', 'Controlled with medication', '2024-01-15'),
    ]
    cursor.executemany('INSERT OR IGNORE INTO user_health_conditions VALUES (?, ?, ?, ?, ?, ?, ?, ?)', user_conditions)
    
    # Add allergies
    user_allergies = [
        (2, 1, 'severe', '2015-06-10', '2023-12-01', 1),
    ]
    cursor.executemany('INSERT OR IGNORE INTO user_allergies VALUES (?, ?, ?, ?, ?, ?)', user_allergies)

    # Add medications
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            medication_name TEXT NOT NULL,
            dosage TEXT,
            frequency TEXT,
            condition_treated TEXT,
            interactions_flag TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    user_meds = [
        (2, 'Metformin', '500mg', 'Twice daily', 'Diabetes', 'Avoid high sugar foods', datetime.now().isoformat()),
        (2, 'Lisinopril', '10mg', 'Once daily', 'Hypertension', 'Avoid high sodium, high potassium', datetime.now().isoformat()),
    ]
    cursor.executemany('''
        INSERT OR IGNORE INTO user_medications
        (user_id, medication_name, dosage, frequency, condition_treated, interactions_flag, added_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', user_meds)
    
    # Add dietary preferences
    user_prefs = [
        (2, 4, 'strict', '2023-01-01', 'Doctor recommended for hypertension'),
    ]
    cursor.executemany('INSERT OR IGNORE INTO user_dietary_preferences VALUES (?, ?, ?, ?, ?)', user_prefs)
    
    # Add some scan history
    scan_history = [
        (1, 2, 'PROD001', datetime.now().isoformat(), 'consumed', 1.0, 'snack', 'Low sugar, good choice', 'followed', 5, 'Great recommendation!', None, None, 'web'),
        (2, 2, 'PROD004', datetime.now().isoformat(), 'avoided', 0, None, 'High sodium warning', 'followed', 4, 'Thank you for the warning', None, None, 'web'),
        (3, 1, 'PROD002', datetime.now().isoformat(), 'consumed', 0.5, 'breakfast', None, None, None, None, None, None, 'web'),
    ]
    cursor.executemany('''
        INSERT OR IGNORE INTO scan_history 
        (id, user_id, product_id, scanned_at, user_decision, consumption_amount, consumption_time, assistant_advice_given, user_response, feedback_rating, feedback_comment, location_lat, location_lng, device_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', scan_history)
    
    # Add a chatbot conversation example
    chatbot_convs = [
        (1, 2, 'session_001', 'Is Pepsi good for diabetes?', 
         'Pepsi Regular contains 41g of sugar per serving, which is very high for diabetes management. I recommend Pepsi Zero Sugar instead with 0g sugar.',
         'PROD005', 'health_analysis', '{"product": "Pepsi", "condition": "diabetes"}', 0.9, 1, datetime.now().isoformat()),
    ]
    cursor.executemany('INSERT OR IGNORE INTO chatbot_conversations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', chatbot_convs)
    
    # Create indexes for better performance
    print("Creating indexes for better performance...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_history_user ON scan_history(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_history_product ON scan_history(product_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_conditions ON user_health_conditions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_allergies ON user_allergies(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chatbot_user ON chatbot_conversations(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chatbot_session ON chatbot_conversations(session_id)")
    
    conn.commit()
    conn.close()
    
    print("\n" + "="*50)
    print("✅ Database 'nutrition_enhanced.db' created successfully!")
    print("="*50)
    print("\n📊 Database Statistics:")
    print("   - 2 users (admin & regular)")
    print("   - 10 sample products")
    print("   - 4 health conditions")
    print("   - 4 allergens")
    print("   - 4 dietary preferences")
    print("   - 4 nutrition rules")
    print("   - 3 scan history records")
    print("   - 1 chatbot conversation")
    print("\n🔐 Login Credentials:")
    print("   Admin: admin@nutrition.com / admin123")
    print("   User:  john@example.com / password123")
    print("\n📋 User Health Profile (John):")
    print("   - Diabetes (Type 2)")
    print("   - Hypertension")
    print("   - Peanut allergy (severe)")
    print("   - Follows low-sodium diet")
    print("\n🚀 Next Steps:")
    print("   1. Run: python app.py")
    print("   2. Login with demo account")
    print("   3. Try the AI Assistant at /assistant")
    print("="*50)

def verify_database():
    """Verify the database was created correctly"""
    conn = sqlite3.connect('nutrition_enhanced.db')
    cursor = conn.cursor()
    
    print("\n🔍 Verifying database...")
    
    # Check all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"   Table '{table_name}': {count} rows")
    
    conn.close()
    print("✅ Verification complete!")

if __name__ == '__main__':
    print("🧠 Creating Nutrition Scanner Enhanced Database...")
    print("="*50)
    create_enhanced_database()
    verify_database()
    print("="*50)