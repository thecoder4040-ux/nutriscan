from flask import Flask, render_template, request, jsonify, redirect, session, flash, url_for
from functools import wraps
import sqlite3
import pickle
import numpy as np
import os
from datetime import datetime
import qrcode
from io import BytesIO
import base64
import hashlib
import urllib.parse
import re
from dotenv import load_dotenv

load_dotenv()

# Global cache for AI-generated products
_ai_product_cache = {}
from ai_assistant import ai_bp

app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'nutrition-scanner-secret-key-2024')

# ── Register AI blueprint ──
app.register_blueprint(ai_bp)

# ── Single DB path (everything uses this now) ──
DB_PATH = 'nutrition_enhanced.db'

# ── Initialize database & model ──
import database
database.init_db()

if os.path.exists('health_model.pkl'):
    with open('health_model.pkl', 'rb') as f:
        model = pickle.load(f)
else:
    model = database.train_ml_model()


# ─────────────────────────────────────────────
#  Helper functions
# ─────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_product(product_id):
    product_id = str(product_id).strip()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE UPPER(id) = UPPER(?)", (product_id,))
    product = cur.fetchone()
    conn.close()
    return product

def is_admin():
    if 'user_id' not in session:
        return False
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT is_admin FROM users WHERE id = ?", (session['user_id'],))
    result = cur.fetchone()
    conn.close()
    return result and result['is_admin'] == 1

def get_user_health(user_id):
    """Get user's health conditions from the new schema"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT hc.name, uhc.severity
        FROM user_health_conditions uhc
        JOIN health_conditions hc ON hc.id = uhc.condition_id
        WHERE uhc.user_id = ?
    """, (user_id,))
    conditions = cur.fetchall()
    conn.close()
    return conditions


# ─────────────────────────────────────────────
#  Auth decorators
# ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            session['next_url'] = request.url
            flash('Please login first to access this feature', 'warning')
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            session['next_url'] = request.url
            flash('Please login first', 'warning')
            return redirect('/login')
        if not is_admin():
            flash('Admin access required!', 'danger')
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function


# ─────────────────────────────────────────────
#  Template filters
# ─────────────────────────────────────────────
@app.template_filter('healthy_badge')
def healthy_badge(is_healthy):
    if is_healthy == 1:
        return '<span class="badge bg-success">HEALTHY</span>'
    return '<span class="badge bg-danger">RISKY</span>'

@app.template_filter('healthy_stars')
def healthy_stars(is_healthy):
    if is_healthy == 1:
        return '⭐⭐⭐⭐⭐ <span class="text-success">(Excellent)</span>'
    return '⭐☆☆☆☆ <span class="text-danger">(Poor)</span>'


# ─────────────────────────────────────────────
#  Main routes
# ─────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET','POST'])
def contact():
    if request.method == 'POST':
        name    = request.form.get('name','').strip()
        email   = request.form.get('email','').strip()
        subject = request.form.get('subject','').strip()
        message = request.form.get('message','').strip()
        if name and email and subject and message:
            try:
                conn = get_db()
                cur  = conn.cursor()
                cur.execute('''CREATE TABLE IF NOT EXISTS contact_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL, email TEXT NOT NULL,
                    subject TEXT NOT NULL, message TEXT NOT NULL,
                    is_read INTEGER DEFAULT 0,
                    sent_at TEXT DEFAULT (datetime('now')))''')
                cur.execute('INSERT INTO contact_messages (name,email,subject,message) VALUES (?,?,?,?)',
                    (name, email, subject, message))
                conn.commit()
                conn.close()
                flash('Your message has been sent! We will get back to you soon.', 'success')
            except Exception as e:
                flash(f'Error sending message: {str(e)}', 'danger')
        else:
            flash('Please fill in all fields.', 'danger')
        return redirect('/contact')
    return render_template('contact.html')

@app.route('/product', methods=['POST'])
def product_lookup():
    product_id = request.form.get('product_id', '').strip()
    if not product_id:
        flash('Please enter a product ID.', 'warning')
        return redirect('/')
    product = get_product(product_id)
    if not product:
        flash(f'Product "{product_id}" not found!', 'danger')
        return redirect('/')
    return render_template('product.html', product=product)


# ─────────────────────────────────────────────
#  AI Assistant route
# ─────────────────────────────────────────────
@app.route('/assistant')
@login_required
def assistant():
    product_id = request.args.get('product', '')
    return render_template('ai_chat.html', product_id=product_id)


# ─────────────────────────────────────────────
#  Register
# ─────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('firstName', '').strip()
        last_name  = request.form.get('lastName', '').strip()
        email      = request.form.get('email', '').strip().lower()
        password   = request.form.get('password', '').strip()

        if not all([first_name, last_name, email, password]):
            flash('All fields are required!', 'danger')
            return redirect('/register')

        if len(password) < 6:
            flash('Password must be at least 6 characters!', 'danger')
            return redirect('/register')

        password_hash = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db()
        cur = conn.cursor()
        try:
            # Basic registration
            age        = request.form.get('age', '').strip()
            gender     = request.form.get('gender', '').strip()
            weight_kg  = request.form.get('weight_kg', '').strip()
            height_cm  = request.form.get('height_cm', '').strip()
            has_diabetes     = request.form.get('diabetes') == 'on'
            has_hyp          = request.form.get('hypertension') == 'on'
            has_chol         = request.form.get('high_cholesterol') == 'on'
            has_heart        = request.form.get('heart_disease') == 'on'

            cur.execute('''
                INSERT INTO users (email, password_hash, first_name, last_name, created_at,
                    age, gender, weight_kg, height_cm)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (email, password_hash, first_name, last_name, datetime.now().isoformat(),
                   int(age) if age else None,
                   gender if gender else None,
                   float(weight_kg) if weight_kg else None,
                   float(height_cm) if height_cm else None))
            user_id = cur.lastrowid

            # Save health conditions from registration if provided
            cond_map = {'diabetes':1,'hypertension':2,'high_cholesterol':3,'heart_disease':4}
            for cname, cid in cond_map.items():
                if request.form.get(cname) == 'on':
                    try:
                        cur.execute(
                            "INSERT OR IGNORE INTO user_health_conditions (user_id,condition_id) VALUES (?,?)",
                            (user_id, cid))
                    except Exception:
                        pass

            conn.commit()

            session['user_id']    = user_id
            session['user_name']  = f"{first_name} {last_name}"
            session['user_email'] = email
            session['is_admin']   = False

            flash('Registration successful! Welcome to Nutrition Scanner!', 'success')
            return redirect('/')

        except sqlite3.IntegrityError:
            flash('Email already registered! Please use another email.', 'danger')
        finally:
            conn.close()

    return render_template('register.html')


# ─────────────────────────────────────────────
#  Login / Logout
# ─────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        if not email or not password:
            flash('Please enter both email and password', 'danger')
            return redirect('/login')

        password_hash = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            SELECT id, first_name, last_name, is_admin FROM users
            WHERE email = ? AND password_hash = ?
        ''', (email, password_hash))
        user = cur.fetchone()
        conn.close()

        if user:
            session['user_id']    = user['id']
            session['user_name']  = f"{user['first_name']} {user['last_name']}"
            session['user_email'] = email
            session['is_admin']   = user['is_admin'] == 1

            if user['is_admin'] == 1:
                flash('Admin login successful! Welcome to the dashboard.', 'success')
                return redirect('/admin')
            else:
                next_url = session.pop('next_url', None)
                flash('Login successful!', 'success')
                return redirect(next_url or '/')
        else:
            flash('Invalid email or password!', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect('/')


# ─────────────────────────────────────────────
#  Profile
# ─────────────────────────────────────────────
@app.route('/profile')
@login_required
def profile():
    conn = get_db()
    cur  = conn.cursor()

    # Ensure new columns exist
    for col, defn in [
        ("bp_systolic","INTEGER DEFAULT 120"), ("bp_diastolic","INTEGER DEFAULT 80"),
        ("fasting_blood_sugar_mg","REAL DEFAULT 100"), ("hba1c_pct","REAL"),
        ("total_cholesterol_mg","REAL DEFAULT 180"), ("ldl_mg","REAL"),
        ("hdl_mg","REAL"), ("triglycerides_mg","REAL"), ("medications","TEXT"),
        ("is_pregnant","INTEGER DEFAULT 0"), ("is_breastfeeding","INTEGER DEFAULT 0"),
        ("profile_complete","INTEGER DEFAULT 0"), ("profile_saved_at","TEXT"),
        ("daily_protein_target_g","INTEGER DEFAULT 50"), ("daily_fiber_target_g","INTEGER DEFAULT 28"),
    ]:
        try: cur.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
        except: pass

    cur.execute('''
        SELECT id, first_name, last_name, email, created_at,
               age, gender, weight_kg, height_cm, activity_level, health_goal,
               daily_calorie_target, daily_sugar_limit_g, daily_sodium_limit_mg,
               daily_fat_limit_g, daily_protein_target_g, daily_fiber_target_g,
               bp_systolic, bp_diastolic, fasting_blood_sugar_mg, hba1c_pct,
               total_cholesterol_mg, ldl_mg, hdl_mg, triglycerides_mg,
               medications, is_pregnant, is_breastfeeding,
               profile_complete, profile_saved_at
        FROM users WHERE id = ?
    ''', (session['user_id'],))
    user_data = cur.fetchone()

    cur.execute('''
        SELECT hc.id, hc.name FROM user_health_conditions uhc
        JOIN health_conditions hc ON hc.id = uhc.condition_id
        WHERE uhc.user_id = ?
    ''', (session['user_id'],))
    conditions = cur.fetchall()
    condition_ids = [r['id'] for r in conditions]

    cur.execute('''
        SELECT a.id, a.name FROM user_allergies ua
        JOIN allergens a ON a.id = ua.allergen_id
        WHERE ua.user_id = ?
    ''', (session['user_id'],))
    allergies = cur.fetchall()
    allergen_ids = [r['id'] for r in allergies]
    conn.close()

    # Calculate days remaining
    days_remaining = 0
    if user_data and user_data['profile_saved_at']:
        try:
            from datetime import timedelta
            saved = datetime.fromisoformat(str(user_data['profile_saved_at']))
            delta = timedelta(days=7) - (datetime.now() - saved)
            days_remaining = max(0, delta.days)
        except: pass

    if user_data:
        return render_template('profile.html',
                               user=user_data,
                               conditions=conditions,
                               condition_ids=condition_ids,
                               allergies=allergies,
                               allergen_ids=allergen_ids,
                               days_remaining=days_remaining)
    return redirect('/')


# ─────────────────────────────────────────────
#  Product Image Fetching (multi-source fallback)
# ─────────────────────────────────────────────
def fetch_product_image(product_name: str):
    """Fetch product image - SerpApi primary, Open Food Facts secondary."""
    import urllib.request, json
    ua = {"User-Agent": "Mozilla/5.0 NutriScan/1.0"}
    serp_key = os.environ.get("SERP_API_KEY")
    if serp_key:
        name_lower = product_name.lower()
        if any(w in name_lower for w in ["sprite","cola","pepsi","fanta","7up","miranda","juice","water","milk","tea","coffee","beer","wine","soda","beverage","drink","limca"]):
            suffix = "drink bottle can"
        elif any(w in name_lower for w in ["biscuit","cookie","oreo","wafer","cracker","hide and seek","bourbon","marie"]):
            suffix = "biscuit pack"
        elif any(w in name_lower for w in ["chocolate","nutella","kitkat","snickers","dairy milk","candy","toffee","munch"]):
            suffix = "chocolate product"
        elif any(w in name_lower for w in ["noodle","maggi","pasta","rice","bread","atta","flour","cereal","oats"]):
            suffix = "food packet"
        elif any(w in name_lower for w in ["chips","lays","kurkure","crisp","popcorn","snack"]):
            suffix = "snack packet"
        else:
            suffix = "food product packaging"
        for sq in [product_name + " " + suffix, product_name + " brand product"]:
            try:
                q = urllib.parse.quote(sq)
                url = f"https://serpapi.com/search.json?engine=google_images&q={q}&num=5&safe=active&api_key={serp_key}"
                req = urllib.request.Request(url, headers=ua)
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = json.loads(r.read())
                for item in data.get("images_results", []):
                    img = item.get("original") or item.get("thumbnail")
                    if img and img.startswith("http"):
                        print(f"[Image] SerpApi: {img[:70]}")
                        return img
            except Exception as e:
                print(f"[Image] SerpApi failed: {e}")
    else:
        print("[Image] SERP_API_KEY not set")
    def search_off(query):
        try:
            q = urllib.parse.quote(query)
            url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={q}&search_simple=1&action=process&json=1&page_size=10&fields=product_name,image_front_url,image_url"
            req = urllib.request.Request(url, headers=ua)
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read())
            for p in data.get("products", []):
                img = p.get("image_front_url") or p.get("image_url")
                if img and img.startswith("http"):
                    return img
        except: pass
        return None
    words = product_name.split()
    for q in [product_name, words[0], " ".join(words[:2]) if len(words)>1 else None]:
        if q:
            img = search_off(q)
            if img: return img
    return None


def correct_product_name(raw_name: str) -> str:
    """Use Groq to correct spelling and return the proper product name."""
    # Skip correction for internal IDs — return cleaned version directly
    if raw_name.startswith('AI-') or (raw_name.replace('-','').replace('_','').isupper() and len(raw_name) < 20):
        clean = raw_name.replace('AI-', '').replace('_', ' ').strip()
        return clean if clean else raw_name
    try:
        from groq import Groq
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content":
                f"""The user searched for a food product: "{raw_name}"
This may be misspelled. Return ONLY the correct, properly capitalized product name.
Examples: "neutella" -> "Nutella", "maggie noodles" -> "Maggi Noodles", "miranda" -> "Miranda Soft Drink", "oreo" -> "Oreo"
If it's already correct, return it properly capitalized.
Return ONLY the corrected name, nothing else."""}],
            max_tokens=30,
            temperature=0
        )
        corrected = resp.choices[0].message.content.strip().strip('"').strip("'")
        if corrected and len(corrected) < 80:
            print(f"[Spell] '{raw_name}' -> '{corrected}'")
            return corrected
    except Exception as e:
        print(f"[Spell] correction failed: {e}")
    return raw_name


def ai_generate_product(product_name: str):
    """Ask Groq AI to generate nutrition data for an unknown product.
    Corrects spelling, caches results so same product always returns same data."""
    import json

    # Step 1: Correct spelling
    corrected_name = correct_product_name(product_name)
    cache_key = corrected_name.lower().strip()

    # Step 2: Return cached result if available
    if cache_key in _ai_product_cache:
        print(f"[Cache] Returning cached data for: {corrected_name}")
        return _ai_product_cache[cache_key]

    try:
        from groq import Groq
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

        prompt = f"""You are a nutrition database expert. Generate accurate, realistic nutritional information for the food product: "{corrected_name}"

Return ONLY a valid JSON object with exactly these keys (no extra text, no markdown):
{{
  "id": "AI-GENERATED",
  "name": "{corrected_name}",
  "brand": "infer the real brand name",
  "description": "One sentence describing this product",
  "calories": 0,
  "protein_g": 0,
  "carbohydrates_g": 0,
  "sugar_g": 0,
  "added_sugar_g": 0,
  "fiber_g": 0,
  "fat_g": 0,
  "saturated_fat_g": 0,
  "trans_fat_g": 0,
  "sodium_mg": 0,
  "cholesterol_mg": 0,
  "potassium_mg": 0,
  "serving_size_g": 100,
  "ingredients": "List main ingredients",
  "allergen_info": "List allergens or None",
  "is_gluten_free": 0,
  "is_vegan": 0,
  "is_vegetarian": 0,
  "is_organic": 0,
  "is_non_gmo": 0,
  "health_score": 50,
  "is_healthy": 0
}}

Replace ALL 0 values with real, accurate numbers based on well-known nutrition data.
Set is_healthy to 1 if healthy, 0 otherwise.
Set health_score 0-100.
Return ONLY the JSON."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)

        defaults = {
            "barcode": None, "category_id": None, "serving_size_ml": None,
            "servings_per_container": 1, "calcium_mg": 0, "iron_mg": 0,
            "vitamin_a_iu": 0, "vitamin_c_mg": 0, "vitamin_d_iu": 0,
            "manufacturer": data.get("brand", "Unknown"),
            "country_of_origin": "Unknown", "storage_instructions": None,
            "expiry_days": None, "image_url": None, "qr_code_url": None,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(), "is_active": 1
        }
        for k, v in defaults.items():
            data.setdefault(k, v)

        # Cache it
        # Override id to use actual product name (not "AI-GENERATED")
        safe_id = re.sub(r'[^A-Za-z0-9_-]', '_', data.get('name', corrected_name))[:40]
        data['id'] = safe_id
        _ai_product_cache[cache_key] = data
        return data

    except Exception as e:
        print(f"AI product generation error: {e}")
        return None



# ─────────────────────────────────────────────
#  Product pages
# ─────────────────────────────────────────────
@app.route('/p/<product_identifier>')
def product_page(product_identifier):
    product_identifier = urllib.parse.unquote(product_identifier).strip()
    product = get_product(product_identifier)

    # Try name match in DB
    if not product:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM products WHERE LOWER(name) LIKE ? AND is_active=1 LIMIT 1",
            (f'%{product_identifier.lower()}%',)
        )
        product = cur.fetchone()
        conn.close()

    # Found in DB — fetch image and show
    if product:
        product = dict(product)  # convert Row to dict so we can add image
        if not product.get("image_url"):
            product["image_url"] = fetch_product_image(product.get("name", ""))
        return render_template('product.html', product=product, ai_generated=False)

    # Not in DB — ask AI to generate nutrition info (includes spelling correction)
    ai_product = ai_generate_product(product_identifier)
    if ai_product:
        if not ai_product.get("image_url"):
            # Use corrected name for better image results
            ai_product["image_url"] = fetch_product_image(ai_product.get("name", product_identifier))
        return render_template('product.html', product=ai_product, ai_generated=True)

    flash(f'Product "{product_identifier}" not found and AI could not generate data. Please try a different name.', 'danger')
    return redirect('/')

@app.route('/api/save-ai-product', methods=['POST'])
def save_ai_product():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data"}), 400
        name = data.get("name", "").strip()
        pid  = "AI-" + re.sub(r'[^A-Z0-9]', '', name.upper())[:10]
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("SELECT id FROM products WHERE LOWER(name) = ? AND is_active = 1", (name.lower(),))
        if cur.fetchone():
            conn.close()
            return jsonify({"success": True, "message": "Already in database!"})
        cur.execute("""
            INSERT INTO products (id, name, brand, description,
                calories, protein_g, carbohydrates_g, sugar_g, added_sugar_g, fiber_g,
                fat_g, saturated_fat_g, trans_fat_g, cholesterol_mg, sodium_mg, potassium_mg,
                calcium_mg, iron_mg, vitamin_a_iu, vitamin_c_mg, vitamin_d_iu,
                serving_size_g, ingredients, allergen_info,
                is_gluten_free, is_vegan, is_vegetarian, is_organic, is_non_gmo,
                health_score, is_healthy, manufacturer, country_of_origin,
                image_url, is_active, created_at, last_updated)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            pid, name, data.get("brand",""), data.get("description",""),
            data.get("calories",0), data.get("protein_g",0), data.get("carbohydrates_g",0),
            data.get("sugar_g",0), data.get("added_sugar_g",0), data.get("fiber_g",0),
            data.get("fat_g",0), data.get("saturated_fat_g",0), data.get("trans_fat_g",0),
            data.get("cholesterol_mg",0), data.get("sodium_mg",0), data.get("potassium_mg",0),
            data.get("calcium_mg",0), data.get("iron_mg",0), data.get("vitamin_a_iu",0),
            data.get("vitamin_c_mg",0), data.get("vitamin_d_iu",0),
            data.get("serving_size_g",100), data.get("ingredients",""), data.get("allergen_info",""),
            int(data.get("is_gluten_free",0)), int(data.get("is_vegan",0)),
            int(data.get("is_vegetarian",0)), int(data.get("is_organic",0)),
            int(data.get("is_non_gmo",0)), int(data.get("health_score",50)),
            int(data.get("is_healthy",0)),
            data.get("manufacturer", data.get("brand","")),
            data.get("country_of_origin","Unknown"),
            data.get("image_url",""), 1,
            datetime.now().isoformat(), datetime.now().isoformat()
        ))
        conn.commit(); conn.close()
        return jsonify({"success": True, "message": f"'{name}' saved to database!", "id": pid})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/compare/<product1>/vs/<product2>')
def compare_products(product1, product2):
    product1 = urllib.parse.unquote(product1).strip()
    product2 = urllib.parse.unquote(product2).strip()

    def get_by_id_or_name(term):
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("SELECT * FROM products WHERE UPPER(id) = UPPER(?)", (term,))
        p = cur.fetchone()
        if not p:
            cur.execute("SELECT * FROM products WHERE LOWER(name) LIKE ? AND is_active=1 LIMIT 1",
                        (f'%{term.lower()}%',))
            p = cur.fetchone()
        conn.close()
        if p:
            return dict(p), False
        ai_p = ai_generate_product(term)
        if ai_p:
            if not ai_p.get("image_url"):
                ai_p["image_url"] = fetch_product_image(ai_p.get("name", term))
            return ai_p, True
        return None, False

    p1, p1_ai = get_by_id_or_name(product1)
    p2, p2_ai = get_by_id_or_name(product2)

    if not p1 or not p2:
        flash('One or both products not found. Please try different names.', 'danger')
        return redirect('/')

    return render_template('compare.html', product1=p1, product2=p2, p1_ai=p1_ai, p2_ai=p2_ai)


# ─────────────────────────────────────────────
#  Search
# ─────────────────────────────────────────────
@app.route('/api/compare-verdict', methods=['POST'])
def compare_verdict():
    """Generate AI verdict comparing two products using Groq."""
    try:
        data   = request.get_json()
        p1     = data.get('product1', {})
        p2     = data.get('product2', {})
        from groq import Groq
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        prompt = f"""You are a nutrition expert. Compare these two food products and give a verdict.

Product 1: {p1.get('name')}
Calories: {p1.get('calories')} kcal, Sugar: {p1.get('sugar_g')}g, Fat: {p1.get('fat_g')}g, Protein: {p1.get('protein_g')}g, Sodium: {p1.get('sodium_mg')}mg, Fiber: {p1.get('fiber_g')}g, Health Score: {p1.get('health_score')}/100

Product 2: {p2.get('name')}
Calories: {p2.get('calories')} kcal, Sugar: {p2.get('sugar_g')}g, Fat: {p2.get('fat_g')}g, Protein: {p2.get('protein_g')}g, Sodium: {p2.get('sodium_mg')}mg, Fiber: {p2.get('fiber_g')}g, Health Score: {p2.get('health_score')}/100

Give: 1) A clear winner, 2) 2-3 specific reasons why, 3) Who should prefer the other product, 4) One-line recommendation. No markdown symbols."""
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400, temperature=0.4
        )
        text = resp.choices[0].message.content.strip()
        return jsonify({"success": True, "verdict": text})
    except Exception as e:
        print(f"[Verdict] Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/search')
def search_results():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT * FROM products
        WHERE is_active = 1
          AND (LOWER(name) LIKE ? OR LOWER(id) LIKE ? OR LOWER(brand) LIKE ?)
        ORDER BY
            CASE
                WHEN LOWER(name) LIKE ? THEN 1
                WHEN LOWER(id)   = ?    THEN 2
                WHEN LOWER(id)   LIKE ? THEN 3
                ELSE 4
            END, name
    ''', (
        f'%{query.lower()}%', f'%{query.lower()}%', f'%{query.lower()}%',
        f'{query.lower()}%', query.lower(), f'{query.lower()}%'
    ))
    products = cur.fetchall()
    conn.close()

    return render_template('search.html', query=query, products=products)


# ─────────────────────────────────────────────
#  Analyze
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
#  Full user profile loader
# ─────────────────────────────────────────────
def get_full_user_profile(user_id):
    """Load complete health profile: vitals, conditions, allergies, prefs."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT id, first_name, last_name, age, gender, weight_kg, height_cm,
                   activity_level, health_goal,
                   daily_calorie_target, daily_sugar_limit_g, daily_sodium_limit_mg,
                   daily_fat_limit_g, daily_protein_target_g, daily_fiber_target_g,
                   bp_systolic, bp_diastolic,
                   fasting_blood_sugar_mg, hba1c_pct,
                   total_cholesterol_mg, ldl_mg, hdl_mg, triglycerides_mg,
                   resting_heart_rate, is_pregnant, is_breastfeeding,
                   medications, profile_complete
            FROM users WHERE id = ?
        """, (user_id,))
        user = cur.fetchone()
    except Exception:
        # Older DB — fall back to basic columns only
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cur.fetchone()

    if not user:
        conn.close()
        return {}

    profile = dict(user)

    # Apply defaults for columns that may not exist yet
    # Only set daily limit defaults (needed for AI analysis math)
    # Clinical vitals are left blank so new users see empty profile
    profile.setdefault('daily_calorie_target', 2000)
    profile.setdefault('daily_sugar_limit_g', 50)
    profile.setdefault('daily_sodium_limit_mg', 2300)
    profile.setdefault('daily_fat_limit_g', 78)
    profile.setdefault('daily_protein_target_g', 50)
    profile.setdefault('daily_fiber_target_g', 28)
    profile.setdefault('health_goal', 'general_wellness')

    # Health conditions
    try:
        cur.execute("""
            SELECT hc.name, uhc.severity, uhc.medication
            FROM user_health_conditions uhc
            JOIN health_conditions hc ON hc.id = uhc.condition_id
            WHERE uhc.user_id = ?
        """, (user_id,))
        profile['conditions']      = [dict(r) for r in cur.fetchall()]
        profile['condition_names'] = [c['name'].lower() for c in profile['conditions']]
    except Exception:
        profile['conditions']      = []
        profile['condition_names'] = []

    # Allergies
    try:
        cur.execute("""
            SELECT a.name, ua.reaction_severity, ua.epipen_required
            FROM user_allergies ua
            JOIN allergens a ON a.id = ua.allergen_id
            WHERE ua.user_id = ?
        """, (user_id,))
        profile['allergies']      = [dict(r) for r in cur.fetchall()]
        profile['allergen_names'] = [a['name'].lower() for a in profile['allergies']]
    except Exception:
        profile['allergies']      = []
        profile['allergen_names'] = []

    # Dietary preferences
    try:
        cur.execute("""
            SELECT dp.name, udp.adherence_level
            FROM user_dietary_preferences udp
            JOIN dietary_preferences dp ON dp.id = udp.preference_id
            WHERE udp.user_id = ?
        """, (user_id,))
        profile['diet_prefs'] = [dict(r) for r in cur.fetchall()]
    except Exception:
        profile['diet_prefs'] = []

    conn.close()
    return profile


# ─────────────────────────────────────────────
#  Profile expiry: clear vitals after 7 days
# ─────────────────────────────────────────────
def check_profile_expiry(user_id):
    """If profile was saved more than 7 days ago, wipe clinical vitals and return True (expired)."""
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("SELECT profile_saved_at FROM users WHERE id=?", (user_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            conn.close()
            return False
        from datetime import timedelta
        saved_at = datetime.fromisoformat(str(row[0]))
        if datetime.now() - saved_at > timedelta(days=7):
            # Wipe clinical vitals
            cur.execute("""
                UPDATE users SET
                    bp_systolic=120, bp_diastolic=80,
                    fasting_blood_sugar_mg=100, hba1c_pct=NULL,
                    total_cholesterol_mg=180, ldl_mg=NULL, hdl_mg=NULL,
                    triglycerides_mg=NULL, medications=NULL,
                    is_pregnant=0, is_breastfeeding=0,
                    profile_complete=0, profile_saved_at=NULL
                WHERE id=?
            """, (user_id,))
            conn.commit()
            conn.close()
            return True
    except Exception as e:
        print(f"[expiry check] {e}")
    conn.close()
    return False


# ─────────────────────────────────────────────
#  /api/save-health-profile  — save profile from modal (7-day retention)
# ─────────────────────────────────────────────
@app.route('/api/save-health-profile', methods=['POST'])
@login_required
def save_health_profile():
    data = request.get_json() or {}
    try:
        conn = get_db(); cur = conn.cursor()

        # Ensure new columns exist (safe migration)
        for col, defn in [
            ("bp_systolic",           "INTEGER DEFAULT 120"),
            ("bp_diastolic",          "INTEGER DEFAULT 80"),
            ("fasting_blood_sugar_mg","REAL DEFAULT 100"),
            ("hba1c_pct",             "REAL"),
            ("total_cholesterol_mg",  "REAL DEFAULT 180"),
            ("ldl_mg",                "REAL"),
            ("hdl_mg",                "REAL"),
            ("triglycerides_mg",      "REAL"),
            ("medications",           "TEXT"),
            ("is_pregnant",           "INTEGER DEFAULT 0"),
            ("is_breastfeeding",      "INTEGER DEFAULT 0"),
            ("profile_complete",      "INTEGER DEFAULT 0"),
            ("profile_saved_at",      "TEXT"),
            ("daily_protein_target_g","INTEGER DEFAULT 50"),
            ("daily_fiber_target_g",  "INTEGER DEFAULT 28"),
        ]:
            try:
                cur.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
            except Exception:
                pass

        cur.execute("""
            UPDATE users SET
                age                   = COALESCE(?, age),
                gender                = COALESCE(?, gender),
                weight_kg             = COALESCE(?, weight_kg),
                height_cm             = COALESCE(?, height_cm),
                bp_systolic           = COALESCE(?, 120),
                bp_diastolic          = COALESCE(?, 80),
                fasting_blood_sugar_mg= COALESCE(?, 100),
                hba1c_pct             = ?,
                total_cholesterol_mg  = COALESCE(?, 180),
                ldl_mg                = ?,
                hdl_mg                = ?,
                triglycerides_mg      = ?,
                medications           = ?,
                is_pregnant           = ?,
                is_breastfeeding      = ?,
                profile_complete      = 1,
                profile_saved_at      = ?
            WHERE id = ?
        """, (
            data.get('age'),        data.get('gender'),
            data.get('weight_kg'),  data.get('height_cm'),
            data.get('bp_systolic'),data.get('bp_diastolic'),
            data.get('fasting_blood_sugar_mg'),
            data.get('hba1c_pct'),
            data.get('total_cholesterol_mg'),
            data.get('ldl_mg'),     data.get('hdl_mg'),
            data.get('triglycerides_mg'),
            data.get('medications'),
            1 if data.get('is_pregnant')      else 0,
            1 if data.get('is_breastfeeding') else 0,
            datetime.now().isoformat(),
            session['user_id']
        ))

        # Save conditions
        conditions_map = {
            'diabetes':        1, 'hypertension':    2,
            'high_cholesterol':3, 'heart_disease':   4,
            'kidney_disease':  5, 'gerd':            6,
            'pcos':            7, 'gout':            8,
            'celiac':          9, 'thyroid':        10,
        }
        for key, cid in conditions_map.items():
            if data.get(key):
                try:
                    cur.execute(
                        "INSERT OR IGNORE INTO user_health_conditions (user_id,condition_id,diagnosed_date) VALUES (?,?,?)",
                        (session['user_id'], cid, datetime.now().date().isoformat())
                    )
                except Exception:
                    pass
            else:
                try:
                    cur.execute(
                        "DELETE FROM user_health_conditions WHERE user_id=? AND condition_id=?",
                        (session['user_id'], cid)
                    )
                except Exception:
                    pass

        # Save allergens
        allergen_map = {
            'peanuts':1,'milk':2,'gluten':3,'shellfish':4,
            'eggs':5,'soy':6,'tree nuts':7,'fish':8,'sesame':10
        }
        for aname, aid in allergen_map.items():
            if aname in [a.lower() for a in data.get('allergens', [])]:
                try:
                    cur.execute(
                        "INSERT OR IGNORE INTO user_allergies (user_id,allergen_id,reaction_severity) VALUES (?,?,'unknown')",
                        (session['user_id'], aid)
                    )
                except Exception:
                    pass
            else:
                try:
                    cur.execute(
                        "DELETE FROM user_allergies WHERE user_id=? AND allergen_id=?",
                        (session['user_id'], aid)
                    )
                except Exception:
                    pass

        conn.commit(); conn.close()
        return jsonify({'success': True, 'message': 'Profile saved for 7 days.'})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────
#  /api/user-profile  — pre-fill modal from saved profile
# ─────────────────────────────────────────────
@app.route('/api/user-profile')
@login_required
def api_user_profile():
    # Check 7-day expiry first
    expired = check_profile_expiry(session['user_id'])
    profile = get_full_user_profile(session['user_id'])

    # Calculate days remaining
    days_remaining = None
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT profile_saved_at FROM users WHERE id=?", (session['user_id'],))
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            from datetime import timedelta
            saved_at = datetime.fromisoformat(str(row[0]))
            delta = timedelta(days=7) - (datetime.now() - saved_at)
            days_remaining = max(0, delta.days)
    except Exception:
        pass

    return jsonify({
        'expired':                expired,
        'days_remaining':         days_remaining,
        'age':                    profile.get('age'),
        'gender':                 profile.get('gender'),
        'weight_kg':              profile.get('weight_kg'),
        'height_cm':              profile.get('height_cm'),
        'bp_systolic':            profile.get('bp_systolic'),
        'bp_diastolic':           profile.get('bp_diastolic'),
        'fasting_blood_sugar_mg': profile.get('fasting_blood_sugar_mg'),
        'hba1c_pct':              profile.get('hba1c_pct'),
        'total_cholesterol_mg':   profile.get('total_cholesterol_mg'),
        'ldl_mg':                 profile.get('ldl_mg'),
        'hdl_mg':                 profile.get('hdl_mg'),
        'triglycerides_mg':       profile.get('triglycerides_mg'),
        'is_pregnant':            profile.get('is_pregnant', 0),
        'is_breastfeeding':       profile.get('is_breastfeeding', 0),
        'medications':            profile.get('medications', ''),
        'activity_level':         profile.get('activity_level'),
        'health_goal':            profile.get('health_goal'),
        'conditions':             profile.get('condition_names', []),
        'allergens':              profile.get('allergen_names', []),
        'diet_prefs':             [d['name'] for d in profile.get('diet_prefs', [])],
        'profile_complete':       profile.get('profile_complete', 0),
        'health_goal':            profile.get('health_goal', 'general_wellness'),
    })


# ─────────────────────────────────────────────
#  /api/analyze  — Groq AI personalised analysis
# ─────────────────────────────────────────────
@app.route('/api/analyze', methods=['POST'])
@login_required
def api_analyze():
    import json as _json
    try:
        data       = request.get_json() or {}
        product_id = str(data.get('product_id', '')).strip()

        # ── Step 1: exact DB lookup ──
        product = get_product(product_id)

        # ── Step 2: fuzzy DB lookup by name (handles AI-KELLOGGSCO saved in DB) ──
        if not product:
            conn = get_db(); cur = conn.cursor()
            # Try name match derived from the ID (AI-KELLOGGSCO → kelloggs)
            name_guess = product_id.replace('AI-','').replace('_',' ').replace('-',' ').strip()
            cur.execute(
                "SELECT * FROM products WHERE UPPER(REPLACE(REPLACE(id,'-',''),'_','')) = UPPER(REPLACE(REPLACE(?,'-',''),'_','')) AND is_active=1 LIMIT 1",
                (product_id,)
            )
            product = cur.fetchone()
            if not product and name_guess:
                cur.execute(
                    "SELECT * FROM products WHERE LOWER(name) LIKE ? AND is_active=1 LIMIT 1",
                    (f'%{name_guess.lower()[:12]}%',)
                )
                product = cur.fetchone()
            conn.close()

        # ── Step 3: in-memory AI cache (if server hasn't restarted) ──
        if not product:
            for key in [product_id, product_id.lower(),
                        product_id.lower().replace('_',' '),
                        product_id.lower().replace('ai-','').replace('_',' ').strip()]:
                product = _ai_product_cache.get(key)
                if product:
                    break

        # ── Step 4: use product_data sent directly from the page (always works) ──
        if not product:
            product = data.get('product_data')

        if not product:
            return jsonify({'error': 'Product not found'}), 404

        profile = get_full_user_profile(session['user_id'])
        p = dict(product) if not isinstance(product, dict) else product
        ov = {k: v for k, v in data.items()
              if k not in ('product_id', 'user_allergens') and v not in (None, '', False)}

        # Merge values: modal overrides win over saved profile
        age         = ov.get('age')                    or profile.get('age', 30)
        gender      = ov.get('gender')                 or profile.get('gender', 'unspecified')
        weight      = ov.get('weight_kg')              or profile.get('weight_kg', 70)
        height      = ov.get('height_cm')              or profile.get('height_cm', 170)
        bp_sys      = ov.get('bp_systolic')            or profile.get('bp_systolic', 120)
        bp_dia      = ov.get('bp_diastolic')           or profile.get('bp_diastolic', 80)
        fbs         = ov.get('fasting_blood_sugar_mg') or profile.get('fasting_blood_sugar_mg', 100)
        hba1c       = ov.get('hba1c_pct')              or profile.get('hba1c_pct', '')
        chol        = ov.get('total_cholesterol_mg')   or profile.get('total_cholesterol_mg', 180)
        ldl         = ov.get('ldl_mg')                 or profile.get('ldl_mg', '')
        hdl         = ov.get('hdl_mg')                 or profile.get('hdl_mg', '')
        trig        = ov.get('triglycerides_mg')       or profile.get('triglycerides_mg', '')
        medications = ov.get('medications')            or profile.get('medications', 'None')
        is_pregnant = bool(ov.get('is_pregnant')       or profile.get('is_pregnant', False))
        is_bf       = bool(ov.get('is_breastfeeding')  or profile.get('is_breastfeeding', False))
        health_goal = ov.get('health_goal') or profile.get('health_goal', 'general_wellness')

        # Conditions: DB + modal checkboxes
        cond_names = list(profile.get('condition_names', []))
        for c in ['diabetes','hypertension','heart_disease','kidney_disease',
                  'high_cholesterol','gerd','pcos','gout','celiac','thyroid']:
            label = c.replace('_', ' ')
            if ov.get(c) and label not in cond_names:
                cond_names.append(label)

        # Allergens: DB + modal ticks
        modal_allergens = data.get('user_allergens', [])
        allergen_names  = list(profile.get('allergen_names', []))
        for a in modal_allergens:
            if a.lower() not in allergen_names:
                allergen_names.append(a.lower())

        cal_limit    = profile.get('daily_calorie_target', 2000)
        sugar_limit  = profile.get('daily_sugar_limit_g', 50)
        sodium_limit = profile.get('daily_sodium_limit_mg', 2300)
        fat_limit    = profile.get('daily_fat_limit_g', 78)
        prot_target  = profile.get('daily_protein_target_g', 50)
        fiber_target = profile.get('daily_fiber_target_g', 28)
        bmi = round(float(weight) / ((float(height)/100)**2), 1) if height else '?'

        prompt = f"""You are a clinical nutrition expert and medical AI. Analyse whether this food product is safe and suitable for this specific person. Be medically accurate and use the person's actual numbers in your explanations.

=== PERSON'S HEALTH PROFILE ===
Age: {age} | Gender: {gender} | Weight: {weight}kg | Height: {height}cm | BMI: {bmi}
Blood Pressure: {bp_sys}/{bp_dia} mmHg
Fasting Blood Sugar: {fbs} mg/dL{f" | HbA1c: {hba1c}%" if hba1c else ""}
Cholesterol: Total {chol} mg/dL{f" | LDL {ldl} mg/dL" if ldl else ""}{f" | HDL {hdl} mg/dL" if hdl else ""}{f" | Triglycerides {trig} mg/dL" if trig else ""}
Health Conditions: {", ".join(cond_names) if cond_names else "None"}
Medications: {medications if medications else "None"}
Food Allergies: {", ".join(allergen_names) if allergen_names else "None"}
Pregnant: {"Yes" if is_pregnant else "No"} | Breastfeeding: {"Yes" if is_bf else "No"}
Health Goal: {health_goal.replace('_',' ').title()}
Daily Limits: {cal_limit} kcal | Sugar {sugar_limit}g | Sodium {sodium_limit}mg | Fat {fat_limit}g | Protein {prot_target}g | Fibre {fiber_target}g

=== FOOD PRODUCT ===
Name: {p.get("name","Unknown")} | Brand: {p.get("brand","Unknown")}
Serving: {p.get("serving_size_g",100)}g
Calories: {p.get("calories",0)} kcal | Sugar: {p.get("sugar_g",0)}g | Added Sugar: {p.get("added_sugar_g",0)}g
Fat: {p.get("fat_g",0)}g | Saturated Fat: {p.get("saturated_fat_g",0)}g | Trans Fat: {p.get("trans_fat_g",0)}g
Sodium: {p.get("sodium_mg",0)}mg | Potassium: {p.get("potassium_mg",0)}mg
Protein: {p.get("protein_g",0)}g | Fibre: {p.get("fiber_g",0)}g | Carbs: {p.get("carbohydrates_g",0)}g
Caffeine: {p.get("caffeine_mg",0)}mg | Glycemic Index: {p.get("glycemic_index","unknown")}
Allergen label: {p.get("allergen_info","Not listed")}
Ingredients: {p.get("ingredients","Not listed")}
Vegan: {bool(p.get("is_vegan"))} | Gluten-Free: {bool(p.get("is_gluten_free"))}

Return ONLY a valid JSON object, no markdown, no text outside JSON:
{{
  "verdict": "safe|moderate|caution|avoid",
  "verdict_title": "one short verdict sentence",
  "verdict_reason": "one sentence summary",
  "allergen_alerts": [
    {{"name": "allergen", "severity": "mild|moderate|severe|unknown", "epipen": false, "detail": "why this is a concern"}}
  ],
  "warnings": [
    {{"severity": "critical|danger|warning|info", "icon": "bi-exclamation-octagon-fill|bi-exclamation-triangle-fill|bi-exclamation-triangle|bi-info-circle", "title": "short title", "reason": "explanation using this person's actual numbers"}}
  ],
  "positives": [
    {{"icon": "bi-check-circle-fill|bi-heart|bi-lightning|bi-tree|bi-activity", "title": "short title", "reason": "specific benefit for this person"}}
  ],
  "daily_pct": {{
    "calories": {round(float(p.get("calories",0))/cal_limit*100,1)},
    "sugar":    {round(float(p.get("sugar_g",0))/sugar_limit*100,1)},
    "sodium":   {round(float(p.get("sodium_mg",0))/sodium_limit*100,1)},
    "fat":      {round(float(p.get("fat_g",0))/fat_limit*100,1)},
    "protein":  {round(float(p.get("protein_g",0))/prot_target*100,1)},
    "fiber":    {round(float(p.get("fiber_g",0))/fiber_target*100,1)}
  }},
  "recommendation": "2-3 sentence personalised advice: safe portion, best time to eat, what to pair with, or what to eat instead",
  "profile_used": {{
    "age": {age}, "gender": "{gender}", "weight": {weight},
    "bp": "{bp_sys}/{bp_dia}", "fbs": {fbs}, "hba1c": "{hba1c}",
    "cholesterol": {chol}, "conditions": {_json.dumps(cond_names)},
    "is_pregnant": {str(is_pregnant).lower()}, "medications": "{medications}"
  }}
}}

Rules:
- allergen_alerts: ONLY if the person has that allergy AND the label lists or may contain it
- warnings: use person's real numbers in the reason text
- verdict "avoid"=allergen or critical risk; "caution"=significant concern; "moderate"=manageable; "safe"=genuinely fine
- Consider the person's health goal in your recommendation: does this product support or hinder it?
- Return ONLY the JSON"""

        from groq import Groq
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1800,
            temperature=0.2
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.replace("```json","").replace("```","").strip()
        result = _json.loads(raw)
        result['ai_powered']   = True
        result['product_name'] = p.get('name', product_id)

        # Save scan history
        try:
            conn = get_db(); cur = conn.cursor()
            cur.execute('INSERT INTO scan_history (user_id, product_id, scanned_at) VALUES (?,?,?)',
                        (session['user_id'], product_id, datetime.now().isoformat()))
            conn.commit(); conn.close()
        except Exception:
            pass

        return jsonify(result)

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────
#  /analyze  — legacy form POST (kept for compatibility)
# ─────────────────────────────────────────────
@app.route('/analyze', methods=['POST'])
@login_required
def analyze():
    flash('Please use the Personalized Analysis button on the product page.', 'info')
    return redirect('/')


# ─────────────────────────────────────────────
#  Favourites
# ─────────────────────────────────────────────
def ensure_favourites_table():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_favourites (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            product_id TEXT    NOT NULL,
            saved_at   TEXT    DEFAULT (datetime('now')),
            UNIQUE(user_id, product_id),
            FOREIGN KEY (user_id)    REFERENCES users(id)    ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        )
    """)
    conn.commit(); conn.close()


@app.route('/favourites')
@login_required
def favourites():
    ensure_favourites_table()
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.name, p.brand, p.calories, p.sugar_g, p.protein_g,
               p.fat_g, p.sodium_mg, p.health_score, p.is_healthy,
               p.image_url, p.category_id, uf.saved_at
        FROM user_favourites uf
        JOIN products p ON p.id = uf.product_id
        WHERE uf.user_id = ?
        ORDER BY uf.saved_at DESC
    """, (session['user_id'],))
    products = cur.fetchall()
    conn.close()
    return render_template('favourites.html', products=products)


@app.route('/api/favourite/toggle', methods=['POST'])
@login_required
def toggle_favourite():
    ensure_favourites_table()
    data       = request.get_json() or {}
    product_id = str(data.get('product_id', '')).strip()
    if not product_id:
        return jsonify({'error': 'No product_id'}), 400

    # If product is AI-generated and not in DB yet, save it first
    product = get_product(product_id)
    if not product:
        for key in [product_id, product_id.lower(),
                    product_id.lower().replace('_',' '),
                    product_id.lower().replace('ai-','').replace('_',' ').strip()]:
            product = _ai_product_cache.get(key)
            if product: break
    if not product:
        product = data.get('product_data')

    # Auto-save AI product to DB so the foreign key works
    if product and not get_product(product_id):
        p = dict(product) if not isinstance(product, dict) else product
        pid = product_id
        try:
            conn2 = get_db(); cur2 = conn2.cursor()
            cur2.execute("""
                INSERT OR IGNORE INTO products
                (id, name, brand, description, calories, protein_g, carbohydrates_g,
                 sugar_g, added_sugar_g, fiber_g, fat_g, saturated_fat_g, trans_fat_g,
                 cholesterol_mg, sodium_mg, potassium_mg, serving_size_g,
                 ingredients, allergen_info, is_gluten_free, is_vegan, is_vegetarian,
                 is_organic, is_non_gmo, health_score, is_healthy,
                 manufacturer, image_url, is_active, created_at, last_updated)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)
            """, (
                pid, p.get('name',''), p.get('brand',''), p.get('description',''),
                p.get('calories',0), p.get('protein_g',0), p.get('carbohydrates_g',0),
                p.get('sugar_g',0), p.get('added_sugar_g',0), p.get('fiber_g',0),
                p.get('fat_g',0), p.get('saturated_fat_g',0), p.get('trans_fat_g',0),
                p.get('cholesterol_mg',0), p.get('sodium_mg',0), p.get('potassium_mg',0),
                p.get('serving_size_g',100), p.get('ingredients',''), p.get('allergen_info',''),
                int(p.get('is_gluten_free',0)), int(p.get('is_vegan',0)),
                int(p.get('is_vegetarian',0)), int(p.get('is_organic',0)),
                int(p.get('is_non_gmo',0)), int(p.get('health_score',50)),
                int(p.get('is_healthy',0)), p.get('brand',''), p.get('image_url',''),
                datetime.now().isoformat(), datetime.now().isoformat()
            ))
            conn2.commit(); conn2.close()
        except Exception as e:
            print(f'[fav auto-save] {e}')

    conn = get_db(); cur = conn.cursor()
    # Check if already saved
    cur.execute("SELECT id FROM user_favourites WHERE user_id=? AND product_id=?",
                (session['user_id'], product_id))
    existing = cur.fetchone()

    if existing:
        cur.execute("DELETE FROM user_favourites WHERE user_id=? AND product_id=?",
                    (session['user_id'], product_id))
        conn.commit(); conn.close()
        return jsonify({'success': True, 'saved': False, 'message': 'Removed from favourites'})
    else:
        try:
            cur.execute("INSERT INTO user_favourites (user_id, product_id) VALUES (?,?)",
                        (session['user_id'], product_id))
            conn.commit(); conn.close()
            return jsonify({'success': True, 'saved': True, 'message': 'Saved to favourites!'})
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/favourite/check/<product_id>')
@login_required
def check_favourite(product_id):
    ensure_favourites_table()
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id FROM user_favourites WHERE user_id=? AND product_id=?",
                (session['user_id'], product_id))
    saved = cur.fetchone() is not None
    conn.close()
    return jsonify({'saved': saved})


@app.route('/favourites/remove/<product_id>', methods=['POST'])
@login_required
def remove_favourite(product_id):
    ensure_favourites_table()
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM user_favourites WHERE user_id=? AND product_id=?",
                (session['user_id'], product_id))
    conn.commit(); conn.close()
    flash('Removed from favourites.', 'info')
    return redirect('/favourites')


# ─────────────────────────────────────────────
#  BMI Calculator
# ─────────────────────────────────────────────
@app.route('/bmi')
def bmi_calculator():
    return render_template('bmi.html')


# ─────────────────────────────────────────────
#  /api/update-account
# ─────────────────────────────────────────────
@app.route('/api/update-account', methods=['POST'])
@login_required
def update_account():
    data = request.get_json() or {}
    try:
        conn = get_db(); cur = conn.cursor()
        new_email = data.get('email','').strip().lower()
        if new_email:
            cur.execute("SELECT id FROM users WHERE email=? AND id!=?", (new_email, session['user_id']))
            if cur.fetchone():
                conn.close()
                return jsonify({'success': False, 'error': 'Email already in use'}), 400
        updates = []; params = []
        if data.get('first_name'): updates.append("first_name=?"); params.append(data['first_name'].strip())
        if data.get('last_name'):  updates.append("last_name=?");  params.append(data['last_name'].strip())
        if new_email:              updates.append("email=?");       params.append(new_email)
        if data.get('password'):
            import hashlib
            updates.append("password_hash=?")
            params.append(hashlib.sha256(data['password'].encode()).hexdigest())
        if updates:
            params.append(session['user_id'])
            cur.execute("UPDATE users SET " + ", ".join(updates) + " WHERE id=?", params)
            conn.commit()
            if data.get('first_name') or data.get('last_name'):
                cur.execute("SELECT first_name, last_name FROM users WHERE id=?", (session['user_id'],))
                u = cur.fetchone()
                if u: session['user_name'] = f"{u['first_name']} {u['last_name']}"
            if new_email: session['user_email'] = new_email
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────
#  /api/update-goals
# ─────────────────────────────────────────────
@app.route('/api/update-goals', methods=['POST'])
@login_required
def update_goals():
    data = request.get_json() or {}
    try:
        conn = get_db(); cur = conn.cursor()
        for col, defn in [("daily_protein_target_g","INTEGER DEFAULT 50"),("daily_fiber_target_g","INTEGER DEFAULT 28")]:
            try: cur.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
            except: pass
        cur.execute(
            "UPDATE users SET health_goal=?, daily_calorie_target=?, daily_sugar_limit_g=?, "
            "daily_sodium_limit_mg=?, daily_fat_limit_g=?, daily_protein_target_g=?, daily_fiber_target_g=? WHERE id=?",
            (data.get('health_goal','general_wellness'), data.get('daily_calorie_target',2000),
             data.get('daily_sugar_limit_g',50), data.get('daily_sodium_limit_mg',2300),
             data.get('daily_fat_limit_g',78), data.get('daily_protein_target_g',50),
             data.get('daily_fiber_target_g',28), session['user_id'])
        )
        conn.commit(); conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────
#  Autocomplete API
# ─────────────────────────────────────────────
@app.route('/api/autocomplete')
def autocomplete():
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify([])

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, calories, is_healthy, brand
        FROM products
        WHERE is_active = 1
          AND (LOWER(name) LIKE ? OR LOWER(id) LIKE ? OR LOWER(brand) LIKE ?)
        ORDER BY
            CASE
                WHEN LOWER(name) LIKE ? THEN 1
                WHEN LOWER(id)   = ?    THEN 2
                WHEN LOWER(id)   LIKE ? THEN 3
                ELSE 4
            END, name
        LIMIT 15
    """, (
        f'%{query}%', f'%{query}%', f'%{query}%',
        f'{query}%', query, f'{query}%'
    ))
    rows = cur.fetchall()
    conn.close()

    db_results = [{
        "id": r['id'], "name": r['name'],
        "calories": r['calories'], "is_healthy": r['is_healthy'],
        "brand": r['brand'], "source": "db"
    } for r in rows]

    # If we have enough DB results, return them
    if len(db_results) >= 5:
        return jsonify(db_results)

    # Otherwise, ask AI to suggest food products matching the query
    try:
        from groq import Groq
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content":
                f"""List 6 real food products or brands that start with or match "{query}".
Return ONLY a JSON array of objects like:
[{{"name": "Product Name", "brand": "Brand", "calories": 150, "is_healthy": 0}}]
Only include actual food/drink products. No descriptions, no markdown.
Return ONLY the JSON array."""}],
            max_tokens=300,
            temperature=0.3
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.replace("```json","").replace("```","").strip()
        import json as _json
        ai_suggestions = _json.loads(raw)
        ai_results = [{
            "id": f"ai-{s.get('name','').lower().replace(' ','-')}",
            "name": s.get("name", ""),
            "calories": s.get("calories", 0),
            "is_healthy": s.get("is_healthy", 0),
            "brand": s.get("brand", ""),
            "source": "ai"
        } for s in ai_suggestions if s.get("name")]

        # DB results first, then AI suggestions (deduplicated)
        db_names = {r["name"].lower() for r in db_results}
        ai_results = [r for r in ai_results if r["name"].lower() not in db_names]
        return jsonify(db_results + ai_results[:6])

    except Exception as e:
        print(f"AI autocomplete error: {e}")

    return jsonify(db_results)


# ─────────────────────────────────────────────
#  Admin routes
# ─────────────────────────────────────────────
@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db()
    cur  = conn.cursor()

    cur.execute("SELECT COUNT(*) as c FROM users")
    total_users = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) as c FROM products WHERE is_active=1")
    total_products = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) as c FROM products WHERE is_active=1 AND is_healthy=1")
    healthy_count = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) as c FROM products WHERE is_active=1 AND id LIKE 'AI-%'")
    ai_products = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) as c FROM scan_history")
    total_scans = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) as c FROM scan_history WHERE DATE(scanned_at)=DATE('now')")
    scans_today = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) as c FROM users WHERE DATE(created_at)=DATE('now')")
    new_users_today = cur.fetchone()["c"]

    cur.execute("""
        SELECT sh.scanned_at, p.name, u.email, u.first_name
        FROM scan_history sh
        JOIN products p ON sh.product_id = p.id
        JOIN users u ON sh.user_id = u.id
        ORDER BY sh.scanned_at DESC LIMIT 10
    """)
    recent_scans = cur.fetchall()

    cur.execute("""
        SELECT p.name, COUNT(*) as cnt
        FROM scan_history sh
        JOIN products p ON sh.product_id = p.id
        GROUP BY sh.product_id
        ORDER BY cnt DESC LIMIT 5
    """)
    top_products = cur.fetchall()

    cur.execute("SELECT id, first_name, last_name, email, created_at, is_admin FROM users ORDER BY created_at DESC LIMIT 10")
    recent_users = cur.fetchall()

    try:
        cur.execute("SELECT COUNT(*) as c FROM contact_messages WHERE is_read=0")
        unread_messages = cur.fetchone()["c"]
        cur.execute("SELECT * FROM contact_messages ORDER BY sent_at DESC LIMIT 5")
        recent_messages = cur.fetchall()
    except:
        unread_messages = 0
        recent_messages = []

    conn.close()

    return render_template("admin_dashboard.html",
                           total_users=total_users,
                           total_products=total_products,
                           healthy_count=healthy_count,
                           ai_products=ai_products,
                           total_scans=total_scans,
                           scans_today=scans_today,
                           new_users_today=new_users_today,
                           recent_scans=recent_scans,
                           top_products=top_products,
                           recent_users=recent_users,
                           unread_messages=unread_messages,
                           recent_messages=recent_messages)
@app.route('/admin/messages')
@admin_required
def admin_messages():
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('SELECT * FROM contact_messages ORDER BY sent_at DESC')
        messages = cur.fetchall()
    except:
        messages = []
    conn.close()
    return render_template('admin_messages.html', messages=messages)

@app.route('/admin/messages/read/<int:msg_id>')
@admin_required
def mark_message_read(msg_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('UPDATE contact_messages SET is_read=1 WHERE id=?', (msg_id,))
    conn.commit()
    conn.close()
    return redirect('/admin/messages')

@app.route('/admin/messages/delete/<int:msg_id>')
@admin_required
def delete_message(msg_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM contact_messages WHERE id=?', (msg_id,))
    conn.commit()
    conn.close()
    flash('Message deleted.', 'success')
    return redirect('/admin/messages')

@app.route('/admin/users')
@admin_required
def admin_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, first_name, last_name, email, is_admin, created_at FROM users ORDER BY created_at DESC")
    users = cur.fetchall()
    conn.close()
    return render_template('admin_users.html', users=users)

@app.route('/admin/products')
@admin_required
def admin_products():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE is_active=1 ORDER BY name")
    products = cur.fetchall()
    conn.close()
    return render_template('admin_products.html', products=products)

@app.route('/admin/qr-codes')
@admin_required
def admin_qr_codes():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, brand, is_healthy, health_score, category_id FROM products WHERE is_active=1 ORDER BY name")
    products = cur.fetchall()
    conn.close()
    return render_template('admin_qr.html', products=products or [])

@app.route('/admin/generate-qr/<product_id>')
@admin_required
def generate_product_qr(product_id):
    product = get_product(product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    qr = qrcode.QRCode(version=1,
                       error_correction=qrcode.constants.ERROR_CORRECT_L,
                       box_size=10, border=4)
    base_url = request.host_url.rstrip("/")
    product_url = f"{base_url}/p/{product_id}"
    qr.add_data(product_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    return jsonify({
        'qr_code': img_str,
        'product_id': product_id,
        'product_name': product['name'],
        'product_url': product_url
    })

@app.route('/admin/add-product', methods=['POST'])
@admin_required
def admin_add_product():
    try:
        conn = get_db()
        cur = conn.cursor()

        product_id = request.form['id'].strip().upper()
        name       = request.form['name'].strip()
        brand      = request.form.get('brand', '').strip()
        calories   = float(request.form.get('calories', 0))
        sugar      = float(request.form.get('sugar', 0))
        fat        = float(request.form.get('fat', 0))
        protein    = float(request.form.get('protein', 0))
        sodium     = float(request.form.get('sodium', 0))
        ingredients= request.form.get('chemicals', '').strip()
        is_healthy = 1 if request.form.get('is_healthy') == 'on' else 0

        cur.execute("""
            INSERT OR REPLACE INTO products
            (id, name, brand, calories, sugar_g, fat_g, protein_g, sodium_mg,
             ingredients, is_healthy, is_active, created_at, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (product_id, name, brand, calories, sugar, fat, protein, sodium,
              ingredients, is_healthy,
              datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()
        flash(f'Product "{name}" added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding product: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect('/admin/products')

@app.route('/admin/edit-product/<product_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(product_id):
    if request.method == 'POST':
        try:
            conn = get_db()
            cur = conn.cursor()

            name       = request.form['name'].strip()
            brand      = request.form.get('brand', '').strip()
            calories   = float(request.form.get('calories', 0))
            sugar      = float(request.form.get('sugar', 0))
            fat        = float(request.form.get('fat', 0))
            protein    = float(request.form.get('protein', 0))
            sodium     = float(request.form.get('sodium', 0))
            ingredients= request.form.get('chemicals', '').strip()
            is_healthy = 1 if request.form.get('is_healthy') == 'on' else 0

            cur.execute("""
                UPDATE products
                SET name=?, brand=?, calories=?, sugar_g=?, fat_g=?,
                    protein_g=?, sodium_mg=?, ingredients=?, is_healthy=?,
                    last_updated=?
                WHERE id=?
            """, (name, brand, calories, sugar, fat, protein, sodium,
                  ingredients, is_healthy, datetime.now().isoformat(), product_id))
            conn.commit()
            flash(f'Product "{name}" updated successfully!', 'success')
        except Exception as e:
            flash(f'Error updating product: {str(e)}', 'danger')
        finally:
            conn.close()
        return redirect('/admin/products')

    product = get_product(product_id)
    if not product:
        flash('Product not found!', 'danger')
        return redirect('/admin/products')
    return render_template('admin_edit_product.html', product=product)

@app.route('/admin/delete-product/<product_id>')
@admin_required
def admin_delete_product(product_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT name FROM products WHERE id = ?", (product_id,))
        row = cur.fetchone()
        product_name = row['name'] if row else product_id
        # Soft delete
        cur.execute("UPDATE products SET is_active=0 WHERE id=?", (product_id,))
        conn.commit()
        flash(f'Product "{product_name}" deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting product: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect('/admin/products')

@app.route('/admin/toggle-admin/<user_id>')
@admin_required
def toggle_admin(user_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        new_status = 0 if row['is_admin'] == 1 else 1
        cur.execute("UPDATE users SET is_admin=? WHERE id=?", (new_status, user_id))
        conn.commit()
        flash(f'User status changed to {"Admin" if new_status else "Regular User"}', 'success')
    except Exception as e:
        flash(f'Error updating user: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect('/admin/users')

@app.route('/admin/delete-user/<user_id>')
@admin_required
def admin_delete_user(user_id):
    if int(user_id) == session['user_id']:
        flash('Cannot delete your own account!', 'danger')
        return redirect('/admin/users')
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT email FROM users WHERE id=?", (user_id,))
        row = cur.fetchone()
        user_email = row['email'] if row else user_id
        cur.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
        flash(f'User "{user_email}" deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting user: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect('/admin/users')


# ─────────────────────────────────────────────
#  Error handlers
# ─────────────────────────────────────────────
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)