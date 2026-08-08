import sqlite3

DB_NAME = "shop.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    # Таблица корзин
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cart (
            user_id INTEGER,
            product_id TEXT,
            quantity INTEGER,
            PRIMARY KEY (user_id, product_id)
        )
    """)
    # Таблица заказов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            items TEXT,
            total INTEGER,
            phone TEXT,
            address TEXT,
            status TEXT DEFAULT 'Новый'
        )
    """)
    conn.commit()
    conn.close()

# --- Функции для корзины ---
def add_to_cart(user_id, product_id, quantity=1):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + ?",
        (user_id, product_id, quantity, quantity)
    )
    conn.commit()
    conn.close()

def get_cart(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT product_id, quantity FROM cart WHERE user_id=?", (user_id,))
    data = cur.fetchall()
    conn.close()
    return data

def clear_cart(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

# --- Функции для заказов ---
def save_order(user_id, items, total, phone, address):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (user_id, items, total, phone, address) VALUES (?, ?, ?, ?, ?)",
        (user_id, items, total, phone, address)
    )
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id

def get_orders(limit=10):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, user_id, items, total, phone, address, status FROM orders ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    data = cur.fetchall()
    conn.close()
    return data