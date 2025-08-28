"""Policies package convenient exports.

This package re-exports frequently used functions from
``services.policies.policy_service`` so existing imports like
``from services.policies import add_policy`` keep working.
"""

from .policy_service import (
    add_policy,
    update_policy,
    DuplicatePolicyError,
    build_policy_query,
    get_all_policies,
    get_policies_by_client_id,
    get_policies_by_deal_id,
    get_policies_page,
    get_policy_counts_by_deal_id,
    get_policy_by_number,
    get_policy_by_id,
    mark_policy_deleted,
    mark_policies_deleted,
    mark_policy_renewed,
    mark_policies_renewed,
    get_unique_policy_field_values,
    attach_premium,
)

__all__ = [
    "add_policy",
    "update_policy",
    "DuplicatePolicyError",
    "build_policy_query",
    "get_all_policies",
    "get_policies_by_client_id",
    "get_policies_by_deal_id",
    "get_policies_page",
    "get_policy_counts_by_deal_id",
    "get_policy_by_number",
    "get_policy_by_id",
    "mark_policy_deleted",
    "mark_policies_deleted",
    "mark_policy_renewed",
    "mark_policies_renewed",
    "get_unique_policy_field_values",
    "attach_premium",
]
