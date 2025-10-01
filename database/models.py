from datetime import datetime
from enum import Enum
from peewee import (
    Model,
    BigIntegerField,
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    DecimalField,
    ForeignKeyField,
    TextField,
)

from database.db import db


class BaseModel(Model):
    class Meta:
        database = db


class SoftDeleteModel(BaseModel):
    """Base with soft-delete support via is_deleted flag."""

    is_deleted = BooleanField(default=False)

    def soft_delete(self) -> None:
        """Mark instance as deleted without physical removal."""
        self.is_deleted = True
        self.save()

    @classmethod
    def active(cls):
        return cls.select().where(cls.is_deleted == False)


class Client(SoftDeleteModel):
    name = CharField(index=True)
    phone = CharField(null=True)
    email = CharField(null=True)
    is_company = BooleanField(default=False)
    note = TextField(null=True)
    drive_folder_path = CharField(null=True)
    drive_folder_link = CharField(null=True)

    def __str__(self) -> str:
        return self.name


class DealStatus(str, Enum):
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class DispatchState(str, Enum):
    IDLE = "idle"
    QUEUED = "queued"
    SENT = "sent"


class Deal(SoftDeleteModel):
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

    def __str__(self) -> str:
        client = self.client.name if self.client_id else ""
        return f"{client} — {self.description}"


class Policy(SoftDeleteModel):
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
    drive_folder_path = CharField(null=True)
    drive_folder_link = CharField(null=True)
    renewed_to = CharField(null=True)

    def __str__(self) -> str:
        client_name = self.client.name if self.client_id else ""
        return f"{client_name} — {self.policy_number}"


class Payment(SoftDeleteModel):
    policy = ForeignKeyField(Policy, backref="payments")
    amount = DecimalField(max_digits=12, decimal_places=2)
    payment_date = DateField()
    actual_payment_date = DateField(null=True)


class Task(SoftDeleteModel):
    # core
    title = CharField()
    due_date = DateField()
    deal = ForeignKeyField(Deal, null=True, backref="tasks")
    policy = ForeignKeyField(Policy, null=True, backref="tasks")
    note = TextField(null=True)

    # state
    is_done = BooleanField(default=False)

    # telegram
    dispatch_state = CharField(default=DispatchState.IDLE.value)
    queued_at = DateTimeField(null=True)
    tg_chat_id = BigIntegerField(null=True)
    tg_message_id = BigIntegerField(null=True)


class Income(SoftDeleteModel):
    payment = ForeignKeyField(Payment, backref="incomes")
    amount = DecimalField(max_digits=12, decimal_places=2)
    received_date = DateField(null=True)
    commission_source = CharField(null=True)
    note = TextField(null=True)


class Expense(SoftDeleteModel):
    payment = ForeignKeyField(Payment, backref="expenses")
    amount = DecimalField(max_digits=12, decimal_places=2)
    expense_type = CharField()
    expense_date = DateField(null=True)
    note = TextField(null=True)
    policy = ForeignKeyField(Policy, backref="expenses")


class Executor(BaseModel):
    full_name = CharField()
    tg_id = BigIntegerField(unique=True)
    is_active = BooleanField(default=True)


class DealExecutor(BaseModel):
    deal = ForeignKeyField(Deal, backref="executors")
    executor = ForeignKeyField(Executor, backref="deals")
    assigned_date = DateField()
    note = TextField(null=True)


class DealCalculation(SoftDeleteModel):
    deal = ForeignKeyField(Deal, backref="calc_entries")
    insurance_company = CharField(null=True)
    insurance_type = CharField(null=True)
    insured_amount = DecimalField(max_digits=12, decimal_places=2, null=True)
    premium = DecimalField(max_digits=12, decimal_places=2, null=True)
    deductible = DecimalField(max_digits=12, decimal_places=2, null=True)
    note = TextField(null=True)
    created_at = DateTimeField(default=datetime.utcnow)

