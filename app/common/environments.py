import os

from pymongo import MongoClient


def __next_env_id(collection):
    pipeline = [
        {"$sort": {"ENV_ID": -1}},
        {"$limit": 1}
    ]

    items = list(collection.aggregate(pipeline))

    if len(items) > 0:
        item = items.pop(0)
        return item["ENV_ID"] + 1
    else:
        return 1


def get_environment_id(name):
    env = collection.find_one({"name": name})
    if not env:
        env_id = __next_env_id(collection)
        inserted = collection.insert_one({
            "_id": env_id,
            "name": name,
            "ENV_ID": env_id
        })
        if inserted.inserted_id == env_id:
            return inserted.inserted_id
    else:
        return env["ENV_ID"]


def connect(uri):
    client = MongoClient(uri)
    db = client["spinless"]
    return db["environments"]


MONGODB_CONNECTION_STRING = os.environ['MONGODB_CONNECTION_STRING']
collection = connect(MONGODB_CONNECTION_STRING)

