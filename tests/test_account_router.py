from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi_mail import MessageType
from sqlmodel import select

from app.database import Account, OTP, get_session
from app.exceptions import ErrorCode
from app.main import app
from app.services import account_service, auth_service, otp_service


def test_send_otp_by_username_success(client: TestClient):
    username = "hoangphuc"
    with patch("app.services.account_service.send_email"):
        response = client.post(
            "/accounts/send-otp", json={"username": username}
        )
        assert response.status_code == 204

    session_gen = get_session()
    session = next(session_gen)
    account = session.exec(
        select(Account).where(Account.username == username)
    ).first()
    assert account is not None
    otp_record = session.exec(
        select(OTP)
        .where(OTP.email == account.email)
        .order_by(OTP.expires_at.desc())
    ).first()
    assert otp_record is not None
    assert not otp_record.used


def test_send_otp_account_not_found(client: TestClient):
    response = client.post(
        "/accounts/send-otp", json={"username": "non_existent_user_9999"}
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == ErrorCode.ACCOUNT_NOT_FOUND.value


def test_send_otp_account_no_email(client: TestClient):
    session_gen = get_session()
    session = next(session_gen)

    account = session.exec(
        select(Account).where(Account.username == "qwerwert")
    ).first()
    if account:
        original_email = account.email
        account.email = None
        session.add(account)
        session.commit()

        response = client.post(
            "/accounts/send-otp", json={"username": "qwerwert"}
        )
        assert response.status_code == 400
        assert (
            response.json()["error_code"]
            == ErrorCode.ACCOUNT_HAS_NO_EMAIL.value
        )

        account.email = original_email
        session.add(account)
        session.commit()


def test_send_email_change_otp_success(client: TestClient):
    session_gen = get_session()
    session = next(session_gen)

    account = session.exec(
        select(Account).where(Account.username == "hoangphuc")
    ).first()
    learner = account.learner

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    new_email = "new_verified_email@example.com"
    with patch("app.services.account_service.send_email"):
        response = client.post(
            "/accounts/email/send-otp",
            json={
                "old_email": "hellophucnh@gmail.com",
                "new_email": new_email,
            },
        )
        assert response.status_code == 204

    app.dependency_overrides.clear()

    otp_record = session.exec(
        select(OTP)
        .where(OTP.email == new_email)
        .order_by(OTP.expires_at.desc())
    ).first()
    assert otp_record is not None
    assert not otp_record.used


def test_send_email_change_otp_wrong_old_email(client: TestClient):
    session_gen = get_session()
    session = next(session_gen)

    account = session.exec(
        select(Account).where(Account.username == "hoangphuc")
    ).first()
    learner = account.learner

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    response = client.post(
        "/accounts/email/send-otp",
        json={
            "old_email": "wrong_old_email@example.com",
            "new_email": "brand_new@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == ErrorCode.INCORRECT_EMAIL.value

    app.dependency_overrides.clear()


def test_reset_password_success(client: TestClient):
    session_gen = get_session()
    session = next(session_gen)

    account = session.exec(
        select(Account).where(Account.username == "hoangphuc")
    ).first()
    assert account is not None
    assert account.email is not None

    code = otp_service.create_otp(session, account.email)

    response = client.post(
        "/accounts/reset-password",
        json={
            "username": "hoangphuc",
            "new_password": "NewSecretPassword123!",
            "otp": code,
        },
    )
    assert response.status_code == 204

    session.refresh(account)
    from app import security

    assert security.verify_password(
        "NewSecretPassword123!", account.hashed_password
    )


def test_reset_password_invalid_otp(client: TestClient):
    session_gen = get_session()
    session = next(session_gen)

    account = session.exec(
        select(Account).where(Account.username == "hoangphuc")
    ).first()
    otp_service.create_otp(session, account.email)

    response = client.post(
        "/accounts/reset-password",
        json={
            "username": "hoangphuc",
            "new_password": "AnotherPassword123!",
            "otp": "000000",
        },
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == ErrorCode.INVALID_OTP.value


def test_reset_password_account_not_found(client: TestClient):
    response = client.post(
        "/accounts/reset-password",
        json={
            "username": "non_existent_user_12345",
            "new_password": "AnotherPassword123!",
            "otp": "123456",
        },
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == ErrorCode.ACCOUNT_NOT_FOUND.value


def test_change_email_success(client: TestClient):
    session_gen = get_session()
    session = next(session_gen)

    account = session.exec(
        select(Account).where(Account.username == "hoangphuc")
    ).first()
    learner = account.learner

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    new_email = "updated_hoangphuc@example.com"
    code = otp_service.create_otp(session, new_email)

    response = client.patch(
        "/accounts/email",
        json={
            "old_email": "hellophucnh@gmail.com",
            "new_email": new_email,
            "otp": code,
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 204

    session.refresh(account)
    assert account.email == new_email

    # Restore email for future tests
    account.email = "hellophucnh@gmail.com"
    session.add(account)
    session.commit()


def test_change_email_wrong_old_email(client: TestClient):
    session_gen = get_session()
    session = next(session_gen)

    account = session.exec(
        select(Account).where(Account.username == "hoangphuc")
    ).first()
    learner = account.learner

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    new_email = "some_email@example.com"
    code = otp_service.create_otp(session, new_email)

    response = client.patch(
        "/accounts/email",
        json={
            "old_email": "incorrect_email@example.com",
            "new_email": new_email,
            "otp": code,
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["error_code"] == ErrorCode.INCORRECT_EMAIL.value


def test_change_email_taken(client: TestClient):
    session_gen = get_session()
    session = next(session_gen)

    account1 = session.exec(
        select(Account).where(Account.username == "hoangphuc")
    ).first()
    learner = account1.learner

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    other_account = session.exec(
        select(Account).where(Account.username == "qwerwert")
    ).first()
    if other_account:
        other_account.email = "other_taken_email@example.com"
        session.add(other_account)
        session.commit()

        code = otp_service.create_otp(session, "other_taken_email@example.com")
        response = client.patch(
            "/accounts/email",
            json={
                "old_email": "hellophucnh@gmail.com",
                "new_email": "other_taken_email@example.com",
                "otp": code,
            },
        )
        assert response.status_code == 400
        assert (
            response.json()["error_code"]
            == ErrorCode.USERNAME_OR_EMAIL_TAKEN.value
        )

    app.dependency_overrides.clear()


def test_change_email_invalid_otp(client: TestClient):
    session_gen = get_session()
    session = next(session_gen)

    account = session.exec(
        select(Account).where(Account.username == "hoangphuc")
    ).first()
    learner = account.learner

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    new_email = "invalid_otp_test@example.com"
    otp_service.create_otp(session, new_email)

    response = client.patch(
        "/accounts/email",
        json={
            "old_email": "hellophucnh@gmail.com",
            "new_email": new_email,
            "otp": "999999",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["error_code"] == ErrorCode.INVALID_OTP.value


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_send_email_async_direct():
    with patch.object(
        account_service.fast_mail, "send_message", new_callable=AsyncMock
    ) as mock_send:
        await account_service.send_email(
            to_email="test@example.com",
            subject="Test Subject",
            body="Hello!<br><br>Your email verification code is: <strong>123456</strong>",
        )
        mock_send.assert_awaited_once()
        message = mock_send.call_args[0][0]
        assert message.subject == "Test Subject"
        assert message.subtype == MessageType.html
        assert "<strong>123456</strong>" in message.body
