# ia_whatsapp_assistant/app/nlp/processor.py

import re
from datetime import datetime, timedelta

# Simple patterns for MVP, will be replaced by a proper NLP engine (e.g., Rasa, spaCy + LLM)
# Order matters: more specific or potentially conflicting patterns should be ordered carefully.
PATTERNS = {
    "list_tasks": re.compile(r"(quais minhas tarefas|minhas tarefas|listar tarefas|ver tarefas)(?:\s+(?:de|para)\s+(?P<date>hoje|amanhã))?", re.IGNORECASE),
    "list_reminders": re.compile(r"(quais meus lembretes|meus lembretes|ver lembretes|lembretes de hoje|consultar lembretes)(?:\s+(?:de|para)\s+(?P<date>hoje|amanhã))?", re.IGNORECASE),
    "complete_task": re.compile(r"(marcar tarefa|concluir tarefa|tarefa concluída|finalizar tarefa)[:\s]*(?P<task_id>\d+)(?:\s+como concluída)?", re.IGNORECASE),
    # Add task is placed after list_tasks to avoid "tarefas de hoje" (list) being caught by "tarefa" (add)
    "add_task": re.compile(r"(lembrar de|adicionar tarefa|anotar|lembrete|tarefa)[:\s]*(?P<description>.+?)(?:\s+(?:(?:para|em|no dia)\s+)?(?P<date>amanhã|hoje|\d{1,2}[-/]\d{1,2}(?:[-/]\d{2,4})?))?(?:\s+(?:(?:às|as|@)\s+)?(?P<time>\d{1,2}(?:[:hH]\d{2})?))?$", re.IGNORECASE),
    "opt_in_yes": re.compile(r"\b(sim|s|aceito|concordo)\b", re.IGNORECASE),
    "opt_in_no": re.compile(r"\b(não|nao|n|recuso|negar)\b", re.IGNORECASE),
    "help": re.compile(r"\b(ajuda|comandos|o que você faz\??)\b", re.IGNORECASE),
}

def parse_datetime_from_text(date_str, time_str):
    """Rudimentary date/time parser for MVP."""
    now = datetime.now()
    parsed_date = now # Default to today

    if date_str:
        date_str = date_str.lower()
        if date_str == "hoje":
            parsed_date = now
        elif date_str == "amanhã":
            parsed_date = now + timedelta(days=1)
        else:
            try:
                # Try to parse dd/mm or dd/mm/yy or dd/mm/yyyy
                day, month, *year_parts = map(int, re.split(r"[-/]", date_str))
                year = year_parts[0] if year_parts else now.year
                if year < 100: # Assuming yy format
                    year += 2000
                parsed_date = datetime(year, month, day)
            except ValueError:
                pass # Invalid date format, keep default

    parsed_time_hour, parsed_time_minute = 9, 0 # Default time if only date is given (e.g., 9 AM)

    if time_str:
        time_str = time_str.lower()
        try:
            parts = re.split(r"[:hH]", time_str)
            parsed_time_hour = int(parts[0])
            parsed_time_minute = int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            pass # Invalid time format
    
    final_datetime = parsed_date.replace(hour=parsed_time_hour, minute=parsed_time_minute, second=0, microsecond=0)
    return final_datetime.strftime("%Y-%m-%d %H:%M:%S")

def process_message_nlp(message_text: str):
    """Processes a user message and extracts intent and entities."""
    
    for intent, pattern in PATTERNS.items():
        match = pattern.search(message_text)
        if match:
            entities = match.groupdict()
            
            if intent == "add_task":
                description = entities.get("description", "").strip()
                if not description:
                    return {"intent": "clarify_add_task", "entities": {}}
                
                date_entity = entities.get("date")
                time_entity = entities.get("time")

                due_date_str_for_task_manager = None # Initialize
                if date_entity or time_entity:
                    due_date_str_for_task_manager = parse_datetime_from_text(date_entity, time_entity)
                else: # No explicit date/time from regex, default to today
                    due_date_str_for_task_manager = parse_datetime_from_text(None, None) # Defaults to today at 09:00
                
                return {"intent": "add_task", "entities": {"description": description, "due_date": due_date_str_for_task_manager}}
            
            if intent == "list_tasks" or intent == "list_reminders":
                date_entity = entities.get("date")
                if date_entity:
                    date_filter = date_entity.lower()
                else:
                    date_filter = "all" # Signify all tasks/reminders if no specific date is mentioned
                return {"intent": intent, "entities": {"date_filter": date_filter}}
                
            if intent == "complete_task":
                task_id = entities.get("task_id")
                if task_id:
                    return {"intent": "complete_task", "entities": {"task_id": int(task_id)}}
            
            if intent in ["opt_in_yes", "opt_in_no", "help"]:
                 return {"intent": intent, "entities": {}}

    return {"intent": "unknown", "entities": {"original_message": message_text}}

# Example Usage (for testing)
if __name__ == "__main__":
    tests = [
        "Lembrar de comprar pão amanhã às 8h",
        "adicionar tarefa reunião com cliente para 20/12 às 14:30",
        "anotar consulta médica dia 25/05/2025 as 10",
        "tarefa: ligar para o João hoje 17H",
        "Lembrar de comprar leite", # No date/time
        "Lembrar de call com time amanhã", # Date only
        "Lembrar de apresentação às 15h", # Time only
        "Tarefa urgente para agora mesmo", # No date/time, should default to today
        "Quais minhas tarefas de hoje?",
        "minhas tarefas para amanhã",
        "listar tarefas", # Should now result in date_filter: "all"
        "Quais meus lembretes de hoje?",
        "ver lembretes para amanhã",
        "marcar tarefa 123 como concluída",
        "Sim",
        "Não quero",
        "ajuda",
        "Qual o tempo para amanhã?" # Unknown
    ]
    print("--- Testing NLP Processor ---")
    for test in tests:
        result = process_message_nlp(test)
        print(f"\nInput: \t\"{test}\"")
        print(f"Output:\t{result}")
        if result["intent"] == "add_task":
            description_val = result.get("entities",{}).get("description")
            due_date_val = result.get("entities",{}).get("due_date")
            print(f"Parsed Desc: \t'{description_val}'")
            print(f"Parsed Due: \t'{due_date_val}'")
    print("--- End NLP Processor Test ---")

