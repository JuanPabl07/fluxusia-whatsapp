# ia_whatsapp_assistant/config/settings.py

import os

WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN", "seu_token_de_acesso_whatsapp")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "seu_token_de_verificacao_webhook")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "id_do_seu_numero_de_telefone")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ia_whatsapp_assistant.db")

# Configurações para o motor de PLN (exemplo)
NLP_MODEL_NAME = "default_pt_br_model"

# Outras configurações globais
DEBUG = True

