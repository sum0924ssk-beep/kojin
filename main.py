from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3, shutil, os, datetime

app = FastAPI()
templates = Jinja2Templates(directory="templates")

DB_NAME = "condiments.db"
# uploadsディレクトリが存在しない場合は作成
os.makedirs("uploads", exist_ok=True)

# 💡 修正ポイント: /uploads パスに uploads ディレクトリをマウント
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# DB初期化
conn = sqlite3.connect(DB_NAME)
conn.execute("""
CREATE TABLE IF NOT EXISTS condiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    expiry TEXT,
    image_path TEXT,
    created_at TEXT
)
""")
conn.commit()
conn.close()


# -----------------------------------------------------------
# GET: 登録画面（トップ）
# -----------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name, expiry, image_path, created_at FROM condiments ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    items = []
    for item_id, name, expiry, image_path, created_at in rows:
        # 💡 修正: DBに保存されたパスをそのままURLとして利用 (例: 'uploads/file.jpg' -> '/uploads/file.jpg')
        image_url = f"/{image_path}" if image_path and os.path.exists(image_path) else "/static/noimage.png"

        items.append({
            "id": item_id,
            "name": name,
            "expiry": expiry if expiry else "未設定",
            "image_url": image_url,
            "registered_date": created_at
        })

    # index.html はリスト表示に使われていなかったので、list.html にリダイレクトするのが自然ですが、
    # 元のコードに合わせて index.html を使用します。
    return templates.TemplateResponse("index.html", {"request": request, "items": items})


# -----------------------------------------------------------
# POST: 登録処理
# -----------------------------------------------------------
@app.post("/upload")
async def upload(name: str = Form(...), file: UploadFile = File(...), expiry: str = Form(None)):
    # ファイル名が一意になるようにタイムスタンプを付加
    filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    # 💡 修正: DBには、マウントされたディレクトリ名を含むパス 'uploads/ファイル名' を保存
    file_path_db = f"uploads/{filename}"

    # サーバーのファイルシステムに保存
    with open(file_path_db, "wb") as buffer:
        # ファイルポインタが既に読み込まれている場合があるため rewind する
        file.file.seek(0)
        shutil.copyfileobj(file.file, buffer)

    conn = sqlite3.connect(DB_NAME)
    conn.execute(
        "INSERT INTO condiments (name, expiry, image_path, created_at) VALUES (?, ?, ?, ?)",
        (name, expiry if expiry else "", file_path_db, datetime.datetime.now().strftime("%Y-%m-%d"))
    )
    conn.commit()
    conn.close()

    return RedirectResponse("/", status_code=303)


# -----------------------------------------------------------
# GET: 一覧ページ (list.html を使う)
# -----------------------------------------------------------
@app.get("/list", response_class=HTMLResponse)
async def list_items(request: Request):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name, expiry, image_path, created_at FROM condiments ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    items = []
    for item_id, name, expiry, image_path, created_at in rows:
        # 💡 修正: DBに保存されたパスをそのままURLとして利用
        image_url = f"/{image_path}" if image_path and os.path.exists(image_path) else "/static/noimage.png"
        
        items.append({
            "id": item_id,
            "name": name,
            "expiry": expiry if expiry else "未設定",
            "image_url": image_url,
            "registered_date": created_at
        })

    return templates.TemplateResponse("list.html", {"request": request, "items": items})


# -----------------------------------------------------------
# POST: 削除処理
# -----------------------------------------------------------
@app.post("/delete/{item_id}")
async def delete_item(item_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # 削除前にファイルパスを取得し、ファイルシステムから削除
    cur.execute("SELECT image_path FROM condiments WHERE id=?", (item_id,))
    row = cur.fetchone()
    if row:
        image_path = row[0]
        if os.path.exists(image_path):
            os.remove(image_path) # ファイル削除

    # DBからレコードを削除
    cur.execute("DELETE FROM condiments WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/list", status_code=303) # 一覧へリダイレクト