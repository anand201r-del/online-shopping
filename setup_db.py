"""
One-step database setup + repair + product photos.

    python setup_db.py

1. Creates the database and any missing tables (from schema.sql).
2. Repairs old tables whose columns don't match what the app uses
   (the old table is kept as  <name>_backup_<date>  — nothing is deleted).
3. Lists the picture each product will show (uploaded photo, or a matching
   illustration picked from the product name).

Uses the MySQL login in your .env file, so the 'mysql' command is not needed.
"""

import os
import re
import sys
from datetime import datetime

import mysql.connector
from dotenv import load_dotenv

load_dotenv()
HERE = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(HERE, "templates", "static", "images")
DB_NAME = os.getenv("DB_NAME", "shopping_db")

# columns the app needs in each table
NEEDED = {
    "users":    {"username", "password"},
    "products": {"id", "name", "price", "stock", "image", "category"},
    "cart":     {"username", "product_id", "quantity"},
    "wishlist": {"username", "product_id"},
    "orders":   {"username", "product_name", "price", "quantity", "total", "order_date"},
}


# ---------------------------------------------------------------- SQL helpers

def statements(path):
    """Split schema.sql into single statements, skipping comments."""
    with open(path, encoding="utf-8") as f:
        text = "".join(l for l in f if not l.strip().startswith("--"))
    return [s.strip() for s in text.split(";") if s.strip()]


def create_statement(table, all_statements):
    for s in all_statements:
        if re.match(rf"CREATE TABLE IF NOT EXISTS {table}\b", s, re.I):
            return s
    return None


def columns(cursor, table):
    cursor.execute("""
        SELECT COLUMN_NAME FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
    """, (DB_NAME, table))
    return {r[0].lower() for r in cursor.fetchall()}


# ---------------------------------------------------------------- 1 + 2: schema

def setup_schema(db):
    cursor = db.cursor()
    stmts = statements(os.path.join(HERE, "schema.sql"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # create database + missing tables
    for s in stmts:
        if not s.upper().startswith("INSERT"):
            cursor.execute(s)

    # repair tables with wrong columns
    for table, needed in NEEDED.items():
        have = columns(cursor, table)
        missing = needed - have
        if not missing:
            print(f"   ✔ {table}: OK")
            continue

        if table == "products":
            # keep products, just add the missing columns
            if "image" in missing:
                cursor.execute("ALTER TABLE products ADD COLUMN image VARCHAR(255) NULL")
            if "category" in missing:
                cursor.execute("ALTER TABLE products ADD COLUMN category VARCHAR(100) NULL DEFAULT 'General'")
            still = NEEDED["products"] - columns(cursor, "products")
            if still:
                print(f"   ✖ products is missing {still} — please tell Claude.")
            else:
                print(f"   ✔ products: added {', '.join(sorted(missing))}")
            continue

        if table == "orders" and missing == {"order_date"}:
            cursor.execute("ALTER TABLE orders ADD COLUMN order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print("   ✔ orders: added order_date")
            continue

        backup = f"{table}_backup_{stamp}"
        cursor.execute(f"RENAME TABLE `{table}` TO `{backup}`")
        cursor.execute(create_statement(table, stmts))
        print(f"   ✔ {table}: rebuilt (old columns didn't match; old data kept in {backup})")

    # sample products only if the table is empty
    for s in stmts:
        if s.upper().startswith("INSERT"):
            cursor.execute(s)

    db.commit()
    cursor.close()


# ---------------------------------------------------------------- 3: pictures

def show_pictures(db):
    """Every product without an uploaded photo gets a matching illustration
    automatically (see product_art.py) — this just lists what each one shows."""
    from product_art import art_for
    cursor = db.cursor()
    # forget photos that were auto-downloaded earlier (they were often wrong)
    cursor.execute("UPDATE products SET image=NULL WHERE image LIKE 'product-%'")
    db.commit()
    cursor.execute("SELECT name, image FROM products ORDER BY id")
    for name, image in cursor.fetchall():
        has_photo = image and os.path.exists(os.path.join(IMAGE_DIR, image)) \
            and image not in ("headphones.jpg", "laptop.jpg", "phone.jpg")
        shown = f"your photo ({image})" if has_photo else art_for(name).replace("art/", "illustration: ")
        print(f"   🖼  {name:30} → {shown}")
    cursor.close()


# ---------------------------------------------------------------- main

def main():
    password = os.getenv("DB_PASSWORD", "")
    if not password or password == "your-mysql-password":
        print("❌ Put your MySQL password in the .env file first (DB_PASSWORD=...).")
        sys.exit(1)

    try:
        db = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=password,
        )
    except mysql.connector.Error as e:
        print(f"❌ Could not connect to MySQL: {e}")
        print("   • Is the MySQL server running? (Windows: Services → MySQL80 → Start)")
        print("   • Is DB_PASSWORD in .env correct?")
        sys.exit(1)

    print("1/2  Checking database tables…")
    setup_schema(db)

    print("2/2  Product pictures…")
    show_pictures(db)

    db.close()
    print("\n✅ All done. Now run:  python app.py")


if __name__ == "__main__":
    main()
