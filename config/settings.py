# ia_whatsapp_assistant/config/settings.py

import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente de um arquivo .env para desenvolvimento local.
# No Render, as variáveis de ambiente são configuradas diretamente no painel do serviço.
load_dotenv()

# Token de API para enviar mensagens (ainda não estamos usando ativamente no MVP para envio, mas bom ter)
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")

# Token para verificar o Webhook do WhatsApp.
# No Render, este DEVE ser lido da variável de ambiente "VERIFY_TOKEN" configurada no painel.
# Removemos o valor padrão para garantir que ele falhe explicitamente se não estiver configurado no ambiente.
WHATSAPP_VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# ID do número de telefone do WhatsApp Business (será necessário para enviar mensagens)
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

# URL do Banco de Dados
# Para o Render, se você não configurar uma variável DATABASE_URL, ele usará o SQLite local.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ia_whatsapp_assistant.db")

# Configurações para o motor de PLN (exemplo)
NLP_MODEL_NAME = "default_pt_br_model"

# Outras configurações globais
# Em um ambiente de produção como o Render, DEBUG idealmente seria False ou lido de uma variável de ambiente.
DEBUG_MODE_STR = os.getenv("DEBUG", "True") # Padrão para True se não definido
DEBUG = DEBUG_MODE_STR.lower() in ('true', '1', 't')

# Verificação importante na inicialização (opcional, mas bom para depuração)
if WHATSAPP_VERIFY_TOKEN is None and not DEBUG: # Em modo não-debug, é crítico
    print("ALERTA CRÍTICO: A variável de ambiente VERIFY_TOKEN não está configurada!")
elif WHATSAPP_VERIFY_TOKEN is None and DEBUG:
    print("AVISO DEBUG: A variável de ambiente VERIFY_TOKEN não está configurada. Webhook GET falhará se não for um teste local com valor mockado.")
