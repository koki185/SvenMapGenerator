"""Генератор AngelScript-карты и CFG (этап 11).

Сообщения НЕ привязаны к конкретному триггеру. Каждый вызов просто
увеличивает счётчик в скрипте, и на HUD выводится реальное состояние
задачи (X/N). Так порядок нажатий не может дать ложное сообщение.
"""

import os

TEMPLATE = """\
// ---------------------------------------------------------------------------
// Сгенерировано SvenMap Generator. Не редактируйте вручную.
// Карта: {map_name}
// ---------------------------------------------------------------------------

int g_total = {count};
int g_progress = 0;
int g_secrets = 0;
int g_secrets_total = {secret_total};

void MapInit()
{{
    g_progress = 0;
    g_secrets = 0;
}}

void ShowProgress( string label )
{{
    HUDTextParams params;
    params.x = -1;
    params.y = -1;
    params.effect = 0;
    params.r1 = 255;
    params.g1 = 224;
    params.b1 = 128;
    params.a1 = 0;
    params.r2 = 255;
    params.g2 = 224;
    params.b2 = 128;
    params.a2 = 0;
    params.fadeinTime = 0.0f;
    params.fadeoutTime = 0.5f;
    params.holdTime = 2.0f;
    params.channel = 3;
    g_PlayerFuncs.HudMessageAll( params, label );
}}

void MapActivate()
{{
    ShowProgress( "{intro}" );
}}

void Progress( CBaseEntity@ pActivator, CBaseEntity@ pCaller,
    USE_TYPE useType, float flValue )
{{
    if( g_progress < g_total )
        g_progress++;
    ShowProgress( "{label}: " + string(g_progress) + "/" + string(g_total) );
}}

void DoorOpened( CBaseEntity@ pActivator, CBaseEntity@ pCaller,
    USE_TYPE useType, float flValue )
{{
    if( g_progress < g_total )
        return;
    ShowProgress( "Objective complete! Door opened." );
}}

void SecretFound( CBaseEntity@ pActivator, CBaseEntity@ pCaller,
    USE_TYPE useType, float flValue )
{{
    if( g_secrets < g_secrets_total )
        g_secrets++;
    ShowProgress( "Secrets: " + string(g_secrets) + "/" + string(g_secrets_total) );
}}

void TierDone( CBaseEntity@ pActivator, CBaseEntity@ pCaller,
    USE_TYPE useType, float flValue )
{{
    ShowProgress( "Secret tier complete! Bonus area opened." );
}}

void AllSecretsFound( CBaseEntity@ pActivator, CBaseEntity@ pCaller,
    USE_TYPE useType, float flValue )
{{
    if( g_secrets < g_secrets_total )
        return;
    ShowProgress( "All secrets found!" );
}}
"""


def script_text(map_name, count, label="Generators", chapter=None,
                final=False, secret_total=0):
    # Только ASCII: движок GoldSrc нестабильно показывает кириллицу в HUD.
    if final:
        intro = "Final chapter: defeat the entity and escape."
    else:
        intro = "Complete the objective and reach the exit."
    if chapter:
        intro = "Chapter {}. ".format(chapter) + intro

    return TEMPLATE.format(
        map_name=map_name,
        count=count,
        label=label,
        intro=intro.replace("\n", " "),
        secret_total=secret_total,
    )


def write_map_script(game_dir, map_name, count,
                     label="Generators", chapter=None, final=False,
                     secret_total=0):
    """Положить .as и .cfg в svencoop_addon. Возвращает имена файлов."""
    addon = os.path.join(game_dir, "svencoop_addon")
    scripts_dir = os.path.join(addon, "scripts", "maps")
    maps_dir = os.path.join(addon, "maps")
    os.makedirs(scripts_dir, exist_ok=True)
    os.makedirs(maps_dir, exist_ok=True)

    script_path = os.path.join(scripts_dir, map_name + ".as")
    # Движок Sven Co-op читает AngelScript как ANSI/CP1251.
    # UTF-8 даёт в HUD «Б┬Н» вместо «Образцы».
    with open(script_path, "w", encoding="cp1251", newline="\n") as f:
        f.write(script_text(map_name, count, label, chapter, final,
                            secret_total))

    cfg_path = os.path.join(maps_dir, map_name + ".cfg")
    with open(cfg_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("map_script {}\n".format(map_name))

    return script_path, cfg_path
