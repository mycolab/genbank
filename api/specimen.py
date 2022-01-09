import hashlib
import json


def get_id(body: dict) -> str:
    body_str = json.dumps(body)
    return hashlib.md5(body_str.encode('utf-8')).hexdigest()


def post(body: dict = None, **kwargs):
    id = get_id(body)
    resp = {
        'id': id
    }
    return resp, 200


def put(id: str = None, body: dict = None, **kwargs):
    pass


def get(id: str = None, **kwargs):
    pass


def delete(id: str = None, **kwargs):
    pass
