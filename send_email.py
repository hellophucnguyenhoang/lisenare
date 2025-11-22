import smtplib
from email.message import EmailMessage
from app.config import settings

def send_email(to_email: str, subject: str, body: str):
    EMAIL_ADDRESS = settings.google_app_email_address
    EMAIL_PASSWORD = settings.google_app_password

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg.set_content(body)

    # Connect to Gmail SMTP server
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

    print(f"Email sent to {to_email}")

if __name__ == "__main__":
    otp = "123456"
    send_email(
        "nguyenphuc1234sonhoapy@gmail.com",
        "Your OTP Code",
        f"Hello!\n\nYour OTP code is: {otp}\nIt will expire in 5 minutes."
    )