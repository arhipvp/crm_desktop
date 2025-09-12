import pytest
from datetime import date

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


class TestIncome:
    @staticmethod
    def _create_income_for_executor(
        make_policy_with_payment, name: str, tg_id: int
    ) -> Income:
        client, deal, _policy, payment = make_policy_with_payment(
            client_kwargs={"name": f"Client {name}"},
            deal_kwargs={"description": f"Deal {name}"},
            policy_kwargs={"policy_number": f"P{name}"},
            payment_kwargs={"amount": 100},
        )
        income = Income.create(payment=payment, amount=100)
        executor = Executor.create(full_name=name, tg_id=tg_id)
        DealExecutor.create(
            deal=deal,
            executor=executor,
            assigned_date=date.today(),
        )
        return income

    @staticmethod
    def _make_income(contractor: str | None) -> Income:
        """Create an ``Income`` instance with an optional contractor."""

        policy = Policy(
            policy_number="123",
            contractor=contractor,
            start_date=date.today(),
        )
        payment = Payment(
            policy=policy,
            amount=100,
            payment_date=date.today(),
        )
        return Income(
            payment=payment,
            amount=10,
            received_date=date.today(),
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

    def test_filter_by_executor_full_name(self, in_memory_db, make_policy_with_payment):
        inc1 = self._create_income_for_executor(make_policy_with_payment, "Alice", 1)
        self._create_income_for_executor(make_policy_with_payment, "Bob", 2)
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
    def test_income_search_related_models(
        self, in_memory_db, make_policy_with_payment, search, expected
    ):
        _, _, _, pay1 = make_policy_with_payment(
            client_kwargs={"name": "Alice"},
            deal_kwargs={"description": "DealA"},
            policy_kwargs={"policy_number": "P1", "note": "NoteA"},
            payment_kwargs={"amount": 100},
        )
        Income.create(payment=pay1, amount=10)

        _, _, _, pay2 = make_policy_with_payment(
            client_kwargs={"name": "Bob"},
            deal_kwargs={"description": "DealB"},
            policy_kwargs={"policy_number": "P2", "note": "NoteB"},
            payment_kwargs={"amount": 200},
        )
        Income.create(payment=pay2, amount=20)

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
    def test_expense_search_related_models(
        self, in_memory_db, make_policy_with_payment, search, expected
    ):
        _, _, p1, pay1 = make_policy_with_payment(
            client_kwargs={"name": "Alice"},
            deal_kwargs={"description": "DealA"},
            policy_kwargs={"policy_number": "P1", "note": "NoteA"},
            payment_kwargs={"amount": 100},
        )
        Expense.create(payment=pay1, amount=10, expense_type="t", policy=p1)

        _, _, p2, pay2 = make_policy_with_payment(
            client_kwargs={"name": "Bob"},
            deal_kwargs={"description": "DealB"},
            policy_kwargs={"policy_number": "P2", "note": "NoteB"},
            payment_kwargs={"amount": 200},
        )
        Expense.create(payment=pay2, amount=20, expense_type="t", policy=p2)

        query = build_expense_query(search_text=search)
        results = list(query)
        assert [r.policy.policy_number for r in results] == [expected]

    def test_apply_expense_filters_field_keys(
        self, in_memory_db, make_policy_with_payment
    ):
        client = Client.create(name="C1")
        _, deal1, policy1, pay1 = make_policy_with_payment(
            client=client,
            deal_kwargs={"description": "D1"},
            policy_kwargs={"policy_number": "P1"},
            payment_kwargs={"amount": 100},
        )
        _, deal2, policy2, pay2 = make_policy_with_payment(
            client=client,
            deal_kwargs={"description": "D2"},
            policy_kwargs={"policy_number": "P2"},
            payment_kwargs={"amount": 200},
        )
        Expense.create(payment=pay1, amount=10, expense_type="t1", policy=policy1)
        Expense.create(payment=pay2, amount=20, expense_type="t1", policy=policy2)

        query = build_expense_query(column_filters={Deal.description: "D1"})
        results = list(query)
        assert len(results) == 1
        assert results[0].policy.policy_number == "P1"
