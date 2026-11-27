import hashlib
import hmac
import io
import os
import secrets
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from azure.core.exceptions import AzureError
from flask import Flask, abort, flash, redirect, render_template, request, send_file, session, url_for
from PIL import Image, ImageOps, UnidentifiedImageError

from services.store import Azure, Local

CATEGORIES = ("勉強", "課題", "進路", "部活動", "相談", "雑談")
JST = timezone(timedelta(hours=9))
app = Flask(__name__)
cloud = bool(os.getenv("WEBSITE_SITE_NAME") or os.getenv("STORAGE_MODE") == "azure"
             or os.getenv("AZURE_STORAGE_CONNECTION_STRING"))
directory = Path(app.instance_path)
directory.mkdir(exist_ok=True)
secret = os.getenv("SECRET_KEY")
if not secret and not cloud:
    file = directory / "session.key"
    try:
        with file.open("x") as stream:
            stream.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    secret = file.read_text()
app.config.update(SECRET_KEY=secret, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=cloud,
                  MAX_CONTENT_LENGTH=5 * 1024 * 1024 + 65536)
store = None


def storage():
    global store
    if store is None:
        store = Azure() if cloud else Local(directory)
    return store


def timestamp():
    return datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S")


@app.before_request
def protect():
    if request.endpoint == "static":
        return
    if not app.secret_key:
        abort(503)
    if "owner" not in session:
        session.update(owner=secrets.token_hex(24), csrf=secrets.token_hex(24))
    if request.method == "POST" and not secrets.compare_digest(
            session["csrf"].encode(), request.form.get("csrf", "").encode()):
        abort(403)


@app.after_request
def headers(response):
    response.headers.update({"X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin",
                             "Content-Security-Policy": "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
    return response


def field(key, limit, default=""):
    value = request.form.get(key, "").strip() or default
    if not value or len(value) > limit:
        abort(400)
    return value


def rate_limit():
    # One write per address per ten-second interval, shared across workers.
    address = request.remote_addr or ""
    digest = hmac.new(app.secret_key.encode(), address.encode(), hashlib.sha256).hexdigest()
    if not storage().add("rate", f"{int(time.time()) // 10}-{digest}", {}):
        abort(429)


def board():
    posts = storage().rows("board")
    counts = {part: Counter(row["post"] for row in storage().rows(part))
              for part in ("comment", "like", "resolved")}
    for p in posts:
        key = p["RowKey"]
        p.setdefault("title", p["text"][:50])
        p.setdefault("category", "雑談")
        p.update(answers=counts["comment"][key], likes=counts["like"][key], solved=bool(counts["resolved"][key]))
    return posts


@app.get("/")
def index():
    posts = board()
    category = request.args.get("category", "")
    query = request.args.get("q", "").strip().casefold()
    rows = [p for p in posts if (not category or p["category"] == category)
            and query in (p["title"] + " " + p["text"]).casefold()
            and (not request.args.get("unanswered") or not p["answers"] and not p["solved"])]
    popular = request.args.get("sort") == "popular"
    rows.sort(key=lambda p: (p["likes"] if popular else 0, p["posted_at"], p["RowKey"]), reverse=True)
    return render_template("index.html", posts=rows, categories=CATEGORIES, category=category)


@app.get("/new")
def new():
    return render_template("new.html", categories=CATEGORIES)


def uploaded_image():
    upload = request.files.get("image")
    if not upload or not upload.filename:
        return None
    data = upload.read(5 * 1024 * 1024 + 1)
    if len(data) > 5 * 1024 * 1024:
        abort(413)
    try:
        with Image.open(io.BytesIO(data), formats=("JPEG", "PNG")) as img:
            if img.width * img.height > 12_000_000:
                abort(400)
            img.load()
            clean = ImageOps.exif_transpose(img).convert("RGB")
            clean.thumbnail((1600, 1600))
            output = io.BytesIO()
            clean.save(output, "JPEG", quality=85)
            return output.getvalue()
    except (ValueError, OSError, Image.DecompressionBombError, UnidentifiedImageError):
        abort(400)


@app.post("/post")
def post():
    body = field("message", 3000)
    title = field("title", 80, body[:50])
    name = field("name", 24, "名無し")
    category = field("category", 8, "雑談")
    if category not in CATEGORIES:
        abort(400)
    image = uploaded_image()
    rate_limit()
    key = str(uuid.uuid4())
    if image:
        storage().picture(key, image)
    storage().add("board", key, dict(title=title, name=name, text=body, category=category,
                                    owner=session["owner"], posted_at=timestamp(), image=bool(image)))
    flash("投稿を公開しました。")
    return redirect(url_for("detail", key=key), 303)


def find_post(key):
    return next((p for p in board() if p["RowKey"] == str(key)), None) or abort(404)


@app.get("/p/<uuid:key>")
def detail(key):
    p = find_post(key)
    comments = sorted((r for r in storage().rows("comment") if r["post"] == str(key)),
                      key=lambda r: (r["posted_at"], r["RowKey"]))
    return render_template("detail.html", p=p, comments=comments)


@app.post("/p/<uuid:key>/<action>")
def act(key, action):
    p = find_post(key)
    key = str(key)
    data = {"post": key}
    if action == "comment":
        if p["solved"]:
            abort(409)
        data.update(text=field("message", 2000), name=field("name", 24, "名無し"), posted_at=timestamp())
        row = str(uuid.uuid4())
    elif action == "resolved":
        if p.get("owner") != session["owner"]:
            abort(403)
        row = key
    elif action in ("like", "report"):
        row = key + "-" + session["owner"]
    else:
        abort(404)
    rate_limit()
    added = storage().add(action, row, data)
    flash(("受け付けました。" if added else "すでに受け付けています。"))
    return redirect(url_for("detail", key=key), 303)


@app.get("/image/<uuid:key>")
def image(key):
    if not find_post(key).get("image"):
        abort(404)
    try:
        return send_file(io.BytesIO(storage().picture(str(key))), mimetype="image/jpeg")
    except FileNotFoundError:
        abort(404)


def error(exc):
    code = getattr(exc, "code", 503)
    return render_template("error.html", code=code), code


for status in (400, 403, 404, 409, 413, 429, 503):
    app.register_error_handler(status, error)
app.register_error_handler(AzureError, error)
app.register_error_handler(KeyError, error)

if __name__ == "__main__":
    app.run()
