from fastapi import FastAPI
from api.routers.prediction import router as prediction_router

def routing(app:FastAPI):
    """
    Main routing function
    """
    app.include_router(prediction_router)
