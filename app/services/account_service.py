from datetime import datetime, timezone

from fastapi import BackgroundTasks, status
from fastapi_mail import MessageSchema, MessageType
from sqlmodel import Session, or_, select

from app import security
from app.config import fast_mail, logger, settings
from app.database import Account, Learner
from app.exceptions import ErrorCode, RequestException
from app.schemas import (
    EmailChangeOTPRequest,
    EmailChangeRequest,
    LearnerAccountCreate,
    PasswordResetRequest,
)
from app.services import auth_service, otp_service


def get_account_by_username(session: Session, username: str) -> Account:
    logger.info(f"Fetching account details for username: {username}")
    stmt = select(Account).where(Account.username == username)
    return session.exec(stmt).first()


def create_learner_account(
    session: Session, learner_account_create: LearnerAccountCreate
) -> Account:
    logger.info(
        f"Initiating account creation for username: {learner_account_create.username}"
    )
    conditions = [Account.username == learner_account_create.username]

    if learner_account_create.email is not None:
        conditions.append(Account.email == learner_account_create.email)

    existing_account = session.scalars(
        select(Account).where(or_(*conditions))
    ).first()

    if existing_account:
        logger.warning(
            f"Account creation conflict. Username/Email already exists. "
            f"Input Username: {learner_account_create.username}, Email: {learner_account_create.email}"
        )
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message="Username or email registration conflicts.",
            error_code=ErrorCode.USERNAME_OR_EMAIL_TAKEN,
        )

    learner = Learner(name=learner_account_create.name)
    hashed_password = security.get_password_hash(
        learner_account_create.password
    )
    account = Account(
        username=learner_account_create.username,
        hashed_password=hashed_password,
        email=learner_account_create.email,
        learner=learner,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    logger.info(
        f"Successfully created account for username: {account.username} (ID: {account.id})"
    )
    return account


def change_learner_account_password(
    session: Session, learner_id: int, old_password: str, new_password: str
) -> Account:
    logger.info(f"Attempting password change for learner_id: {learner_id}")
    account = session.exec(
        select(Account).where(Account.learner_id == learner_id)
    ).first()
    if not account:
        logger.warning(
            f"Password change failed: Account for learner_id={learner_id} not found"
        )
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Account for {learner_id=} not found",
        )
    if not security.verify_password(old_password, account.hashed_password):
        logger.warning(
            f"Password change failed: Incorrect old password for learner_id={learner_id}"
        )
        raise RequestException(
            status_code=status.HTTP_403_FORBIDDEN,
            debug_message="Wrong old password",
            error_code=ErrorCode.INCORRECT_PASSWORD,
        )
    hashed_new_password = security.get_password_hash(new_password)
    account.hashed_password = hashed_new_password
    session.add(account)
    session.commit()
    session.refresh(account)
    logger.info(f"Successfully updated password for learner_id: {learner_id}")
    return account


async def send_email(to_email: str, subject: str, body: str):
    logger.info(
        f"Preparing to send email to {to_email} with subject: '{subject}'"
    )
    message = MessageSchema(
        subject=subject,
        recipients=[to_email],
        body=body,
        subtype=MessageType.html,
    )
    try:
        await fast_mail.send_message(message)
        logger.info("Email successfully sent")
    except Exception as e:
        logger.error(f"Failed to send email. Error: {str(e)}")
        raise e


def send_email_background(
    background_tasks: BackgroundTasks, to_email: str, subject: str, body: str
):
    logger.info(f"Queueing email delivery to {to_email} as a background task")
    background_tasks.add_task(send_email, to_email, subject, body)


def send_otp_by_username(
    session: Session, background_tasks: BackgroundTasks, username: str
):
    logger.info(f"Initiating OTP sending for username: '{username}'")
    account = get_account_by_username(session, username)
    if not account:
        logger.warning(f"OTP sending failed: Username '{username}' not found")
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Account not found for username={username}",
            error_code=ErrorCode.ACCOUNT_NOT_FOUND,
        )

    if not account.email:
        logger.warning(
            f"OTP sending failed: Account '{username}' has no linked email address"
        )
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=f"Account username={username} does not have an email",
            error_code=ErrorCode.ACCOUNT_HAS_NO_EMAIL,
        )

    code = otp_service.create_otp(session, account.email)
    subject = "Your OTP Code from Lisenare"
    body = (
        f"<div style=\"font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 16px; color: #333333; line-height: 1.6; max-width: 500px; margin: 0 auto; padding: 24px; border: 1px solid #e0e0e0; border-radius: 8px; background-color: #ffffff;\">"
        f'  <h2 style="color: #00685f; margin-top: 0; font-size: 22px; font-weight: 700;">Security Verification</h2>'
        f"  Hello!<br><br>"
        f"  Your verification code is:<br>"
        f'  <div style="font-size: min(7vw, 28px); font-weight: bold; letter-spacing: 4px; color: #00685f; background-color: #f0f7f6; padding: 14px 8px; text-align: center; border-radius: 6px; margin: 16px 0; border: 1px dashed #00685f;">{code}</div>'
        f"  This code expires in <strong>{settings.otp_expire_minutes} minutes</strong>.<br><br>"
        f"  Best regards,<br>"
        f"  <strong>Lisenare Team</strong>"
        f"</div>"
    )
    send_email_background(background_tasks, account.email, subject, body)


def send_email_change_otp(
    session: Session,
    background_tasks: BackgroundTasks,
    learner_id: int,
    request: EmailChangeOTPRequest,
):
    logger.info(
        f"Initiating email change OTP for learner_id: {learner_id} to new email: {request.new_email}"
    )
    account = session.exec(
        select(Account).where(Account.learner_id == learner_id)
    ).first()
    if not account:
        logger.warning(
            f"Email change OTP failed: Account for learner_id={learner_id} not found"
        )
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Account for learner_id={learner_id} not found",
            error_code=ErrorCode.ACCOUNT_NOT_FOUND,
        )

    if account.email:
        if not request.old_email or request.old_email != account.email:
            logger.warning(
                f"Email change OTP failed: Incorrect old email provided for learner_id={learner_id}"
            )
            raise RequestException(
                status_code=status.HTTP_400_BAD_REQUEST,
                debug_message="Incorrect old email.",
                error_code=ErrorCode.INCORRECT_EMAIL,
            )

    existing_account = session.scalars(
        select(Account).where(
            Account.email == request.new_email,
            Account.learner_id != learner_id,
        )
    ).first()
    if existing_account:
        logger.warning(
            f"Email change OTP failed: Email '{request.new_email}' is already taken by another account"
        )
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=f"Email {request.new_email} is already in use.",
            error_code=ErrorCode.USERNAME_OR_EMAIL_TAKEN,
        )

    code = otp_service.create_otp(session, request.new_email)
    subject = "Verify your new email for Lisenare"
    body = (
        f"<div style=\"font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 16px; color: #333333; line-height: 1.6; max-width: 500px; margin: 0 auto; padding: 24px; border: 1px solid #e0e0e0; border-radius: 8px; background-color: #ffffff;\">"
        f'  <h2 style="color: #00685f; margin-top: 0; font-size: 22px; font-weight: 700;">Verify Your Email</h2>'
        f"  Hello!<br><br>"
        f"  Your email verification code is:<br>"
        f'  <div style="font-size: min(7vw, 28px); font-weight: bold; letter-spacing: 4px; color: #00685f; background-color: #f0f7f6; padding: 14px 8px; text-align: center; border-radius: 6px; margin: 16px 0; border: 1px dashed #00685f;">{code}</div>'
        f"  This code expires in <strong>{settings.otp_expire_minutes} minutes</strong>.<br><br>"
        f"  Best regards,<br>"
        f"  <strong>Lisenare Team</strong>"
        f"</div>"
    )
    send_email_background(background_tasks, request.new_email, subject, body)


def verify_and_consume_otp(session: Session, email: str, otp: str):
    otp_entry = auth_service.get_most_recent_unused_otp(session, email)
    if not otp_entry:
        logger.warning(
            f"OTP verification failed: No valid OTP record found for email: {email}"
        )
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=(f"No valid OTP found for email={email}"),
            error_code=ErrorCode.OTP_NOT_FOUND,
        )

    expires_at = (
        otp_entry.expires_at
        if otp_entry.expires_at.tzinfo
        else otp_entry.expires_at.replace(tzinfo=timezone.utc)
    )
    if expires_at < datetime.now(timezone.utc):
        logger.warning(
            f"OTP verification failed: OTP expired for email: {email}"
        )
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=(f"Expired OTP for email={email}"),
            error_code=ErrorCode.OTP_EXPIRED,
        )

    if not security.verify_otp(otp, otp_entry.hashed_code):
        logger.warning(
            f"OTP verification failed: Invalid OTP submitted for email: {email}"
        )
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=(f"Invalid OTP for email={email}"),
            error_code=ErrorCode.INVALID_OTP,
        )

    otp_entry.used = True
    session.add(otp_entry)
    return otp_entry


def reset_account_password(session: Session, request: PasswordResetRequest):
    logger.info(
        f"Attempting password reset via OTP for username: {request.username}"
    )
    account = get_account_by_username(session, request.username)
    if not account:
        logger.warning(
            f"Password reset failed: Username '{request.username}' not found"
        )
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=(
                f"Account not found for username={request.username}"
            ),
            error_code=ErrorCode.ACCOUNT_NOT_FOUND,
        )

    if not account.email:
        logger.warning(
            f"Password reset failed: Account '{request.username}' has no linked email address"
        )
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=(
                f"Account username={request.username} does not have an email"
            ),
            error_code=ErrorCode.ACCOUNT_HAS_NO_EMAIL,
        )

    verify_and_consume_otp(session, account.email, request.otp)

    account.hashed_password = security.get_password_hash(request.new_password)
    session.add(account)
    session.commit()
    logger.info(
        f"Successfully reset password for username: {request.username}"
    )


def change_learner_account_email(
    session: Session, learner_id: int, request: EmailChangeRequest
) -> Account:
    logger.info(
        f"Attempting email change via OTP for learner_id: {learner_id} to new email: {request.new_email}"
    )
    account = session.exec(
        select(Account).where(Account.learner_id == learner_id)
    ).first()
    if not account:
        logger.warning(
            f"Email change failed: Account for learner_id={learner_id} not found"
        )
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Account for learner_id={learner_id} not found",
            error_code=ErrorCode.ACCOUNT_NOT_FOUND,
        )

    if account.email:
        if not request.old_email or request.old_email != account.email:
            logger.warning(
                f"Email change failed: Incorrect old email provided for learner_id={learner_id}"
            )
            raise RequestException(
                status_code=status.HTTP_400_BAD_REQUEST,
                debug_message="Incorrect old email.",
                error_code=ErrorCode.INCORRECT_EMAIL,
            )

    existing_account = session.scalars(
        select(Account).where(
            Account.email == request.new_email,
            Account.learner_id != learner_id,
        )
    ).first()
    if existing_account:
        logger.warning(
            f"Email change failed: Email '{request.new_email}' is already taken by another account"
        )
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=f"Email {request.new_email} is already in use.",
            error_code=ErrorCode.USERNAME_OR_EMAIL_TAKEN,
        )

    verify_and_consume_otp(session, request.new_email, request.otp)

    account.email = request.new_email
    session.add(account)
    session.commit()
    session.refresh(account)
    logger.info(
        f"Successfully changed email for learner_id: {learner_id} to {request.new_email}"
    )
    return account
