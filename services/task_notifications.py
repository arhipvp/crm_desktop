"""Уведомления и взаимодействие задач с Telegram."""

import logging

from database.db import db
from database.models import Task
from .task_states import IDLE, SENT


logger = logging.getLogger(__name__)


def notify_task(task_id: int) -> None:
    """Переотправить уведомление исполнителю по задаче."""
    t = Task.active().where(Task.id == task_id).get_or_none()
    if not t or t.is_done:
        return
    if t.dispatch_state == SENT:
        if t.tg_chat_id:
            try:
                from services.telegram_service import send_exec_task

                send_exec_task(t, t.tg_chat_id)
                logger.info("🔔 Напоминание отправлено по задаче #%s", t.id)
            except Exception:  # pragma: no cover - logging
                logger.debug("Failed to resend task", exc_info=True)
        else:
            from .task_queue import return_to_queue

            return_to_queue(task_id)
    elif t.dispatch_state == IDLE:
        from .task_queue import queue_task

        queue_task(task_id)


def link_telegram(task_id: int, chat_id: int, msg_id: int):
    with db.atomic():
        Task.update(tg_chat_id=chat_id, tg_message_id=msg_id).where(
            Task.id == task_id
        ).execute()
    logger.info("🔗 Telegram-связь установлена для задачи #%s", task_id)


def mark_done(task_id: int, note: str | None = None) -> None:
    """Отметить задачу выполненной и уведомить администратора."""
    task = Task.get_or_none(Task.id == task_id)
    if not task:
        logger.warning("❗ Задача %s не найдена для завершения", task_id)
        return

    full_note = note if note is not None else task.note
    from .task_crud import update_task

    update_task(task, is_done=True, note=full_note)
    try:
        from services.telegram_service import notify_admin

        notify_admin(f"✅ Задача #{task.id} выполнена")
    except Exception:  # pragma: no cover - logging
        logger.debug("Failed to notify admin", exc_info=True)


def append_note(task_id: int, text: str):
    if not text.strip():
        return
    t = Task.get_or_none(Task.id == task_id)
    if t:
        with db.atomic():
            t.note = ((t.note + "\n") if t.note else "") + text
            t.save()
        logger.info("🗒 К задаче #%s добавлена заметка", t.id)
        try:
            from services.telegram_service import notify_admin

            notify_admin(f"📝 Обновление по задаче #{t.id}: {text}")
        except Exception:  # pragma: no cover - logging
            logger.debug("Failed to notify admin", exc_info=True)


def unassign_from_telegram(task_id: int) -> None:
    with db.atomic():
        task = Task.get_by_id(task_id)
        task.dispatch_state = IDLE
        task.tg_chat_id = None
        task.tg_message_id = None
        task.save()
    logger.info("❎ Задача #%s снята с Telegram", task.id)


__all__ = [
    "notify_task",
    "link_telegram",
    "mark_done",
    "append_note",
    "unassign_from_telegram",
]

