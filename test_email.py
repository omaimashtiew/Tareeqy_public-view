import smtplib
from email.message import EmailMessage

EMAIL_ADDRESS = 'samiabdelrazeq87@gmail.com'
EMAIL_PASSWORD = 'jtjlhsupdxgjmsfs'


msg = EmailMessage()
msg['Subject'] = 'Test Email'
msg['From'] = EMAIL_ADDRESS
msg['To'] = 'samiabdelrazeq87@gmail.com'
msg.set_content('This is a test email from Python.')

with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
    smtp.ehlo()
    smtp.starttls()
    smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    smtp.send_message(msg)

print("Email sent successfully")
