# pydiag

Streamlit-приложение для интерактивной карты процесса планирования и бурения скважин.

Схема рендерится локальным bidi-компонентом из репозитория. `node`, `npm`,
`poetry`, `uv` и отдельный frontend build не нужны. Рабочий сценарий проекта:
обычный `.venv` и установка зависимостей из `requirements*.txt`.

## Быстрый запуск

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\streamlit.exe run app.py
```

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

Для разработки и тестов:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
```

## Каноническая структура данных

Единственная runtime-папка проекта: `data/`.

```text
data/
  flow_sources/
    flow_source.yaml
    flow_source.v0001.yaml
    flow_source.v0002.yaml
  real_true_data.json
  flow_graph.json
  wells.yaml
```

Смысл файлов:

- `data/flow_sources/flow_source.yaml`:
  главный человекочитаемый source-of-truth графа.
- `data/flow_sources/flow_source.vNNNN.yaml`:
  архивные версии source YAML.
- `data/real_true_data.json`:
  сырой импорт из Figma.
- `data/flow_graph.json`:
  materialized/generated runtime-граф для быстрого чтения приложением.
- `data/wells.yaml`:
  текущее состояние скважин.

Главное правило:

- редактируемым источником схемы считается `flow_source.yaml`;
- `flow_graph.json` не является отдельным источником истины;
- `real_true_data.json` нужен для импорта и пересборки source-схемы;
- `wells.yaml` хранит только runtime-состояние скважин.

Каталог `data/` полностью игнорируется git и не попадает в runtime bundle.

## Форматы входных данных

Поддерживаются два источника схемы:

1. `flow-source/1.0` YAML.
2. Figma-like JSON skeleton из `real_true_data.json`.

### Нормальный рабочий формат

Пример `flow_source.yaml`:

```yaml
schema_version: flow-source/1.0
graph_id: pilot-drilling
title: Pilot drilling flow
version: 7
responsibles:
  planning:
    label: Planning
    type: team
    fill: "#dcecff"
    border: "#356ca8"
    text: "#17314f"
nodes:
  review_data:
    title: Проверка комплекта данных
    kind: process
    responsible: planning
    participants: [geology]
    approvers: [hse]
    duration: 40m
    transitions:
      - to: data_complete
  data_complete:
    title: Данные полные?
    kind: decision_diamond
    responsible: planning
    transitions:
      - to: well_design
        kind: yes
      - to: review_data
        kind: no
layout:
  review_data:
    x: 380
    y: 60
    w: 320
    h: 120
```

### Сырой Figma JSON

Импорт поддерживает:

- `TEXT`
- `SHAPE_WITH_TEXT`
- `CONNECTOR`

Семантика может приходить двумя путями:

- через явные `flowNode` / `flowEdge`;
- через fallback metadata в поле `name`.

Для `TEXT` или `SHAPE_WITH_TEXT` ожидаются такие смысловые поля:

- `flowNode.id`
- `flowNode.type`
- `flowNode.responsibles`
- `flowNode.time`

Для `CONNECTOR`:

- `flowEdge.id`
- `flowEdge.kind`
- `flowEdge.source`
- `flowEdge.target`
- `flowEdge.label`

Если `source/target` не заданы явно, importer пытается восстановить связь по
геометрии.

## Импорт и материализация

Из сырого Figma JSON в нормальный YAML:

```bash
.venv/bin/python scripts/materialize_flow_source.py
```

Из `flow_source.yaml` в materialized runtime-граф:

```bash
.venv/bin/python scripts/materialize_flow_graph.py
```

Нормализация старого skeleton JSON:

```bash
.venv/bin/python scripts/normalize_flow_graph_skeleton.py
```

Если нужно использовать внешнюю папку с данными, доступны env-переменные:

- `PYDIAG_SOURCE_GRAPH_PATH`
- `PYDIAG_RAW_GRAPH_PATH`
- `PYDIAG_GRAPH_PATH`
- `PYDIAG_WELLS_PATH`

Пример:

```bash
PYDIAG_SOURCE_GRAPH_PATH=/opt/pydiag/flow_sources/flow_source.yaml \
PYDIAG_GRAPH_PATH=/opt/pydiag/flow_graph.json \
PYDIAG_WELLS_PATH=/opt/pydiag/wells.yaml \
.venv/bin/streamlit run app.py
```

## UI и авторизация

Авторизация настраивается в `.streamlit/secrets.toml`.
Шаблон лежит в `.streamlit/secrets.example.toml`.

Минимальный пример:

```toml
[users.admin]
name = "Администратор"
password = "replace-me-strong"
```

`super_admin` дополнительно может:

- включать режим редактирования расположения карточек;
- сохранять layout обратно в live `flow_source.yaml`;
- создавать архивную версию source YAML.

## Архитектура

Проект специально разделен на слои.

- `src/pydiag/domain/`
  Pydantic-модели, инварианты графа, переходы скважин, pure domain logic.
- `src/pydiag/application/`
  use-case слой: загрузка документов, состояние схемы, persistence orchestration,
  редактирование layout, admin-сценарии.
- `src/pydiag/presentation/`
  Streamlit UI, sidebar, inspector, auth, screen composition.
- `src/pydiag/infrastructure/`
  файловое хранение, atomic writes, lock-файлы, импорт Figma, path/env resolution.
- `src/pydiag/rendering/`
  canvas payload, layout/routing, HTML/CSS/JS локального компонента.
- `src/pydiag/common/`
  общие примитивы и ошибки.

Правила зависимостей:

- `domain` не знает про Streamlit, JSON и локальные компоненты;
- `application` знает про `domain`, но не про Streamlit и файловый I/O;
- `presentation` не должна ходить в storage напрямую;
- `infrastructure` не зависит от presentation;
- `rendering` не должен тащить application-flow или storage.

`app.py` остается тонким entrypoint. Новую логику туда не складываем.

## Правила разработки

Куда класть код:

- бизнес-правила и инварианты: `domain/`
- session/use-case orchestration: `application/`
- Streamlit rendering и формы: `presentation/`
- JSON/YAML I/O, locks, import/export: `infrastructure/`
- canvas/layout/render helpers: `rendering/`

Практические правила:

- предпочитать маленькие owner-модули вместо разрастания `app.py` и крупных runtime-файлов;
- если логика pure и переиспользуемая, выносить ее рядом с owner-модулем;
- presentation-рендереры не должны сами выбирать low-level file operations;
- новые импорты делать через пакеты `pydiag.domain`, `pydiag.application`,
  `pydiag.presentation`, `pydiag.infrastructure`, `pydiag.rendering`.

## Проверки качества

Быстрый прогон тестов:

```bash
.venv/bin/python -m pytest
```

Полный quality gate:

```bash
.venv/bin/python scripts/quality.py
```

Что делает `scripts/quality.py`:

- проверяет repository safety;
- валидирует fixture-данные;
- компилирует Python-файлы;
- запускает `ruff check` и `ruff format --check` с фиксированными параметрами;
- запускает `pytest` с покрытием.

## Runtime bundle

Сборка runtime bundle:

```bash
python scripts/project_pack.py pack
```

Распаковка:

```bash
python scripts/project_pack.py unpack --archive dist/project_bundle.txt
```

Bundle включает весь код приложения, runtime-скрипты и безопасные конфиги,
достаточные для запуска и локальной генерации `data/` на месте. `.venv`,
секреты, runtime-данные из `data/` и unsafe-входы вроде symlink или
неразрешенных runtime-asset файлов туда не попадают. Это дополнительно
проверяет `scripts/verify_repository_safety.py`.

## Production checklist

Состояние можно считать production-ready, если выполнено следующее:

1. Реальные данные лежат в `data/` или во внешнем каталоге по env-переменным.
2. `data/flow_sources/flow_source.yaml` валиден и соответствует `wells.yaml`.
3. Запускаются `scripts/materialize_flow_graph.py` и `scripts/quality.py`.
4. Настроен `.streamlit/secrets.toml` с нормальными паролями.
5. В git не попали `data/` и `.streamlit/secrets.toml`.
