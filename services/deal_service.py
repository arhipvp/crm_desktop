from __future__ import annotations

"""Deal service module — CRUD‑операции и вспомогательные функции для сущности Deal.
Исправлено:
• Папка сделки создаётся через create_deal_folder() с гарантированным префиксом «Сделка - …».
• Сохранение локального пути производится в поле ``drive_folder_path`` (обновите модель ``Deal``).
• Удалён неиспользуемый импорт DealStatus.
• Типизация и мелкие правки PEP 8.
"""
import logging
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from utils.time_utils import now_str


from peewee import JOIN, ModelSelect, Field, fn, Model  # если ещё не импортирован

from core.app_context import get_app_context
from infrastructure.drive_gateway import DriveGateway
from database.db import db
from database.models import (
    Client,
    Deal,
    Policy,
    Task,
    DealExecutor,
    Executor,
)
from services.clients import get_client_by_id
from services.query_utils import apply_search_and_filters
from services.folder_utils import (
    create_deal_folder,
    find_drive_folder,
    sanitize_name,
    extract_folder_id,
)
from services import deal_journal

logger = logging.getLogger(__name__)


def _resolve_gateway(gateway: DriveGateway | None) -> DriveGateway:
    return gateway or get_app_context().drive_gateway


def _ensure_distinct_order_columns(
    query: ModelSelect, *fields_with_aliases: tuple[Field, str]
) -> ModelSelect:
    """Добавить поля сортировки в SELECT при ``DISTINCT`` запросах."""

    distinct_flag = getattr(query, "_distinct", None)
    if distinct_flag in (None, False):
        return query

    existing_aliases = {
        getattr(item, "_alias", None)
        for item in (getattr(query, "_returning", None) or ())
        if getattr(item, "_alias", None)
    }

    for field, alias in fields_with_aliases:
        if alias in existing_aliases:
            continue
        query = query.select_extend(field.alias(alias))
        existing_aliases.add(alias)

    return query

# ──────────────────────────── Получение ─────────────────────────────


def get_all_deals():
    """Возвращает все сделки, кроме помеченных как удалённые."""
    return Deal.active()


def get_open_deals():
    """Открытые (не закрытые) сделки, не помеченные как удалённые."""
    return Deal.active().where(Deal.is_closed == False)


def get_deals_by_client_id(client_id: int):
    return Deal.active().where(Deal.client_id == client_id)


def get_deal_by_id(deal_id: int) -> Deal | None:
    return Deal.active().where(Deal.id == deal_id).get_or_none()


def get_distinct_statuses() -> list[str]:
    """Возвращает список уникальных статусов сделок."""
    query = Deal.select(Deal.status.distinct()).where(Deal.status.is_null(False))
    return [row.status for row in query]


# ──────────────────────────── Добавление ─────────────────────────────


def add_deal(*, gateway: DriveGateway | None = None, **kwargs):
    """Создаёт новую сделку.

    Обязательные поля: ``client_id``, ``start_date``, ``description``.
    После создания создаётся локальная папка сделки «Сделка - …» внутри папки клиента;
    путь сохраняется в ``deal.drive_folder_path``.
    """

    required_fields = {"client_id", "start_date", "description"}
    missing = [f for f in required_fields if not kwargs.get(f)]
    if missing:
        raise ValueError(f"Отсутствуют обязательные поля: {', '.join(missing)}")

    client = get_client_by_id(kwargs["client_id"])
    if not client:
        raise ValueError("Клиент не найден.")

    allowed_fields = {
        "start_date",
        "status",
        "description",
        "calculations",
        "reminder_date",
        "is_closed",
        "closed_reason",
    }

    clean_data: dict = {
        key: kwargs[key]
        for key in allowed_fields
        if key in kwargs and kwargs[key] not in ("", None)
    }

    initial_note = clean_data.pop("calculations", None)

    # FK клиент
    clean_data["client"] = client
    with db.atomic():
        deal: Deal = Deal.create(**clean_data)
        if initial_note:
            deal_journal.append_entry(deal, initial_note)
        logger.info(
            "✅ Сделка id=%s создана: клиент %s — %s",
            deal.id,
            client.name,
            deal.description,
        )

        # ───── создание папки сделки ─────
        try:
            resolved_gateway = _resolve_gateway(gateway)
            local_path, web_link = create_deal_folder(
                client.name,
                deal.description,
                client_drive_link=client.drive_folder_link,
                gateway=resolved_gateway,
            )
            logger.info("📁 Папка сделки создана: %s", local_path)
            if web_link:
                logger.info("🔗 Google Drive-ссылка сделки: %s", web_link)
            deal.drive_folder_path = local_path
            deal.drive_folder_link = web_link
            deal.save()
        except Exception as e:
            logger.error("❌ Ошибка создания папки сделки: %s", e)

        return deal


def add_deal_from_policy(
    policy: Policy, *, gateway: DriveGateway | None = None
) -> Deal:
    """Создаёт сделку на основе полиса и привязывает полис к ней."""

    parts = []
    if policy.insurance_type:
        parts.append(policy.insurance_type)
    if policy.vehicle_brand:
        brand = policy.vehicle_brand
        if policy.vehicle_model:
            brand += f" {policy.vehicle_model}"
        parts.append(brand)
    description = " ".join(parts).strip() or f"Из полиса {policy.policy_number}"

    start_date = policy.start_date or date.today()
    reminder_date = start_date + relativedelta(months=9)

    deal = add_deal(
        gateway=gateway,
        client_id=policy.client_id,
        start_date=start_date,
        description=description,
        reminder_date=reminder_date,
    )

    new_folder_path = None
    try:
        from services.folder_utils import move_policy_folder_to_deal

        resolved_gateway = _resolve_gateway(gateway)
        new_folder_path = move_policy_folder_to_deal(
            policy.drive_folder_link,
            policy.client.name,
            deal.description,
            gateway=resolved_gateway,
        )
        if new_folder_path:
            policy.drive_folder_path = new_folder_path
    except Exception:
        logger.exception("Не удалось переместить папку полиса")

    policy.deal = deal
    fields_to_update = [Policy.deal]
    if new_folder_path:
        fields_to_update.append(Policy.drive_folder_path)
    policy.save(only=fields_to_update)
    return deal


def add_deal_from_policies(
    policies: list[Policy], *, gateway: DriveGateway | None = None
) -> Deal:
    """Создаёт сделку и привязывает к ней несколько полисов.

    Первая политика используется для формирования описания сделки,
    аналогично :func:`add_deal_from_policy`, остальные полисы просто
    привязываются к созданной сделке.

    Parameters
    ----------
    policies: list[Policy]
        Список полисов, которые необходимо объединить в одну сделку.

    Returns
    -------
    Deal
        Созданная сделка.
    """

    if not policies:
        raise ValueError("Нет полисов для создания сделки")

    first, *rest = policies
    deal = add_deal_from_policy(first, gateway=gateway)

    from services.folder_utils import move_policy_folder_to_deal

    resolved_gateway = _resolve_gateway(gateway)
    for policy in rest:
        new_path = None
        try:
            new_path = move_policy_folder_to_deal(
                policy.drive_folder_link,
                policy.client.name,
                deal.description,
                gateway=resolved_gateway,
            )
            if new_path:
                policy.drive_folder_path = new_path
        except Exception:
            logger.exception("Не удалось переместить папку полиса")
        policy.deal = deal
        fields_to_update = [Policy.deal]
        if new_path:
            fields_to_update.append(Policy.drive_folder_path)
        policy.save(only=fields_to_update)

    return deal


# ──────────────────────────── Обновление ─────────────────────────────


def update_deal(
    deal: Deal,
    *,
    journal_entry: str | None = None,
    gateway: DriveGateway | None = None,
    **kwargs,
):
    """Обновляет сделку.

    Параметр ``journal_entry`` добавляет запись в журнал ``Deal.calculations``.
    Передаваемый ``calculations`` трактуется как текст расчёта и сохраняется в
    таблицу :class:`DealCalculation`.
    """

    with db.atomic():
        allowed_fields = {
            "start_date",
            "status",
            "description",
            "reminder_date",
            "is_closed",
            "closed_reason",
            "client_id",
        }

        old_client_name = deal.client.name if deal.client_id else None
        old_desc = deal.description

        # Собираем простые обновления (кроме calculations)
        updates: dict = {
            key: kwargs[key]
            for key in allowed_fields
            if key in kwargs
            and key != "closed_reason"
            and kwargs[key] not in ("", None)
        }

        if "closed_reason" in kwargs:
            updates["closed_reason"] = kwargs["closed_reason"] or None

        # Смена клиента
        if "client_id" in updates:
            client = get_client_by_id(updates.pop("client_id"))
            if not client:
                raise ValueError("Клиент не найден.")
            deal.client = client

        # calculations -> отдельная таблица
        new_calc: str | None = kwargs.get("calculations")
        new_note: str | None = journal_entry
        auto_note: str | None = None

        if kwargs.get("is_closed") and kwargs.get("closed_reason"):
            auto_note = f"Сделка закрыта. Причина: {kwargs['closed_reason']}"

        if not updates and not new_calc and not new_note and not auto_note:
            return deal

        # Применяем простые обновления
        for key, value in updates.items():
            setattr(deal, key, value)

        dirty_fields = list(deal.dirty_fields)
        log_updates = {}
        for f in dirty_fields:
            value = getattr(deal, f.name)
            if isinstance(value, (date, datetime)):
                value = value.isoformat()
            elif isinstance(value, Model):
                value = str(value)
            log_updates[f.name] = value

        deal.save()
        logger.info("✏️ Обновлена сделка id=%s: %s", deal.id, log_updates)

        # Переименование папки при изменении описания или клиента
        new_client_name = deal.client.name if deal.client_id else None
        new_desc = deal.description
        if (
            (old_client_name and new_client_name and old_client_name != new_client_name)
            or old_desc != new_desc
        ):
            try:
                from services.folder_utils import rename_deal_folder

                resolved_gateway = _resolve_gateway(gateway)
                new_path, _ = rename_deal_folder(
                    old_client_name or "",
                    old_desc,
                    new_client_name or "",
                    new_desc,
                    deal.drive_folder_link,
                    deal.drive_folder_path,
                    gateway=resolved_gateway,
                )
                if new_path and new_path != deal.drive_folder_path:
                    deal.drive_folder_path = new_path
                    deal.save(only=[Deal.drive_folder_path, Deal.drive_folder_link])
            except Exception:
                logger.exception("Не удалось переименовать папку сделки")

        if auto_note:
            deal_journal.append_entry(deal, auto_note)

        if new_note:
            deal_journal.append_entry(deal, new_note)

        # Добавляем расчётную запись
        if new_calc:
            from services.calculation_service import add_calculation

            add_calculation(deal.id, note=new_calc)
        return deal


# ──────────────────────────── Удаление ─────────────────────────────


def mark_deal_deleted(deal_id: int, *, gateway: DriveGateway | None = None):
    with db.atomic():
        deal = Deal.get_or_none(Deal.id == deal_id)
        if deal:
            deal.soft_delete()
            try:
                from services.folder_utils import rename_deal_folder

                resolved_gateway = _resolve_gateway(gateway)
                new_desc = f"{deal.description} deleted"
                new_path, _ = rename_deal_folder(
                    deal.client.name,
                    deal.description,
                    deal.client.name,
                    new_desc,
                    deal.drive_folder_link,
                    deal.drive_folder_path,
                    gateway=resolved_gateway,
                )
                deal.description = new_desc
                deal.drive_folder_path = new_path
                deal.save(
                    only=[Deal.description, Deal.drive_folder_path, Deal.is_deleted]
                )
                logger.info("Сделка id=%s помечена удалённой", deal.id)
            except Exception:
                logger.exception("Не удалось пометить папку сделки удалённой")
        else:
            logger.warning("❗ Сделка с id=%s не найдена для удаления", deal_id)


def apply_deal_filters(
    query,
    search_text: str = "",
    column_filters: dict | None = None,
):
    extra_fields = [
        Deal.description,
        Deal.status,
        Client.name,
        Client.phone,
        Deal.calculations,
    ]

    policy_search_condition = None
    if search_text:
        policy_search_condition = fn.EXISTS(
            Policy.select(1).where(
                (Policy.deal == Deal.id)
                & (Policy.is_deleted == False)
                & Policy.vehicle_vin.cast("TEXT").contains(search_text)
            )
        )

    if column_filters and Executor.full_name in column_filters:
        query = (
            query.switch(Deal)
            .join(DealExecutor, JOIN.LEFT_OUTER, on=(DealExecutor.deal == Deal.id))
            .join(Executor, JOIN.LEFT_OUTER, on=(DealExecutor.executor == Executor.id))
        )

    query = apply_search_and_filters(
        query,
        Deal,
        search_text,
        column_filters,
        extra_fields,
        extra_condition=policy_search_condition,
    )
    return query


# ──────────────────────────── Пагинация ─────────────────────────────


def get_deals_page(
    page: int,
    per_page: int,
    search_text: str = "",
    show_deleted: bool = False,
    order_by: str = "reminder_date",
    order_dir: str = "asc",
    column_filters: dict | None = None,
    **filters,
) -> ModelSelect:
    """Вернуть страницу сделок с указанными фильтрами."""
    logger.debug("column_filters=%s", column_filters)
    query = build_deal_query(
        search_text=search_text,
        show_deleted=show_deleted,
        column_filters=column_filters,
        **filters,
    )

    # 👉 Стабильная сортировка
    if order_by == "executor":
        query = (
            query.switch(Deal)
            .join(DealExecutor, JOIN.LEFT_OUTER, on=(DealExecutor.deal == Deal.id))
            .join(Executor, JOIN.LEFT_OUTER, on=(DealExecutor.executor == Executor.id))
        )
        # Поле исполнителя участвует в ORDER BY, поэтому добавляем его в
        # результирующий SELECT (PostgreSQL требует, чтобы такие столбцы были
        # явно выбраны при использовании DISTINCT).
        query = query.select(Deal, Client, Executor.full_name.alias("executor_order"))
        query = _ensure_distinct_order_columns(
            query,
            (Executor.full_name, "order_executor"),
            (Deal.id, "order_deal_id"),
        )
        if order_dir == "desc":
            query = query.order_by(Executor.full_name.desc(), Deal.id.desc())
        else:
            query = query.order_by(Executor.full_name.asc(), Deal.id.asc())
    elif order_by == "client_name":
        query = _ensure_distinct_order_columns(
            query,
            (Client.name, "order_client_name"),
            (Deal.id, "order_deal_id"),
        )
        if order_dir == "desc":
            query = query.order_by(Client.name.desc(), Deal.id.desc())
        else:
            query = query.order_by(Client.name.asc(), Deal.id.asc())
    elif order_by and hasattr(Deal, order_by):
        order_field = getattr(Deal, order_by)
        query = _ensure_distinct_order_columns(
            query,
            (order_field, f"order_{order_by}"),
            (Deal.id, "order_deal_id"),
        )
        if order_dir == "desc":
            query = query.order_by(order_field.desc(), Deal.id.desc())
        else:
            query = query.order_by(order_field.asc(), Deal.id.asc())
    else:
        query = _ensure_distinct_order_columns(
            query,
            (Deal.start_date, "order_start_date"),
            (Deal.id, "order_deal_id"),
        )
        query = query.order_by(Deal.start_date.desc(), Deal.id.desc())

    offset = (page - 1) * per_page
    page_query = query.limit(per_page).offset(offset)
    items = list(page_query)
    if not items:
        return []

    from peewee import prefetch

    deal_ids = [deal.id for deal in items]

    base_query = (
        Deal.select(Deal, Client)
        .join(Client)
        .where(Deal.id.in_(deal_ids))
    )

    related_deals = prefetch(
        base_query,
        DealExecutor.select(DealExecutor, Executor).join(Executor),
        Policy,
    )

    related_map = {deal.id: deal for deal in related_deals}

    for deal in items:
        related = related_map.get(deal.id)
        executors = list(getattr(related, "executors", [])) if related else []
        if related:
            setattr(deal, "executors", executors)
            setattr(deal, "policies", list(getattr(related, "policies", [])))
        ex = executors[0].executor if executors else None
        setattr(deal, "_executor", ex)
    return items


def get_open_deals_page(page: int = 1, per_page: int = 50) -> ModelSelect:
    """Возвращает открытые сделки постранично."""
    return (
        Deal.active()
        .where(Deal.is_closed == False)
        .order_by(Deal.start_date.desc())
        .paginate(page, per_page)
    )


# ──────────────────────────── Связанные сущности ─────────────────────────────


def get_policies_by_deal_id(deal_id: int) -> ModelSelect:
    """Вернуть полисы, привязанные к сделке."""
    return Policy.active().where(Policy.deal == deal_id)


def get_tasks_by_deal_id(deal_id: int) -> ModelSelect:
    """Вернуть задачи, связанные со сделкой."""
    return Task.active().where(Task.deal == deal_id)


def build_deal_query(
    search_text: str = "",
    show_deleted: bool = False,
    show_closed: bool = False,
    column_filters: dict | None = None,
) -> ModelSelect:
    """Базовый запрос сделок с фильтрами по статусам."""
    base = Deal.active() if not show_deleted else Deal.select()
    # В выборку добавляем поля клиента, чтобы их можно было использовать
    # в выражениях ORDER BY даже при DISTINCT-запросах (PostgreSQL требует,
    # чтобы такие поля присутствовали в списке SELECT).
    query = base.join(Client).select(Deal, Client)

    query = apply_deal_filters(query, search_text, column_filters)

    if not show_closed:
        if show_deleted:
            query = query.where(
                (Deal.is_closed == False) | (Deal.is_deleted == True)
            )
        else:
            query = query.where(Deal.is_closed == False)

    return query


def get_next_deal(current_deal: Deal) -> Deal | None:
    """Найти следующую сделку по дате напоминания."""
    if current_deal.reminder_date is None:
        return None

    return (
        get_open_deals()
        .where(
            (Deal.reminder_date > current_deal.reminder_date)
            | (
                (Deal.reminder_date == current_deal.reminder_date)
                & (Deal.id > current_deal.id)
            )
        )
        .order_by(Deal.reminder_date.asc(), Deal.id.asc())
        .first()
    )


def get_prev_deal(current_deal: Deal) -> Deal | None:
    """Найти предыдущую сделку по дате напоминания."""
    if current_deal.reminder_date is None:
        return None

    return (
        get_open_deals()
        .where(
            (Deal.reminder_date < current_deal.reminder_date)
            | (
                (Deal.reminder_date == current_deal.reminder_date)
                & (Deal.id < current_deal.id)
            )
        )
        .order_by(Deal.reminder_date.desc(), Deal.id.desc())
        .first()
    )


def refresh_deal_drive_link(
    deal: Deal, *, gateway: DriveGateway | None = None
) -> None:
    """Попытаться найти ссылку папки сделки на Google Drive."""
    if deal.drive_folder_link:
        return

    client_link = deal.client.drive_folder_link if deal.client else None
    if not client_link:
        return

    try:
        resolved_gateway = _resolve_gateway(gateway)
        deal_name = sanitize_name(f"Сделка - {deal.description}")
        parent_id = extract_folder_id(client_link)
        if not parent_id:
            return
        link = find_drive_folder(
            deal_name, gateway=resolved_gateway, parent_id=parent_id
        )
        if link:
            deal.drive_folder_link = link
            deal.save(only=[Deal.drive_folder_link])
            logger.info("🔗 Обновлена ссылка сделки на Drive: %s", link)
    except Exception:
        logger.exception("Не удалось обновить ссылку на папку сделки %s", deal.id)
