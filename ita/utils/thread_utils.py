import uuid


def create_thread_id() -> str:
    return str(uuid.uuid4())