# 🛍 ShopEase — Online Shopping System

A full-stack e-commerce web app built with **Flask** and **MySQL**, with a built-in checkout (Cash on Delivery, plus simulated UPI and card payments).

## Features

| For shoppers | For admins |
|---|---|
| Sign up / log in (hashed passwords) | Dashboard: products, users, orders, revenue |
| Browse, search and filter by category | Stock chart (Chart.js) with low-stock colours |
| Product detail page with quantity picker | Add products with image upload |
| Cart with live badge, quantity update, stock limits | Edit / delete products |
| Wishlist | Recent orders table |
| Checkout: Cash on Delivery / UPI (demo) / Card (demo) | Admin access limited to `ADMIN_USERS` |
| Order history with total spent | |

Stock is reduced automatically when an order is placed, and you can't add more items to the cart than are in stock.

## Tech stack

- Python 3, Flask 3, Jinja2
- MySQL (`mysql-connector-python`)
- Bootstrap 5, Font Awesome, Chart.js

## Project structure

```
Online Shopping/
├── app.py                 # all routes and logic
├── schema.sql             # creates the database, tables and 3 sample products
├── requirements.txt
├── .env.example           # copy to .env and fill in
├── templates/
│   ├── base.html          # shared navbar, messages, footer
│   ├── index.html         # product listing + search
│   ├── product.html       # product detail
│   ├── cart.html  wishlist.html  orders.html
│   ├── payment.html       # checkout page
│   ├── success.html
│   ├── admin.html  edit.html
│   ├── login.html  signup.html  error.html
│   └── static/
│       ├── style.css
│       └── images/        # product images (uploads go here)
```

## Setup (Windows)

```bash
# 1. create the database (asks for your MySQL root password)
mysql -u root -p < schema.sql

# 2. virtual environment + packages
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 3. settings
copy .env.example .env      # then put your MySQL password in .env

# 4. run
python app.py
```

Open http://127.0.0.1:5000, sign up, and log in.

**Admin access:** sign up with a username listed in `ADMIN_USERS` in `.env` (default `admin`), then use the **Dashboard** button.

**Checkout:** choose Cash on Delivery, or try the demo UPI/card options (any UPI ID like `name@okaxis`, any 12–19 digit card number). No real payment is taken.

## Security notes

- Secrets live in `.env`, which is git-ignored — never commit it.
- Passwords are hashed with Werkzeug.
- Stock and cart contents are re-checked on the server when an order is placed.
- Delete actions use POST, so a link can't trigger them by accident.
