import sqlite3
import shutil
import os
from datetime import date, timedelta
import httpx
from fastapi import FastAPI, Request, File, UploadFile, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from pathlib import Path
from dotenv import load_dotenv  # ← 追加

# --- .envから環境変数読み込み ---
load_dotenv()

# --- 設定 ---
TMP_DIR = Path(os.environ.get("TEMP_DIR", "/tmp/condiments_app"))
DB_NAME = TMP_DIR / "condiments.db"
UPLOAD_DIR = TMP_DIR / "uploads"
EXPIRY_THRESHOLD_DAYS = 7  # 期限切れが近いとみなす日数

# --- データベース初期化 ---
def init_db():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    conn = sqlite3.connect(str(DB_NAME))
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS condiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            expiry TEXT,
            image_path TEXT
        )
    """)
    conn.commit()
    conn.close()

# 初期化
init_db()

# --- FastAPI設定 ---
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# 静的ファイルマウント
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# --- レシピAPI設定 ---
RAKUTEN_APP_ID = os.environ.get("RAKUTEN_APP_ID")  # .envに設定
RAKUTEN_RECIPE_URL = "https://app.rakuten.co.jp/services/api/Recipe/RecipeSearch/20170426"

# --- レシピ取得関数 ---
async def fetch_recipes_from_api(ingredients_query: str):
    """楽天レシピAPIからレシピを取得"""
    if not RAKUTEN_APP_ID:
        print("⚠️ RAKUTEN_APP_ID が設定されていません。")
        return []

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                RAKUTEN_RECIPE_URL,
                params={
                    "applicationId": RAKUTEN_APP_ID,
                    "keyword": ingredients_query,
                    "format": "json"
                },
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()

            # 結果の整形（API仕様に応じて修正）
            recipes = []
            if "result" in data:
                for recipe in data["result"]:
                    recipes.append({
                        "title": recipe.get("recipeTitle", "タイトルなし"),
                        "url": recipe.get("recipeUrl", "#")
                    })
            return recipes

        except Exception as e:
            print(f"レシピAPI呼び出し中にエラー: {e}")
            return []

# --- エンドポイント ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def register_condiment(
    name: str = Form(...),
    expiry: str = Form(None),
    image: UploadFile = File(None)
):
    image_path = None
    if image and image.filename:
        ext = Path(image.filename).suffix
        unique_filename = f"{Path(name).stem}_{date.today().strftime('%Y%m%d')}_{os.urandom(8).hex()}{ext}"
        file_path = UPLOAD_DIR / unique_filename

        try:
            with file_path.open("wb") as buffer:
                image.file.seek(0)
                shutil.copyfileobj(image.file, buffer)
            image_path = f"/uploads/{unique_filename}"
        except Exception as e:
            print(f"ファイル保存エラー: {e}")
            raise HTTPException(status_code=500, detail="ファイルアップロードに失敗しました。")

    conn = sqlite3.connect(str(DB_NAME))
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO condiments (name, expiry, image_path) VALUES (?, ?, ?)",
        (name, expiry if expiry else None, image_path)
    )
    conn.commit()
    conn.close()

    return RedirectResponse(url="/list", status_code=303)

@app.get("/list", response_class=HTMLResponse)
async def list_condiments(request: Request):
    conn = sqlite3.connect(str(DB_NAME))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, expiry, image_path
        FROM condiments
        ORDER BY CASE WHEN expiry IS NULL THEN 1 ELSE 0 END, expiry ASC
    """)
    condiments = [dict(row) for row in cur.fetchall()]
    conn.close()

    today = date.today()
    for item in condiments:
        item["is_expired"] = False
        item["near_expiry"] = False
        if item["expiry"]:
            try:
                expiry_date = date.fromisoformat(item["expiry"])
                days_left = (expiry_date - today).days
                if days_left <= 0:
                    item["is_expired"] = True
                elif days_left <= EXPIRY_THRESHOLD_DAYS:
                    item["near_expiry"] = True
            except ValueError:
                pass

    return templates.TemplateResponse("list.html", {"request": request, "condiments": condiments})

@app.post("/delete/{item_id}")
async def delete_condiment(item_id: int):
    conn = sqlite3.connect(str(DB_NAME))
    cur = conn.cursor()
    cur.execute("SELECT image_path FROM condiments WHERE id = ?", (item_id,))
    row = cur.fetchone()
    if row and row[0]:
        image_filename = Path(row[0]).name
        file_to_delete = UPLOAD_DIR / image_filename
        if file_to_delete.exists():
            os.remove(file_to_delete)
    cur.execute("DELETE FROM condiments WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/list", status_code=303)

@app.get("/recipes", response_class=HTMLResponse)
async def get_near_expiry_recipes(request: Request):
    conn = sqlite3.connect(str(DB_NAME))
    cur = conn.cursor()
    expiry_limit = (date.today() + timedelta(days=EXPIRY_THRESHOLD_DAYS)).strftime("%Y-%m-%d")
    cur.execute("""
        SELECT name FROM condiments 
        WHERE expiry IS NOT NULL AND expiry != ''
        AND expiry <= ?
        ORDER BY expiry ASC
    """, (expiry_limit,))
    near_expiry_items = [row[0] for row in cur.fetchall()]
    conn.close()

    if not near_expiry_items:
        return templates.TemplateResponse("recipe_search.html", {
            "request": request,
            "recipes": [],
            "query": f"期限が{EXPIRY_THRESHOLD_DAYS}日以内に切れる調味料はありません。"
        })

    query = " ".join(near_expiry_items)
    recipes = await fetch_recipes_from_api(query)
    return templates.TemplateResponse("recipe_search.html", {
        "request": request,
        "recipes": recipes,
        "query": query
    })
