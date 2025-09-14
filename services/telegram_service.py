import logging
from pathlib import Path
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, constants

from database.models import Task
from services.task_notifications import link_telegram

from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

BOT_TOKEN = settings.tg_bot_token
_bot = Bot(BOT_TOKEN) if BOT_TOKEN else None
ADMIN_CHAT_ID = settings.admin_chat_id or 0


def format_exec_task(t: Task) -> tuple[str, InlineKeyboardMarkup]:
    """Сформировать текст и клавиатуру для задачи исполнителю."""
    lines = [f"<b>{t.title.upper()}</b>"]
    d = getattr(t, "deal", None)
    if d and d.client:
        lines.append(f"{d.client.name}, {d.description}")
        folder = d.drive_folder_path or d.drive_folder_link
        if folder:
            lines.append(folder)
        try:
            from services.calculation_service import export_calculations_excel

            file_path = export_calculations_excel(d.id)
            file_name = Path(file_path).name
            if d.drive_folder_link:
                file_link = f"{d.drive_folder_link}/{file_name}"
                lines.append(f'<a href="{file_link}">📊 Файл расчётов</a>')
            else:
                lines.append(file_path)
        except Exception:
            logger.debug("Не удалось прикрепить файл с расчётами", exc_info=True)
    if t.note:
        lines.append(t.note.strip())
    text = "\n".join(lines)

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Выполнить", callback_data=f"task_done:{t.id}")],
            [InlineKeyboardButton("Написать вопрос", callback_data=f"question:{t.id}")],
        ]
    )
    return text, kb


def send_exec_task(t: Task, tg_id: int) -> None:
    """Отправить задачу исполнителю и связать её с сообщением."""
    if not _bot:
        logger.warning("TG_BOT_TOKEN не настроен")
        return
    text, kb = format_exec_task(t)
    msg = _bot.send_message(
        chat_id=tg_id,
        text=text,
        reply_markup=kb,
        parse_mode=constants.ParseMode.HTML,
    )
    link_telegram(t.id, msg.chat_id, msg.message_id)


def notify_admin(text: str) -> None:
    """Отправить текстовое уведомление администратору."""
    if not _bot or not ADMIN_CHAT_ID:
        return
    try:
        _bot.send_message(ADMIN_CHAT_ID, text, parse_mode=constants.ParseMode.HTML)
    except Exception as exc:
        logger.warning("Не удалось отправить уведомление администратору: %s", exc)


def notify_admin_safe(text: str) -> None:
    """Отправить уведомление администратору, игнорируя ошибки."""
    try:
        notify_admin(text)
    except Exception:
        logger.debug("Не удалось отправить уведомление администратору", exc_info=True)


def notify_executor(tg_id: int, text: str) -> None:
    """Отправить уведомление исполнителю."""
    if not _bot or not tg_id:
        return
    try:
        _bot.send_message(tg_id, text, parse_mode=constants.ParseMode.HTML)
    except Exception as exc:
        logger.warning("Не удалось отправить уведомление исполнителю %s: %s", tg_id, exc)

