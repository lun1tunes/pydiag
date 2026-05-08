# pydiag

Прототип Streamlit-приложения для карты процесса планирования и бурения скважины.

## Запуск

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

Если в системе нет `python3.13-venv`, окружение можно создать любым инструментом, который создает обычный `.venv`, а зависимости все равно ставятся из `requirements.txt`.

## Данные

- `data/flow_graph.json` содержит узлы, связи, координаты и ответственных.
- `data/wells.json` содержит скважины, их `current_node_id` и историю переходов.

Админ-панель включается паролем из `PYDIAG_ADMIN_PASSWORD` или `st.secrets["admin_password"]`. Для локального прототипа запасной пароль: `admin`.

Пути к данным можно переопределить переменными окружения:

```bash
PYDIAG_GRAPH_PATH=/path/to/flow_graph.json
PYDIAG_WELLS_PATH=/path/to/wells.json
.venv/bin/streamlit run app.py
```

## Тесты

Установка dev-зависимостей:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
```

Быстрый прогон:

```bash
.venv/bin/python -m pytest
```

Quality gate с покрытием:

```bash
.venv/bin/python -m pytest --cov=src/pydiag --cov-report=term-missing --cov-fail-under=85
```

В набор входят unit-тесты доменной модели, сервисов переходов и JSON-хранилища, а также Streamlit UI-интеграционные тесты через `streamlit.testing.v1.AppTest`. UI-тесты подменяют `PYDIAG_GRAPH_PATH` и `PYDIAG_WELLS_PATH`, поэтому реальные `data/*.json` не изменяются.

## Проверка JSON

```bash
.venv/bin/python scripts/validate_data.py
```
