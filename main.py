from flask import Flask, render_template, request, redirect, url_for, session, g, flash, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"
DATABASE1 = "products.db"
DATABASE2 = "userdata.db"

# --- DB Helper ---
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE1)
        db.row_factory = sqlite3.Row   # return rows as dictionaries
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# --- Initialize DB ---
def init_db():
    with app.app_context():
        db = get_db()
        db.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        description TEXT,
        price TEXT,
        image TEXT
    )
""")

        db.commit()
        
# -- Create table if not exists for userdata
def create_table():
    with sqlite3.connect('database.db') as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullname TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                password TEXT NOT NULL
            )             
        """)
create_table()

def init_orders_table():
    conn = sqlite3.connect("userdata.db")  # or your main DB
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            order_id TEXT,
            phone TEXT,
            address TEXT,
            delivery_date TEXT,
            total_price REAL
        )
    """)
    conn.commit()
    conn.close()
    
def init_bookings_table():
    conn = sqlite3.connect("userdata.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            email TEXT,
            phone TEXT,
            event_type TEXT,
            event_date TEXT,
            guests INTEGER,
            message TEXT,
            submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# Call this function once at app startup
init_orders_table()

@app.route("/save_order", methods=["POST"])
def save_order():
    data = request.get_json()
    order_id = data.get("order_id")
    email = data.get("email")
    phone = data.get("phone")
    address = data.get("address")
    delivery_date = data.get("date")
    total = data.get("total")

    conn = sqlite3.connect("userdata.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO orders (user_email, order_id, phone, address, delivery_date, total_price)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (email, order_id, phone, address, delivery_date, total))
    conn.commit()
    conn.close()

    return "Order saved successfully"


# --- Homepage ---
@app.route("/")
def home():
    db = get_db()
    products = db.execute("SELECT * FROM products").fetchall()
    return render_template("homepage.html", products=products)

#-- SIgnup route ---
@app.route("/signup", methods=['POST'])
def signup():
    fullname = request.form['fullname']
    email = request.form['email']
    role = request.form['role']
    password = request.form['password']
    
    try:
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO users (fullname, email, role, password) VALUES (?, ?, ?, ?)", (fullname, email, role, password))
            
            # save user in session to use later
            session['user_name'] = fullname
            session['user_email'] = email
            flash("Account created successfully!", 'success')
            
            return redirect(url_for('user_dashboard'))
        
    except sqlite3.IntegrityError:
        flash("Email already regestered. Try loggin in.", 'danger')
        return redirect(url_for('home'))
    
# -- User Dashboard -- 
@app.route("/user_dashboard")
def user_dashboard():
    if 'user_name' not in session:
        return redirect(url_for('home'))
    else:
        user_name = session['user_name']
        user_email = session['user_email']
        db = get_db()
        products = db.execute("SELECT * FROM products").fetchall()
        
        # Connect to user database to fetch orders
        conn = sqlite3.connect("userdata.db")
        c = conn.cursor()
        c.execute("""
            SELECT order_id, phone, address, delivery_date, total_price
            FROM orders
            WHERE user_email=?
            ORDER BY id DESC
        """, (user_email,))
        orders = c.fetchall()
        conn.close()
        
        return render_template('admindashboard.html',products=products, name=user_name, email=user_email, orders=orders)

# --- Login ---
@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]

    if email == "abhidashewar@gmail.com" and password == "password":
        session["admin"] = True
        return redirect(url_for("dashboard"))
    else:
        db = get_db()
        products = db.execute("SELECT * FROM products").fetchall()
        return render_template("homepage.html", products=products, error="Invalid credentials")

# --- Logout ---
@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for('home'))

# --- Dashboard ---
@app.route("/dashboard")
def dashboard():
    if not session.get("admin"):
        return redirect(url_for("home"))
    db = get_db()
    products = db.execute("SELECT * FROM products").fetchall()

    # Get all orders
    conn = sqlite3.connect("userdata.db")
    c = conn.cursor()
    c.execute("""
        SELECT user_email, order_id, phone, address, delivery_date, total_price
        FROM orders
        ORDER BY id DESC
    """)
    all_orders = c.fetchall()

    # Get all bookings
    c.execute("SELECT * FROM bookings ORDER BY submitted_at DESC")
    all_bookings = c.fetchall()
    conn.close()

    return render_template("dashboardpage.html", products=products, orders=all_orders, bookings=all_bookings)

#-- User Dashboard ---
def userdashboard():
    if not session.get("user"):
        return redirect(url_for("home"))
    db = get_db()
    products = db.execute("SELECT * FROM products").fetchall()
    return redirect('userdashboard.html', products=products)

# --- Add Product ---
@app.route("/add", methods=["POST"])
def add():
    if not session.get("admin"):
        return redirect(url_for("homepage"))

    name = request.form["name"]
    description = request.form["description"]
    price = request.form["price"]
    image = request.form["image"]   # image URL, not file upload

    db = get_db()
    db.execute("INSERT INTO products (name, description, price, image) VALUES (?, ?, ?, ?)",
               (name, description, price, image))
    db.commit()
    return redirect(url_for("dashboard"))

# --- Edit Product ---
@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    if not session.get("admin"):
        return redirect(url_for("homepage"))

    name = request.form["name"]
    description = request.form["description"]
    price = request.form["price"]
    image = request.form["image"]

    db = get_db()
    db.execute("UPDATE products SET name=?, description=?, price=?, image=? WHERE id=?",
               (name, description, price, image, id))
    db.commit()
    return redirect(url_for("dashboard"))

# --- Delete Product ---
@app.route("/delete/<int:id>")
def delete(id):
    if not session.get("admin"):
        return redirect(url_for("homepage"))

    db = get_db()
    db.execute("DELETE FROM products WHERE id=?", (id,))
    db.commit()
    return redirect(url_for("dashboard"))

@app.route("/clear_cart", methods=["POST"])
def clear_cart():
    if "cart" in session:
        session["cart"] = []  # clear the cart list
    return "Cart cleared"

@app.route("/submit_booking", methods=["POST"])
def submit_booking():
    full_name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    event_type = request.form.get("eventType")
    event_date = request.form.get("eventDate")
    guests = request.form.get("guests")
    message = request.form.get("message")

    conn = sqlite3.connect("userdata.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO bookings (full_name, email, phone, event_type, event_date, guests, message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (full_name, email, phone, event_type, event_date, guests, message))
    conn.commit()
    conn.close()

    # You can redirect to the same page or show a success message
    return redirect(url_for('home', _anchor='booking'))


if __name__ == "__main__":
    init_db()
    init_orders_table()
    init_bookings_table()   # Add this line
    app.run(debug=True, port=4000)
