"""
Telegram‑бот для очереди задач CRM_desktop.
Контейнер запускает именно этот файл.
Бот забирает токен из .env (том монтируется в контейнер).
Теперь поддерживает приём документов и фотографий в ответ на сообщение сделки — файл сохраняется в папку сделки на диске.
"""
from database.init import init_from_env

import os, re, datetime as _dt, tempfile
from dotenv import load_dotenv
from pathlib import Path
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ForceReply, Update, constants,
)
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    MessageHandler, ContextTypes, filters,
)

# ───────────── env ─────────────
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
init_from_env()

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TG_BOT_TOKEN не найден. Укажите его в .env")

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
    return InlineKeyboardMarkup([[ 
        InlineKeyboardButton("✅ Выполнить", callback_data=f"done:{tid}"),
        InlineKeyboardButton("💬 Ответить",  callback_data=f"reply:{tid}"),
        InlineKeyboardButton("🔄 Вернуть",   callback_data=f"ret:{tid}"),
    ]])

# ───────────── handlers ─────────────
async def h_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📥 Получить задачу", callback_data="get")]])
    await update.message.reply_text(
        "Привет! Я бот CRM. Нажми кнопку, чтобы взять следующую задачу.",
        reply_markup=kb,
    )

async def h_get(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    task = ts.pop_next(q.from_user.id)
    if not task:
        return await q.answer("Очередь пуста 💤", show_alert=True)

    msg = await q.message.reply_html(fmt_task(task), reply_markup=kb_task(task.id))
    ts.link_telegram(task.id, msg.chat_id, msg.message_id)

async def h_action(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    action, tid = q.data.split(":")
    tid = int(tid)

    if action == "done":
        ts.unassign_from_telegram(tid)
        await q.message.edit_text("✅ Задача скрыта из очереди", parse_mode=constants.ParseMode.HTML)

    elif action == "ret":
        ts.return_to_queue(tid)
        await q.message.edit_text("🔄 <i>Задача возвращена в очередь</i>", parse_mode=constants.ParseMode.HTML)

    elif action == "reply":
        await q.message.reply_text(
            f"Напишите комментарий к задаче #{tid}:",
            reply_markup=ForceReply(selective=True),
        )

async def h_text(update: Update, _ctx):
    if not update.message.reply_to_message:
        return
    m = re.search(r"#(\d+)", update.message.reply_to_message.text_html or "")
    if not m:
        return
    tid = int(m.group(1))
    stamp = _dt.datetime.now().strftime("%d.%m %H:%M")
    ts.append_note(tid, f"[TG {stamp}] {update.message.text}")
    await update.message.reply_text("Комментарий сохранён 👍")

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

    ext = Path(tg_file.file_name or "").suffix if msg.document else ".jpg"
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext)
    os.close(tmp_fd)
    print(f"[DEBUG] Получен файл: {tg_file.file_name or tg_file.file_id}")
    await tg_file.get_file().download_to_drive(tmp_path)

    dest = deal_path / Path(tmp_path).name
    os.replace(tmp_path, dest)
    await msg.reply_text("📂 Файл сохранён в папке сделки ✔️")

# ───────────── main ─────────────
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", h_start))
    app.add_handler(CallbackQueryHandler(h_get, pattern="^get$"))
    app.add_handler(CallbackQueryHandler(h_action, pattern=r"^(done|ret|reply):"))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, h_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, h_text))

    print("Telegram‑бот запущен внутри контейнера…")
    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
