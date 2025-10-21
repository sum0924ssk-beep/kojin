from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3, shutil, os, datetime

app = FastAPI()

# 静的ファイルとテンプレート設定
os.makedirs("uploads", exist_ok=True)
templates = Jinja2Templates(directory="templates")

# 【重要】静的ファイルとして CSSやJSなど（static/）と、アップロードされた画像（uploads/）をマウント
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

DB_NAME = "condiments.db"

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

# ----------------------------------------------------------------------
# GET: 登録画面と一覧表示の統合エンドポイント
# ----------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    # 必要なデータを取得: id, name, image_path
    cur.execute("SELECT name, image_path FROM condiments ORDER BY id DESC")
    raw_items = cur.fetchall()
    conn.close()

    # 【★修正点★】データベースのファイルパスを、Webアクセス可能なURL形式に変換
    items = []
    for row in raw_items:
        name, image_path = row
        
        # データベースに保存されているパス (例: "uploads/filename.jpg") を
        # Webブラウザからアクセス可能な URL (例: "/uploads/filename.jpg") に変換
        image_url = f"/{image_path}" 
        
        # テンプレートに渡すデータ形式 (調味料名, 画像URL) を作成
        items.append((name, image_url))

    # index.html は「登録」画面と「一覧」表示を兼ねているものとする
    return templates.TemplateResponse("index.html", {"request": request, "items": items})

# ----------------------------------------------------------------------
# POST: 画像とデータのアップロード
# ----------------------------------------------------------------------
@app.post("/upload")
async def upload(name: str = Form(...), expiry: str = Form(...), file: UploadFile = File(...)):
    # UploadFile の変数名を 'file' に統一
    filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_path = f"uploads/{filename}" # DBに保存するパス

    # ファイルの保存
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    conn = sqlite3.connect(DB_NAME)
    conn.execute(
        "INSERT INTO condiments (name, expiry, image_path, created_at) VALUES (?, ?, ?, ?)",
        (name, expiry, file_path, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

    return RedirectResponse("/", status_code=303)

# ----------------------------------------------------------------------
# POST: アイテムの削除
# ----------------------------------------------------------------------
@app.post("/delete/{item_id}")
async def delete_item(item_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # 画像パスを取得し、ファイルを削除
    cur.execute("SELECT image_path FROM condiments WHERE id=?", (item_id,))
    row = cur.fetchone()
    if row:
        image_path = row[0]
        if os.path.exists(image_path):
            os.remove(image_path) # 物理ファイルの削除
    
    # データベースのレコードを削除
    cur.execute("DELETE FROM condiments WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=303)