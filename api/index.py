import sys
from pathlib import Path

# Ensure root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from backend.main import app as main_app

# Create root app that mounts backend with and without /api prefix
app = FastAPI()

# Mount all routes directly
for route in main_app.routes:
    app.routes.append(route)

# Add fallback prefix routes for Vercel path rewriting
@app.get("/")
def home():
    return {"status": "online", "service": "Smart Expense Intelligence System"}

handler = app
