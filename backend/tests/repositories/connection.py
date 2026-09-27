import os

from pymongo import MongoClient

_CACHE = {}


def get_database():
    if 'client' not in _CACHE:
        uri = (f"mongodb://{os.environ['MONGO_LOCAL_USERNAME']}:"
               f"{os.environ['MONGO_LOCAL_PASSWORD']}@"
               f"{os.environ['MONGO_LOCAL_HOST']}:"
               f"{os.environ['MONGO_LOCAL_PORT']}/?authSource=admin")
        _CACHE['client'] = MongoClient(uri)
    return _CACHE['client'][os.environ['MONGO_LOCAL_DBNAME']]


def delete_all(collection_name):
    get_database()[collection_name].delete_many({})
