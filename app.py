import os
import logging
from dotenv import load_dotenv

# === Flask Imports ===
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

# === FastAPI Imports ===
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.wsgi import WSGIMiddleware

# === Load .env ===
load_dotenv()

# ---------------------- FLASK SETUP ---------------------- #
flask_app = Flask(__name__)
CORS(flask_app, supports_credentials=True)
flask_app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "defaultsecret")

# Logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# SocketIO
socketio = SocketIO(flask_app, cors_allowed_origins="*", async_mode="threading")

# Register Socket Events
from routes.events import register_socket_events
register_socket_events(socketio)

# Register Blueprint from results.controller
from results.controller import results_bp
flask_app.register_blueprint(results_bp, url_prefix="/api")

# HTML Homepage for Flask
@flask_app.route("/")
def flask_index():
    return "<h1>AI Recruiter Backend</h1><p>The results API is available at /api/results/&lt;candidate_id&gt;</p>"

# ---------------------- FASTAPI SETUP ---------------------- #
fastapi_app = FastAPI()

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and mount FastAPI routers
from routes.test_routes import router as test_router
from routes.hr_routes import router as hr_router

fastapi_app.include_router(test_router, prefix="/api/test")
fastapi_app.include_router(hr_router, prefix="/api/hr")

# Mount Flask inside FastAPI
fastapi_app.mount("/flask", WSGIMiddleware(flask_app))

# FastAPI Home
@fastapi_app.get("/")
async def root():
    return {"message": "Unified FastAPI + Flask-SocketIO App 🚀"}

# ---------------------- ENTRY POINT ---------------------- #
# This 'app' variable is what production servers (gunicorn/uvicorn) will run
app = fastapi_app

# For local development only
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
