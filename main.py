from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3, shutil, os, datetime

# アプリケーションの初期化
app = FastAPI()

# 設定
templates = Jinja2Templates(directory="templates")
DB_NAME = "condiments.db"
os.makedirs("uploads", exist_ok=True) # 画像アップロードフォルダの確認/作成

# 静的ファイルとアップロードフォルダをWebからアクセス可能にする設定
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads") # アップロード画像を公開

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
# GET: 登録画面（ルートパス）
# ----------------------------------------------------------------------
# ルートパスでは、フォームを表示するだけでなく、一覧表示のデータも渡す（index.htmlで両方表示するため）
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    # 登録アイテムを取得 (削除機能がないため、すべてのフィールドを取得)
    cur.execute("SELECT id, name, expiry, image_path, created_at FROM condiments ORDER BY id DESC")
    raw_items = cur.fetchall()
    conn.close()
    
    # テンプレートに渡すデータ形式を調整 (ここではindex.html側で使用しないが、一貫性のためリストを渡す)
    items = []
    for row in raw_items:
        item_id, name, expiry, image_path, created_at = row
        # image_path は "uploads/..." なので、URLとしては "/uploads/..." になる
        image_url = f"/{image_path}"
        # 登録画面で一覧が必要な場合は、適切なデータ形式で渡す
        items.append((item_id, name, image_url))

    # index.html は「登録」画面と「一覧」表示を兼ねているものとする
    return templates.TemplateResponse("index.html", {"request": request, "items": items})


# ----------------------------------------------------------------------
# POST: 画像とデータのアップロード（修正済）
# ----------------------------------------------------------------------
@app.post("/upload")
# 【★修正点★】expiryを必須ではない(Noneを許可)にし、画像フィールド名を 'file' に統一
async def upload(name: str = Form(...), file: UploadFile = File(...), expiry: str = Form(None)):
    filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_path = f"uploads/{filename}"

    # ファイルの保存
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    conn = sqlite3.connect(DB_NAME)
    conn.execute(
        "INSERT INTO condiments (name, expiry, image_path, created_at) VALUES (?, ?, ?, ?)",
        (name, expiry if expiry else "", file_path, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

    return RedirectResponse("/", status_code=303)


# ----------------------------------------------------------------------
# GET: 一覧表示専用エンドポイント（リクエストされた追加機能）
# ----------------------------------------------------------------------
@app.get("/list", response_class=HTMLResponse)
async def list_items(request: Request):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    # 必要なデータをDBから取得: name, image_path
    cur.execute("SELECT name, image_path FROM condiments ORDER BY id DESC")
    raw_items = cur.fetchall()
    conn.close()

    # 画像パスをURLに変換する処理
    items = []
    for row in raw_items:
        name, image_path = row
        # DBパス ("uploads/...") をWeb URL ("/uploads/...") に変換
        image_url = f"/{image_path}"
        items.append((name, image_url))
        
    # 【★ポイント★】一覧表示用のテンプレート名 list.html を使用
    return templates.TemplateResponse("list.html", {"request": request, "items": items})

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
            os.remove(image_path)
    
    # データベースのレコードを削除
    cur.execute("DELETE FROM condiments WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=303)
