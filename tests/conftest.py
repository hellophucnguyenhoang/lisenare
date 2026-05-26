import pytest
from fastapi.testclient import TestClient

from app.main import app

"""
[ START ] User runs `pytest` in the terminal
1. Pytest looks inside the test function and sees `client` in the parentheses.
2. Pytest pauses the test and jumps over to run the `client()` fixture first.
3. Inside the fixture, it opens the `TestClient(app)`.
4. The fixture hits the `yield client` line. 
   It pauses right there and hands the client over to the test.
5. Your test function runs from top to bottom:
   • It overrides the login dependency.
   • It sends the `GET` request to the database.
   • It asserts that the status code is 200.
6. Your test function finishes successfully.
7. Pytest jumps back to the fixture and runs the code *after* the `yield` line.
   (It closes the `TestClient` safely).
[ END ] Pytest prints a green checkmark in the terminal.
"""


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client
