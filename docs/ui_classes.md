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

## Пример использования `FilterHeaderView`

```python
from PySide6.QtWidgets import QTableView
from ui.common.filter_header_view import FilterHeaderView


class MyTableView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        header = FilterHeaderView(self)
        self.setHorizontalHeader(header)
        header.filter_changed.connect(self._on_filter)

    def _on_filter(self, column: int, text: str) -> None:
        ...  # примените фильтрацию
```

## Ссылки

- [MainWindow](../ui/main_window.py)
- [BaseTableView](../ui/base/base_table_view.py)
- [TableController](../ui/base/table_controller.py)
- [BaseEditForm](../ui/base/base_edit_form.py)
- Пример таблицы: [ClientTableView](../ui/views/client_table_view.py)
- Пример формы: [ClientForm](../ui/forms/client_form.py)

