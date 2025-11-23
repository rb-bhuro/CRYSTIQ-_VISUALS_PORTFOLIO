from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

import os
import psycopg2
import psycopg2.extras

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "replace_this_with_a_strong_secret")  # change for production

# Database URL from environment (set this in Render as the External DATABASE_URL)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # For local dev you can fallback to a local Postgres URL or raise an error
    # raise RuntimeError("DATABASE_URL environment variable not set")
    # Using fallback only for local dev convenience; remove if you want strict behavior
    DATABASE_URL = os.getenv("LOCAL_DATABASE_URL", None)

# ---------- DB helpers ----------
def get_db():
    """
    Return a psycopg2 connection (RealDictCursor for dict-like rows) stored in flask.g
    """
    if "db" not in g:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured. Set DATABASE_URL env var to your Postgres URL.")
        g.db = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass


def query_db(query, args=(), one=False):
    """
    Execute a SELECT and return rows. args must be a tuple or list.
    """
    db = get_db()
    cur = db.cursor()
    cur.execute(query, args)
    data = cur.fetchall()
    cur.close()
    return (data[0] if data else None) if one else data


def execute_db(query, args=()):
    """
    Execute INSERT/UPDATE/DELETE (non-select) and commit.
    """
    db = get_db()
    cur = db.cursor()
    cur.execute(query, args)
    db.commit()
    cur.close()


# ---------- Schema init (Postgres safe) ----------
def init_db():
    """
    Create necessary tables if they do not exist (Postgres-compatible DDL).
    This runs on app startup so you don't need to import schema manually.
    """
    ddl_admin = """
    CREATE TABLE IF NOT EXISTS admin (
        id SERIAL PRIMARY KEY,
        username VARCHAR(255) UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    );
    """

    ddl_category = """
    CREATE TABLE IF NOT EXISTS category (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    ddl_design = """
    CREATE TABLE IF NOT EXISTS design (
        id SERIAL PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        image_url TEXT NOT NULL,
        category_id INTEGER,
        featured INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_category
          FOREIGN KEY(category_id)
            REFERENCES category(id)
            ON DELETE SET NULL
    );
    """

    # Create tables
    db = get_db()
    cur = db.cursor()
    cur.execute(ddl_admin)
    cur.execute(ddl_category)
    cur.execute(ddl_design)
    db.commit()
    cur.close()


# -------- Public routes --------
@app.route('/')
def home():
    # show a few newest/featured designs
    featured = query_db("SELECT * FROM design WHERE featured=1 ORDER BY created_at DESC LIMIT 6")
    newest = query_db("SELECT * FROM design ORDER BY created_at DESC LIMIT 6")
    return render_template('home.html', featured=featured, newest=newest)


@app.route('/gallery')
def gallery():
    q = request.args.get('q', '').strip()
    cat = request.args.get('cat', '')
    view = request.args.get('view', 'grid')  # grid or list

    sql = "SELECT design.*, category.name AS category_name FROM design LEFT JOIN category ON design.category_id = category.id"
    params = []
    where = []
    if cat:
        where.append("category.id = %s")
        params.append(cat)
    if q:
        # ILIKE for case-insensitive search on Postgres
        where.append("(design.title ILIKE %s OR design.image_url ILIKE %s)")
        params.extend([f'%{q}%', f'%{q}%'])

    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY featured DESC, created_at DESC"

    designs = query_db(sql, params)
    categories = query_db("SELECT * FROM category ORDER BY name")
    return render_template('gallery.html', designs=designs, categories=categories, q=q, selected_cat=cat, view=view)


@app.route('/design/<int:design_id>')
def design_preview(design_id):
    d = query_db(
        "SELECT design.*, category.name AS category_name FROM design LEFT JOIN category ON design.category_id = category.id WHERE design.id = %s",
        (design_id,), one=True
    )
    if not d:
        return ("Not found", 404)
    return render_template('design_preview.html', design=d)


@app.route('/about')
def about():
    # placeholder stats
    total = query_db("SELECT COUNT(*) as c FROM design", one=True)['c']
    categories = query_db("SELECT COUNT(*) as c FROM category", one=True)['c']
    return render_template('about.html', total=total, categories=categories)


@app.route('/contact')
def contact():
    return render_template('contact.html')


# -------- Admin auth and panel --------
def is_logged_in():
    return session.get('admin_id') is not None


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for('admin_login', next=request.path))
        return f(*args, **kwargs)
    return decorated


@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        admin = query_db("SELECT * FROM admin WHERE username = %s", (username,), one=True)
        if admin and check_password_hash(admin['password_hash'], password):
            session['admin_id'] = admin['id']
            session['admin_username'] = admin['username']
            flash('Logged in', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    flash('Logged out', 'info')
    return redirect(url_for('home'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    total_designs = query_db("SELECT COUNT(*) AS c FROM design", one=True)['c']
    total_cats = query_db("SELECT COUNT(*) AS c FROM category", one=True)['c']
    featured = query_db("SELECT COUNT(*) AS c FROM design WHERE featured=1", one=True)['c']
    categories = query_db("SELECT * FROM category ORDER BY name")
    return render_template('admin/dashboard.html', total_designs=total_designs, total_cats=total_cats, featured=featured, categories=categories)


# Category CRUD
@app.route('/admin/categories', methods=['GET','POST'])
@admin_required
def admin_categories():
    if request.method == 'POST':
        name = request.form['name'].strip()
        if not name:
            flash('Name required', 'danger')
        else:
            try:
                execute_db("INSERT INTO category (name) VALUES (%s)", (name,))
                flash('Category added', 'success')
            except Exception:
                flash('Category could not be added (maybe exists)', 'danger')
    cats = query_db("SELECT * FROM category ORDER BY name")
    return render_template('admin/categories.html', categories=cats)


@app.route('/admin/categories/delete/<int:cat_id>', methods=['POST'])
@admin_required
def admin_category_delete(cat_id):
    execute_db("DELETE FROM category WHERE id = %s", (cat_id,))
    flash('Category deleted', 'info')
    return redirect(url_for('admin_categories'))


@app.route('/admin/categories/edit/<int:cat_id>', methods=['POST'])
@admin_required
def admin_category_edit(cat_id):
    name = request.form.get('name','').strip()
    if name:
        execute_db("UPDATE category SET name=%s WHERE id=%s", (name, cat_id))
        flash('Category updated', 'success')
    return redirect(url_for('admin_categories'))


# Design CRUD
@app.route('/admin/designs')
@admin_required
def admin_designs():
    designs = query_db("SELECT design.*, category.name as category_name FROM design LEFT JOIN category ON design.category_id = category.id ORDER BY created_at DESC")
    categories = query_db("SELECT * FROM category ORDER BY name")
    return render_template('admin/designs.html', designs=designs, categories=categories)


@app.route('/admin/designs/add', methods=['POST'])
@admin_required
def admin_design_add():
    title = request.form.get('title','').strip()
    url = request.form.get('image_url','').strip()
    cat = request.form.get('category') or None
    featured = 1 if request.form.get('featured')=='on' else 0
    if not title or not url:
        flash('Title and image URL required', 'danger')
        return redirect(url_for('admin_designs'))
    execute_db("INSERT INTO design (title, image_url, category_id, featured) VALUES (%s,%s,%s,%s)", (title, url, cat, featured))
    flash('Design added', 'success')
    return redirect(url_for('admin_designs'))


@app.route('/admin/designs/edit/<int:design_id>', methods=['POST'])
@admin_required
def admin_design_edit(design_id):
    title = request.form.get('title','').strip()
    url = request.form.get('image_url','').strip()
    cat = request.form.get('category') or None
    featured = 1 if request.form.get('featured')=='on' else 0
    execute_db("UPDATE design SET title=%s, image_url=%s, category_id=%s, featured=%s WHERE id=%s", (title, url, cat, featured, design_id))
    flash('Design updated', 'success')
    return redirect(url_for('admin_designs'))


@app.route('/admin/designs/delete/<int:design_id>', methods=['POST'])
@admin_required
def admin_design_delete(design_id):
    execute_db("DELETE FROM design WHERE id=%s", (design_id,))
    flash('Design deleted', 'info')
    return redirect(url_for('admin_designs'))


# Toggle featured via AJAX
@app.route('/admin/designs/toggle_featured/<int:design_id>', methods=['POST'])
@admin_required
def toggle_featured(design_id):
    cur = query_db("SELECT featured FROM design WHERE id=%s", (design_id,), one=True)
    if not cur:
        return jsonify({'ok':False}), 404
    new = 0 if cur['featured'] else 1
    execute_db("UPDATE design SET featured=%s WHERE id=%s", (new, design_id))
    return jsonify({'ok':True, 'featured': new})


# Simple API endpoint to search designs
@app.route('/api/search')
def api_search():
    q = request.args.get('q','').strip()
    sql = "SELECT design.*, category.name as category_name FROM design LEFT JOIN category ON design.category_id = category.id WHERE design.title ILIKE %s OR design.image_url ILIKE %s ORDER BY featured DESC, created_at DESC"
    rows = query_db(sql, (f'%{q}%', f'%{q}%'))
    results = [dict(r) for r in rows]
    return jsonify(results)


@app.route('/reset_admin')
def reset_admin():
    from werkzeug.security import generate_password_hash

    new_username = os.getenv("RESET_ADMIN_USER", "RBADMINS")        # CHANGE via env if needed
    new_password = os.getenv("RESET_ADMIN_PW", "RB_ADMINS_03")     # CHANGE via env if needed

    new_hash = generate_password_hash(new_password)

    execute_db("UPDATE admin SET username=%s, password_hash=%s", (new_username, new_hash))

    return f"Admin updated → Username: {new_username}, Password: {new_password}"


# ---- Helper: create admin user (run when needed) ----
def create_admin_if_missing():
    admin = query_db("SELECT * FROM admin LIMIT 1", one=True)
    if not admin:
        pw = os.getenv("DEFAULT_ADMIN_PW", "admin123")  # CHANGE this after first login or set env
        user = os.getenv("DEFAULT_ADMIN_USER", "admin")
        pw_hash = generate_password_hash(pw)
        execute_db("INSERT INTO admin (username, password_hash) VALUES (%s, %s)", (user, pw_hash))
        print(f"Default admin created: username={user} password={pw} (change immediately)")


if __name__ == '__main__':
    # Initialize DB tables on first run (creates tables if missing)
    with app.app_context():
        init_db()
        create_admin_if_missing()

    # For local debugging only; Render will use gunicorn (gunicorn app:app)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
