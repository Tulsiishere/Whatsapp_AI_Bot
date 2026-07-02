import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()


def send_whatsapp_message(to: str, body: str) -> str:
    """
    Send an outbound WhatsApp message via Twilio REST API.

    Args:
        to: Recipient in E.164 format, e.g. '+919876543210'
           (whatsapp: prefix added automatically)
        body: Message text to send

    Returns:
        Twilio message SID
    """
    # Read credentials fresh each call — avoids module-load crash if .env missing
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM")  # e.g. whatsapp:+14155238886

    client = Client(account_sid, auth_token)

    # Normalise: strip any existing whatsapp: prefix so we never double-add it
    to_normalised = to if to.startswith("whatsapp:") else f"whatsapp:{to}"

    message = client.messages.create(
        from_=from_number,
        to=to_normalised,
        body=body,
    )
    return message.sid