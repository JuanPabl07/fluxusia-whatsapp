# ia_whatsapp_assistant/app/gateway/whatsapp_handler.py

import requests
import json
from config.settings import WHATSAPP_API_TOKEN, PHONE_NUMBER_ID

# In a real scenario, this URL would be the Meta Graph API endpoint
WHATSAPP_API_URL = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"

# For MVP, we'll simulate sending messages by printing to console or returning the payload
SIMULATE_WHATSAPP_MESSAGES = True

def send_whatsapp_message(to_phone_number: str, message_text: str):
    """Simulates or sends a message to WhatsApp."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone_number,
        "type": "text",
        "text": {"body": message_text}
    }

    if SIMULATE_WHATSAPP_MESSAGES:
        print(f"SIMULATING WHATSAPP SEND to {to_phone_number}: {message_text}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        return {"status": "simulated_success", "payload": payload}
    else:
        headers = {
            "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
            "Content-Type": "application/json"
        }
        try:
            response = requests.post(WHATSAPP_API_URL, headers=headers, data=json.dumps(payload))
            response.raise_for_status() # Raise an exception for HTTP errors
            print(f"Message sent to {to_phone_number}. Response: {response.json()}")
            return {"status": "success", "response": response.json()}
        except requests.exceptions.RequestException as e:
            print(f"Error sending WhatsApp message to {to_phone_number}: {e}")
            return {"status": "error", "error_message": str(e)}

def parse_incoming_whatsapp_message(payload: dict):
    """Parses an incoming WhatsApp message payload (simplified for MVP)."""
    try:
        if payload.get("object") == "whatsapp_business_account":
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    if value.get("messaging_product") == "whatsapp":
                        # Get message details
                        message_object = value.get("messages", [{}])[0]
                        if message_object.get("type") == "text":
                            text_body = message_object.get("text", {}).get("body")
                            from_phone = message_object.get("from")
                            # In a real app, you'd also get message_id, timestamp, etc.
                            # whatsapp_id is usually the same as from_phone for user messages
                            return {
                                "whatsapp_id": from_phone, 
                                "phone_number": from_phone, 
                                "text": text_body
                            }
    except Exception as e:
        print(f"Error parsing incoming WhatsApp message: {e}")
        return None
    return None

# Example of an incoming payload structure (for testing parse_incoming_whatsapp_message)
EXAMPLE_INCOMING_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "BUSINESS_ACCOUNT_ID",
        "changes": [{
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {
                    "display_phone_number": "YOUR_PHONE_NUMBER",
                    "phone_number_id": PHONE_NUMBER_ID
                },
                "contacts": [{
                    "profile": {"name": "User Name"},
                    "wa_id": "USER_WHATSAPP_ID"
                }],
                "messages": [{
                    "from": "USER_WHATSAPP_ID", # This is the user's phone number
                    "id": "MESSAGE_ID",
                    "timestamp": "TIMESTAMP",
                    "text": {"body": "Olá! Quero adicionar uma tarefa."},
                    "type": "text"
                }]
            },
            "field": "messages"
        }]
    }]
}

if __name__ == "__main__":
    # Test sending (simulation)
    send_whatsapp_message("USER_PHONE_NUMBER", "Olá, este é um teste do assistente!")

    # Test parsing
    parsed = parse_incoming_whatsapp_message(EXAMPLE_INCOMING_PAYLOAD)
    print("\nParsed incoming message:")
    print(json.dumps(parsed, indent=2))

