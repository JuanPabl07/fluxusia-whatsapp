# tests/test_integration_mvp.py

import unittest
import os
import json
from unittest.mock import patch, MagicMock

os.environ["DATABASE_URL"] = "sqlite:///file:memdb1?mode=memory&cache=shared"
SQLALCHEMY_DATABASE_URL_TEST = "sqlite:///file:memdb1?mode=memory&cache=shared"

from app.db.database import initialize_database, create_db_and_tables, get_engine, get_session_local, Base
print("DEBUG TEST: Initializing database for tests...")
initialize_database(SQLALCHEMY_DATABASE_URL_TEST, is_test_setup=True)
print(f"DEBUG TEST: Database initialized for tests with engine: {get_engine().url if get_engine() else 'None'}")

from fastapi.testclient import TestClient
from sqlalchemy import inspect as sqlalchemy_inspect
from app.main import app, get_db_session as app_get_db_session
from app.models import models
from config import settings

def override_get_db():
    TestSessionLocal = get_session_local()
    print(f"DEBUG TEST override_get_db: Using SessionLocal bound to engine: {TestSessionLocal.kw['bind'].url if 'bind' in TestSessionLocal.kw else 'N/A'}")
    try:
        db = TestSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[app_get_db_session] = override_get_db

client = TestClient(app)
mock_sent_messages_list = []

def helper_simulate_whatsapp_post(mock_whatsapp_send_fn, user_phone, message_body):
    current_test_engine = get_engine()
    print(f"DEBUG HELPER: Ensuring tables on engine {current_test_engine.url} before POST.")
    create_db_and_tables(current_test_engine)
    
    mock_sent_messages_list.clear()
    mock_whatsapp_send_fn.side_effect = lambda to, msg: mock_sent_messages_list.append({"to": to, "text": msg})
    
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "BUSINESS_ACCOUNT_ID",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "TEST_PHONE", "phone_number_id": settings.PHONE_NUMBER_ID},
                    "contacts": [{"profile": {"name": "Test User"}, "wa_id": user_phone}],
                    "messages": [{
                        "from": user_phone,
                        "id": "MSG_ID_TEST",
                        "timestamp": "1678886400",
                        "text": {"body": message_body},
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    response = client.post("/webhook", json=payload)
    return response, mock_sent_messages_list

class TestWhatsappIntegration(unittest.TestCase):

    def setUp(self):
        print("\nRunning setUp...")
        self.current_test_engine = get_engine()
        print(f"Engine in setUp: {self.current_test_engine.url}")
        Base.metadata.drop_all(bind=self.current_test_engine) 
        create_db_and_tables(self.current_test_engine)
        print("Tables dropped and recreated in setUp.")
        
        try:
            with self.current_test_engine.connect() as connection:
                inspector = sqlalchemy_inspect(connection)
                tables_in_engine = inspector.get_table_names()
                print(f"Tables in engine_test after create_all in setUp: {tables_in_engine}")
                if "users" in tables_in_engine:
                    print("DEBUG setUp: Table 'users' FOUND by inspector.")
                else:
                    print("DEBUG setUp: Table 'users' NOT FOUND by inspector.")
        except Exception as e:
            print(f"DEBUG setUp: Error during inspection: {e}")
        print("Finished setUp.")

    def tearDown(self):
        print("\nRunning tearDown...")
        mock_sent_messages_list.clear()
        print("Finished tearDown.")

    @patch("app.gateway.whatsapp_handler.send_whatsapp_message")
    def test_01_new_user_flow_and_opt_in(self, mock_send_whatsapp_message_fn):
        print("\nExecutando test_01_new_user_flow_and_opt_in")
        user_phone = "whatsapp:+550000000001"
        
        response, sent = helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, "Olá")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "new_user_prompted_for_opt_in")
        self.assertEqual(len(sent), 1)
        self.assertIn("Olá! Sou sua assistente de rotina pessoal.", sent[0]["text"])
        self.assertIn("Responda 'Sim' para continuar", sent[0]["text"])

        response, sent = helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, "Não")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "opt_in_processed")
        self.assertEqual(len(sent), 1)
        self.assertIn("Entendido. Se mudar de ideia", sent[0]["text"])

        # Re-prompt by sending another message, then opt-in
        response, sent = helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, "Oi de novo")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "opt_in_processed") # Still expects opt-in
        self.assertIn("Por favor, responda 'Sim' para confirmar", sent[0]["text"])
        
        response, sent = helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, "Sim, eu aceito")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "opt_in_processed")
        self.assertEqual(len(sent), 1)
        self.assertIn("Ótimo! Sua inscrição foi confirmada.", sent[0]["text"])

    @patch("app.gateway.whatsapp_handler.send_whatsapp_message")
    def test_02_task_management_flow(self, mock_send_whatsapp_message_fn):
        print("\nExecutando test_02_task_management_flow")
        user_phone = "whatsapp:+550000000002"

        # Step 1: Initial contact to trigger opt-in prompt
        response, sent = helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, "Olá, assistente")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "new_user_prompted_for_opt_in")
        self.assertIn("Responda 'Sim' para continuar", sent[0]["text"])
        mock_sent_messages_list.clear()

        # Step 2: User opts in
        response, sent = helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, "Sim")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "opt_in_processed")
        self.assertIn("Ótimo! Sua inscrição foi confirmada.", sent[0]["text"])
        mock_sent_messages_list.clear()

        # Step 3: Add a task
        response, sent = helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, "Lembrar de comprar leite amanhã às 10h")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Tarefa 'comprar leite amanhã às 10h' adicionada!", sent[0]["text"])
        # self.assertRegex(sent[0]["text"], r"para \d{2}/\d{2}/\d{4} 10:00\.")

        # Step 4: List tasks
        response, sent = helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, "Minhas tarefas de hoje")
        self.assertEqual(response.status_code, 200)
        self.assertIn("comprar leite amanhã às 10h", sent[0]["text"])

        # Step 5: Add another task (for simulated reminder)
        helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, "Tarefa urgente para agora mesmo")
        mock_sent_messages_list.clear()

        # Step 6: Send a message to trigger simulated reminder
        response, sent = helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, "Ok, entendi")
        self.assertEqual(response.status_code, 200)
        # Now checking for composite message including the reminder
        self.assertIn("Não entendi. Tente 'ajuda' para ver o que posso fazer.", sent[0]["text"])
        self.assertIn("Lembrete Rápido!", sent[0]["text"])
        self.assertIn("urgente para agora mesmo", sent[0]["text"])
        self.assertEqual(len(sent), 1) # Ensure the message is still a single concatenated string        # Step 7: List reminders
        response, sent = helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, "Meus lembretes de hoje")
        self.assertEqual(response.status_code, 200)
        self.assertIn("urgente para agora mesmo", sent[0]["text"])
        
        # Step 8: List tasks again to get ID for completion
        response, sent_list_resp = helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, "Minhas tarefas")
        # Find the urgent task's ID
        task_id_urgent = None
        for line in sent_list_resp[0]["text"].split("\n"):
            if "urgente para agora mesmo" in line:
                task_id_urgent = line.split(".")[0]
                break
        self.assertIsNotNone(task_id_urgent, "Urgent task ID not found in list")
        
        # Step 9: Complete the task
        response, sent = helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, f"Concluir tarefa {task_id_urgent}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(f"Tarefa {task_id_urgent} marcada como concluída!", sent[0]["text"])

    @patch("app.gateway.whatsapp_handler.send_whatsapp_message")
    def test_03_help_and_unknown_intent(self, mock_send_whatsapp_message_fn):
        print("\nExecutando test_03_help_and_unknown_intent")
        user_phone = "whatsapp:+550000000003"

        # Step 1: Initial contact
        response, sent = helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, "Oi")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "new_user_prompted_for_opt_in")
        mock_sent_messages_list.clear()

        # Step 2: User opts in
        response, sent = helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, "Sim")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "opt_in_processed")
        self.assertIn("Ótimo! Sua inscrição foi confirmada.", sent[0]["text"])
        mock_sent_messages_list.clear()

        # Step 3: Ask for help
        response, sent = helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, "ajuda")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Comandos disponíveis (MVP):", sent[0]["text"])
        self.assertIn("Adicionar tarefa", sent[0]["text"])

        # Step 4: Send unknown intent
        response, sent = helper_simulate_whatsapp_post(mock_send_whatsapp_message_fn, user_phone, "Qual a previsão do tempo para amanhã?")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Não entendi. Tente 'ajuda'", sent[0]["text"])

if __name__ == "__main__":
    print("Iniciando testes de integração do MVP...")
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestWhatsappIntegration))
    runner = unittest.TextTestRunner()
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\nTodos os testes de integração passaram com sucesso!")
    else:
        print("\nAlguns testes de integração falharam.")

