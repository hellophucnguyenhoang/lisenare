from app.database import get_session
from app.services.collection_service import temp_get_data


def show_result(results, n=3):
    print()
    print(f"len(result)={len(results)}")
    for i in range(n):
        print(results[i])


def test_get_data():
    session_gen = get_session()
    session = next(session_gen)
    results = temp_get_data(session=session)
    assert results is not None

    show_result(results)
