"""Компиляция .map -> .bsp инструментами Sven Co-op SDK.

Порядок фиксирован: CSG -> BSP -> VIS -> RAD (как в штатном пайплайне
GoldSrc). Используем 64-битные бинарники SC-* из SDK 5.26.
"""

import os
import subprocess
import time

COMPILERS_REL = os.path.join("Sven Co-op SDK", "mapping", "compilers")
GAME_REL = "Sven Co-op"
STEAM_ROOTS = (
    r"K:\SteamLibrary\steamapps\common",
    r"D:\SteamLibrary\steamapps\common",
    r"C:\Program Files (x86)\Steam\steamapps\common",
)

TOOL_NAMES = ("SC-CSG_x64.exe", "SC-BSP_x64.exe", "SC-VIS_x64.exe", "SC-RAD_x64.exe")


class CompileError(RuntimeError):
    pass


def detect_roots():
    """Найти каталоги SDK и игры. Возвращает (steam_common, compilers_dir, game_dir)."""
    for root in STEAM_ROOTS:
        if not os.path.isdir(root):
            continue
        compilers = os.path.join(root, COMPILERS_REL)
        game = os.path.join(root, GAME_REL)
        if os.path.isdir(compilers) and os.path.isdir(game):
            if all(os.path.isfile(os.path.join(compilers, n)) for n in TOOL_NAMES):
                return root, compilers, game
    raise FileNotFoundError("не найден Sven Co-op SDK с компиляторами SC-*")


def compile_map(map_path, compilers_dir, log_dir=None, extra_args=()):
    """Последовательно запустить CSG, BSP, VIS, RAD.

    Возвращает словарь {имя_этапа: (returncode, путь_к_логу)}.
    При ошибке любого этапа поднимает CompileError.
    """
    map_path = os.path.abspath(map_path)
    if not os.path.isfile(map_path):
        raise FileNotFoundError(map_path)

    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    results = {}
    for tool in TOOL_NAMES:
        exe = os.path.join(compilers_dir, tool)
        stage = tool.replace("_x64.exe", "")
        args = [exe, map_path, "-console", "0", "-noinfo"]
        args.extend(extra_args)

        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        log_path = None
        if log_dir:
            log_path = os.path.join(log_dir, stage + ".log")
            with open(log_path, "w", encoding="utf-8", errors="replace") as f:
                f.write(output)

        results[stage] = (proc.returncode, log_path)
        print("[{}] код возврата: {}".format(stage, proc.returncode))
        if proc.returncode != 0:
            tail = "\n".join(output.splitlines()[-25:])
            raise CompileError(
                "этап {} завершился с кодом {}\n{}".format(
                    stage, proc.returncode, tail
                )
            )

    bsp_path = os.path.splitext(map_path)[0] + ".bsp"
    if not os.path.isfile(bsp_path):
        raise CompileError("BSP не создан: {}".format(bsp_path))
    results["bsp"] = bsp_path
    return results


def _sdl3_search_dir():
    """Каталог с 32-битной SDL3.dll для запуска x86-бинарников игры.

    В установке Sven Co-op эта DLL отсутствует, но Steam её содержит.
    Добавляем каталог в PATH процесса — без копирования файлов в игру.
    """
    candidates = (
        r"C:\Program Files (x86)\Steam\bin\cef\cef.win7",
        r"C:\Program Files (x86)\Steam",
    )
    for path in candidates:
        if os.path.isfile(os.path.join(path, "SDL3.dll")):
            return path
    return None


def smoke_test_load(bsp_name, game_dir, seconds=8, extra_args=()):
    """Коротко запустить дедикальный сервер с картой и собрать лог.

    Это проверка «карта грузится без ошибок», а не игровой тест.
    Сервер принудительно завершается по истечении `seconds`.
    """
    exe = os.path.join(game_dir, "svends.exe")
    if not os.path.isfile(exe):
        raise FileNotFoundError(exe)

    env = os.environ.copy()
    sdl_dir = _sdl3_search_dir()
    if sdl_dir:
        env["PATH"] = sdl_dir + os.pathsep + env.get("PATH", "")

    args = [
        exe,
        "-console",
        "+map",
        bsp_name,
        "+sv_lan",
        "1",
        "+maxplayers",
        "2",
        # Отдельный порт: основной 27015 может быть занят клиентом игры.
        "+port",
        "27021",
    ]
    args.extend(extra_args)
    proc = subprocess.Popen(
        args,
        cwd=game_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        output, _ = proc.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            output, _ = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            output, _ = proc.communicate()
    return output or ""
