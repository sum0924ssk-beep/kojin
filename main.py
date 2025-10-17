from fastapi import FastAPI, Form, UploadFile, File, Request, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware # セッション管理用
from passlib.context import CryptContext # パスワードハッシュ化用

import sqlite3
import shutil
import os
import datetime

# --- 設定と初期化 ---
app = FastAPI()

# 環境変数からシークレットキーを取得するか、固定値を設定
# ★ 運用時は必ず安全なシークレットキーを設定してください！
SECRET_KEY = os.environ.get("SECRET_KEY", "your-super-secret-key-that-should-be-random")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# 静的ファイルとテンプレート設定
os.makedirs("uploads", exist_ok=True)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

DB_NAME = "condiments.db"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- データベース初期化 ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    
    # 1. 調味料テーブル
    conn.execute("""
    CREATE TABLE IF NOT EXISTS condiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        expiry TEXT,
        image_path TEXT,
        created_at TEXT
    )
    """)
    
    # 2. ユーザーテーブル (ログイン機能用)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL
    )
    """)
    
    # 動作確認用に初期ユーザーを登録 (既に存在する場合は無視)
    try:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            hashed = pwd_context.hash("password") # 初期パスワードは 'password'
            conn.execute("INSERT INTO users (username, hashed_password) VALUES (?, ?)", ("user", hashed))
    except Exception:
        pass # テーブルが存在しない場合は無視
        
    conn.commit()
    conn.close()

init_db()


# --- 依存性注入 (認証ガード) ---
def require_login(request: Request):
    """ログインしていない場合はログインページにリダイレクトする"""
    if "user_id" not in request.session:
        # 302 Found (一時的なリダイレクト) を使用
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            detail="Not authenticated",
            headers={"Location": "/login"}
        )
    return request.session["user_id"]

# --- 認証ルート ---

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, error: str = None):
    """ログインフォームを表示"""
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    """認証処理を実行"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, hashed_password FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()

    if not row or not pwd_context.verify(password, row[1]):
        # 認証失敗: エラーメッセージを表示してログインページに戻す
        error_msg = "ユーザー名またはパスワードが正しくありません"
        return templates.TemplateResponse("login.html", {"request": request, "error": error_msg}, status_code=status.HTTP_401_UNAUTHORIZED)
    
    # 認証成功: セッションにユーザーIDを保存し、メインページにリダイレクト
    user_id = row[0]
    request.session["user_id"] = user_id
    
    # 303 See Other (POST後のリダイレクトに最適)
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/logout")
async def logout(request: Request):
    """ログアウト処理"""
    request.session.clear() # セッション情報をクリア
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)


# --- アプリケーションルート (ログイン必須) ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user_id: int = Depends(require_login)):
    """登録ページ（メインページ）を表示"""
    # データベースからデータを取得するロジックは/listに移動することを推奨
    # 暫定的にこのルートは登録フォームを表示
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/list", response_class=HTMLResponse)
async def list_items(request: Request, user_id: int = Depends(require_login)):
    """登録済み調味料の一覧を表示"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    # データベースの設計上、ユーザーごとのデータを絞り込む処理がないため、全件取得
    # ★ データベースに user_id カラムを追加して絞り込むことを推奨します
    cur.execute("SELECT id, name, image_path FROM condiments ORDER BY id DESC")
    # item[0]=id, item[1]=name, item[2]=image_path
    items = [(item[1], app.url_path_for('uploads', path=item[2].replace('uploads/', '')), item[0]) for item in cur.fetchall()]
    conn.close()
    
    return templates.TemplateResponse("list.html", {"request": request, "items": items})

@app.post("/upload")
async def upload(user_id: int = Depends(require_login), name: str = Form(...), expiry: str = Form(""), image: UploadFile = File(...)):
    """調味料を登録"""
    # ファイル名衝突防止のため、タイムスタンプと元のファイル名を組み合わせる
    filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{image.filename}"
    file_path = os.path.join("uploads", filename)
    
    # ファイルを保存
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    # データベースに登録
    conn = sqlite3.connect(DB_NAME)
    conn.execute(
        "INSERT INTO condiments (name, expiry, image_path, created_at) VALUES (?, ?, ?, ?)",
        (name, expiry, file_path, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

    return RedirectResponse("/list", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/delete/{item_id}")
async def delete_item(item_id: int, user_id: int = Depends(require_login)):
    """調味料を削除"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # 画像パスを取得し、ファイルを削除
    cur.execute("SELECT image_path FROM condiments WHERE id=?", (item_id,))
    row = cur.fetchone()
    if row:
        file_to_delete = row[0]
        if os.path.exists(file_to_delete):
            os.remove(file_to_delete)
            
    # レコードを削除
    cur.execute("DELETE FROM condiments WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    
    return RedirectResponse("/list", status_code=status.HTTP_303_SEE_OTHER)