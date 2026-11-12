"""Book management - Flask + SQLite
Features:
  1. CRUD book categories
  2. CRUD books by category
  3. Dashboard for categories and books
  4. SQLite database (library.db, created on first run)
"""
import os
import sqlite3
from flask import Flask, g, render_template, request, redirect, url_for, flash, abort

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "library.db")

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS books (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    author      TEXT NOT NULL,
    price       INTEGER NOT NULL DEFAULT 0 CHECK (price >= 0),
    quantity    INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    year        INTEGER,
    description TEXT DEFAULT '',
    category_id INTEGER NOT NULL,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
);
"""

SEED_CATEGORIES = [
    ("Lap trinh", "Sach ve ngon ngu lap trinh va ky thuat phan mem"),
    ("Van hoc", "Tieu thuyet, truyen ngan, tho"),
    ("Kinh te", "Quan tri, tai chinh, khoi nghiep"),
]
SEED_BOOKS = [
    ("Python co ban", "Nguyen Van An", 95000, 12, 2022, "Nhap mon Python cho nguoi moi.", 1),
    ("Clean Code", "Robert C. Martin", 220000, 5, 2019, "Viet ma sach va de bao tri.", 1),
    ("De Men phieu luu ky", "To Hoai", 45000, 30, 2020, "Tac pham thieu nhi kinh dien.", 2),
    ("Cha giau cha ngheo", "Robert Kiyosaki", 110000, 8, 2018, "Tu duy tai chinh ca nhan.", 3),
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
        db.executemany("INSERT INTO categories(name, description) VALUES (?, ?)", SEED_CATEGORIES)
        db.executemany(
            "INSERT INTO books(title, author, price, quantity, year, description, category_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)", SEED_BOOKS)
    db.commit()
    db.close()


@app.template_filter("vnd")
def vnd(value):
    return f"{int(value or 0):,}".replace(",", ".") + " VND"


# ---- Dashboard ----
@app.route("/")
def dashboard():
    db = get_db()
    stats = db.execute(
        "SELECT (SELECT COUNT(*) FROM categories) AS categories, "
        "COUNT(*) AS titles, COALESCE(SUM(quantity),0) AS stock, "
        "COALESCE(SUM(price*quantity),0) AS value FROM books").fetchone()
    per_category = db.execute(
        "SELECT c.id, c.name, COUNT(b.id) AS titles, COALESCE(SUM(b.quantity),0) AS stock "
        "FROM categories c LEFT JOIN books b ON b.category_id = c.id "
        "GROUP BY c.id ORDER BY titles DESC, c.name").fetchall()
    latest = db.execute(
        "SELECT b.*, c.name AS category FROM books b JOIN categories c ON c.id=b.category_id "
        "ORDER BY b.id DESC LIMIT 5").fetchall()
    low_stock = db.execute(
        "SELECT b.*, c.name AS category FROM books b JOIN categories c ON c.id=b.category_id "
        "WHERE b.quantity <= 5 ORDER BY b.quantity, b.title LIMIT 5").fetchall()
    max_titles = max([r["titles"] for r in per_category], default=0) or 1
    return render_template("dashboard.html", stats=stats, per_category=per_category,
                           latest=latest, low_stock=low_stock, max_titles=max_titles)


# ---- Categories ----
@app.route("/categories")
def category_list():
    rows = get_db().execute(
        "SELECT c.*, COUNT(b.id) AS book_count FROM categories c "
        "LEFT JOIN books b ON b.category_id = c.id GROUP BY c.id ORDER BY c.name").fetchall()
    return render_template("category_list.html", categories=rows)


@app.route("/categories/new", methods=["GET", "POST"])
def category_create():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        desc = request.form.get("description", "").strip()
        if not name:
            flash("Hay nhap ten danh muc.", "error")
        else:
            try:
                get_db().execute("INSERT INTO categories(name, description) VALUES (?, ?)", (name, desc))
                get_db().commit()
                flash(f"Da them danh muc '{name}'.", "ok")
                return redirect(request.referrer or url_for("category_list"))
            except sqlite3.IntegrityError:
                flash("Ten danh muc da ton tai. Hay chon ten khac.", "error")
        return render_template("category_form.html", category={"name": name, "description": desc}, editing=False)
    return render_template("category_form.html", category={"name": "", "description": ""}, editing=False)


@app.route("/categories/<int:cid>/edit", methods=["GET", "POST"])
def category_edit(cid):
    db = get_db()
    cat = db.execute("SELECT * FROM categories WHERE id=?", (cid,)).fetchone() or abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        desc = request.form.get("description", "").strip()
        if not name:
            flash("Hay nhap ten danh muc.", "error")
        else:
            try:
                db.execute("UPDATE categories SET name=?, description=? WHERE id=?", (name, desc, cid))
                db.commit()
                flash("Da luu thay doi danh muc.", "ok")
                return redirect(url_for("category_list"))
            except sqlite3.IntegrityError:
                flash("Ten danh muc da ton tai. Hay chon ten khac.", "error")
        cat = {"id": cid, "name": name, "description": desc}
    return render_template("category_form.html", category=cat, editing=True)


@app.route("/categories/<int:cid>/delete", methods=["POST"])
def category_delete(cid):
    db = get_db()
    cat = db.execute("SELECT name FROM categories WHERE id=?", (cid,)).fetchone() or abort(404)
    db.execute("DELETE FROM categories WHERE id=?", (cid,))  # ON DELETE CASCADE also deletes the books in this category
    db.commit()
    flash(f"Da xoa danh muc '{cat['name']}' va cac sach thuoc danh muc.", "ok")
    return redirect(url_for("category_list"))


# ---- Books ----
def parse_book_form(form):
    data = {
        "title": form.get("title", "").strip(),
        "author": form.get("author", "").strip(),
        "price": form.get("price", "0").strip(),
        "quantity": form.get("quantity", "0").strip(),
        "year": form.get("year", "").strip(),
        "description": form.get("description", "").strip(),
        "category_id": form.get("category_id", "").strip(),
    }
    errors = []
    if not data["title"]:
        errors.append("Hay nhap ten sach.")
    if not data["author"]:
        errors.append("Hay nhap ten tac gia.")
    if not data["category_id"].isdigit():
        errors.append("Hay chon danh muc.")
    for field, label in (("price", "Gia"), ("quantity", "So luong")):
        if not data[field].isdigit():
            errors.append(f"{label} phai la so nguyen khong am.")
    if data["year"] and not data["year"].isdigit():
        errors.append("Nam xuat ban phai la so.")
    return data, errors


@app.route("/books")
def book_list():
    db = get_db()
    cid = request.args.get("category", type=int)
    q = request.args.get("q", "").strip()
    sql = ("SELECT b.*, c.name AS category FROM books b JOIN categories c ON c.id=b.category_id WHERE 1=1")
    params = []
    if cid:
        sql += " AND b.category_id = ?"
        params.append(cid)
    if q:
        sql += " AND (b.title LIKE ? OR b.author LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY b.id DESC"
    books = db.execute(sql, params).fetchall()
    categories = db.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
    return render_template("book_list.html", books=books, categories=categories, selected=cid, q=q)


@app.route("/books/new", methods=["GET", "POST"])
def book_create():
    db = get_db()
    categories = db.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
    if not categories:
        flash("Hay tao it nhat mot danh muc truoc khi them sach.", "error")
        return redirect(url_for("category_create"))
    if request.method == "POST":
        data, errors = parse_book_form(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            db.execute(
                "INSERT INTO books(title, author, price, quantity, year, description, category_id) "
                "VALUES (:title, :author, :price, :quantity, NULLIF(:year,''), :description, :category_id)", data)
            db.commit()
            flash(f"Da them sach '{data['title']}'.", "ok")
            return redirect(url_for("book_list", category=data["category_id"]))
        return render_template("book_form.html", book=data, categories=categories, editing=False)
    pre = request.args.get("category", "")
    book = {"title": "", "author": "", "price": "", "quantity": "", "year": "", "description": "", "category_id": pre}
    return render_template("book_form.html", book=book, categories=categories, editing=False)


@app.route("/books/<int:bid>/edit", methods=["GET", "POST"])
def book_edit(bid):
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id=?", (bid,)).fetchone() or abort(404)
    categories = db.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
    if request.method == "POST":
        data, errors = parse_book_form(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            data["id"] = bid
            return render_template("book_form.html", book=data, categories=categories, editing=True)
        data["id"] = bid
        db.execute(
            "UPDATE books SET title=:title, author=:author, price=:price, quantity=:quantity, "
            "year=NULLIF(:year,''), description=:description, category_id=:category_id WHERE id=:id", data)
        db.commit()
        flash("Da luu thay doi sach.", "ok")
        return redirect(url_for("book_list", category=data["category_id"]))
    return render_template("book_form.html", book=book, categories=categories, editing=True)


@app.route("/books/<int:bid>/delete", methods=["POST"])
def book_delete(bid):
    db = get_db()
    book = db.execute("SELECT title, category_id FROM books WHERE id=?", (bid,)).fetchone() or abort(404)
    db.execute("DELETE FROM books WHERE id=?", (bid,))
    db.commit()
    flash(f"Da xoa sach '{book['title']}'.", "ok")
    return redirect(request.referrer or url_for("book_list"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
