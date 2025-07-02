import os
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, constants
from services import task_service as ts
import logging

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")

_bot = Bot(BOT_TOKEN) if BOT_TOKEN else None
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID") or 0)


def format_exec_task(t: ts.Task) -> tuple[str, InlineKeyboardMarkup]:
    """Сформировать текст и клавиатуру для задачи исполнителю."""
    lines = [f"<b>{t.title.upper()}</b>"]
    d = getattr(t, "deal", None)
    if d and d.client:
        lines.append(f"{d.client.name}, {d.description}")
        folder = d.drive_folder_path or d.drive_folder_link
        if folder:
            lines.append(folder)
    if t.note:
        lines.append(t.note.strip())
    text = "\n".join(lines)

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Добавить расчёт", callback_data=f"calc:{t.id}")],
            [InlineKeyboardButton("Выполнить", callback_data=f"task_done:{t.id}")],
            [InlineKeyboardButton("Написать вопрос", callback_data=f"question:{t.id}")],
        ]
    )
    return text, kb


def send_exec_task(t: ts.Task, tg_id: int) -> None:
    """Отправить задачу исполнителю и связать её с сообщением."""
    if not _bot:
        import logging
        logging.getLogger(__name__).warning("TG_BOT_TOKEN not configured")
        return
    text, kb = format_exec_task(t)
    msg = _bot.send_message(
        chat_id=tg_id,
        text=text,
        reply_markup=kb,
        parse_mode=constants.ParseMode.HTML,
    )
    ts.link_telegram(t.id, msg.chat_id, msg.message_id)


def notify_admin(text: str) -> None:
    """Отправить текстовое уведомление администратору."""
    if not _bot or not ADMIN_CHAT_ID:
        return
    try:
        _bot.send_message(ADMIN_CHAT_ID, text, parse_mode=constants.ParseMode.HTML)
    except Exception as exc:
        logging.getLogger(__name__).warning("Failed to notify admin: %s", exc)

