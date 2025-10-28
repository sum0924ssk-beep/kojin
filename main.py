import sqlite3
import shutil
import os
from datetime import date, timedelta
import httpx # API呼び出し用
from fastapi import FastAPI, Request, File, UploadFile, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from pathlib import Path

# --- 設定 ---
DB_NAME = "condiments.db"
# 画像アップロード先のディレクトリ (uploadsフォルダを作成しておく)
UPLOAD_DIR = Path("uploads")
# 期限切れが近いと見なす日数
EXPIRY_THRESHOLD_DAYS = 7 

# FastAPIとテンプレート設定
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# 静的ファイルの提供 (CSS, JS, 画像など)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# --- データベース初期化 ---
def init_db():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS condiments (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            expiry TEXT,
            image_path TEXT
        )
    """)
    conn.commit()
    conn.close()

# アプリ起動時にDB初期化
init_db()


# --- レシピAPI設定 (外部APIを利用する場合はここに設定) ---

# ⚠ 注意: 楽天APIのCategoryRankingはキーワード検索には適しません。
# 実際には、キーワード検索が可能な別のレシピAPI、またはChatGPT APIなどを利用してください。
# ここでは、API呼び出しの構造を示すための例として利用します。
RAKUTEN_APP_ID = "YOUR_RAKUTEN_APP_ID" # 👈 自分のIDに置き換える
RAKUTEN_RECIPE_URL = "https://app.rakuten.co.jp/services/api/Recipe/CategoryRanking/20170426" 

# --- API呼び出し関数 ---
async def fetch_recipes_from_api(ingredients_query: str):
    """
    期限が近い調味料名 (ingredients_query) を使ってレシピAPIを呼び出す
    """
    # 楽天APIはCategoryRankingのため、キーワード検索が難しい。
    # 実際は、材料検索が可能なAPIを使用するか、OpenAI APIでレシピを生成する
    
    # 💡 実際にはここにAPI呼び出しロジックを実装する
    # async with httpx.AsyncClient() as client:
    #     try:
    #         response = await client.get(
    #             RAKUTEN_RECIPE_URL,
    #             params={
    #                 "applicationId": RAKUTEN_APP_ID,
    #                 "keyword": ingredients_query,
    #                 "format": "json"
    #             },
    #             timeout=10.0
    #         )
    #         # レスポンス解析ロジック...
    #         # return parsed_recipes 
    #     except Exception as e:
    #         print(f"レシピAPI呼び出しエラー: {e}")
    #         return []


    # 🚨 ダミーデータ: 検索クエリに基づいた仮のレシピを返す
    # 実際のAPI実装が完了するまではこのダミーデータを使用してください
    return [
        {"title": f"【活用レシピ1】{ingredients_query}", "url": "https://cookpad.com/"},
        {"title": f"【活用レシピ2】{ingredients_query}で時短", "url": "https://www.kurashiru.com/"},
        {"title": f"【活用レシピ3】基本の{ingredients_query}料理", "url": "https://delishkitchen.tv/"},
    ]


# --- エンドポイント ---

# GET: 登録フォーム表示
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# POST: 調味料の登録処理
@app.post("/register")
async def register_condiment(
    name: str = Form(...),
    expiry: str = Form(None),
    image: UploadFile = File(None)
):
    image_path = None
    if image and image.filename:
        # ファイルの拡張子を取得
        ext = Path(image.filename).suffix
        # ユニークなファイル名を生成
        unique_filename = f"{Path(name).stem}_{date.today().strftime('%Y%m%d')}_{os.urandom(8).hex()}{ext}"
        file_path = UPLOAD_DIR / unique_filename
        
        # ファイルを保存
        try:
            with file_path.open("wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
            image_path = f"/uploads/{unique_filename}"
        except Exception as e:
            print(f"ファイル保存エラー: {e}")
            raise HTTPException(status_code=500, detail="ファイルのアップロードに失敗しました。")

    # DBに保存
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO condiments (name, expiry, image_path) VALUES (?, ?, ?)",
        (name, expiry if expiry else None, image_path)
    )
    conn.commit()
    conn.close()

    return RedirectResponse(url="/list", status_code=303)


# GET: 調味料一覧表示
@app.get("/list", response_class=HTMLResponse)
async def list_condiments(request: Request):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # 全ての調味料を期限が近い順に取得
    cur.execute("""
        SELECT id, name, expiry, image_path 
        FROM condiments 
        ORDER BY CASE WHEN expiry IS NULL THEN 1 ELSE 0 END, expiry ASC
    """)
    condiments = [dict(row) for row in cur.fetchall()]
    conn.close()
    
    # 期限切れチェック
    today = date.today()
    for item in condiments:
        item['is_expired'] = False
        item['near_expiry'] = False
        if item['expiry']:
            try:
                expiry_date = date.fromisoformat(item['expiry'])
                days_left = (expiry_date - today).days
                if days_left <= 0:
                    item['is_expired'] = True
                elif days_left <= EXPIRY_THRESHOLD_DAYS:
                    item['near_expiry'] = True
            except ValueError:
                # 日付形式が不正な場合
                pass

    return templates.TemplateResponse("list.html", {"request": request, "condiments": condiments})


# POST: 調味料の削除
@app.post("/delete/{item_id}")
async def delete_condiment(item_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # 削除対象の画像パスを取得
    cur.execute("SELECT image_path FROM condiments WHERE id = ?", (item_id,))
    row = cur.fetchone()
    if row and row[0]:
        image_path = row[0].replace("/uploads/", "")
        file_to_delete = UPLOAD_DIR / image_path
        if file_to_delete.exists():
            os.remove(file_to_delete)
            
    # DBから削除
    cur.execute("DELETE FROM condiments WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/list", status_code=303)


# -----------------------------------------------------------
# GET: 期限間近の調味料を使ったレシピ検索ページ
# -----------------------------------------------------------
@app.get("/recipes", response_class=HTMLResponse)
async def get_near_expiry_recipes(request: Request):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # 期限が今日から設定日数以内のアイテムを抽出
    expiry_limit = (date.today() + timedelta(days=EXPIRY_THRESHOLD_DAYS)).strftime("%Y-%m-%d")
    
    cur.execute("""
        SELECT name FROM condiments 
        WHERE expiry IS NOT NULL AND expiry != ''
        AND expiry <= ? 
        ORDER BY expiry ASC
    """, (expiry_limit,))
    
    # 取得した調味料名をリスト化
    near_expiry_items = [row[0] for row in cur.fetchall()]
    conn.close()

    # 期限が近い調味料がない場合の処理
    if not near_expiry_items:
        return templates.TemplateResponse("recipe_search.html", {
            "request": request,
            "recipes": [],
            "query": f"期限が{EXPIRY_THRESHOLD_DAYS}日以内に切れる調味料はありません。",
        })

    # 調味料名をクエリとして結合 (例: "しょうゆ みりん")
    query = " ".join(near_expiry_items) 
    
    # APIを呼び出す
    recipes = await fetch_recipes_from_api(query) 

    return templates.TemplateResponse("recipe_search.html", {
        "request": request,
        "recipes": recipes, 
        "query": query,
    })