# Основные классы интерфейса

```mermaid
classDiagram
    class MainWindow
    class BaseTableView
    class TableController
    class BaseEditForm
    class ClientTableView
    class ClientForm

    MainWindow --> ClientTableView : вкладка
    ClientTableView --|> BaseTableView
    BaseTableView --> TableController : загрузка данных
    BaseTableView --> BaseEditForm : редактирование
    ClientForm --|> BaseEditForm
```

## Поток взаимодействия

1. `MainWindow` создаёт вкладки с конкретными таблицами и подписывается на сигнал `data_loaded`, чтобы отображать число записей.
2. Каждый наследник `BaseTableView` настраивает `TableController`, передавая сервисные функции для загрузки страниц и подсчёта записей. Контроллер обновляет модель и эмитит `data_loaded`.
3. `BaseTableView` обновляет таблицу и фильтры. При редактировании открывается форма, наследующая `BaseEditForm`; она сохраняет данные через сервисы и инициирует обновление представления.

## QSortFilterProxyModel

Для фильтрации таблиц используется стандартная `QSortFilterProxyModel`. Клик по заголовку открывает меню с полем ввода, которое устанавливает фильтр через `setFilterKeyColumn`.

## Ссылки

- [MainWindow](../ui/main_window.py)
- [BaseTableView](../ui/base/base_table_view.py)
- [TableController](../ui/base/table_controller.py)
- [BaseEditForm](../ui/base/base_edit_form.py)
- Пример таблицы: [ClientTableView](../ui/views/client_table_view.py)
- Пример формы: [ClientForm](../ui/forms/client_form.py)

## Действия вкладки «Сделка»

- **💾 Добавить заметку** — сохраняет текст из поля «Новая запись…» в журнал сделки. Кнопка активна всегда, но запись с пустым текстом не добавляется.
- **🤖 Распознать документы** — открывает диалог [AiDocumentFilesDialog](../ui/forms/ai_document_files_dialog.py), где можно перетащить файлы, получить автоматическую заметку и при необходимости уточнить ответ ассистента. Диалог запоминает свою геометрию, показывает подробный лог общения с ИИ и позволяет вручную редактировать итог перед сохранением в журнал.

