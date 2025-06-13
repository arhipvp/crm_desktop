"""
Telegram‑бот для очереди задач CRM_desktop.
Контейнер запускает именно этот файл.
Бот забирает токен из .env (том монтируется в контейнер).
Теперь поддерживает приём документов и фотографий в ответ на сообщение сделки — файл сохраняется в папку сделки на диске.
"""

from database.init import init_from_env

import os
import re
import datetime as _dt
from utils.time_utils import now_str
import tempfile
import logging
from utils.logging_config import setup_logging
from dotenv import load_dotenv
from pathlib import Path
from html import escape
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ForceReply,
    Update,
    constants,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ───────────── env ─────────────
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
init_from_env()
setup_logging()

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TG_BOT_TOKEN не найден. Укажите его в .env")

ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
try:
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID) if ADMIN_CHAT_ID else None
except ValueError:
    ADMIN_CHAT_ID = None

logger = logging.getLogger(__name__)

# Задачи, ожидающие подтверждения администратора
pending_accept: dict[int, int] = {}

# ───────────── imports из core ─────────────
from services import task_service as ts


# ───────────── helpers ─────────────
def fmt_task(t: ts.Task) -> str:
    due = t.due_date.strftime("%d.%m.%Y") if t.due_date else "—"
    lines = [f"📌 <b>Задача #{t.id}</b> (до <b>{due}</b>)", t.title.strip()]

    d = getattr(t, "deal", None)
    if d:
        lines.append(f"\n🔗 <b>Сделка #{d.id}</b>")
        if d.start_date:
            lines.append(f"📅 Дата: {d.start_date.strftime('%d.%m.%Y')}")
        if d.description:
            lines.append(f"📝 {d.description.strip()}")

        c = getattr(d, "client", None)
        if c:
            lines.append(f"👤 Клиент: {c.name}")
            if d.drive_folder_link:
                lines.append(f'<a href="{d.drive_folder_link}">📂 Папка сделки</a>')
            elif c.drive_folder_link:
                lines.append(f'<a href="{c.drive_folder_link}">📂 Папка клиента</a>')

        lines.append("\n<b>Журнал:</b>")
        if d.calculations:
            calc = escape(d.calculations)
            lines.append(f"<pre>{calc}</pre>")
        else:
            lines.append("—")

    p = getattr(t, "policy", None)
    if p:
        lines.append(f"\n📄 <b>Полис #{p.id}</b>")
        lines.append(f"№ {p.policy_number}")
        lines.append(f"Тип: {p.insurance_type}")
        if p.client:
            lines.append(f"👤 Страхователь: {p.client.name}")

    if t.note:
        lines.append(f"\n📝 {t.note.strip()}")

    return "\n".join(lines)


def kb_task(tid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Выполнить", callback_data=f"done:{tid}"),
                InlineKeyboardButton("💬 Ответить", callback_data=f"reply:{tid}"),
                InlineKeyboardButton("🔄 Вернуть", callback_data=f"ret:{tid}"),
            ]
        ]
    )


def kb_admin(tid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("\u2705 Принять", callback_data=f"accept:{tid}"),
                InlineKeyboardButton("\u270F\ufe0f Внести информацию", callback_data=f"info:{tid}"),
            ],
            [
                InlineKeyboardButton(
                    "\u21a9\ufe0f Прокомментировать и вернуть",
                    callback_data=f"rework:{tid}",
                )
            ],
        ]
    )


async def notify_admin(bot, tid: int, user_text: str | None = None):
    if not ADMIN_CHAT_ID:
        return
    task = ts.Task.get_or_none(ts.Task.id == tid)
    if not task:
        return
    text = fmt_task(task)
    if user_text:
        text += f"\n\n{user_text}"
    logger.info("Notify admin about %s", tid)
    await bot.send_message(
        ADMIN_CHAT_ID,
        text,
        reply_markup=kb_admin(tid),
        parse_mode=constants.ParseMode.HTML,
    )


# ───────────── handlers ─────────────
async def h_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    logger.info("/start from %s", update.effective_user.id)
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📥 Получить задачу", callback_data="get")]]
    )
    await update.message.reply_text(
        "Привет! Я бот CRM. Нажми кнопку, чтобы взять следующую задачу.",
        reply_markup=kb,
    )


async def h_get(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    logger.info("Action '%s' from %s", q.data, q.from_user.id)
    logger.info("%s requested tasks", q.from_user.id)

    clients = ts.get_clients_with_queued_tasks()
    if not clients:
        return await q.answer("Очередь пуста 💤", show_alert=True)

    buttons = [
        [InlineKeyboardButton(c.name.split()[0], callback_data=f"client:{c.id}")]
        for c in clients
    ]
    kb = InlineKeyboardMarkup(buttons)
    await q.message.reply_text("Выберите клиента:", reply_markup=kb)


async def h_choose_client(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    logger.info("%s chose client", q.from_user.id)

    _p, cid = q.data.split(":")
    cid = int(cid)

    task = ts.pop_next_by_client(q.from_user.id, cid)
    if not task:
        return await q.answer("Задачи закончились", show_alert=True)

    logger.info("Выдана задача %s пользователю %s", task.id, q.from_user.id)
    msg = await q.message.reply_html(fmt_task(task), reply_markup=kb_task(task.id))
    ts.link_telegram(task.id, msg.chat_id, msg.message_id)


async def h_action(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    action, tid = q.data.split(":")
    tid = int(tid)

    if action == "done":
        ts.unassign_from_telegram(tid)
        await q.message.edit_text(
            "✅ Задача скрыта из очереди", parse_mode=constants.ParseMode.HTML
        )
        pending_accept[tid] = q.message.chat_id
        await notify_admin(_ctx.bot, tid)
        logger.info("Task %s marked done, awaiting admin", tid)

    elif action == "ret":
        ts.return_to_queue(tid)
        await q.message.edit_text(
            "🔄 <i>Задача возвращена в очередь</i>", parse_mode=constants.ParseMode.HTML
        )
        logger.info("Task %s returned to queue", tid)

    elif action == "reply":
        await q.message.reply_text(
            f"Напишите комментарий к задаче #{tid}:",
            reply_markup=ForceReply(selective=True),
        )
        logger.info("Awaiting comment for %s", tid)


async def h_admin_action(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    logger.info("Admin action '%s'", q.data)

    action, tid = q.data.split(":")
    tid = int(tid)

    if action == "accept":
        ts.mark_done(tid)
        await q.message.edit_text(
            "✅ Задача подтверждена", parse_mode=constants.ParseMode.HTML
        )
        chat_id = pending_accept.pop(tid, None)
        if chat_id:
            await _ctx.bot.send_message(chat_id, "Задача принята")
        logger.info("Task %s accepted", tid)
    elif action == "info":
        await q.message.reply_text(
            f"Введите информацию для задачи #{tid}:",
            reply_markup=ForceReply(selective=True),
        )
        logger.info("Requesting info for task %s", tid)
    elif action == "rework":
        ts.queue_task(tid)
        await q.message.edit_text(
            "↩ Задача возвращена на доработку",
            parse_mode=constants.ParseMode.HTML,
        )
        await q.message.reply_text(
            f"Прокомментируйте задачу #{tid}:",
            reply_markup=ForceReply(selective=True),
        )
        logger.info("Task %s returned for rework", tid)


async def h_text(update: Update, _ctx):
    if not update.message.reply_to_message:
        return
    m = re.search(r"#(\d+)", update.message.reply_to_message.text_html or "")
    if not m:
        return
    tid = int(m.group(1))
    logger.info("Text reply for %s from %s", tid, update.message.chat_id)
    stamp = now_str()
    ts.append_note(tid, f"[TG {stamp}] {update.message.text}")
    await update.message.reply_text("Комментарий сохранён 👍")
    logger.info("Note added to %s", tid)
    if update.message.chat_id != ADMIN_CHAT_ID:
        await notify_admin(_ctx.bot, tid, update.message.text)


async def h_file(update: Update, _ctx):
    msg = update.message
    if not msg or not msg.reply_to_message:
        return

    m = re.search(r"Сделка\s+#(\d+)", msg.reply_to_message.text_html or "")
    if not m:
        return

    deal_id = int(m.group(1))
    deal = ts.get_deal_by_id(deal_id)
    if not deal or not deal.drive_folder_path:
        return await msg.reply_text("⚠️ Папка сделки не найдена.")

    deal_path = Path(deal.drive_folder_path)
    deal_path.mkdir(parents=True, exist_ok=True)

    tg_file = msg.document or (msg.photo[-1] if msg.photo else None)
    if not tg_file:
        await msg.reply_text("⚠️ Не удалось определить файл.")
        return
    logger.info("File from %s for deal %s", msg.chat_id, deal_id)

    ext = Path(tg_file.file_name or "").suffix if msg.document else ".jpg"
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext)
    os.close(tmp_fd)
    logger.debug("Получен файл: %s", tg_file.file_name or tg_file.file_id)
    await tg_file.get_file().download_to_drive(tmp_path)

    dest = deal_path / Path(tmp_path).name
    os.replace(tmp_path, dest)
    await msg.reply_text("📂 Файл сохранён в папке сделки ✔️")
    logger.info("Saved file to %s", dest)


# ───────────── main ─────────────
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", h_start))
    app.add_handler(CallbackQueryHandler(h_get, pattern="^get$"))
    app.add_handler(CallbackQueryHandler(h_choose_client, pattern=r"^client:\d+$"))
    app.add_handler(CallbackQueryHandler(h_action, pattern=r"^(done|ret|reply):"))
    app.add_handler(CallbackQueryHandler(h_admin_action, pattern=r"^(accept|info|rework):"))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, h_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, h_text))

    logger.info("Telegram‑бот запущен внутри контейнера…")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
