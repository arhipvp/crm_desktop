"""Профили для сопоставления сделок и полисов."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
import re
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from playhouse.shortcuts import prefetch

from database.models import Client, Deal, Expense, Policy


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


def _normalize_policy_number_for_match(value: Optional[str]) -> Optional[str]:
    normalized = _normalize_string(value)
    if normalized is None:
        return None
    compact = re.sub(r"[^0-9a-zа-яё]", "", normalized)
    return compact or None


def _normalize_text_for_match(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.lower()
    compact = re.sub(r"[^0-9a-zа-яё]", "", normalized)
    return compact or None


def _is_subpath(child: str, parent: str) -> bool:
    child_clean = child.strip().rstrip("/")
    parent_clean = parent.strip().rstrip("/")
    if not parent_clean:
        return False
    if child_clean == parent_clean:
        return True
    return child_clean.startswith(parent_clean + "/")


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
    client_phones: Set[str] = field(default_factory=set)
    client_emails: Set[str] = field(default_factory=set)
    contractors: Set[str] = field(default_factory=set)
    brand_model_pairs: Set[Tuple[str, str]] = field(default_factory=set)
    min_start: Optional[date] = None
    max_end: Optional[date] = None
    insurance_companies: Set[str] = field(default_factory=set)
    insurance_types: Set[str] = field(default_factory=set)
    sales_channels: Set[str] = field(default_factory=set)


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
    brand_model_pairs: Set[Tuple[str, str]] = field(default_factory=set)
    min_start: Optional[date] = None
    max_end: Optional[date] = None
    insurance_companies: Set[str] = field(default_factory=set)
    insurance_types: Set[str] = field(default_factory=set)
    sales_channels: Set[str] = field(default_factory=set)
    expense_contractors: Set[str] = field(default_factory=set)


@dataclass
class CandidateDeal:
    """Результат строгого сопоставления полиса со сделкой."""

    deal_id: int
    score: float = 1.0
    reasons: List[str] = field(default_factory=list)


PHONE_MATCH_WEIGHT = 0.6
EMAIL_MATCH_WEIGHT = 0.6
CONTRACTOR_NAME_WEIGHT = 0.5
BRAND_MODEL_DATE_WEIGHT = 0.5
INSURANCE_CHANNEL_WEIGHT = 0.5
EXPENSE_CONTRACTOR_WEIGHT = 0.3
CONTRACTOR_SIMILARITY_THRESHOLD = 0.8
DATE_DIFF_TOLERANCE_DAYS = 30


def make_policy_profile(policy: Policy) -> PolicyMatchProfile:
    """Построить профиль полиса с нормализованными значениями."""

    normalized_policy_number = _normalize_string(policy.policy_number)
    normalized_vin = _normalize_vin(policy.vehicle_vin)
    normalized_contractor = _normalize_string(policy.contractor)
    drive_link = policy.drive_folder_link.strip() if policy.drive_folder_link else None

    client_phones: Set[str] = set()
    client_emails: Set[str] = set()
    if policy.client_id:
        phone_normalized = _normalize_phone(policy.client.phone)
        if phone_normalized:
            client_phones.add(phone_normalized)
        email_normalized = _normalize_string(policy.client.email)
        if email_normalized:
            client_emails.add(email_normalized)

    contractors: Set[str] = set()
    if normalized_contractor:
        contractors.add(normalized_contractor)

    brand_model_pairs: Set[Tuple[str, str]] = set()
    brand_normalized = _normalize_string(policy.vehicle_brand)
    model_normalized = _normalize_string(policy.vehicle_model)
    if brand_normalized and model_normalized:
        brand_model_pairs.add((brand_normalized, model_normalized))

    insurance_companies: Set[str] = set()
    insurance_company_normalized = _normalize_string(policy.insurance_company)
    if insurance_company_normalized:
        insurance_companies.add(insurance_company_normalized)

    insurance_types: Set[str] = set()
    insurance_type_normalized = _normalize_string(policy.insurance_type)
    if insurance_type_normalized:
        insurance_types.add(insurance_type_normalized)

    sales_channels: Set[str] = set()
    sales_channel_normalized = _normalize_string(policy.sales_channel)
    if sales_channel_normalized:
        sales_channels.add(sales_channel_normalized)

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
        client_phones=client_phones,
        client_emails=client_emails,
        contractors=contractors,
        brand_model_pairs=brand_model_pairs,
        min_start=policy.start_date,
        max_end=policy.end_date,
        insurance_companies=insurance_companies,
        insurance_types=insurance_types,
        sales_channels=sales_channels,
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

    deals = prefetch(base_query, Client, Policy, Expense)
    result: Dict[int, DealMatchProfile] = {}

    for deal in deals:
        client: Client = deal.client
        policies = [
            policy
            for policy in deal.policies
            if getattr(policy, "is_deleted", False) is False
        ]
        policy_profiles = [make_policy_profile(policy) for policy in policies]

        vins = {p.normalized_vehicle_vin for p in policy_profiles if p.normalized_vehicle_vin}
        policy_numbers = {
            p.normalized_policy_number for p in policy_profiles if p.normalized_policy_number
        }
        contractors: Set[str] = set()
        brand_model_pairs: Set[Tuple[str, str]] = set()
        insurance_companies: Set[str] = set()
        insurance_types: Set[str] = set()
        sales_channels: Set[str] = set()

        start_dates = [p.start_date for p in policy_profiles if p.start_date]
        end_dates = [p.end_date for p in policy_profiles if p.end_date]
        min_start = min(start_dates) if start_dates else None
        max_end = max(end_dates) if end_dates else None

        for profile in policy_profiles:
            contractors.update(profile.contractors)
            brand_model_pairs.update(profile.brand_model_pairs)
            insurance_companies.update(profile.insurance_companies)
            insurance_types.update(profile.insurance_types)
            sales_channels.update(profile.sales_channels)

        folder_paths = _collect_folder_paths(deal, client, policy_profiles)

        client_phones: Set[str] = set()
        client_emails: Set[str] = set()

        phone_normalized = _normalize_phone(client.phone)
        if phone_normalized:
            client_phones.add(phone_normalized)

        email_normalized = _normalize_string(client.email)
        if email_normalized:
            client_emails.add(email_normalized)

        for profile in policy_profiles:
            client_phones.update(profile.client_phones)
            client_emails.update(profile.client_emails)

        expense_contractors: Set[str] = set()
        for policy in policies:
            contractor_normalized = _normalize_string(policy.contractor)
            if not contractor_normalized:
                continue
            has_expense = any(
                getattr(expense, "is_deleted", False) is False for expense in policy.expenses
            )
            if has_expense:
                expense_contractors.add(contractor_normalized)

        result[deal.id] = DealMatchProfile(
            deal=deal,
            client=client,
            policy_profiles=policy_profiles,
            vins=vins,
            policy_numbers=policy_numbers,
            contractors=contractors,
            policy_date_range=(min_start, max_end),
            folder_paths=folder_paths,
            client_phones=client_phones,
            client_emails=client_emails,
            brand_model_pairs=brand_model_pairs,
            min_start=min_start,
            max_end=max_end,
            insurance_companies=insurance_companies,
            insurance_types=insurance_types,
            sales_channels=sales_channels,
            expense_contractors=expense_contractors,
        )

    return result


def find_strict_matches(
    policy_profile: PolicyMatchProfile, deal_index: Dict[int, DealMatchProfile]
) -> List[CandidateDeal]:
    """Найти сделки, удовлетворяющие строгим правилам сопоставления."""

    matches: List[CandidateDeal] = []
    policy_vin = policy_profile.normalized_vehicle_vin
    policy_number_search = _normalize_policy_number_for_match(
        policy_profile.policy_number
    )
    policy_drive_link = (
        policy_profile.drive_folder_link.strip()
        if policy_profile.drive_folder_link
        else None
    )

    for deal_id, deal_profile in deal_index.items():
        reasons: List[str] = []

        if policy_vin and policy_vin in deal_profile.vins:
            matched_policy = next(
                (
                    p
                    for p in deal_profile.policy_profiles
                    if p.normalized_vehicle_vin == policy_vin
                ),
                None,
            )
            if matched_policy is not None:
                reasons.append(
                    f"VIN совпадает с полисом №{matched_policy.policy_number}"
                )
            else:
                reasons.append("VIN совпадает с полисом сделки")

        if policy_number_search:
            existing_policy = next(
                (
                    p
                    for p in deal_profile.policy_profiles
                    if _normalize_policy_number_for_match(p.policy_number)
                    == policy_number_search
                ),
                None,
            )
            if existing_policy is not None:
                reasons.append(
                    f"Номер полиса совпадает с полисом №{existing_policy.policy_number}"
                )
            else:
                description_normalized = _normalize_text_for_match(
                    deal_profile.deal.description
                )
                if (
                    description_normalized
                    and policy_number_search in description_normalized
                ):
                    reasons.append(
                        f"Номер полиса {policy_profile.policy_number} найден в описании сделки"
                    )
                calculations_normalized = _normalize_text_for_match(
                    deal_profile.deal.calculations
                )
                if (
                    calculations_normalized
                    and policy_number_search in calculations_normalized
                ):
                    reasons.append(
                        f"Номер полиса {policy_profile.policy_number} найден в расчётах сделки"
                    )

        if policy_drive_link:
            deal_folder_candidates = [
                deal_profile.deal.drive_folder_path,
                deal_profile.deal.drive_folder_link,
            ]
            if any(
                candidate and _is_subpath(policy_drive_link, candidate)
                for candidate in deal_folder_candidates
            ):
                reasons.append(
                    "Ссылка на диск полиса вложена в папку сделки"
                )

        if reasons:
            matches.append(CandidateDeal(deal_id=deal_id, reasons=reasons))

    return matches


def _format_similarity(value: float) -> str:
    return f"{value:.2f}"


def collect_indirect_matches(
    policy_profile: PolicyMatchProfile, deal_index: Dict[int, DealMatchProfile]
) -> List[CandidateDeal]:
    """Собрать кандидатов по косвенным правилам сопоставления."""

    matches: List[CandidateDeal] = []

    for deal_id, deal_profile in deal_index.items():
        score = 0.0
        reasons: List[str] = []

        phone_matches = policy_profile.client_phones & deal_profile.client_phones
        if phone_matches:
            score += PHONE_MATCH_WEIGHT
            phone_example = next(iter(phone_matches))
            reasons.append(f"Совпадает телефон клиента: {phone_example}")

        email_matches = policy_profile.client_emails & deal_profile.client_emails
        if email_matches:
            score += EMAIL_MATCH_WEIGHT
            email_example = next(iter(email_matches))
            reasons.append(f"Совпадает email клиента: {email_example}")

        contractor_reason_added = False
        normalized_contractor = policy_profile.normalized_contractor
        if normalized_contractor:
            client_name_normalized = _normalize_string(deal_profile.client.name)
            if client_name_normalized:
                similarity = SequenceMatcher(
                    None, normalized_contractor, client_name_normalized
                ).ratio()
                if similarity >= CONTRACTOR_SIMILARITY_THRESHOLD:
                    score += CONTRACTOR_NAME_WEIGHT
                    reasons.append(
                        "Контрагент полиса похож на имя клиента сделки "
                        f"(совпадение {_format_similarity(similarity)})"
                    )
                    contractor_reason_added = True

            if not contractor_reason_added:
                best_similarity = 0.0
                for contractor in deal_profile.contractors:
                    similarity = SequenceMatcher(
                        None, normalized_contractor, contractor
                    ).ratio()
                    if similarity >= CONTRACTOR_SIMILARITY_THRESHOLD and similarity > best_similarity:
                        best_similarity = similarity
                if best_similarity >= CONTRACTOR_SIMILARITY_THRESHOLD:
                    score += CONTRACTOR_NAME_WEIGHT
                    reasons.append(
                        "Контрагент полиса похож на контрагента сделки "
                        f"(совпадение {_format_similarity(best_similarity)})"
                    )

        vin_intersects = (
            policy_profile.normalized_vehicle_vin
            and policy_profile.normalized_vehicle_vin in deal_profile.vins
        )
        brand_model_matches = (
            policy_profile.brand_model_pairs & deal_profile.brand_model_pairs
        )
        if brand_model_matches and not vin_intersects:
            date_match = False
            if policy_profile.start_date and deal_profile.min_start:
                start_diff = abs(
                    (policy_profile.start_date - deal_profile.min_start).days
                )
                if start_diff <= DATE_DIFF_TOLERANCE_DAYS:
                    date_match = True
            if (
                not date_match
                and policy_profile.end_date
                and deal_profile.max_end
            ):
                end_diff = abs(
                    (policy_profile.end_date - deal_profile.max_end).days
                )
                if end_diff <= DATE_DIFF_TOLERANCE_DAYS:
                    date_match = True
            if date_match:
                score += BRAND_MODEL_DATE_WEIGHT
                brand_normalized, model_normalized = next(iter(brand_model_matches))
                reasons.append(
                    "Совпадают марка и модель без совпадения VIN ("
                    f"{policy_profile.policy.vehicle_brand or brand_normalized} / "
                    f"{policy_profile.policy.vehicle_model or model_normalized})"
                )

        if (
            policy_profile.insurance_companies
            and policy_profile.insurance_types
            and policy_profile.sales_channels
            and policy_profile.insurance_companies
            & deal_profile.insurance_companies
            and policy_profile.insurance_types & deal_profile.insurance_types
            and policy_profile.sales_channels & deal_profile.sales_channels
        ):
            score += INSURANCE_CHANNEL_WEIGHT
            reasons.append(
                "Совпадают страховая компания, тип страхования и канал продаж ("
                f"{policy_profile.policy.insurance_company or ''} / "
                f"{policy_profile.policy.insurance_type or ''} / "
                f"{policy_profile.policy.sales_channel or ''})"
            )

        if (
            normalized_contractor
            and normalized_contractor in deal_profile.expense_contractors
        ):
            score += EXPENSE_CONTRACTOR_WEIGHT
            reasons.append(
                "В сделке есть расходы по контрагенту "
                f"{policy_profile.contractor or normalized_contractor}"
            )

        if score > 0:
            matches.append(CandidateDeal(deal_id=deal_id, score=score, reasons=reasons))

    matches.sort(key=lambda candidate: candidate.score, reverse=True)
    return matches

