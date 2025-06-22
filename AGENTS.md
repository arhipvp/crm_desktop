Перед запуском тестов установите системные библиотеки `libegl1` и `libgl1`:

```bash
sudo apt-get update
sudo apt-get install -y libegl1 libgl1
```

Рекомендуется запускать тесты командой:

```bash
PYTEST_TIMEOUT=120 pytest -vv
```

При необходимости можно запускать подмножества тестов с помощью флага `-k`.
