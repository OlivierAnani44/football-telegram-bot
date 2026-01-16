from twilio.rest import Client

ACCOUNT_SID = "TWILIO_SID"
AUTH_TOKEN = "TWILIO_TOKEN"
FROM = "whatsapp:+14155238886"
TO = "whatsapp:+228XXXXXXXX"

client = Client(ACCOUNT_SID, AUTH_TOKEN)

def publish_whatsapp(text):
    client.messages.create(
        body=text,
        from_=FROM,
        to=TO
    )
