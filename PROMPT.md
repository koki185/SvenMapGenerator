# Как описать кампанию для SvenMapGenerator

Модель заполняет **только** `campaign.json`. Не пишет код, не придумывает новые
поля и значения. Генератор сам превращает JSON в `.map`, `.as`, `.cfg` и
проверяет результат (CSG/BSP/VIS/RAD + загрузка карты).

## Закрытый словарь

| Поле | Допустимые значения |
|---|---|
| `name` | имя кампании: латиница, цифры, `_` |
| `chapters[].name` | имя карты: строчные латиница, цифры, `_` (стаёт именем `.map`/`.cfg`) |
| `chapters[].seed` | целое число, **уникальное** в кампании |
| `chapters[].rooms` | целое 4–16 |
| `chapters[].branches` | целое 0–4 |
| `chapters[].theme` | `industrial` |
| `chapters[].puzzles` | ровно одна цель: `collect` **или** `buttons`; плюс `secret`, `super_secret`, `enemies`, `multi_floor` |
| `chapters[].final` | `true` — только у последней главы |

Последняя глава — арена босса: `final: true`, без `enemies` и без `changelevel`.

## Пример (две главы)

```json
{
  "name": "sc_test",
  "chapters": [
    {
      "name": "sc_test_1", "seed": 201, "rooms": 7, "branches": 1,
      "theme": "industrial", "puzzles": ["collect", "enemies"]
    },
    {
      "name": "sc_test_2", "seed": 202, "rooms": 8, "branches": 2,
      "theme": "industrial", "puzzles": ["buttons", "secret"],
      "final": true
    }
  ]
}
```

## Проверка перед генерацией

```bash
python -m svenmap.campaign_schema campaign.json
```

При ошибке валидатор печатает точный путь и подсказку, одну строку на проблему:

```
chapters[1].seed: seed 201 уже используется в chapters[0]. Выберите другое число.
chapters[0].theme: тема 'lab' не поддерживается. Доступно: industrial
```

Машиночитаемая схема для редактора: `campaign.schema.json`.
