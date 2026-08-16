import sys
from pathlib import Path

# Ensure root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from backend.main import app as main_app

# Create Vercel FastAPI app
app = FastAPI(title="Smart Expense Intelligence")

# Mount both with /api and without /api to guarantee matching on Vercel
for route in main_app.routes:
    app.routes.append(route)
    if hasattr(route, "path") and route.path.startswith("/api/"):
        # Duplicate route without /api prefix
        import copy
        alt_route = copy.copy(route)
        alt_route.path = route.path[4:]  # remove '/api'
        app.routes.append(alt_route)

handler = app
