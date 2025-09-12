import datetime
import pytest

from database.models import (
    Client,
    Policy,
    Executor,
    Deal,
    Payment,
    Income,
    DealExecutor,
    Expense,
)
from services.income_service import get_incomes_page, get_income_highlight_color
from services.expense_service import build_expense_query


TODAY = datetime.date(2024, 1, 1)


class TestIncome:
    @staticmethod
    def _create_income_for_executor(name: str, tg_id: int) -> Income:
        client = Client.create(name=f"Client {name}")
        deal = Deal.create(
            client=client,
            description=f"Deal {name}",
            start_date=TODAY,
        )
        policy = Policy.create(
            client=client,
            deal=deal,
            policy_number=f"P{name}",
            start_date=TODAY,
        )
        payment = Payment.create(
            policy=policy,
            amount=100,
            payment_date=TODAY,
        )
        income = Income.create(payment=payment, amount=100)
        executor = Executor.create(full_name=name, tg_id=tg_id)
        DealExecutor.create(
            deal=deal,
            executor=executor,
            assigned_date=TODAY,
        )
        return income

    @staticmethod
    def _make_income(contractor: str | None) -> Income:
        """Create an ``Income`` instance with an optional contractor."""

        policy = Policy(
            policy_number="123",
            contractor=contractor,
            start_date=TODAY,
        )
        payment = Payment(
            policy=policy,
            amount=100,
            payment_date=TODAY,
        )
        return Income(
            payment=payment,
            amount=10,
            received_date=TODAY,
        )

    @pytest.mark.parametrize(
        "contractor, expected_color",
        [
            ("Some Corp", "#ffcccc"),
            (None, None),
        ],
    )
    def test_income_highlight(self, contractor, expected_color):
        income = self._make_income(contractor)
        assert get_income_highlight_color(income) == expected_color

    def test_filter_by_executor_full_name(self, in_memory_db):
        inc1 = self._create_income_for_executor("Alice", 1)
        self._create_income_for_executor("Bob", 2)
        result = list(
            get_incomes_page(
                page=1,
                per_page=10,
                column_filters={Executor.full_name: "Alice"},
            )
        )
        assert len(result) == 1
        assert result[0].id == inc1.id

    @pytest.mark.parametrize(
        "search, expected",
        [
            ("P1", "P1"),
            ("Alice", "P1"),
            ("DealA", "P1"),
            ("NoteA", "P1"),
        ],
    )
    def test_income_search_related_models(self, in_memory_db, search, expected):
        client1 = Client.create(name="Alice")
        deal1 = Deal.create(
            client=client1, description="DealA", start_date=TODAY
        )
        policy1 = Policy.create(
            client=client1,
            deal=deal1,
            policy_number="P1",
            start_date=TODAY,
            note="NoteA",
        )
        payment1 = Payment.create(
            policy=policy1, amount=100, payment_date=TODAY
        )
        Income.create(payment=payment1, amount=10)

        client2 = Client.create(name="Bob")
        deal2 = Deal.create(
            client=client2, description="DealB", start_date=TODAY
        )
        policy2 = Policy.create(
            client=client2,
            deal=deal2,
            policy_number="P2",
            start_date=TODAY,
            note="NoteB",
        )
        payment2 = Payment.create(
            policy=policy2, amount=200, payment_date=TODAY
        )
        Income.create(payment=payment2, amount=20)

        query = get_incomes_page(page=1, per_page=10, search_text=search)
        results = list(query)
        assert [r.payment.policy.policy_number for r in results] == [expected]


class TestExpense:
    @pytest.mark.parametrize(
        "search, expected",
        [
            ("P1", "P1"),
            ("Alice", "P1"),
            ("DealA", "P1"),
            ("NoteA", "P1"),
        ],
    )
    def test_expense_search_related_models(self, in_memory_db, search, expected):
        client1 = Client.create(name="Alice")
        deal1 = Deal.create(
            client=client1, description="DealA", start_date=TODAY
        )
        policy1 = Policy.create(
            client=client1,
            deal=deal1,
            policy_number="P1",
            start_date=TODAY,
            note="NoteA",
        )
        payment1 = Payment.create(
            policy=policy1, amount=100, payment_date=TODAY
        )
        Expense.create(
            payment=payment1, amount=10, expense_type="t", policy=policy1
        )

        client2 = Client.create(name="Bob")
        deal2 = Deal.create(
            client=client2, description="DealB", start_date=TODAY
        )
        policy2 = Policy.create(
            client=client2,
            deal=deal2,
            policy_number="P2",
            start_date=TODAY,
            note="NoteB",
        )
        payment2 = Payment.create(
            policy=policy2, amount=200, payment_date=TODAY
        )
        Expense.create(
            payment=payment2, amount=20, expense_type="t", policy=policy2
        )

        query = build_expense_query(search_text=search)
        results = list(query)
        assert [r.policy.policy_number for r in results] == [expected]

    def test_apply_expense_filters_field_keys(self, in_memory_db):
        client = Client.create(name="C1")
        deal1 = Deal.create(client=client, description="D1", start_date=TODAY)
        deal2 = Deal.create(client=client, description="D2", start_date=TODAY)
        policy1 = Policy.create(
            client=client, deal=deal1, policy_number="P1", start_date=TODAY
        )
        policy2 = Policy.create(
            client=client, deal=deal2, policy_number="P2", start_date=TODAY
        )
        payment1 = Payment.create(
            policy=policy1, amount=100, payment_date=TODAY
        )
        payment2 = Payment.create(
            policy=policy2, amount=200, payment_date=TODAY
        )
        Expense.create(payment=payment1, amount=10, expense_type="t1", policy=policy1)
        Expense.create(payment=payment2, amount=20, expense_type="t1", policy=policy2)

        query = build_expense_query(column_filters={Deal.description: "D1"})
        results = list(query)
        assert len(results) == 1
        assert results[0].policy.policy_number == "P1"
