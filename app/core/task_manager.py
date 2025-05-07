# ia_whatsapp_assistant/app/core/task_manager.py

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, cast, Date
from app.models import models
from app.db.database import SessionLocal, engine # Import engine as well
from datetime import datetime, timedelta, date

# Ensure tables are created (idempotent call)
# models.Base.metadata.create_all(bind=engine) # This should be handled by app startup or migrations, not here.

# --- User Management --- #

def get_user_by_whatsapp_id(db: Session, whatsapp_id: str):
    return db.query(models.User).filter(models.User.whatsapp_id == whatsapp_id).first()

def create_user(db: Session, whatsapp_id: str, phone_number: str):
    db_user = models.User(whatsapp_id=whatsapp_id, phone_number=phone_number, opt_in_status=False)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_opt_in(db: Session, whatsapp_id: str, opt_in_status: bool):
    db_user = get_user_by_whatsapp_id(db, whatsapp_id)
    if db_user:
        db_user.opt_in_status = opt_in_status
        db_user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_user)
    return db_user

# --- Task Management (including Reminders) --- #

def create_task(db: Session, user_whatsapp_id: str, description: str, due_date_str: str = None, priority: str = None):
    db_user = get_user_by_whatsapp_id(db, user_whatsapp_id)
    if not db_user:
        return None 
    
    parsed_due_date = None
    if due_date_str:
        try:
            # Ensure due_date_str is correctly parsed if provided
            parsed_due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M:%S") 
        except ValueError:
            # Fallback or error handling if due_date_str format is unexpected
            pass # Or log an error, for now, it might result in None

    db_task = models.Task(
        description=description, 
        due_date=parsed_due_date, 
        priority=priority, 
        owner_id=db_user.id,
        status="pending"
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

def get_tasks_by_user(db: Session, user_whatsapp_id: str, status: str = "pending"):
    db_user = get_user_by_whatsapp_id(db, user_whatsapp_id)
    if not db_user:
        return []
    return db.query(models.Task).filter(models.Task.owner_id == db_user.id, models.Task.status == status).order_by(models.Task.due_date.asc()).all()

def get_reminders_for_user_by_date_filter(db: Session, user_whatsapp_id: str, date_filter: str = "hoje"):
    db_user = get_user_by_whatsapp_id(db, user_whatsapp_id)
    if not db_user:
        return []

    # Determine the target date based on the filter
    target_query_date = date.today()
    if date_filter == "amanhã":
        target_query_date = date.today() + timedelta(days=1)
    # Add more conditions for other date_filter values if needed (e.g., "esta semana")

    # Define the start and end of the target day for datetime comparison
    day_start_dt = datetime.combine(target_query_date, datetime.min.time())
    next_day_start_dt = datetime.combine(target_query_date + timedelta(days=1), datetime.min.time())

    return db.query(models.Task).filter(
        models.Task.owner_id == db_user.id,
        models.Task.status == "pending",
        models.Task.due_date != None,  # Ensure there is a due date
        models.Task.due_date >= day_start_dt, # Due date is on or after the start of the target day
        models.Task.due_date < next_day_start_dt  # Due date is before the start of the next day
    ).order_by(models.Task.due_date.asc()).all()

def get_pending_reminders_for_today(db: Session, user_whatsapp_id: str):
    db_user = get_user_by_whatsapp_id(db, user_whatsapp_id)
    if not db_user:
        return []
    
    today_query_date = date.today()
    day_start_dt = datetime.combine(today_query_date, datetime.min.time())
    next_day_start_dt = datetime.combine(today_query_date + timedelta(days=1), datetime.min.time())

    return db.query(models.Task).filter(
        models.Task.owner_id == db_user.id,
        models.Task.status == "pending",
        models.Task.due_date != None,
        models.Task.due_date >= day_start_dt,
        models.Task.due_date < next_day_start_dt
        # models.Task.due_date <= datetime.now() # Optionally, only if due time has passed or is now (for immediate reminders)
    ).order_by(models.Task.due_date.asc()).all()

def get_task_by_id(db: Session, task_id: int, user_whatsapp_id: str):
    db_user = get_user_by_whatsapp_id(db, user_whatsapp_id)
    if not db_user:
        return None
    return db.query(models.Task).filter(models.Task.id == task_id, models.Task.owner_id == db_user.id).first()

def update_task_status(db: Session, task_id: int, user_whatsapp_id: str, new_status: str):
    db_task = get_task_by_id(db, task_id, user_whatsapp_id)
    if db_task:
        db_task.status = new_status
        db_task.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_task)
    return db_task

def delete_task(db: Session, task_id: int, user_whatsapp_id: str):
    db_task = get_task_by_id(db, task_id, user_whatsapp_id)
    if db_task:
        db.delete(db_task)
        db.commit()
        return True
    return False

