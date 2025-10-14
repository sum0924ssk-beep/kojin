from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3, shutil, os, datetime

app = FastAPI()

# 静的ファイルとテンプレート設定
os.makedirs("uploads", exist_ok=True)
templates = Jinja2Templates(directory="templates")
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

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name, expiry, image_path, created_at FROM condiments ORDER BY id DESC")
    items = cur.fetchall()
    conn.close()
    return templates.TemplateResponse("index.html", {"request": request, "items": items})

@app.post("/upload")
async def upload(name: str = Form(...), expiry: str = Form(...), image: UploadFile = File(...)):
    filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{image.filename}"
    file_path = f"uploads/{filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    conn = sqlite3.connect(DB_NAME)
    conn.execute(
        "INSERT INTO condiments (name, expiry, image_path, created_at) VALUES (?, ?, ?, ?)",
        (name, expiry, file_path, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

    return RedirectResponse("/", status_code=303)

@app.post("/delete/{item_id}")
async def delete_item(item_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT image_path FROM condiments WHERE id=?", (item_id,))
    row = cur.fetchone()
    if row and os.path.exists(row[0]):
        os.remove(row[0])
    cur.execute("DELETE FROM condiments WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=303)
