"""
Online Shopping System
Flask + MySQL — built-in checkout (Cash on Delivery / demo UPI / demo Card)

Run:
    1. mysql -u root -p < schema.sql
    2. create .env with your MySQL password  (see .env.example)
    3. pip install -r requirements.txt
    4. python app.py   ->  http://127.0.0.1:5000
"""

import os
import secrets
from datetime import datetime
from functools import wraps

import mysql.connector
from dotenv import load_dotenv
from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from product_art import art_for

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "templates", "static")
IMAGE_DIR = os.path.join(STATIC_DIR, "images")
ALLOWED_IMAGES = {"png", "jpg", "jpeg", "webp", "gif"}

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # 4 MB uploads

# 💳 Payment methods offered at checkout (no payment gateway needed)
PAYMENT_METHODS = {
    "cod":  "Cash on Delivery",
    "upi":  "UPI (demo)",
    "card": "Debit / Credit Card (demo)",
}

# 👑 Usernames that may open the admin dashboard (comma separated in .env)
ADMIN_USERS = {u.strip() for u in os.getenv("ADMIN_USERS", "admin,anand").split(",") if u.strip()}

# Column order used by every template:  0 id, 1 name, 2 price, 3 stock, 4 image, 5 category
PRODUCT_COLS = "id, name, price, stock, image, category"


# ✅ DATABASE CONNECTION
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "shopping_db"),
    )


def query(sql, params=(), one=False, commit=False):
    """Run one SQL statement and close the connection."""
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(sql, params)
        if commit:
            db.commit()
            return cursor.rowcount
        return cursor.fetchone() if one else cursor.fetchall()
    finally:
        cursor.close()
        db.close()


# ===========================
# 🔒 ACCESS HELPERS
# ===========================

def is_admin():
    return session.get("user") in ADMIN_USERS


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if not is_admin():
            flash("Only admins can do that.", "danger")
            return redirect(url_for("home"))
        return view(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_globals():
    """Values every template can use (navbar cart badge, admin flag)."""
    count = wish = 0
    if "user" in session:
        try:
            row = query("SELECT COALESCE(SUM(quantity), 0) FROM cart WHERE username=%s",
                        (session["user"],), one=True)
            count = int(row[0]) if row else 0
            row = query("SELECT COUNT(*) FROM wishlist WHERE username=%s", (session["user"],), one=True)
            wish = int(row[0]) if row else 0
        except mysql.connector.Error:
            pass
    return {"current_user": session.get("user"),
            "is_admin": is_admin(),
            "cart_count": count,
            "wish_count": wish}


# files that are auto-generated or tiny placeholders, not real product photos
REPLACEABLE = {"headphones.jpg", "laptop.jpg", "phone.jpg"}


@app.template_filter("img")
def image_url(filename, name=None, category=None):
    """Product image URL. Uses the uploaded photo when there is one,
    otherwise a matching illustration chosen from the product name."""
    real_photo = (filename
                  and not filename.startswith("product-")
                  and filename not in REPLACEABLE
                  and os.path.exists(os.path.join(IMAGE_DIR, filename)))
    if real_photo:
        return url_for("static", filename="images/" + filename)
    if name:
        return url_for("static", filename="images/" + art_for(name, category))
    return url_for("static", filename="images/no-image.svg")


def wants_json():
    """True when the page's JavaScript called us (no page reload)."""
    return request.headers.get("X-Requested-With") == "fetch"


def cart_total_qty():
    row = query("SELECT COALESCE(SUM(quantity), 0) FROM cart WHERE username=%s", (session["user"],), one=True)
    return int(row[0]) if row else 0


def wishlist_ids():
    rows = query("SELECT product_id FROM wishlist WHERE username=%s", (session["user"],))
    return {r[0] for r in rows}


def save_image(file_storage):
    """Save an uploaded product image and return its file name (or None)."""
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_IMAGES:
        flash("Image must be png, jpg, jpeg, webp or gif.", "warning")
        return None
    os.makedirs(IMAGE_DIR, exist_ok=True)
    file_storage.save(os.path.join(IMAGE_DIR, filename))
    return filename


def to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def read_product_form():
    """Validate the add/edit product form. Returns a dict or None."""
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip() or "General"
    try:
        price = round(float(request.form.get("price", "")), 2)
        stock = int(request.form.get("stock", ""))
    except ValueError:
        flash("Price and stock must be numbers.", "danger")
        return None
    if not name or price < 0 or stock < 0:
        flash("Name is required and price/stock cannot be negative.", "danger")
        return None
    return {"name": name, "price": price, "stock": stock, "category": category}


# ===========================
# 🔐 AUTH SYSTEM
# ===========================

@app.route('/login')
def login():
    if "user" in session:
        return redirect(url_for("home"))
    return render_template("login.html")


@app.route('/login_check', methods=['POST'])
def login_check():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    user = query("SELECT password FROM users WHERE username=%s", (username,), one=True)

    if user and check_password_hash(user[0], password):
        session.clear()
        session['user'] = username
        flash(f"Welcome back, {username}!", "success")
        return redirect(url_for("home"))
    return render_template("login.html", error="Invalid username or password"), 401


@app.route('/signup')
def signup():
    return render_template("signup.html")


@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if len(username) < 3 or len(password) < 6:
        return render_template("signup.html",
                               error="Username needs 3+ characters and password 6+ characters."), 400

    if query("SELECT id FROM users WHERE username=%s", (username,), one=True):
        return render_template("signup.html", error="That username is already taken."), 400

    query("INSERT INTO users (username, password) VALUES (%s, %s)",
          (username, generate_password_hash(password)), commit=True)

    flash("Account created — please log in.", "success")
    return redirect(url_for("login"))


@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ===========================
# 🏠 HOME / PRODUCTS
# ===========================

@app.route('/')
@login_required
def home():
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    sort = request.args.get('sort', 'new')

    sql = f"SELECT {PRODUCT_COLS} FROM products WHERE 1=1"
    values = []

    if search:
        sql += " AND name LIKE %s"
        values.append('%' + search + '%')

    if category:
        sql += " AND category=%s"
        values.append(category)

    sql += {"price_asc": " ORDER BY price ASC",
            "price_desc": " ORDER BY price DESC",
            "name": " ORDER BY name ASC"}.get(sort, " ORDER BY id DESC")

    products = query(sql, tuple(values))
    categories = query("SELECT DISTINCT category FROM products "
                       "WHERE category IS NOT NULL AND category <> '' ORDER BY category")

    return render_template("index.html",
                           products=products,
                           categories=categories,
                           search=search,
                           category=category,
                           sort=sort,
                           wished=wishlist_ids())


@app.route('/product/<int:id>')
@login_required
def product_detail(id):
    product = query(f"SELECT {PRODUCT_COLS} FROM products WHERE id=%s", (id,), one=True)
    if not product:
        abort(404)
    return render_template("product.html", product=product, wished=product[0] in wishlist_ids())


# ===========================
# 🛠 ADMIN
# ===========================

@app.route('/admin')
@admin_required
def admin():
    total_products = query("SELECT COUNT(*) FROM products", one=True)[0]
    total_users = query("SELECT COUNT(*) FROM users", one=True)[0]
    total_orders = query("SELECT COUNT(*) FROM orders", one=True)[0]
    revenue = query("SELECT COALESCE(SUM(total), 0) FROM orders", one=True)[0]

    products = query(f"SELECT {PRODUCT_COLS} FROM products ORDER BY id DESC")
    recent_orders = query("""
        SELECT username, product_name, quantity, total, order_date
        FROM orders ORDER BY order_date DESC LIMIT 10
    """)

    names = [p[1] for p in products]
    stocks = [p[3] for p in products]

    return render_template("admin.html",
                           total_products=total_products,
                           total_users=total_users,
                           total_orders=total_orders,
                           revenue=revenue,
                           products=products,
                           recent_orders=recent_orders,
                           names=names,
                           stocks=stocks)


@app.route('/add', methods=['POST'])
@admin_required
def add_product():
    data = read_product_form()
    if data:
        image = save_image(request.files.get("image"))
        query("""
            INSERT INTO products (name, price, stock, image, category)
            VALUES (%s, %s, %s, %s, %s)
        """, (data["name"], data["price"], data["stock"], image, data["category"]), commit=True)
        flash(f"Added “{data['name']}”.", "success")
    return redirect(url_for("admin"))


@app.route('/delete/<int:id>', methods=['POST'])
@admin_required
def delete_product(id):
    # remove references first so the delete works even without ON DELETE CASCADE
    query("DELETE FROM cart WHERE product_id=%s", (id,), commit=True)
    query("DELETE FROM wishlist WHERE product_id=%s", (id,), commit=True)
    query("DELETE FROM products WHERE id=%s", (id,), commit=True)
    flash("Product deleted.", "info")
    return redirect(url_for("admin"))


@app.route('/edit/<int:id>')
@admin_required
def edit_product(id):
    product = query(f"SELECT {PRODUCT_COLS} FROM products WHERE id=%s", (id,), one=True)
    if not product:
        abort(404)
    return render_template("edit.html", product=product)


@app.route('/update/<int:id>', methods=['POST'])
@admin_required
def update_product(id):
    data = read_product_form()
    if not data:
        return redirect(url_for("edit_product", id=id))

    image = save_image(request.files.get("image"))
    if image:
        query("UPDATE products SET image=%s WHERE id=%s", (image, id), commit=True)

    query("""
        UPDATE products
        SET name=%s, price=%s, stock=%s, category=%s
        WHERE id=%s
    """, (data["name"], data["price"], data["stock"], data["category"], id), commit=True)

    flash("Product updated.", "success")
    return redirect(url_for("admin"))


# ===========================
# 🛒 CART
# ===========================

@app.route('/add_to_cart/<int:id>', methods=['GET', 'POST'])
@login_required
def add_to_cart(id):
    qty = max(1, to_int(request.form.get("quantity"), 1))
    username = session['user']

    product = query("SELECT name, stock FROM products WHERE id=%s", (id,), one=True)
    if not product:
        abort(404)
    name, stock = product

    item = query("SELECT quantity FROM cart WHERE username=%s AND product_id=%s",
                 (username, id), one=True)
    in_cart = item[0] if item else 0

    if in_cart + qty > stock:
        if in_cart >= stock:
            msg = f"You already have all {stock} “{name}” in your cart."
        elif in_cart:
            msg = f"Only {stock} “{name}” in stock — you have {in_cart} in your cart."
        else:
            msg = f"Sorry, only {stock} “{name}” in stock."
        if wants_json():
            return jsonify({"ok": False, "message": msg, "cart_count": cart_total_qty()})
        flash(msg, "warning")
        return redirect(request.referrer or url_for("home"))

    if item:
        query("UPDATE cart SET quantity = quantity + %s WHERE username=%s AND product_id=%s",
              (qty, username, id), commit=True)
    else:
        query("INSERT INTO cart (username, product_id, quantity) VALUES (%s, %s, %s)",
              (username, id, qty), commit=True)

    msg = f"Added “{name}” to your cart."
    if wants_json():
        return jsonify({"ok": True, "message": msg, "cart_count": cart_total_qty()})
    flash(msg, "success")
    return redirect(request.referrer or url_for("home"))


@app.route('/cart')
@login_required
def cart():
    items = query("""
        SELECT products.id, products.name, products.price, cart.quantity,
               products.image, products.stock, products.category
        FROM cart
        JOIN products ON cart.product_id = products.id
        WHERE cart.username=%s
    """, (session['user'],))

    total = sum(i[2] * i[3] for i in items)
    return render_template("cart.html", items=items, total=total)


@app.route('/remove_from_cart/<int:id>')
@login_required
def remove_from_cart(id):
    query("DELETE FROM cart WHERE username=%s AND product_id=%s",
          (session['user'], id), commit=True)
    flash("Item removed from cart.", "info")
    return redirect(url_for("cart"))


@app.route('/update_cart/<int:id>', methods=['POST'])
@login_required
def update_cart(id):
    qty = to_int(request.form.get('quantity'), 1)

    if qty <= 0:
        query("DELETE FROM cart WHERE username=%s AND product_id=%s",
              (session['user'], id), commit=True)
        flash("Item removed from cart.", "info")
        return redirect(url_for("cart"))

    product = query("SELECT stock FROM products WHERE id=%s", (id,), one=True)
    if product and qty > product[0]:
        qty = product[0]
        flash(f"Only {qty} in stock — quantity adjusted.", "warning")

    query("UPDATE cart SET quantity=%s WHERE username=%s AND product_id=%s",
          (qty, session['user'], id), commit=True)
    return redirect(url_for("cart"))


# ===========================
# ❤️ WISHLIST
# ===========================

@app.route('/add_to_wishlist/<int:id>')
@login_required
def add_to_wishlist(id):
    exists = query("SELECT 1 FROM wishlist WHERE username=%s AND product_id=%s",
                   (session['user'], id), one=True)
    if not exists:
        query("INSERT INTO wishlist (username, product_id) VALUES (%s, %s)",
              (session['user'], id), commit=True)
    flash("Saved to your wishlist ❤️", "success")
    return redirect(request.referrer or url_for("home"))


@app.route('/toggle_wishlist/<int:id>')
@login_required
def toggle_wishlist(id):
    if id in wishlist_ids():
        query("DELETE FROM wishlist WHERE username=%s AND product_id=%s",
              (session['user'], id), commit=True)
        wished, msg = False, "Removed from wishlist."
    else:
        if not query("SELECT 1 FROM products WHERE id=%s", (id,), one=True):
            abort(404)
        query("INSERT INTO wishlist (username, product_id) VALUES (%s, %s)",
              (session['user'], id), commit=True)
        wished, msg = True, "Saved to your wishlist ❤️"
    if wants_json():
        return jsonify({"ok": True, "wished": wished, "message": msg,
                        "wish_count": len(wishlist_ids())})
    flash(msg, "success" if wished else "info")
    return redirect(request.referrer or url_for("home"))


@app.route('/wishlist')
@login_required
def wishlist():
    items = query("""
        SELECT products.id, products.name, products.price, products.image, products.stock,
               products.category
        FROM wishlist
        JOIN products ON wishlist.product_id = products.id
        WHERE wishlist.username=%s
    """, (session['user'],))
    return render_template("wishlist.html", items=items)


@app.route('/remove_wishlist/<int:id>')
@login_required
def remove_wishlist(id):
    query("DELETE FROM wishlist WHERE username=%s AND product_id=%s",
          (session['user'], id), commit=True)
    flash("Removed from wishlist.", "info")
    return redirect(request.referrer or url_for("wishlist"))


# ===========================
# 💳 CHECKOUT (no payment gateway)
# ===========================

def cart_items_for(username, cursor):
    cursor.execute("""
        SELECT products.id, products.name, products.price, cart.quantity, products.stock
        FROM cart
        JOIN products ON cart.product_id = products.id
        WHERE cart.username=%s
    """, (username,))
    return cursor.fetchall()


@app.route('/pay')
@app.route('/checkout')
@login_required
def checkout():
    db = get_db()
    cursor = db.cursor()
    items = cart_items_for(session['user'], cursor)
    cursor.close()
    db.close()

    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("cart"))

    for _, name, _, qty, stock in items:
        if qty > stock:
            flash(f"Only {stock} “{name}” left — please update your cart.", "warning")
            return redirect(url_for("cart"))

    total = sum(i[2] * i[3] for i in items)
    return render_template("payment.html", items=items, total=total, methods=PAYMENT_METHODS)


@app.route('/place_order', methods=['POST'])
@login_required
def place_order():
    method = request.form.get("method", "cod")
    if method not in PAYMENT_METHODS:
        method = "cod"

    # simple checks for the demo UPI / card forms
    if method == "upi" and "@" not in request.form.get("upi_id", ""):
        flash("Enter a valid UPI ID (for example name@okaxis).", "danger")
        return redirect(url_for("checkout"))
    if method == "card":
        digits = request.form.get("card_number", "").replace(" ", "")
        if not (digits.isdigit() and 12 <= len(digits) <= 19):
            flash("Enter a valid card number.", "danger")
            return redirect(url_for("checkout"))

    username = session['user']
    db = get_db()
    cursor = db.cursor()
    try:
        items = cart_items_for(username, cursor)
        if not items:
            flash("Your cart is empty.", "warning")
            return redirect(url_for("cart"))

        for pid, name, price, qty, stock in items:
            if qty > stock:
                flash(f"Only {stock} “{name}” left — please update your cart.", "warning")
                return redirect(url_for("cart"))

        total = 0
        for pid, name, price, qty, stock in items:
            cursor.execute("""
                INSERT INTO orders (username, product_name, price, quantity, total)
                VALUES (%s, %s, %s, %s, %s)
            """, (username, name, price, qty, price * qty))
            cursor.execute("UPDATE products SET stock = GREATEST(stock - %s, 0) WHERE id=%s",
                           (qty, pid))
            total += price * qty

        cursor.execute("DELETE FROM cart WHERE username=%s", (username,))
        db.commit()
    except mysql.connector.Error as e:
        db.rollback()
        app.logger.error("Placing order failed: %s", e)
        flash("Could not place the order. Please try again.", "danger")
        return redirect(url_for("cart"))
    finally:
        cursor.close()
        db.close()

    session['last_order'] = {
        "ref": "ORD-" + datetime.now().strftime("%Y%m%d") + "-" + secrets.token_hex(3).upper(),
        "amount": float(total),
        "method": PAYMENT_METHODS[method],
    }
    return redirect(url_for("success"))


@app.route('/success')
@login_required
def success():
    order = session.pop('last_order', None)
    if not order:
        return redirect(url_for("orders"))
    return render_template("success.html", order=order)


# ===========================
# 📦 ORDERS
# ===========================

@app.route('/orders')
@login_required
def orders():
    data = query("""
        SELECT product_name, price, quantity, total, order_date
        FROM orders
        WHERE username=%s
        ORDER BY order_date DESC
    """, (session['user'],))

    grand_total = sum(o[3] for o in data)
    return render_template("orders.html", orders=data, grand_total=grand_total)


# ===========================
# ⚠️ ERRORS
# ===========================

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404,
                           message="We couldn't find that page or product."), 404


@app.errorhandler(413)
def too_large(e):
    flash("That image is too large (max 4 MB).", "danger")
    return redirect(request.referrer or url_for("home"))


@app.errorhandler(mysql.connector.Error)
def db_error(e):
    app.logger.error("Database error: %s", e)
    return render_template("error.html", code=500,
                           message="Database error — is MySQL running and is schema.sql loaded? "
                                   f"({e})"), 500


# ===========================
# 🚀 RUN
# ===========================

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1")
