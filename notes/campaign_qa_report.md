# SvenMap Generator — QA кампании

Кампания: sc_expedition; глав: 8; время 552.6 с.

| Глава | Результат | Brush | Entity | Секретов | BSP, КБ |
|---|---|---:|---:|---:|---:|
| sc_exp_1 | PASS | 804 | 64 | 0 | 1147 |
| sc_exp_2 | PASS | 1146 | 82 | 0 | 1627 |
| sc_exp_3 | PASS | 747 | 49 | 0 | 1124 |
| sc_exp_4 | PASS | 1139 | 79 | 0 | 1627 |
| sc_exp_5 | PASS | 744 | 62 | 0 | 997 |
| sc_exp_6 | PASS | 1121 | 79 | 0 | 1604 |
| sc_exp_7 | PASS | 938 | 58 | 0 | 1260 |
| sc_exp_8 | PASS | 658 | 50 | 0 | 998 |

## Метрики композиции (P3.0)

| Глава | topo | spatial | stretch | глубина ветки | разнообразие форм | этажей |
|---|---:|---:|---:|---:|---:|---:|
| sc_exp_1 | 0.740 | 0.876 | 1.00 | 2 | 0.40 | 1 |
| sc_exp_2 | 0.700 | 0.815 | 1.00 | 2 | 0.25 | 1 |
| sc_exp_3 | 0.808 | 0.876 | 1.33 | 2 | 0.33 | 1 |
| sc_exp_4 | 0.713 | 0.880 | 1.00 | 2 | 0.27 | 1 |
| sc_exp_5 | 0.694 | 0.573 | 1.00 | 1 | 0.33 | 2 |
| sc_exp_6 | 0.700 | 0.863 | 1.00 | 2 | 0.20 | 1 |
| sc_exp_7 | 0.667 | 0.605 | 1.00 | 1 | 0.33 | 2 |
| sc_exp_8 | 0.650 | 0.930 | 1.00 | 0 | 0.38 | 1 |

Превью планировок: `notes/previews/<имя>.svg`. Метрики — фильтр pass/warn, а не целевая функция: итоговое решение всегда за человеком, который проходит карту.

## Ритм по профилям (P3.1)

| Глава | профиль | боевых % | подряд | до передышки | ролей | предупреждения |
|---|---|---:|---:|---:|---:|---|
| sc_exp_1 | standard_8 | 20% | 1 | 4 | 0.60 | доля боевых комнат 20% ниже порога профиля standard_8 (25%–45%) |
| sc_exp_2 | dense_10 | 12% | 1 | 4 | 0.44 | доля боевых комнат 12% ниже порога профиля dense_10 (35%–55%) |
| sc_exp_3 | short_6 | 22% | 1 | 2 | 0.67 | — |
| sc_exp_4 | standard_8 | 13% | 1 | 4 | 0.47 | доля боевых комнат 13% ниже порога профиля standard_8 (25%–45%) |
| sc_exp_5 | standard_8 | 22% | 2 | 2 | 0.67 | доля боевых комнат 22% ниже порога профиля standard_8 (25%–45%) |
| sc_exp_6 | dense_10 | 13% | 1 | 5 | 0.47 | доля боевых комнат 13% ниже порога профиля dense_10 (35%–55%); передышка только каждые 5 комнат — реже, чем нужно (4) |
| sc_exp_7 | standard_8 | 17% | 1 | 4 | 0.58 | доля боевых комнат 17% ниже порога профиля standard_8 (25%–45%) |
| sc_exp_8 | standard_8 | 25% | 2 | 3 | 0.75 | — |

## Сцены (P3.2)

| Глава | сцен | разнообразие | предупреждения |
|---|---:|---:|---|
| sc_exp_1 | 10 | 0.60 | — |
| sc_exp_2 | 16 | 0.50 | — |
| sc_exp_3 | 9 | 0.78 | — |
| sc_exp_4 | 15 | 0.47 | — |
| sc_exp_5 | 9 | 0.78 | — |
| sc_exp_6 | 15 | 0.53 | — |
| sc_exp_7 | 12 | 0.75 | — |
| sc_exp_8 | 8 | 0.88 | — |

## Атмосфера и нарратив (P4)

| Глава | пресет | звуков | музыка | ламп тревоги | триггер |
|---|---|---:|---|---:|---|
| sc_exp_1 | quiet_lab | 10 | — | 3 | door_manager |
| sc_exp_2 | ventilation | 16 | — | 3 | door_manager |
| sc_exp_3 | security | 9 | да | 3 | door_manager |
| sc_exp_4 | ventilation | 15 | — | 3 | door_manager |
| sc_exp_5 | quiet_lab | 9 | — | 3 | door_manager |
| sc_exp_6 | ventilation | 15 | — | 3 | door_manager |
| sc_exp_7 | ventilation | 12 | — | 3 | door_manager |
| sc_exp_8 | boss | 8 | да | 3 | door_manager |

## Валидатор композиции (P3.3)

> Фильтр pass/warn, а не жёсткий QA: метрики показывают, что улучшить, но не блокируют сборку.

### sc_exp_1 — WARN
- **ритм** — доля боевых комнат 20% ниже порога профиля standard_8 (25%–45%). Добавьте combat-комнату или ослабьте профиль
- **маршрут** — критический путь 50% комнат вне диапазона 60%–80%; нужна развилка или цикл
- **маршрут** — нет развилки с возвратом на карте из 10 комнат — добавьте цикл к боковой комнате

### sc_exp_2 — WARN
- **ритм** — доля боевых комнат 12% ниже порога профиля dense_10 (35%–55%). Добавьте combat-комнату или ослабьте профиль
- **разнообразие** — сцен 0.50 < 0.60 — карта может выглядеть однообразно; раздайте комнатам разные сцены
- **разнообразие** — одна сцена повторяется 3 раза подряд — чередуйте сцены
- **маршрут** — критический путь 38% комнат вне диапазона 60%–80%; нужна развилка или цикл

### sc_exp_3 — WARN
- **маршрут** — критический путь 44% комнат вне диапазона 60%–80%; нужна развилка или цикл

### sc_exp_4 — WARN
- **ритм** — доля боевых комнат 13% ниже порога профиля standard_8 (25%–45%). Добавьте combat-комнату или ослабьте профиль
- **разнообразие** — сцен 0.47 < 0.60 — карта может выглядеть однообразно; раздайте комнатам разные сцены
- **разнообразие** — одна сцена повторяется 3 раза подряд — чередуйте сцены
- **маршрут** — критический путь 40% комнат вне диапазона 60%–80%; нужна развилка или цикл

### sc_exp_5 — WARN
- **ритм** — доля боевых комнат 22% ниже порога профиля standard_8 (25%–45%). Добавьте combat-комнату или ослабьте профиль
- **маршрут** — нет развилки с возвратом на карте из 9 комнат — добавьте цикл к боковой комнате

### sc_exp_6 — WARN
- **ритм** — доля боевых комнат 13% ниже порога профиля dense_10 (35%–55%). Добавьте combat-комнату или ослабьте профиль
- **ритм** — передышка только каждые 5 комнат — реже, чем нужно (4). Добавьте combat-комнату или ослабьте профиль
- **разнообразие** — сцен 0.53 < 0.60 — карта может выглядеть однообразно; раздайте комнатам разные сцены
- **маршрут** — критический путь 47% комнат вне диапазона 60%–80%; нужна развилка или цикл

### sc_exp_7 — WARN
- **ритм** — доля боевых комнат 17% ниже порога профиля standard_8 (25%–45%). Добавьте combat-комнату или ослабьте профиль
- **маршрут** — критический путь 50% комнат вне диапазона 60%–80%; нужна развилка или цикл
- **маршрут** — нет развилки с возвратом на карте из 12 комнат — добавьте цикл к боковой комнате

### sc_exp_8 — PASS
- замечаний нет


### sc_exp_1 — PASS
all_areas=OK, bsp_text=OK, changelevel=OK, compile_BSP=OK, compile_CSG=OK, compile_RAD=OK, compile_VIS=OK, coop_spawns=OK, goal_after_door_opens=OK, goal_gated_by_door=OK, item_sample_1=OK, item_sample_2=OK, item_sample_3=OK, item_sample_4=OK, item_sample_5=OK, map_load=OK, no_leak=OK, objective=OK, portal_binding=OK, script_compile=OK, visual_axes=OK, visual_decor=OK, visual_surfaces=OK, visual_text=OK, visual_textures=OK

### sc_exp_2 — PASS
all_areas=OK, bsp_text=OK, changelevel=OK, compile_BSP=OK, compile_CSG=OK, compile_RAD=OK, compile_VIS=OK, coop_spawns=OK, goal_after_door_opens=OK, goal_gated_by_door=OK, item_sample_1=OK, item_sample_2=OK, item_sample_3=OK, item_sample_4=OK, item_sample_5=OK, map_load=OK, no_leak=OK, objective=OK, portal_binding=OK, script_compile=OK, visual_axes=OK, visual_decor=OK, visual_surfaces=OK, visual_text=OK, visual_textures=OK

### sc_exp_3 — PASS
all_areas=OK, bsp_text=OK, button_gen_button_1=OK, button_gen_button_2=OK, changelevel=OK, compile_BSP=OK, compile_CSG=OK, compile_RAD=OK, compile_VIS=OK, coop_spawns=OK, goal_after_door_opens=OK, goal_gated_by_door=OK, map_load=OK, no_leak=OK, objective=OK, portal_binding=OK, script_compile=OK, visual_axes=OK, visual_decor=OK, visual_surfaces=OK, visual_text=OK, visual_textures=OK

### sc_exp_4 — PASS
all_areas=OK, bsp_text=OK, changelevel=OK, compile_BSP=OK, compile_CSG=OK, compile_RAD=OK, compile_VIS=OK, coop_spawns=OK, goal_after_door_opens=OK, goal_gated_by_door=OK, item_sample_1=OK, item_sample_2=OK, item_sample_3=OK, item_sample_4=OK, item_sample_5=OK, map_load=OK, no_leak=OK, objective=OK, portal_binding=OK, script_compile=OK, visual_axes=OK, visual_decor=OK, visual_surfaces=OK, visual_text=OK, visual_textures=OK

### sc_exp_5 — PASS
all_areas=OK, bsp_text=OK, changelevel=OK, compile_BSP=OK, compile_CSG=OK, compile_RAD=OK, compile_VIS=OK, coop_spawns=OK, goal_after_door_opens=OK, goal_gated_by_door=OK, item_sample_1=OK, item_sample_2=OK, item_sample_3=OK, item_sample_4=OK, item_sample_5=OK, map_load=OK, no_leak=OK, objective=OK, portal_binding=OK, script_compile=OK, visual_axes=OK, visual_decor=OK, visual_surfaces=OK, visual_text=OK, visual_textures=OK

### sc_exp_6 — PASS
all_areas=OK, bsp_text=OK, changelevel=OK, compile_BSP=OK, compile_CSG=OK, compile_RAD=OK, compile_VIS=OK, coop_spawns=OK, goal_after_door_opens=OK, goal_gated_by_door=OK, item_sample_1=OK, item_sample_2=OK, item_sample_3=OK, item_sample_4=OK, item_sample_5=OK, map_load=OK, no_leak=OK, objective=OK, portal_binding=OK, script_compile=OK, visual_axes=OK, visual_decor=OK, visual_surfaces=OK, visual_text=OK, visual_textures=OK

### sc_exp_7 — PASS
all_areas=OK, bsp_text=OK, button_gen_button_1=OK, button_gen_button_2=OK, changelevel=OK, compile_BSP=OK, compile_CSG=OK, compile_RAD=OK, compile_VIS=OK, coop_spawns=OK, goal_after_door_opens=OK, goal_gated_by_door=OK, map_load=OK, no_leak=OK, objective=OK, portal_binding=OK, script_compile=OK, visual_axes=OK, visual_decor=OK, visual_surfaces=OK, visual_text=OK, visual_textures=OK

### sc_exp_8 — PASS
all_areas=OK, boss_waves=OK, bsp_text=OK, button_gen_button_1=OK, button_gen_button_2=OK, compile_BSP=OK, compile_CSG=OK, compile_RAD=OK, compile_VIS=OK, coop_spawns=OK, goal_after_door_opens=OK, goal_gated_by_door=OK, map_load=OK, no_changelevel=OK, no_leak=OK, objective=OK, portal_binding=OK, script_compile=OK, visual_axes=OK, visual_decor=OK, visual_surfaces=OK, visual_text=OK, visual_textures=OK

Итого: 8/8
