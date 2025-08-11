# backend/app.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.test_routes import router as test_router
from routes.hr_routes import router as hr_router

app = FastAPI()

# 🚨 CORS: Allow frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Use "*" if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(test_router, prefix="/api/test")
app.include_router(hr_router, prefix="/api/hr")

@app.get("/")
async def root():
    return {"message": "HR Test Automation API is live 🚀"}
