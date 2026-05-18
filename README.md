# pydiag

Прототип Streamlit-приложения для карты процесса планирования и бурения скважины.

## Запуск на Windows

PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\streamlit.exe run app.py
```

CMD:

```bat
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\streamlit.exe run app.py
```

## Запуск на Linux/macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

Если в системе нет `python3.13-venv`, окружение можно создать любым инструментом, который создает обычный `.venv`, а зависимости все равно ставятся из `requirements.txt`.

Все файловые пути внутри приложения обрабатываются через `pathlib`, атомарная запись использует `os.replace`, а POSIX-only `fsync` директории автоматически пропускается на Windows. Запись `wells.json` дополнительно защищена lock-файлом рядом с JSON: на Windows используется `msvcrt.locking`, на Linux/macOS — `fcntl.flock`.

## Данные

- `data/flow_graph.json` содержит узлы, связи, координаты и ответственных.
- `data/wells.json` содержит скважины, их `current_node_id` и историю переходов.

Узлы схемы используют компактный контракт: `type`, `text`, `position`, `size`,
опционально `responsible`, `time`, `metadata`. Поддерживаемые типы:
`process`, `decision_diamond`, `decision_card`, `database`, `input_data`, `event`.
Для процессов и решений `responsible` обязателен и задается списком: первый
элемент задает основной цвет блока, остальные отображаются короткими боковыми
бейджами. `time` задается строкой в формате `40 minutes`, `10 hours` или
`2 days`.

Связи используют четыре типа `kind`: `usual` — обычная черная стрелка,
`dashed` — серая пунктирная, `yes` — стрелка «Да», `no` — стрелка «Нет».

Авторизация настраивается в `.streamlit/secrets.toml`:

```toml
[users.admin]
name = "Администратор"
password = "replace-me-strong"
```

Можно добавить несколько пользователей:

```toml
[users.planner]
name = "Иван Планировщик"
password = "another-strong-password"
```

После входа имя пользователя показывается сверху в боковой панели. В production
пароли должны быть заданы явно и быть не короче 8 символов.
Для локальной разработки можно временно включить небезопасный fallback:

PowerShell:

```powershell
$env:PYDIAG_ALLOW_INSECURE_ADMIN = "1"
.\.venv\Scripts\streamlit.exe run app.py
```

Linux/macOS:

```bash
PYDIAG_ALLOW_INSECURE_ADMIN=1 .venv/bin/streamlit run app.py
```

Пути к данным можно переопределить переменными окружения:

PowerShell:

```powershell
$env:PYDIAG_GRAPH_PATH = "C:\pydiag-data\flow_graph.json"
$env:PYDIAG_WELLS_PATH = "C:\pydiag-data\wells.json"
.\.venv\Scripts\streamlit.exe run app.py
```

Linux/macOS:

```bash
PYDIAG_GRAPH_PATH=/path/to/flow_graph.json
PYDIAG_WELLS_PATH=/path/to/wells.json
.venv/bin/streamlit run app.py
```

## Тесты

Установка dev-зависимостей:

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Linux/macOS:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
```

Быстрый прогон на любой платформе:

```powershell
python scripts/venv_run.py -m pytest
```

Полный quality gate на любой платформе:

```powershell
python scripts/venv_run.py scripts/quality.py
```

Эквивалентные Unix-команды:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m pytest --cov=src/pydiag --cov-report=term-missing --cov-fail-under=85
```

В набор входят unit-тесты доменной модели, сервисов переходов и JSON-хранилища, а также Streamlit UI-интеграционные тесты через `streamlit.testing.v1.AppTest`. UI-тесты подменяют `PYDIAG_GRAPH_PATH` и `PYDIAG_WELLS_PATH`, поэтому реальные `data/*.json` не изменяются.

Линт на любой платформе:

```powershell
python scripts/venv_run.py -m ruff check .
python scripts/venv_run.py -m ruff format --check .
```

Эквивалентные Unix-команды:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
```

## Проверка JSON

Windows:

```powershell
python scripts/venv_run.py scripts/validate_data.py
```

Linux/macOS:

```bash
.venv/bin/python scripts/validate_data.py
```
