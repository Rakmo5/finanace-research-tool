from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.upload import router

import os

app = FastAPI(title="AI Financial Research Tool")

app.include_router(router)

app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")


# ✅ Get absolute path of this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "index.html")


@app.get("/", response_class=HTMLResponse)
def home():

    try:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        print("HTML LENGTH:", len(content))  # DEBUG
        return content

    except Exception as e:

        print("ERROR:", e)
        return "<h1>ERROR LOADING HTML</h1>"

