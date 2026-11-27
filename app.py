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

from services.emoji import CATALOG, RECOMMENDED, allowed_code
from services.discussion import availability, parse_deadline, reaction_state
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
                             "Content-Security-Policy": "default-src 'self'; img-src 'self' blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
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
    if not storage().add("rate", f"{int(time.time()) // 10}-{request.view_args.get('action', 'post')}-{digest}", {}):
        abort(429)


def board():
    deleted = {r["post"] for r in storage().rows("deleted")}
    posts = [p for p in storage().rows("board") if p["RowKey"] not in deleted]
    counts = {part: Counter(row["post"] for row in storage().rows(part))
              for part in ("comment", "like", "resolved")}
    settings = {r["RowKey"]: r for r in storage().rows("deadlines")}
    now = int(time.time())
    for p in posts:
        key = p["RowKey"]
        p.setdefault("title", p["text"][:50])
        p.setdefault("category", "雑談")
        p.update(answers=counts["comment"][key], likes=counts["like"][key], solved=bool(counts["resolved"][key]))
        if key in settings:
            p.update(deadline=settings[key]["deadline"], paused=settings[key]["paused"])
        availability(p, now)
    return posts


@app.get("/")
def index():
    posts = board()
    category = request.args.get("category", "")
    query = request.args.get("q", "").strip().casefold()
    rows = [p for p in posts if (not category or p["category"] == category)
            and (request.args.get("view") != "mine" or p.get("owner") == session["owner"])
            and query in (p["title"] + " " + p["text"]).casefold()
            and (not request.args.get("unanswered") or not p["answers"] and p["accepting"])]
    popular = request.args.get("sort") == "popular"
    rows.sort(key=lambda p: (p["likes"] if popular else 0, p["posted_at"], p["RowKey"]), reverse=True)
    return render_template("index.html", posts=rows, categories=CATEGORIES, category=category)


@app.get("/guide")
def guide():
    return render_template("guide.html")


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
    deadline = requested_deadline()
    image = uploaded_image()
    rate_limit()
    key = str(uuid.uuid4())
    if image:
        storage().picture(key, image)
    storage().add("board", key, dict(title=title, name=name, text=body, category=category,
                                    deadline=deadline, owner=session["owner"], posted_at=timestamp(), image=bool(image)))
    flash("投稿を公開しました。", "posted")
    return redirect(url_for("detail", key=key), 303)


def find_post(key):
    return next((p for p in board() if p["RowKey"] == str(key)), None) or abort(404)


@app.get("/p/<uuid:key>")
def detail(key):
    p = find_post(key)
    comments = sorted((r for r in storage().rows("comment") if r["post"] == str(key)),
                      key=lambda r: (r["posted_at"], r["RowKey"]))
    return render_template("detail.html", p=p, comments=comments, catalog=CATALOG,
                           reactions=reaction_state(storage(), str(key), session["owner"]))


def requested_deadline():
    try:
        return parse_deadline(request.form.get("deadline_mode", "none"),
                              request.form.get("deadline_custom", ""), int(time.time()))
    except (ValueError, OverflowError, OSError):
        abort(400)


@app.post("/p/<uuid:key>/deadline")
def deadline_settings(key):
    post = find_post(key)
    if post.get("owner") != session["owner"]:
        abort(403)
    operation = request.form.get("operation")
    if operation not in ("pause", "set"):
        abort(400)
    end = post.get("deadline", 0) if operation == "pause" else requested_deadline()
    storage().put("deadlines", str(key), {"deadline": end, "paused": operation == "pause"})
    flash("受付設定を更新しました。")
    return redirect(url_for("detail", key=key), 303)


@app.get("/p/<uuid:key>/emoji-catalog")
def emoji_catalog(key):
    find_post(key)
    post = str(key)
    return {"items": [[code, *entry] for code, entry in CATALOG.items() if allowed_code(code, post)],
            "recommended": [code for code in RECOMMENDED if allowed_code(code, post)]}


@app.post("/p/<uuid:key>/emoji")
def emoji_change(key):
    find_post(key)
    key = str(key)
    code = allowed_code(request.form.get("emoji", ""), key)
    if not code:
        return {"error": "この絵文字はCampus Linkでは使用できません。"}, 400
    active = request.form.get("active")
    revision = request.form.get("revision", type=int)
    if active not in ("0", "1") or revision is None or revision < 0:
        abort(400)
    owner = session["owner"]
    state = reaction_state(storage(), key, owner)
    current = state.get(code, {"revision": 0, "mine": False})
    # Apply desired membership only against the version the user actually saw.
    if current["revision"] == revision and current["mine"] != (active == "1"):
        address = (request.remote_addr or "").encode()
        digest = hmac.new(app.secret_key.encode(), address, hashlib.sha256).hexdigest()
        window = int(time.time()) // 10
        for slot in range(16):
            if storage().add("emoji-rate", f"{window}-{digest}-{slot}", {}):
                break
        else:
            abort(429)
        storage().add("emoji-" + key, f"{owner}-{code}-{revision+1}", {
            "owner": owner, "emoji": code, "revision": revision+1, "active": active == "1",
            "created": int(time.time()),
        })
        state = reaction_state(storage(), key, owner)
    return state


@app.post("/p/<uuid:key>/<action>")
def act(key, action):
    p = find_post(key)
    key = str(key)
    data = {"post": key}
    if action == "comment":
        if not p["accepting"]:
            abort(409)
        data.update(text=field("message", 2000), name=field("name", 24, "名無し"), posted_at=timestamp())
        row = str(uuid.uuid4())
    elif action in ("resolved", "deleted"):
        if p.get("owner") != session["owner"]:
            abort(403)
        row = key
    elif action in ("like", "report"):
        row = key + "-" + session["owner"]
        if action == "report" and request.form.get("reported_emoji"):
            code = allowed_code(request.form["reported_emoji"], key)
            if not code or not reaction_state(storage(), key, session["owner"]).get(code, {}).get("count"):
                abort(400)
            data["emoji"] = code
            row += "-" + code
    else:
        abort(404)
    rate_limit()
    if action == "comment" and p.get("deadline") and time.time() >= p["deadline"]:
        abort(409)
    added = storage().add(action, row, data)
    if action == "deleted":
        flash("投稿を削除しました。")
        return redirect(url_for("index"), 303)
    flash("受け付けました。" if added else "すでに受け付けています。",
          "answered" if action == "comment" else "message")
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
