from pymongo.asynchronous.database import AsyncDatabase

async def create_indexes(database: AsyncDatabase):
    """
    This function creates indexes at startup and left when one already exists"""
    await database["retraining_runs"].create_index(
        "state",
        unique=True,
        partialFilterExpression={"state":"running"},
        name="only_one_running_retraining"
    )
    await database["uploads"].create_index("label")
    await database["users"].create_index("email_address", unique=True, name="unique_email")
    await database["users"].create_index("username", unique=True, name="unique_username")
    # codes delete themselves once expired
    await database["password_codes"].create_index("expires_at", expireAfterSeconds=0, name="delete_expired_codes")
    await database["predictions"].create_index("created_at")
