from peewee import *

from database.db import db


class BaseModel(Model):
    class Meta:
        database = db


# ─────────────────────────── Клиент ────────────────────────────
class Client(BaseModel):
    name = CharField()
    phone = CharField(null=True)
    email = CharField(null=True)
    is_company = BooleanField(default=False)
    note = TextField(null=True)
    drive_folder_path = CharField(null=True)  # локальный путь
    drive_folder_link = CharField(null=True)  # web-ссылка
    is_deleted = BooleanField(default=False)

    def __str__(self) -> str:  # ← NEW
        return self.name


# ─────────────────────────── Сделка ────────────────────────────
class DealStatus:
    NEW = "новая"
    IN_PROGRESS = "в работе"
    SUCCESS = "успешна"
    FAILED = "отказ"


class Deal(BaseModel):
    reminder_date = DateField(null=True)
    client = ForeignKeyField(Client, backref="deals")
    status = CharField(default=DealStatus.NEW)
    description = TextField()
    calculations = TextField(null=True)
    is_closed = BooleanField(default=False)
    closed_reason = TextField(null=True)
    drive_folder_path = CharField(null=True)
    drive_folder_link = CharField(null=True)
    start_date = DateField()
    is_deleted = BooleanField(default=False)

    def __str__(self) -> str:  # NEW
        client = self.client.name if self.client_id else "—"
        return f"{client} — {self.description}"


# ─────────────────────────── Полис ────────────────────────────
class Policy(BaseModel):
    client = ForeignKeyField(Client, backref="policies")
    deal = ForeignKeyField(Deal, backref="policies", null=True)
    policy_number = CharField(unique=True)
    insurance_type = CharField(null=True)
    insurance_company = CharField(null=True)
    contractor = CharField(null=True)
    sales_channel = CharField(null=True)
    start_date = DateField()
    end_date = DateField(null=True)
    vehicle_brand = CharField(null=True)
    vehicle_model = CharField(null=True)
    vehicle_vin = CharField(null=True)
    note = TextField(null=True)
    drive_folder_link = CharField(null=True)
    renewed_to = CharField(null=True)  # Содержит номер нового полиса или "Нет"
    is_deleted = BooleanField(default=False)

    def __str__(self) -> str:
        client_name = self.client.name if self.client_id else "—"
        return f"{client_name} — {self.policy_number}"


# ─────────────────────────── Платёж ────────────────────────────
class Payment(BaseModel):
    policy = ForeignKeyField(Policy, backref="payments")
    amount = FloatField()
    payment_date = DateField()
    actual_payment_date = DateField(null=True)
    is_deleted = BooleanField(default=False)


# ─────────────────────────── Задача ────────────────────────────
class Task(BaseModel):
    # --- контент ---
    title = CharField()
    due_date = DateField()
    deal = ForeignKeyField(Deal, null=True, backref="tasks")
    policy = ForeignKeyField(Policy, null=True, backref="tasks")
    note = TextField(null=True)

    # --- статусы / удаления ---
    is_done = BooleanField(default=False)
    is_deleted = BooleanField(default=False)

    # --- очередь / Telegram (NEW) ---
    dispatch_state = CharField(default="idle")  # idle | queued | sent
    queued_at = DateTimeField(null=True)  # когда поставили в очередь
    tg_chat_id = BigIntegerField(null=True)  # кому выдали
    tg_message_id = BigIntegerField(null=True)  # id сообщения в TG


# ─────────────────────────── Доход ────────────────────────────
class Income(BaseModel):
    payment = ForeignKeyField(Payment, backref="incomes")
    amount = FloatField()
    received_date = DateField(null=True)  # None ⇒ ожидается
    commission_source = CharField(null=True)
    note = TextField(null=True)
    is_deleted = BooleanField(default=False)


# ─────────────────────────── Расход ────────────────────────────
class Expense(BaseModel):
    payment = ForeignKeyField(Payment, backref="expenses")
    amount = FloatField()
    expense_type = CharField()
    expense_date = DateField(null=True)  # None ⇒ ожидается
    note = TextField(null=True)
    is_deleted = BooleanField(default=False)
    policy = ForeignKeyField(Policy, backref="expenses")


# ─────────────────────────── Исполнитель ────────────────────────────
class Executor(BaseModel):
    """Telegram-пользователь, который может выполнять задачи."""

    tg_id = BigIntegerField(primary_key=True)
    full_name = CharField(null=True)
    is_approved = BooleanField(default=False)
