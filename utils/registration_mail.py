import threading
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags


def send_verification_email(user, generated_password):

    # Build verification URL
    subject = 'Email Verification'
    hours = getattr(settings, 'HOURS')
    minutes = getattr(settings, 'MINUTES')
    seconds = getattr(settings, 'SECONDS')

    if generated_password is None:
        generated_password = user.generate_password()

    # HTML email template
    html_message = f"""
    <html>
        <body>
            <h2>Welcome {user.first_name}!</h2>
            <p>Your account has been registered please use the password below and activate your account by changing it:</p>
            <h4>{generated_password}</h4>
            <p>This password will expire in {hours} hours {minutes} minutes and {seconds} seconds.</p>
            <p>If you didn't create this account, please ignore this email.</p>
        </body>
    </html>
    """

    plain_message = strip_tags(html_message)

    mail_thread = threading.Thread(
        target=send_email_wrapper,
        args=(subject, plain_message, [user.email], html_message)
    )
    mail_thread.start()


def send_email_wrapper(subject, message, recipient_list, html_message):
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_list,
        html_message=html_message,
        fail_silently=False,
    )
