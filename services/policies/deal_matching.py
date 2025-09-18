"""Профили для сопоставления сделок и полисов."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from datetime import date
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from playhouse.shortcuts import prefetch

from database.models import Client, Deal, Policy


def _normalize_string(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _normalize_vin(value: Optional[str]) -> Optional[str]:
    normalized = _normalize_string(value)
    if normalized is None:
        return None
    return re.sub(r"[^0-9a-z]", "", normalized)


def _normalize_phone(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    return digits or None


@dataclass
class PolicyMatchProfile:
    """Набор признаков отдельного полиса для сопоставления."""

    policy: Policy
    policy_number: str
    normalized_policy_number: Optional[str]
    vehicle_vin: Optional[str]
    normalized_vehicle_vin: Optional[str]
    contractor: Optional[str]
    normalized_contractor: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    drive_folder_link: Optional[str]


@dataclass
class DealMatchProfile:
    """Профиль сделки, агрегирующий признаки связанных полисов и клиента."""

    deal: Deal
    client: Client
    policy_profiles: List[PolicyMatchProfile] = field(default_factory=list)
    vins: Set[str] = field(default_factory=set)
    policy_numbers: Set[str] = field(default_factory=set)
    contractors: Set[str] = field(default_factory=set)
    policy_date_range: Tuple[Optional[date], Optional[date]] = (None, None)
    folder_paths: Set[str] = field(default_factory=set)
    client_phones: Set[str] = field(default_factory=set)
    client_emails: Set[str] = field(default_factory=set)


def make_policy_profile(policy: Policy) -> PolicyMatchProfile:
    """Построить профиль полиса с нормализованными значениями."""

    normalized_policy_number = _normalize_string(policy.policy_number)
    normalized_vin = _normalize_vin(policy.vehicle_vin)
    normalized_contractor = _normalize_string(policy.contractor)
    drive_link = policy.drive_folder_link.strip() if policy.drive_folder_link else None

    return PolicyMatchProfile(
        policy=policy,
        policy_number=policy.policy_number,
        normalized_policy_number=normalized_policy_number,
        vehicle_vin=policy.vehicle_vin,
        normalized_vehicle_vin=normalized_vin,
        contractor=policy.contractor,
        normalized_contractor=normalized_contractor,
        start_date=policy.start_date,
        end_date=policy.end_date,
        drive_folder_link=drive_link,
    )


def _collect_folder_paths(deal: Deal, client: Client, policy_profiles: Sequence[PolicyMatchProfile]) -> Set[str]:
    paths: Set[str] = set()
    candidates = [
        deal.drive_folder_path,
        deal.drive_folder_link,
        client.drive_folder_path,
        client.drive_folder_link,
    ]
    candidates.extend(profile.drive_folder_link for profile in policy_profiles)
    for value in candidates:
        if value:
            stripped = value.strip()
            if stripped:
                paths.add(stripped)
    return paths


def build_deal_match_index(deal_ids: Iterable[int] | None = None) -> Dict[int, DealMatchProfile]:
    """Собрать индексы сопоставления для сделок.

    Загружает сделки, их клиентов и связанные полисы, формируя удобные для
    сопоставления наборы признаков.
    """

    base_query = Deal.select().where(Deal.is_deleted == False)  # noqa: E712
    if deal_ids is not None:
        ids = list(deal_ids)
        if not ids:
            return {}
        base_query = base_query.where(Deal.id.in_(ids))

    deals = prefetch(base_query, Client, Policy)
    result: Dict[int, DealMatchProfile] = {}

    for deal in deals:
        client: Client = deal.client
        policy_profiles = [
            make_policy_profile(policy)
            for policy in deal.policies
            if getattr(policy, "is_deleted", False) is False
        ]

        vins = {p.normalized_vehicle_vin for p in policy_profiles if p.normalized_vehicle_vin}
        policy_numbers = {p.normalized_policy_number for p in policy_profiles if p.normalized_policy_number}
        contractors = {p.normalized_contractor for p in policy_profiles if p.normalized_contractor}

        start_dates = [p.start_date for p in policy_profiles if p.start_date]
        end_dates = [p.end_date for p in policy_profiles if p.end_date]
        policy_date_range = (
            min(start_dates) if start_dates else None,
            max(end_dates) if end_dates else None,
        )

        folder_paths = _collect_folder_paths(deal, client, policy_profiles)

        client_phones: Set[str] = set()
        client_emails: Set[str] = set()

        phone_normalized = _normalize_phone(client.phone)
        if phone_normalized:
            client_phones.add(phone_normalized)

        email_normalized = _normalize_string(client.email)
        if email_normalized:
            client_emails.add(email_normalized)

        result[deal.id] = DealMatchProfile(
            deal=deal,
            client=client,
            policy_profiles=policy_profiles,
            vins=vins,
            policy_numbers=policy_numbers,
            contractors=contractors,
            policy_date_range=policy_date_range,
            folder_paths=folder_paths,
            client_phones=client_phones,
            client_emails=client_emails,
        )

    return result

