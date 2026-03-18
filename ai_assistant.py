"""
AI Assistant Module for Nutrition Scanner
Uses Groq API (FREE) with llama-3.3-70b for intelligent, context-aware responses.
"""

import os
import sqlite3
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from groq import Groq

# ─────────────────────────────────────────────
#  Blueprint Setup
# ─────────────────────────────────────────────
ai_bp = Blueprint('ai_assistant', __name__)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

DB_PATH = "nutrition_enhanced.db"


# ─────────────────────────────────────────────
#  Helper: fetch user context from DB
# ─────────────────────────────────────────────
def get_user_context(user_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT first_name, age, weight_kg, height_cm, gender,
               activity_level, health_goal,
               daily_calorie_target, daily_sugar_limit_g,
               daily_sodium_limit_mg, daily_fat_limit_g
        FROM users WHERE id = ?
    """, (user_id,))
    user = dict(cur.fetchone() or {})

    cur.execute("""
        SELECT hc.name, uhc.severity
        FROM user_health_conditions uhc
        JOIN health_conditions hc ON hc.id = uhc.condition_id
        WHERE uhc.user_id = ?
    """, (user_id,))
    user["conditions"] = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT a.name, ua.reaction_severity
        FROM user_allergies ua
        JOIN allergens a ON a.id = ua.allergen_id
        WHERE ua.user_id = ?
    """, (user_id,))
    user["allergies"] = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT dp.name
        FROM user_dietary_preferences udp
        JOIN dietary_preferences dp ON dp.id = udp.preference_id
        WHERE udp.user_id = ?
    """, (user_id,))
    user["dietary_prefs"] = [r["name"] for r in cur.fetchall()]

    cur.execute("""
        SELECT p.name, p.calories, p.sugar_g, p.sodium_mg,
               p.fat_g, p.health_score, sh.scanned_at
        FROM scan_history sh
        JOIN products p ON p.id = sh.product_id
        WHERE sh.user_id = ?
        ORDER BY sh.scanned_at DESC LIMIT 5
    """, (user_id,))
    user["recent_scans"] = [dict(r) for r in cur.fetchall()]

    conn.close()
    return user


def get_product_context(product_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id = ? OR barcode = ?",
                (product_id, product_id))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# ─────────────────────────────────────────────
#  Build the system prompt dynamically
# ─────────────────────────────────────────────
def build_system_prompt(user_context: dict, product_context) -> str:
    conditions = ", ".join(
        f"{c['name']} ({c['severity']})" for c in user_context.get("conditions", [])
    ) or "None"

    allergies = ", ".join(
        f"{a['name']} ({a['reaction_severity']})" for a in user_context.get("allergies", [])
    ) or "None"

    diet_prefs = ", ".join(user_context.get("dietary_prefs", [])) or "None"

    recent = user_context.get("recent_scans", [])
    recent_str = ""
    if recent:
        recent_str = "\nRecently scanned products:\n" + "\n".join(
            f"  - {r['name']}: {r['calories']} cal, sugar {r['sugar_g']}g, "
            f"sodium {r['sodium_mg']}mg, health score {r['health_score']}/100"
            for r in recent
        )

    product_str = ""
    if product_context:
        p = product_context
        product_str = f"""
Currently viewed product:
  Name: {p.get('name')} by {p.get('brand')}
  Serving: {p.get('serving_size_g')}g
  Calories: {p.get('calories')} | Protein: {p.get('protein_g')}g
  Carbs: {p.get('carbohydrates_g')}g | Sugar: {p.get('sugar_g')}g
  Fat: {p.get('fat_g')}g | Saturated fat: {p.get('saturated_fat_g')}g
  Sodium: {p.get('sodium_mg')}mg | Fiber: {p.get('fiber_g')}g
  Ingredients: {p.get('ingredients')}
  Allergens: {p.get('allergen_info')}
  Health score: {p.get('health_score')}/100
"""

    return f"""You are a friendly, expert AI nutrition assistant embedded in a Nutrition Scanner app.
Your job is to give personalized, accurate dietary advice based on the user's health profile.

USER HEALTH PROFILE:
  Name: {user_context.get('first_name', 'User')}
  Age: {user_context.get('age')} | Gender: {user_context.get('gender')}
  Weight: {user_context.get('weight_kg')}kg | Height: {user_context.get('height_cm')}cm
  Activity level: {user_context.get('activity_level')}
  Health goal: {user_context.get('health_goal')}

DAILY LIMITS:
  Calories: {user_context.get('daily_calorie_target')} kcal
  Sugar: {user_context.get('daily_sugar_limit_g')}g
  Sodium: {user_context.get('daily_sodium_limit_mg')}mg
  Fat: {user_context.get('daily_fat_limit_g')}g

HEALTH CONDITIONS: {conditions}
ALLERGIES: {allergies}
DIETARY PREFERENCES: {diet_prefs}
{recent_str}
{product_str}

INSTRUCTIONS:
1. Always consider the user's health conditions and allergies in every response.
2. If a product contains an allergen the user is allergic to, WARN them prominently.
3. Give specific numbers and comparisons (e.g. "This has 41g sugar - that's 114% of your daily limit").
4. Suggest healthier alternatives when a product is not ideal.
5. Be conversational, warm and encouraging - not robotic.
6. If asked about calories, macros, ingredients, or health impact - answer precisely.
7. You can answer general nutrition questions, meal planning, recipe ideas, and fitness questions.
8. Keep responses concise (3-5 sentences for simple questions, more for complex ones).
9. Never recommend stopping medication or replacing doctor advice.
10. Today's date: {datetime.now().strftime('%B %d, %Y')}
"""


# ─────────────────────────────────────────────
#  Save chat to DB
# ─────────────────────────────────────────────
def save_conversation(user_id: int, session_id: str, user_msg: str,
                      ai_response: str, product_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO chatbot_conversations
            (user_id, session_id, user_message, assistant_response,
             context_product_id, intent, created_at)
            VALUES (?, ?, ?, ?, ?, 'general_question', ?)
        """, (user_id, session_id, user_msg, ai_response,
              product_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[AI] Could not save conversation: {e}")


# ─────────────────────────────────────────────
#  Main Chat Endpoint  POST /ai/chat
# ─────────────────────────────────────────────
@ai_bp.route('/ai/chat', methods=['POST'])
def chat():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json()
    if not data or not data.get("message", "").strip():
        return jsonify({"error": "Empty message"}), 400

    user_id    = session['user_id']
    user_msg   = data["message"].strip()
    history    = data.get("history", [])
    product_id = data.get("product_id")
    session_id = data.get("session_id", f"sess_{user_id}_{datetime.now().date()}")

    try:
        user_ctx    = get_user_context(user_id)
        product_ctx = get_product_context(product_id) if product_id else None
    except Exception as e:
        return jsonify({"error": f"DB error: {str(e)}"}), 500

    system_prompt = build_system_prompt(user_ctx, product_ctx)

    # Build messages for Groq
    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-10:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_msg})

    # Call Groq API
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=1024,
            temperature=0.7
        )
        ai_reply = response.choices[0].message.content
    except Exception as e:
        return jsonify({"error": f"AI error: {str(e)}"}), 500

    save_conversation(user_id, session_id, user_msg, ai_reply, product_id)

    return jsonify({
        "reply": ai_reply,
        "session_id": session_id,
        "product_context": product_ctx.get("name") if product_ctx else None
    })


# ─────────────────────────────────────────────
#  Get chat history  GET /ai/history
# ─────────────────────────────────────────────
@ai_bp.route('/ai/history', methods=['GET'])
def chat_history():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT user_message, assistant_response,
               context_product_id, created_at
        FROM chatbot_conversations
        WHERE user_id = ?
        ORDER BY created_at DESC LIMIT 20
    """, (session['user_id'],))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    return jsonify({"history": rows})


# ─────────────────────────────────────────────
#  Quick product analysis  POST /ai/analyze
# ─────────────────────────────────────────────
@ai_bp.route('/ai/analyze', methods=['POST'])
def analyze_product():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401

    product_id = request.get_json().get("product_id")
    if not product_id:
        return jsonify({"error": "product_id required"}), 400

    user_id     = session['user_id']
    user_ctx    = get_user_context(user_id)
    product_ctx = get_product_context(product_id)

    if not product_ctx:
        return jsonify({"error": "Product not found"}), 404

    system_prompt = build_system_prompt(user_ctx, product_ctx)

    analysis_prompt = (
        f"Please give me a complete health analysis of '{product_ctx['name']}' "
        f"for my personal health profile. Cover: "
        f"(1) Is it safe for my conditions/allergies? "
        f"(2) How does it fit my daily limits? "
        f"(3) Overall recommendation - should I consume it?"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": analysis_prompt}
            ],
            max_tokens=800,
            temperature=0.7
        )
        analysis = response.choices[0].message.content
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    save_conversation(user_id, f"analysis_{product_id}", analysis_prompt,
                      analysis, product_id)

    return jsonify({
        "product": product_ctx.get("name"),
        "analysis": analysis,
        "health_score": product_ctx.get("health_score")
    })