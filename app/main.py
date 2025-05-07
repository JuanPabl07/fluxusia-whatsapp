# app/main.py

from fastapi import FastAPI, Request, HTTPException, Depends
from sqlalchemy.orm import Session
import json
from datetime import datetime

from app.gateway import whatsapp_handler
from app.nlp import processor as nlp_processor
from app.core import task_manager
# Use the new getter for SessionLocal and the initialization function
from app.db.database import initialize_database, get_session_local, get_engine, create_db_and_tables
from app.models import models # Import models to ensure Base is populated
from config.settings import WHATSAPP_VERIFY_TOKEN, DATABASE_URL

# Initialize the database with the default URL when the app starts
# This will set up the main `engine` and `SessionLocal` for the app
initialize_database(DATABASE_URL)

# If you need to create tables on app startup (for production/dev, not tests):
# create_db_and_tables(get_engine()) 
# For MVP, we are letting tests handle table creation in their own context.

app = FastAPI(
    title="IA WhatsApp Assistant MVP",
    description="MVP para um assistente de IA no WhatsApp para gerenciamento de rotina.",
    version="0.1.2" # Incremented version
)

# Dependency to get DB session
def get_db_session():
    # Use the getter to ensure SessionLocal is initialized
    CurrentSessionLocal = get_session_local()
    db = CurrentSessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def read_root():
    return {"message": "IA WhatsApp Assistant MVP está rodando!"}

@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        print(f"WEBHOOK_VERIFIED: {challenge}")
        return int(challenge)
    else:
        print("WEBHOOK_VERIFICATION_FAILED")
        raise HTTPException(status_code=403, detail="Verification token mismatch")

@app.post("/webhook")
async def handle_whatsapp_message(request: Request, db: Session = Depends(get_db_session)):
    try:
        payload = await request.json()
        print(f"Received payload: {json.dumps(payload, indent=2)}")
    except json.JSONDecodeError:
        print("Error decoding JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    parsed_message = whatsapp_handler.parse_incoming_whatsapp_message(payload)
    if not parsed_message:
        return {"status": "ignored", "reason": "Non-text message or parse error"}

    user_whatsapp_id = parsed_message["whatsapp_id"]
    user_phone_number = parsed_message["phone_number"]
    message_text = parsed_message["text"]
    print(f"Processing message from {user_whatsapp_id}: {message_text}")

    user = task_manager.get_user_by_whatsapp_id(db, user_whatsapp_id)
    if not user:
        user = task_manager.create_user(db, user_whatsapp_id, user_phone_number)
        response_text = ("Olá! Sou sua assistente de rotina pessoal. "
                         "Posso te ajudar a organizar suas tarefas e mais. "
                         "Você concorda em receber minhas mensagens e utilizar meus serviços? "
                         "Responda 'Sim' para continuar ou 'Não' para cancelar.") # Corrected quote
        whatsapp_handler.send_whatsapp_message(user_whatsapp_id, response_text)
        return {"status": "new_user_prompted_for_opt_in"}

    nlp_result = nlp_processor.process_message_nlp(message_text)
    intent = nlp_result.get("intent")
    entities = nlp_result.get("entities", {})
    response_text = "Desculpe, não entendi o que você quis dizer. Pode tentar de outra forma?"

    if not user.opt_in_status:
        if intent == "opt_in_yes":
            task_manager.update_user_opt_in(db, user_whatsapp_id, True)
            response_text = "Ótimo! Sua inscrição foi confirmada. Como posso te ajudar hoje? Digite 'ajuda' para ver os comandos."
        elif intent == "opt_in_no":
            task_manager.update_user_opt_in(db, user_whatsapp_id, False)
            response_text = "Entendido. Se mudar de ideia, é só me chamar e dizer 'Sim'."
        else:
            response_text = ("Por favor, responda 'Sim' para confirmar o uso do serviço ou 'Não' para cancelar.")
        whatsapp_handler.send_whatsapp_message(user_whatsapp_id, response_text)
        return {"status": "opt_in_processed"}

    simulated_reminder_text = ""
    pending_today_reminders = task_manager.get_pending_reminders_for_today(db, user_whatsapp_id)
    if pending_today_reminders:
        simulated_reminder_text = "\n\nLembrete Rápido! Você tem as seguintes tarefas para hoje:\n"
        for task in pending_today_reminders:
            simulated_reminder_text += f"- {task.description}"
            if task.due_date:
                simulated_reminder_text += f" (Prazo: {task.due_date.strftime('%H:%M')})\n"
            else:
                simulated_reminder_text += "\n"
 
    if intent == "add_task":
        description = entities.get("description")
        due_date = entities.get("due_date")
        if description:
            task = task_manager.create_task(db, user_whatsapp_id, description, due_date_str=due_date)
            response_text = f"Tarefa '{description}' adicionada!"
            if due_date:
                response_text += f" para {datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')}."
        else:
            response_text = "Para adicionar uma tarefa, me diga a descrição. Ex: Lembrar de comprar pão amanhã às 8h"

    elif intent == "list_tasks":
        date_filter = entities.get("date_filter", "hoje")
        tasks = task_manager.get_tasks_by_user(db, user_whatsapp_id, status="pending")
        if tasks:
            response_text = f"Suas tarefas pendentes ({date_filter}):\n"
            for i, task in enumerate(tasks):
                response_text += f"{task.id}. {task.description}"
                if task.due_date:
                    response_text += f" (Prazo: {task.due_date.strftime('%d/%m/%Y %H:%M')})\n"
                else:
                    response_text += "\n"
        else:
            response_text = f"Você não tem tarefas pendentes ({date_filter})."

    elif intent == "list_reminders":
        date_filter = entities.get("date_filter", "hoje")
        reminders = task_manager.get_reminders_for_user_by_date_filter(db, user_whatsapp_id, date_filter)
        if reminders:
            response_text = f"Seus lembretes para {date_filter}:\n"
            for i, task in enumerate(reminders):
                response_text += f"{task.id}. {task.description}"
                if task.due_date:
                    response_text += f" (Prazo: {task.due_date.strftime('%d/%m/%Y %H:%M')})\n"
                else:
                    response_text += "\n"
        else:
            response_text = f"Você não tem lembretes agendados para {date_filter}."

    elif intent == "complete_task":
        task_id_str = entities.get("task_id")
        if task_id_str:
            try:
                task_id = int(task_id_str)
                updated_task = task_manager.update_task_status(db, task_id, user_whatsapp_id, "completed")
                if updated_task:
                    response_text = f"Tarefa {task_id} marcada como concluída!"
                else:
                    response_text = f"Não encontrei a tarefa {task_id} ou ela não é sua."
            except ValueError:
                response_text = "Por favor, forneça um número de tarefa válido para concluir."
        else:
            response_text = "Qual o número da tarefa que você quer concluir?"
            
    elif intent == "help":
        response_text = ("Comandos disponíveis (MVP):\n"
                         "- Adicionar tarefa: 'Lembrar de [descrição] para [data] às [hora]'\n"
                         "- Listar tarefas: 'Minhas tarefas de hoje'\n"
                         "- Listar lembretes: 'Meus lembretes de hoje' ou 'Lembretes para amanhã'\n"
                         "- Concluir tarefa: 'Concluir tarefa [número da tarefa]'\n"
                         "- Ajuda: 'ajuda'")

    elif intent == "unknown":
        response_text = "Não entendi. Tente 'ajuda' para ver o que posso fazer."
    
    if simulated_reminder_text and intent not in ["list_reminders"]:
        final_response_text = response_text + simulated_reminder_text
    else:
        final_response_text = response_text

    whatsapp_handler.send_whatsapp_message(user_whatsapp_id, final_response_text)
    return {"status": "processed", "intent": intent, "response_sent": final_response_text}

if __name__ == "__main__":
    print("Para testar a aplicação, rode com Uvicorn: uvicorn app.main:app --reload")

