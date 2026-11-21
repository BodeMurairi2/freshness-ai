from fastapi import FastAPI
from api.routers.prediction import router as prediction_router
from api.routers.retraining import router as retraining_router

def routing(app:FastAPI):
    """
    Main routing function
    """
    app.include_router(prediction_router)
    app.include_router(retraining_router)
