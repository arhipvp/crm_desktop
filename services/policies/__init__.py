"""Удобные экспорты для сервисов полисов.

Пакет переэкспортирует часто используемые функции из
``services.policies.policy_service``. Это позволяет писать привычные
конструкции вроде ``from services.policies import add_policy`` и получать
доступ ко всем нужным утилитам, включая :func:`build_policy_query`,
которой пользуется слой интерфейса. Без такого экспорта при запуске
приложения возникала ``ImportError``.
"""

from .policy_service import (
    add_policy,
    update_policy,
    DuplicatePolicyError,
    build_policy_query,
    ContractorExpenseResult,
    add_contractor_expense,
    get_all_policies,
    get_policies_by_client_id,
    get_policies_by_deal_id,
    get_policies_page,
    get_policy_counts_by_deal_id,
    get_policy_by_number,
    get_policy_by_id,
    mark_policy_deleted,
    mark_policies_deleted,
    get_unique_policy_field_values,
    attach_premium,
)
from .deal_matching import (
    CandidateDeal,
    DealMatchProfile,
    PolicyMatchProfile,
    build_deal_match_index,
    collect_indirect_matches,
    find_candidate_deals,
    find_strict_matches,
    make_policy_profile,
)

__all__ = [
    "add_policy",
    "update_policy",
    "DuplicatePolicyError",
    "build_policy_query",
    "ContractorExpenseResult",
    "get_all_policies",
    "get_policies_by_client_id",
    "get_policies_by_deal_id",
    "get_policies_page",
    "get_policy_counts_by_deal_id",
    "get_policy_by_number",
    "get_policy_by_id",
    "mark_policy_deleted",
    "mark_policies_deleted",
    "get_unique_policy_field_values",
    "attach_premium",
    "add_contractor_expense",
    "CandidateDeal",
    "DealMatchProfile",
    "PolicyMatchProfile",
    "build_deal_match_index",
    "collect_indirect_matches",
    "find_candidate_deals",
    "find_strict_matches",
    "make_policy_profile",
]
