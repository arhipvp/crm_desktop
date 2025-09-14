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
from services.validators import normalize_number
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


def _parse_float(text: str) -> float | None:
    """Преобразовать ввод пользователя в число."""
    if not text:
        return None
    text = (
        text.lower()
        .replace("руб", "")
        .replace("р.", "")
        .replace("р", "")
    )
    text = normalize_number(text)
    try:
        return float(text)
    except ValueError:
        return None


def _parse_calc_line(line: str) -> dict:
    """Преобразовать строку расчёта в словарь полей."""
    parts = [p.strip() for p in line.split(",")]
    while len(parts) < 6:
        parts.append("")
    company, ins_type, insured_amount, premium, deductible, note = parts[:6]
    return {
        "insurance_company": company or None,
        "insurance_type": ins_type or None,
        "insured_amount": _parse_float(insured_amount),
        "premium": _parse_float(premium),
        "deductible": _parse_float(deductible),
        "note": note or None,
    }

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

APPROVED_EXECUTOR_IDS: set[int] = set()
for part in re.split(r"[ ,]+", os.getenv("APPROVED_EXECUTOR_IDS", "").strip()):
    if not part:
        continue
    try:
        APPROVED_EXECUTOR_IDS.add(int(part))
    except ValueError:
        logging.getLogger(__name__).warning(
            "Некорректный id исполнителя: %s", part
        )

logger = logging.getLogger(__name__)

# Допустимые параметры загружаемых файлов
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png"}

# Задачи, ожидающие подтверждения администратора.
# Храним чат исполнителя и его имя для уведомлений.
pending_accept: dict[int, tuple[int, str]] = {}
pending_users: dict[int, tuple[int, str]] = {}
# Ожидаем ввод расчёта одной строкой
pending_calc: dict[int, int] = {}

# ───────────── imports из core ─────────────
from database.models import Task
import services.task_crud as tc
import services.task_queue as tq
import services.task_notifications as tn
from services import executor_service as es
from services.clients import client_service as cs
from services import calculation_service as calc_s
from services.deal_service import get_deal_by_id

es.ensure_executors_from_env()


# ───────────── helpers ─────────────
def fmt_task(t: Task) -> str:
    due = t.due_date.strftime("%d.%m.%Y") if t.due_date else "—"
    lines = [f"📌 <b>Задача #{t.id}</b> (до <b>{due}</b>)", t.title.strip()]

    d = getattr(t, "deal", None)
    if d:
        desc = f" — {d.description.strip()}" if d.description else ""
        lines.append(f"\n🔗 <b>Сделка #{d.id}</b>{desc}")
        if d.start_date:
            lines.append(f"📅 Дата: {d.start_date.strftime('%d.%m.%Y')}")

        c = getattr(d, "client", None)
        if c:
            lines.append(f"👤 Клиент: {c.name}")
            folder = d.drive_folder_path or c.drive_folder_path
            if folder:
                lines.append(f"📂 {folder}")

        lines.append("\n<b>Журнал:</b>")
        if d.calculations:
            calc = escape(d.calculations)
            lines.append(f"<pre>{calc}</pre>")
        else:
            lines.append("—")

    p = getattr(t, "policy", None)
    if p:
        lines.append(f"\n📄 <b>Полис id={p.id} №{p.policy_number}</b>")
        lines.append(f"Тип: {p.insurance_type}")
        if p.client:
            lines.append(f"👤 Страхователь: {p.client.name}")

    if t.note:
        lines.append(f"\n📝 {t.note.strip()}")

    from services.sheets_service import tasks_sheet_url
    url = tasks_sheet_url()
    if url:
        lines.append(f"\n<a href=\"{url}\">📊 Таблица задач</a>")

    return "\n".join(lines)


def fmt_task_short(t: Task) -> str:
    """Краткое описание задачи: заголовок и сделка."""
    d = getattr(t, "deal", None)
    if d:
        desc = d.description.strip() if d.description else ""
        return f"• {t.title.strip()} — #{d.id} {desc}"
    return f"• {t.title.strip()}"


def kb_task(tid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Выполнить", callback_data=f"done:{tid}"),
                InlineKeyboardButton("💬 Ответить", callback_data=f"reply:{tid}"),
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


async def notify_admin(
    bot, tid: int, user_text: str | None = None, executor: str | None = None
):
    """Отправить администратору информацию о задаче."""
    if not ADMIN_CHAT_ID:
        return
    task = Task.get_or_none(Task.id == tid)
    if not task:
        return
    text = fmt_task(task)
    if executor:
        text += f"\n\nИсполнитель: {executor}"
    if user_text:
        text += f"\n\n{user_text}"
    logger.info("Уведомляем администратора о %s", tid)
    await bot.send_message(
        ADMIN_CHAT_ID,
        text,
        reply_markup=kb_admin(tid),
        parse_mode=constants.ParseMode.HTML,
    )


def kb_user(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Согласовать", callback_data=f"approve_exec:{uid}"),
                InlineKeyboardButton("❌ Отказать", callback_data=f"deny_exec:{uid}"),
            ]
        ]
    )


async def notify_admin_user(bot, uid: int, name: str):
    if not ADMIN_CHAT_ID:
        return
    text = f"Запрос на доступ от {name} ({uid})"
    logger.info("Уведомляем администратора об исполнителе %s", uid)
    await bot.send_message(ADMIN_CHAT_ID, text, reply_markup=kb_user(uid))






# ───────────── handlers ─────────────
async def h_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /start от %s", update.effective_user.id)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📂 Мои сделки", callback_data="deals")],
            [InlineKeyboardButton("📋 Мои задачи", callback_data="tasks")],
        ]
    )
    await update.message.reply_text(
        "Привет! Я бот CRM. Нажмите кнопку, чтобы посмотреть свои сделки.",
        reply_markup=kb,
    )


async def h_show_deals(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    logger.info("Действие '%s' от %s", q.data, q.from_user.id)
    logger.info("%s запросил сделки", q.from_user.id)

    user_id = q.from_user.id
    user_name = q.from_user.full_name or ("@" + q.from_user.username) if q.from_user.username else str(user_id)
    es.ensure_executor(user_id, user_name)
    if not es.is_approved(user_id):
        if user_id in APPROVED_EXECUTOR_IDS:
            es.approve_executor(user_id)
        else:
            if user_id not in pending_users:
                pending_users[user_id] = (q.message.chat_id, user_name)
                await notify_admin_user(_ctx.bot, user_id, user_name)
            return await q.answer(
                "⏳ Ожидайте одобрения администратора",
                show_alert=True,
            )

    deals = es.get_deals_for_executor(user_id)
    if not deals:
        await q.answer()
        await q.message.reply_text("Нет назначенных сделок")
        return

    buttons = []
    for d in deals:
        tasks_count = len(tc.get_incomplete_tasks_by_deal(d.id))
        text = (
            f"#{d.id} "
            f"{(d.client.name.split()[0] + ' ') if d.client and d.client.name else ''}"
            f"{d.description.split()[0]}"
        )
        text += f" ({tasks_count})"
        buttons.append(
            [InlineKeyboardButton(text, callback_data=f"deal:{d.id}")]
        )
    
    kb = InlineKeyboardMarkup(buttons)

    await q.message.reply_html("Выберите сделку:", reply_markup=kb)


async def h_choose_client(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    logger.info("%s выбрал клиента", q.from_user.id)

    if not es.is_approved(q.from_user.id):
        return await q.answer("⏳ Ожидайте одобрения администратора", show_alert=True)

    _p, cid = q.data.split(":")
    cid = int(cid)

    deals = tq.get_deals_with_queued_tasks(cid)
    if not deals:
        await q.answer()
        await q.message.reply_text("Нет задач по сделкам")
        return

    client = cs.get_client_by_id(cid)
    surname = client.name.split()[0] if client and client.name else ""
    buttons = [
        [InlineKeyboardButton(d.description.split()[0], callback_data=f"deal:{d.id}")]
        for d in deals
    ]
    kb = InlineKeyboardMarkup(buttons)

    info_lines = []
    for d in deals:
        calc = escape(d.calculations) if d.calculations else "журнал пуст"
        info_lines.append(f"<b>{d.description}</b>\n<pre>{calc}</pre>")
    info = "\n\n".join(info_lines)

    await q.message.reply_html(
        f"Выберите сделку клиента {surname}:\n{info}", reply_markup=kb
    )


async def h_choose_deal(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    logger.info("%s выбрал сделку", q.from_user.id)

    if not es.is_approved(q.from_user.id):
        return await q.answer("⏳ Ожидайте одобрения администратора", show_alert=True)

    _p, did = q.data.split(":")
    did = int(did)

    tasks = tc.get_incomplete_tasks_by_deal(did)
    if not tasks:
        await q.answer()
        await q.message.reply_text("Нет задач")
        return

    buttons = [
        [InlineKeyboardButton(t.title.split()[0], callback_data=f"task:{t.id}")]
        for t in tasks
    ]
    kb = InlineKeyboardMarkup(buttons)

    await q.message.reply_text("Выберите задачу:", reply_markup=kb)


async def h_choose_task(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if not es.is_approved(q.from_user.id):
        return await q.answer("⏳ Ожидайте одобрения администратора", show_alert=True)

    _p, tid = q.data.split(":")
    tid = int(tid)

    task = tq.pop_task_by_id(q.message.chat_id, tid)
    if not task:
        task = tc.get_incomplete_task(tid)
        if not task:
            return await q.answer("Задача не найдена", show_alert=True)

    msg = await q.message.reply_html(
        fmt_task(task), reply_markup=kb_task(task.id)
    )
    tn.link_telegram(task.id, msg.chat_id, msg.message_id)


async def h_action(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    action, tid = q.data.split(":")
    tid = int(tid)

    if action == "done":
        tn.mark_done(tid)
        await q.message.edit_text(
            "✅ Задача выполнена", parse_mode=constants.ParseMode.HTML
        )
        logger.info("Задача %s отмечена исполнителем как выполненная", tid)

    elif action == "reply":
        await q.message.reply_text(
            f"Напишите комментарий к задаче #{tid}:",
            reply_markup=ForceReply(selective=True),
        )
        logger.info("Ожидание комментария по задаче %s", tid)


async def h_admin_action(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    logger.info("Действие администратора '%s'", q.data)

    action, tid = q.data.split(":")
    tid = int(tid)

    if action == "accept":
        task = Task.get_or_none(Task.id == tid)
        if task and not task.is_done:
            tn.mark_done(tid)
        await q.message.edit_text(
            "✅ Задача подтверждена", parse_mode=constants.ParseMode.HTML
        )
        info = pending_accept.pop(tid, None)
        chat_id = info[0] if isinstance(info, tuple) else info
        if chat_id:
            await _ctx.bot.send_message(chat_id, "Задача принята")
        logger.info("Задача %s принята", tid)
    elif action == "info":
        await q.message.reply_text(
            f"Введите информацию для задачи #{tid}:",
            reply_markup=ForceReply(selective=True),
        )
        logger.info("Запрос информации по задаче %s", tid)
    elif action == "rework":
        tq.queue_task(tid)
        await q.message.edit_text(
            "↩ Задача возвращена на доработку",
            parse_mode=constants.ParseMode.HTML,
        )
        await q.message.reply_text(
            f"Прокомментируйте задачу #{tid}:",
            reply_markup=ForceReply(selective=True),
        )
        logger.info("Задача %s возвращена на доработку", tid)
    elif action == "approve_exec":
        es.approve_executor(tid)
        info = pending_users.pop(tid, None)
        chat_id = info[0] if isinstance(info, tuple) else info
        await q.message.edit_text("Исполнитель подтверждён")
        if chat_id:
            await _ctx.bot.send_message(chat_id, "Вы одобрены. Можно брать задачи")
        logger.info("Исполнитель id=%s одобрен", tid)
    elif action == "deny_exec":
        info = pending_users.pop(tid, None)
        chat_id = info[0] if isinstance(info, tuple) else info
        await q.message.edit_text("Запрос отклонён")
        if chat_id:
            await _ctx.bot.send_message(chat_id, "Администратор отклонил доступ")
        logger.info("Исполнителю %s отказано", tid)


async def h_task_button(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    action, tid = q.data.split(":")
    tid = int(tid)

    if action == "task_done":
        task = Task.get_or_none(Task.id == tid)
        if task and not task.is_done:
            tn.mark_done(tid)
        await q.message.edit_text(
            "✅ Задача выполнена", parse_mode=constants.ParseMode.HTML
        )
    elif action == "question":
        await q.message.reply_text(
            f"Напишите вопрос по задаче #{tid}:",
            reply_markup=ForceReply(selective=True),
        )
    elif action == "calc":
        pending_calc[q.from_user.id] = tid
        await q.message.reply_text(
            f"Введите расчёт для задачи #{tid} в формате:\n"
            "Страховая компания, вид страхования, страховая сумма, "
            "страховая премия, франшиза, комментарий.\n"
            "Можно отправить несколько строк, каждый расчёт с новой строки.",
            reply_markup=ForceReply(selective=True),
        )


async def h_text(update: Update, _ctx):
    user_id = update.effective_user.id
    if user_id in pending_calc:
        tid = pending_calc.pop(user_id)
        lines = [l.strip() for l in update.message.text.splitlines() if l.strip()]
        task = Task.get_or_none(Task.id == tid)
        if not task or not task.deal_id:
            await update.message.reply_text("⚠️ Сделка не найдена")
            return
        saved: list[calc_s.DealCalculation] = []
        for line in lines:
            data = _parse_calc_line(line)
            if not data.get("insurance_company") or data.get("premium") is None:
                await update.message.reply_text(
                    "⚠️ Расчёт не сохранён: укажите страховую компанию и премию.\n"
                    "Формат: Страховая компания, вид страхования, страховая сумма, "
                    "страховая премия, франшиза, комментарий."
                )
                continue
            try:
                calc = calc_s.add_calculation(task.deal_id, **data)
            except Exception as e:  # pragma: no cover - log unexpected
                logger.exception("Не удалось добавить расчёт для %s", tid)
                await update.message.reply_text(f"⚠️ Ошибка сохранения: {e}")
                continue
            saved.append(calc)
        if saved:
            lines = ["Расчёты сохранены:"] + [calc_s.format_calculation(c) for c in saved]
            await update.message.reply_text("\n".join(lines) + " 👍")
            logger.info("Для %s добавлено расчётов: %s", tid, len(saved))
        return

    if not update.message.reply_to_message:
        return

    reply_txt = update.message.reply_to_message.text_html or ""
    m = re.search(r"#(\d+)", reply_txt)
    if not m:
        return
    tid = int(m.group(1))
    logger.info("Текстовый ответ по %s от %s", tid, update.message.chat_id)
    stamp = now_str()
    user_name = (
        update.effective_user.full_name
        or ("@" + update.effective_user.username)
        if update.effective_user.username
        else str(update.effective_user.id)
    )

    tn.append_note(tid, f"[TG {stamp}] {user_name}: {update.message.text}")
    await update.message.reply_text("Комментарий сохранён 👍")
    logger.info("Заметка добавлена к %s", tid)
    if update.message.chat_id != ADMIN_CHAT_ID:
        await notify_admin(_ctx.bot, tid, update.message.text, executor=user_name)


async def h_file(update: Update, _ctx):
    msg = update.message
    if not msg or not msg.reply_to_message:
        return

    m = re.search(r"Сделка\s+#(\d+)", msg.reply_to_message.text_html or "")
    if not m:
        return

    deal_id = int(m.group(1))
    deal = get_deal_by_id(deal_id)
    if not deal or not deal.drive_folder_path:
        return await msg.reply_text("⚠️ Папка сделки не найдена.")

    deal_path = Path(deal.drive_folder_path)
    deal_path.mkdir(parents=True, exist_ok=True)

    tg_file = msg.document or (msg.photo[-1] if msg.photo else None)
    if not tg_file:
        await msg.reply_text("⚠️ Не удалось определить файл.")
        return
    logger.info("Файл от %s для сделки %s", msg.chat_id, deal_id)

    ext = Path(tg_file.file_name or "").suffix.lower() if msg.document else ".jpg"
    if tg_file.file_size and tg_file.file_size > MAX_FILE_SIZE:
        await msg.reply_text("⚠️ Файл слишком большой.")
        return
    if ext not in ALLOWED_SUFFIXES:
        await msg.reply_text("⚠️ Недопустимый тип файла.")
        return
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext)
    os.close(tmp_fd)
    logger.debug("Получен файл: %s", tg_file.file_name or tg_file.file_id)
    await tg_file.get_file().download_to_drive(tmp_path)

    dest = deal_path / Path(tmp_path).name
    os.replace(tmp_path, dest)
    await msg.reply_text("📂 Файл сохранён в папке сделки ✔️")
    logger.info("Файл сохранён в %s", dest)


async def h_show_tasks(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not es.is_approved(user_id):
        return await update.message.reply_text("⏳ Ожидайте одобрения администратора")
    tasks = tc.get_incomplete_tasks_for_executor(user_id)
    if not tasks:
        await update.message.reply_text("Нет незавершенных задач")
        return
    for t in tasks:
        msg = await update.message.reply_html(
            fmt_task(t), reply_markup=kb_task(t.id)
        )
        tn.link_telegram(t.id, msg.chat_id, msg.message_id)

async def h_show_tasks_button(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    if not es.is_approved(user_id):
        return await q.message.reply_text("⏳ Ожидайте одобрения администратора")
    tasks = tc.get_incomplete_tasks_for_executor(user_id)
    if not tasks:
        await q.message.reply_text("Нет незавершенных задач")
        return

    lines = [fmt_task_short(t) for t in tasks]
    await q.message.reply_text("\n".join(lines))


async def send_pending_tasks(_ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправить исполнителям задачи из очереди."""
    tasks = tq.get_all_queued_tasks()
    for t in tasks:
        if not t.deal_id:
            continue
        ex = es.get_executor_for_deal(t.deal_id)
        if not ex or not es.is_approved(ex.tg_id):
            continue
        popped = tq.pop_task_by_id(ex.tg_id, t.id)
        if not popped:
            continue
        msg = await _ctx.bot.send_message(
            chat_id=ex.tg_id,
            text=fmt_task(popped),
            reply_markup=kb_task(popped.id),
            parse_mode=constants.ParseMode.HTML,
        )
        tn.link_telegram(popped.id, msg.chat_id, msg.message_id)


# ───────────── main ─────────────
async def _start_dispatcher(app: Application) -> None:
    """Schedule periodic sending of pending tasks."""
    if app.job_queue:
        app.job_queue.run_repeating(send_pending_tasks, interval=60)
    else:
        import asyncio, types

        async def loop() -> None:
            ctx = types.SimpleNamespace(bot=app.bot)
            while True:
                await send_pending_tasks(ctx)
                await asyncio.sleep(60)

        app.create_task(loop())


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).post_init(_start_dispatcher).build()

    app.add_handler(CommandHandler("start", h_start))
    app.add_handler(CallbackQueryHandler(h_show_deals, pattern="^deals$"))
    app.add_handler(CallbackQueryHandler(h_choose_client, pattern=r"^client:\d+$"))
    app.add_handler(CallbackQueryHandler(h_choose_deal, pattern=r"^deal:\d+$"))
    app.add_handler(CallbackQueryHandler(h_choose_task, pattern=r"^task:\d+$"))
    app.add_handler(CallbackQueryHandler(h_action, pattern=r"^(done|reply):"))
    app.add_handler(CallbackQueryHandler(h_admin_action, pattern=r"^(accept|info|rework|approve_exec|deny_exec):"))
    app.add_handler(CallbackQueryHandler(h_task_button, pattern=r"^(task_done|calc|question):"))
    app.add_handler(CallbackQueryHandler(h_show_tasks_button, pattern="^tasks$"))
    app.add_handler(CommandHandler("tasks", h_show_tasks))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, h_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, h_text))

    logger.info("Telegram‑бот запущен внутри контейнера…")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
