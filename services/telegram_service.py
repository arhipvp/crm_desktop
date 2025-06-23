import os
import asyncio
import logging
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton, constants

from database.models import Task
from services import task_service as ts

logger = logging.getLogger(__name__)

_TOKEN = os.getenv("TG_BOT_TOKEN")
if not _TOKEN:
    logger.warning("TG_BOT_TOKEN not set; Telegram sending disabled")
    _BOT = None
else:
    _BOT = Bot(_TOKEN)

async def _send(text: str, tg_id: int, kb: InlineKeyboardMarkup):
    if _BOT is None:
        raise RuntimeError("Telegram bot token not configured")
    return await _BOT.send_message(
        chat_id=tg_id,
        text=text,
        reply_markup=kb,
        parse_mode=constants.ParseMode.HTML,
    )

def send_task(task: Task, executor_tg_id: int) -> None:
    """Отправить задачу исполнителю напрямую в Telegram."""
    lines = [f"<b>{task.title.upper()}</b>", f"#{task.id}"]
    if task.deal and task.deal.client:
        lines.append(f"{task.deal.client.name}, {task.deal.description}")
        folder = task.deal.drive_folder_path or task.deal.drive_folder_link
        if folder:
            lines.append(folder)
    if task.note:
        lines.append(task.note.strip())
    text = "\n".join(lines)

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Добавить расчёт", callback_data=f"calc:{task.id}")],
            [InlineKeyboardButton("Выполнить", callback_data=f"task_done:{task.id}")],
            [InlineKeyboardButton("Написать вопрос", callback_data=f"question:{task.id}")],
        ]
    )

    async def _do():
        return await _send(text, executor_tg_id, kb)

    msg = asyncio.run(_do())
    ts.link_telegram(task.id, executor_tg_id, msg.message_id)
