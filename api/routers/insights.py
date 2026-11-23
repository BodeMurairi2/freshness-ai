import asyncio
from typing import Annotated

from fastapi import Depends
from fastapi.routing import APIRouter
from pymongo.asynchronous.database import AsyncDatabase

from api.database.connection import get_database
from api.schemas.insights import Insights
from api.services.insights import dataset_insights, model_insights, usage_insights

router = APIRouter(
    prefix="/insights",
    tags=["Insights"]
)


@router.get("/", response_model=Insights)
async def insights(database: Annotated[AsyncDatabase, Depends(get_database)]):
    """
    This function returns the dataset, model and usage numbers for the insights page
    """
    dataset, model, usage = await asyncio.gather(
        dataset_insights(database),
        model_insights(database),
        usage_insights(database),
    )
    return {"dataset": dataset, "model": model, "usage": usage}
