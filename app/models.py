from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    BigInteger,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .db import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    is_company = Column(Boolean, default=False)
    note = Column(Text, nullable=True)
    drive_folder_path = Column(String, nullable=True)
    drive_folder_link = Column(String, nullable=True)
    is_deleted = Column(Boolean, default=False)

    deals = relationship("Deal", back_populates="client")
    policies = relationship("Policy", back_populates="client")


class DealStatus:
    NEW = "новая"
    IN_PROGRESS = "в работе"
    SUCCESS = "успешна"
    FAILED = "отказ"


class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True)
    reminder_date = Column(Date, nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    status = Column(String, default=DealStatus.NEW)
    description = Column(Text, nullable=False)
    calculations = Column(Text, nullable=True)
    is_closed = Column(Boolean, default=False)
    closed_reason = Column(Text, nullable=True)
    drive_folder_path = Column(String, nullable=True)
    drive_folder_link = Column(String, nullable=True)
    start_date = Column(Date, nullable=False)
    is_deleted = Column(Boolean, default=False)

    client = relationship("Client", back_populates="deals")
    policies = relationship("Policy", back_populates="deal")
    tasks = relationship("Task", back_populates="deal")
    executors = relationship("DealExecutor", back_populates="deal")
    calc_entries = relationship("DealCalculation", back_populates="deal")


class Policy(Base):
    __tablename__ = "policies"
    __table_args__ = (UniqueConstraint("policy_number"),)

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=True)
    policy_number = Column(String, nullable=False)
    insurance_type = Column(String, nullable=True)
    insurance_company = Column(String, nullable=True)
    contractor = Column(String, nullable=True)
    sales_channel = Column(String, nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    vehicle_brand = Column(String, nullable=True)
    vehicle_model = Column(String, nullable=True)
    vehicle_vin = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    drive_folder_link = Column(String, nullable=True)
    renewed_to = Column(String, nullable=True)
    is_deleted = Column(Boolean, default=False)

    client = relationship("Client", back_populates="policies")
    deal = relationship("Deal", back_populates="policies")
    payments = relationship("Payment", back_populates="policy")
    tasks = relationship("Task", back_populates="policy")
    expenses = relationship("Expense", back_populates="policy")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_date = Column(Date, nullable=False)
    actual_payment_date = Column(Date, nullable=True)
    is_deleted = Column(Boolean, default=False)

    policy = relationship("Policy", back_populates="payments")
    incomes = relationship("Income", back_populates="payment")
    expenses = relationship("Expense", back_populates="payment")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    due_date = Column(Date, nullable=False)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=True)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=True)
    note = Column(Text, nullable=True)
    is_done = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    dispatch_state = Column(String, default="idle")
    queued_at = Column(DateTime, nullable=True)
    tg_chat_id = Column(BigInteger, nullable=True)
    tg_message_id = Column(BigInteger, nullable=True)

    deal = relationship("Deal", back_populates="tasks")
    policy = relationship("Policy", back_populates="tasks")


class Income(Base):
    __tablename__ = "incomes"

    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    amount = Column(Float, nullable=False)
    received_date = Column(Date, nullable=True)
    commission_source = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False)

    payment = relationship("Payment", back_populates="incomes")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    amount = Column(Float, nullable=False)
    expense_type = Column(String, nullable=False)
    expense_date = Column(Date, nullable=True)
    note = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=False)

    payment = relationship("Payment", back_populates="expenses")
    policy = relationship("Policy", back_populates="expenses")


class Executor(Base):
    __tablename__ = "executors"

    id = Column(Integer, primary_key=True)
    full_name = Column(String, nullable=False)
    tg_id = Column(BigInteger, unique=True)
    is_active = Column(Boolean, default=True)

    deals = relationship("DealExecutor", back_populates="executor")


class DealExecutor(Base):
    __tablename__ = "deal_executors"

    id = Column(Integer, primary_key=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=False)
    executor_id = Column(Integer, ForeignKey("executors.id"), nullable=False)
    assigned_date = Column(Date, nullable=False)
    note = Column(Text, nullable=True)

    deal = relationship("Deal", back_populates="executors")
    executor = relationship("Executor", back_populates="deals")


class DealCalculation(Base):
    __tablename__ = "deal_calculations"

    id = Column(Integer, primary_key=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=False)
    insurance_company = Column(String, nullable=True)
    insurance_type = Column(String, nullable=True)
    insured_amount = Column(Float, nullable=True)
    premium = Column(Float, nullable=True)
    deductible = Column(Float, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)

    deal = relationship("Deal", back_populates="calc_entries")
