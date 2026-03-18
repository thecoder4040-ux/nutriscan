"""
Run this to reset admin password.
Place next to app.py and run:  python reset_admin.py
"""
import sqlite3, hashlib

DB_PATH = 'nutrition_enhanced.db'

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

new_password  = 'Admin@nutriscan1'
password_hash = hashlib.sha256(new_password.encode()).hexdigest()

cur.execute("SELECT id, email, is_admin FROM users WHERE is_admin=1")
admins = cur.fetchall()

if admins:
    cur.execute("UPDATE users SET password_hash=? WHERE is_admin=1", (password_hash,))
    conn.commit()
    print("Password reset successful!")
    print(f"\n  Email:    {admins[0][1]}")
    print(f"  Password: {new_password}")
else:
    cur.execute("""
        INSERT OR REPLACE INTO users (id, email, password_hash, first_name, last_name, is_admin)
        VALUES (1, 'admin@nutrition.com', ?, 'Admin', 'User', 1)
    """, (password_hash,))
    conn.commit()
    print("Admin account created!")
    print(f"\n  Email:    admin@nutrition.com")
    print(f"  Password: {new_password}")

conn.close()
print(f"\n  URL: http://localhost:5000/login")