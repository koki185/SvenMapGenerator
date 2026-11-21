# SvenMap Generator

Детерминированная генерация карт Sven Co-op и цепочек карт-продолжений кодом,
без ручного маппинга. Основной результат — кампания из 8 карт `sc_exp_1` …
`sc_exp_8` с механиками, AngelScript, QA и метриками композиции.

Подробная инструкция: [ИНСТРУКЦИЯ.txt](ИНСТРУКЦИЯ.txt).
Словарь и пример для локальной модели: [PROMPT.md](PROMPT.md).

## Требования

- Python 3.10
- Sven Co-op 5.26 + SDK с компиляторами `SC-CSG/BSP/VIS/RAD_x64`

Пути к игре и SDK определяются автоматически (`svenmap/pipeline.py::detect_roots`).
Компиляторы нужны только для `--build`; для генерации `.map`, метрик и превью
достаточно Python.

## Единый вход

Все команды доступны через один модуль:

```bash
python -m svenmap --help
python -m svenmap campaign --only sc_exp_1 --build --smoke
python -m svenmap qa --only sc_exp_1
python -m svenmap propose --all
python -m svenmap map --seed 42
python -m svenmap schema
```

Старые `generate_*.py` остаются для истории и regression-режима.

## Быстрый старт

```bash
# Одна карта без компиляции (быстро)
python generate_campaign.py --only sc_exp_1

# Вся кампания со сборкой и smoke-тестом
python generate_campaign.py --build --smoke

# QA (19 жёстких проверок на карту + метрики композиции)
python run_campaign_qa.py

# Unit-тесты
python -m unittest discover -s tests
```

Перед `--build` и полным QA закройте клиент Sven Co-op: дедикальный сервер
не может инициализировать Steam, пока открыт клиент.

## Управление кампанией

Редактируйте `campaign.json` ( поле `pacing` и `scenes` необязательны ):

```json
{
  "name": "sc_expedition",
  "chapters": [
    { "name": "sc_exp_1", "seed": 101, "rooms": 8, "branches": 1,
      "theme": "industrial", "puzzles": ["collect", "enemies"],
      "pacing": "standard_8" }
  ]
}
```

Проверка перед генерацией:

```bash
python -m svenmap.campaign_schema campaign.json
```

## Композиция и качество

- `pacing.json` — 3 профиля ритма; `scenes.json` — 10 сцен.
- Сцены меняют текстуры, свет и декор комнат.
- Метрики и предупреждения — в `notes/campaign_qa_report.md`.
- Превью планировок — `notes/previews/*.svg` (L/T/U-формы, связи, цели,
  знак выхода, имена сцен, этажи отдельными панелями).
- Подбор альтернативных seed (не меняет `campaign.json`):

```bash
python propose_seeds.py --all --count 12 --top 3
```

## Структура

```
campaign.json          цепочка карт
pacing.json            профили ритма
scenes.json            библиотека сцен
PROMPT.md              закрытый словарь для локальной модели
generate_campaign.py   главная точка входа
run_campaign_qa.py     QA кампании
propose_seeds.py       подбор seed
svenmap/               ядро: planning, геометрия, механики, метрики, QA
notes/progress.md      подробное состояние проекта
```

## Известные ограничения

- Нет бота, который реально проходит карту; QA доказывает «собралось и
  загрузилось», а не «интересно играть».
- Визуальный стиль и баланс по-прежнему требуют человека.
- P4 (событийный свет, звук, нарратив) не реализован.

Лицензия: см. репозиторий. Проект написан для учебного задания.
