from uuid import uuid4

def generate_test_link(question_set_id: str) -> str:
    return f"http://localhost:8000/test/{question_set_id}"
