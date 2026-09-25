from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
DB = os.path.join(os.path.dirname(__file__), "thrift_store.db")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads")
ALLOWED_IMAGE_EXTENSIONS = {"png","jpg","jpeg","webp","gif"}

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_column(conn, table, column, definition):
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        is_admin INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        price REAL NOT NULL,
        image_url TEXT DEFAULT '',
        stock INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        total REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending Approval',
        address TEXT NOT NULL,
        phone TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        price REAL NOT NULL,
        quantity INTEGER NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
    );
    """)
    # Upgrade databases created by older versions of the app.
    ensure_column(conn, "users", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    ensure_column(conn, "products", "description", "TEXT DEFAULT ''")
    ensure_column(conn, "products", "price", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "products", "image_url", "TEXT DEFAULT ''")
    ensure_column(conn, "products", "stock", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "orders", "total", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "orders", "status", "TEXT NOT NULL DEFAULT 'Pending Approval'")
    ensure_column(conn, "orders", "address", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "orders", "phone", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "orders", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    ensure_column(conn, "order_items", "product_name", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "order_items", "price", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "order_items", "quantity", "INTEGER NOT NULL DEFAULT 1")

    admin = conn.execute("SELECT id FROM users WHERE email = ?", ("admin@thrift.local",)).fetchone()
    if not admin:
        conn.execute(
            "INSERT INTO users(name,email,password,is_admin) VALUES(?,?,?,1)",
            ("Store Admin", "admin@thrift.local", generate_password_hash("admin123"))
        )
    if conn.execute("SELECT COUNT(*) c FROM products").fetchone()["c"] == 0:
        conn.executemany(
            "INSERT INTO products(name,description,price,image_url,stock) VALUES(?,?,?,?,?)",
            [
                ("Vintage Denim Jacket", "Oversized vintage denim jacket.", 799, "https://images.unsplash.com/photo-1551028719-00167b16eac5?auto=format&fit=crop&w=900&q=80", 3),
                ("Retro Graphic Tee", "90s-inspired graphic t-shirt.", 399, "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=900&q=80", 5),
                ("Classic Cargo Pants", "Relaxed-fit cargo pants.", 699, "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=900&q=80", 2),
            ]
        )
    conn.commit()
    conn.close()


def save_product_image(file):
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return None
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    import uuid
    name = secure_filename(file.filename.rsplit(".",1)[0]) + "_" + uuid.uuid4().hex[:8] + "." + ext
    file.save(os.path.join(UPLOAD_DIR, name))
    return url_for("uploaded_file", filename=name)

def current_user():
    if "user_id" not in session:
        return None
    conn = db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    conn.close()
    return user

@app.context_processor
def inject_user():
    return {"current_user": current_user()}

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or not user["is_admin"]:
            abort(403)
        return view(*args, **kwargs)
    return wrapped

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.route("/")
def index():
    conn = db()
    products = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("index.html", products=products)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name, email, password = request.form["name"].strip(), request.form["email"].strip().lower(), request.form["password"]
        if not name or len(password) < 6:
            flash("Name is required and password must be at least 6 characters.", "error")
            return redirect(url_for("register"))
        conn = db()
        try:
            conn.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",
                         (name, email, generate_password_hash(password)))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash("An account with that email already exists.", "error")
            return redirect(url_for("register"))
        conn.close()
        flash("Account created. You can now log in.", "success")
        return redirect(url_for("login"))
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email, password = request.form["email"].strip().lower(), request.form["password"]
        conn = db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            if user["is_admin"]:
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("index"))
        flash("Invalid email or password.", "error")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/cart")
def cart():
    cart_data = session.get("cart", {})
    ids = [int(x) for x in cart_data.keys()]
    products = []
    if ids:
        conn = db()
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(f"SELECT * FROM products WHERE id IN ({placeholders})", ids).fetchall()
        conn.close()
        for p in rows:
            qty = max(1, int(cart_data.get(str(p["id"]), 1)))
            products.append({"product": p, "quantity": qty})
    total = sum(x["product"]["price"] * x["quantity"] for x in products)
    return render_template("cart.html", items=products, total=total)

@app.post("/cart/add/<int:product_id>")
def add_to_cart(product_id):
    conn = db()
    product = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    conn.close()
    if not product or product["stock"] <= 0:
        flash("That item is unavailable.", "error")
        return redirect(url_for("index"))
    cart_data = session.get("cart", {})
    current = int(cart_data.get(str(product_id), 0))
    if current < product["stock"]:
        cart_data[str(product_id)] = current + 1
        session["cart"] = cart_data
        flash("Added to cart.", "success")
    else:
        flash("You cannot add more than the available stock.", "error")
    return redirect(url_for("index"))

@app.post("/cart/update")
def update_cart():
    cart_data = session.get("cart", {})
    for key, value in request.form.items():
        if key.startswith("qty_"):
            pid = key[4:]
            try:
                qty = max(0, int(value))
            except ValueError:
                qty = 1
            if qty == 0:
                cart_data.pop(pid, None)
            else:
                cart_data[pid] = qty
    session["cart"] = cart_data
    return redirect(url_for("cart"))

@app.route("/checkout", methods=["GET","POST"])
@login_required
def checkout():
    items = build_cart_items()
    if not items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("index"))
    total = sum(x["product"]["price"] * x["quantity"] for x in items)
    if request.method == "POST":
        address, phone = request.form["address"].strip(), request.form["phone"].strip()
        if not address or not phone:
            flash("Address and phone are required.", "error")
            return render_template("checkout.html", items=items, total=total)
        conn = db()
        for x in items:
            fresh = conn.execute("SELECT stock FROM products WHERE id=?", (x["product"]["id"],)).fetchone()
            if not fresh or fresh["stock"] < x["quantity"]:
                conn.close()
                flash(f"Not enough stock for {x['product']['name']}.", "error")
                return redirect(url_for("cart"))
        cur = conn.execute(
            "INSERT INTO orders(user_id,total,address,phone) VALUES(?,?,?,?)",
            (session["user_id"], total, address, phone)
        )
        order_id = cur.lastrowid
        for x in items:
            p = x["product"]
            conn.execute(
                "INSERT INTO order_items(order_id,product_id,product_name,price,quantity) VALUES(?,?,?,?,?)",
                (order_id, p["id"], p["name"], p["price"], x["quantity"])
            )
        conn.commit()
        conn.close()
        session["cart"] = {}
        return render_template("success.html", order_id=order_id, total=total)
    return render_template("checkout.html", items=items, total=total)

def build_cart_items():
    cart_data = session.get("cart", {})
    ids = [int(x) for x in cart_data.keys()]
    if not ids:
        return []
    conn = db()
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(f"SELECT * FROM products WHERE id IN ({placeholders})", ids).fetchall()
    conn.close()
    return [{"product": p, "quantity": min(max(1, int(cart_data.get(str(p["id"]), 1))), p["stock"])} for p in rows]

@app.route("/my-orders")
@login_required
def my_orders():
    conn = db()
    orders = conn.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (session["user_id"],)).fetchall()
    conn.close()
    return render_template("my_orders.html", orders=orders)

@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = db()
    products = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    orders = conn.execute("""
        SELECT o.*, u.name AS customer_name, u.email AS customer_email
        FROM orders o JOIN users u ON u.id=o.user_id
        ORDER BY o.id DESC
    """).fetchall()
    stats = {
        "products": conn.execute("SELECT COUNT(*) c FROM products").fetchone()["c"],
        "orders": conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"],
        "sales": conn.execute("SELECT COALESCE(SUM(total),0) s FROM orders").fetchone()["s"],
        "customers": conn.execute("SELECT COUNT(*) c FROM users WHERE is_admin=0").fetchone()["c"],
    }
    latest = conn.execute("SELECT COALESCE(MAX(id),0) AS id FROM orders").fetchone()["id"]
    conn.close()
    return render_template("admin.html", products=products, orders=orders, stats=stats, latest_order_id=latest)

@app.route("/admin/product/new", methods=["GET","POST"])
@admin_required
def new_product():
    if request.method == "POST":
        image_url = request.form.get("image_url", "").strip()
        uploaded = save_product_image(request.files.get("image"))
        if uploaded:
            image_url = uploaded
        conn = db()
        conn.execute("INSERT INTO products(name,description,price,image_url,stock) VALUES(?,?,?,?,?)",
                     (request.form["name"], request.form["description"], float(request.form["price"]),
                      image_url, int(request.form["stock"])))
        conn.commit(); conn.close()
        return redirect(url_for("admin_dashboard"))
    return render_template("product_form.html", product=None)

@app.route("/admin/product/<int:product_id>/edit", methods=["GET","POST"])
@admin_required
def edit_product(product_id):
    conn = db()
    product = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not product:
        conn.close(); abort(404)
    if request.method == "POST":
        image_url = request.form.get("image_url", "").strip()
        uploaded = save_product_image(request.files.get("image"))
        if uploaded:
            image_url = uploaded
        conn.execute("""UPDATE products SET name=?,description=?,price=?,image_url=?,stock=? WHERE id=?""",
                     (request.form["name"], request.form["description"], float(request.form["price"]),
                      image_url, int(request.form["stock"]), product_id))
        conn.commit(); conn.close()
        return redirect(url_for("admin_dashboard"))
    conn.close()
    return render_template("product_form.html", product=product)

@app.post("/admin/product/<int:product_id>/delete")
@admin_required
def delete_product(product_id):
    conn = db()
    conn.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit(); conn.close()
    return redirect(url_for("admin_dashboard"))

@app.post("/admin/order/<int:order_id>/status")
@admin_required
def update_order_status(order_id):
    status = request.form["status"]
    allowed = {"Pending Approval", "Approved", "Rejected", "Packed", "Shipped", "Delivered", "Cancelled"}
    if status not in allowed:
        abort(400)
    conn = db()
    order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        conn.close(); abort(404)

    # Only the admin can approve/reject an order. Stock is reserved only on approval.
    if status == "Approved" and order["status"] != "Approved":
        items = conn.execute("SELECT product_id, quantity FROM order_items WHERE order_id=?", (order_id,)).fetchall()
        for item in items:
            product = conn.execute("SELECT stock FROM products WHERE id=?", (item["product_id"],)).fetchone()
            if not product or product["stock"] < item["quantity"]:
                conn.rollback(); conn.close()
                flash("Cannot approve: one or more products no longer have enough stock.", "error")
                return redirect(url_for("admin_dashboard"))
        for item in items:
            conn.execute("UPDATE products SET stock=stock-? WHERE id=?", (item["quantity"], item["product_id"]))

    conn.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit(); conn.close()
    flash(f"Order #{order_id} updated to {status}.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/new-orders")
@admin_required
def admin_new_orders():
    try:
        after = int(request.args.get("after", 0))
    except ValueError:
        after = 0
    conn = db()
    rows = conn.execute("""
        SELECT o.id, o.total, o.status, o.created_at, u.name AS customer_name
        FROM orders o JOIN users u ON u.id=o.user_id
        WHERE o.id > ?
        ORDER BY o.id ASC
    """, (after,)).fetchall()
    conn.close()
    return {
        "orders": [
            {"id": r["id"], "total": r["total"], "status": r["status"],
             "created_at": r["created_at"], "customer_name": r["customer_name"]}
            for r in rows
        ]
    }

@app.route("/admin/order/<int:order_id>")
@admin_required
def order_details(order_id):
    conn = db()
    order = conn.execute("""
        SELECT o.*, u.name customer_name, u.email customer_email
        FROM orders o JOIN users u ON u.id=o.user_id WHERE o.id=?
    """, (order_id,)).fetchone()
    items = conn.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,)).fetchall()
    conn.close()
    if not order: abort(404)
    return render_template("order_details.html", order=order, items=items)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
