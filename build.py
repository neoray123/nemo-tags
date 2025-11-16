#!/usr/bin/env python3
"""Simple builder: склеивает несколько модулей в один dist/nemo-tags.py

Идея такая:
- Разрабатывать код плагина в src/*.py (icons, database, manager, ui, extension и т.д.)
- В этом скрипте перечислить файлы в нужном порядке
- На выходе получить один файл dist/nemo-tags.py, который можно ставить как расширение Nemo

Сейчас src/ может быть пустым — скрипт служит заготовкой под будущую модульную архитектуру.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
OUT_DIR = ROOT / "dist"
OUT_FILE = OUT_DIR / "nemo-tags.py"

# Порядок файлов ВАЖЕН: сначала утилиты и база, потом менеджер, UI, в самом конце — класс расширения.

MODULES: List[Path] = [
    SRC / "header.py",
    SRC / "icons.py",
    SRC / "database.py",
    SRC / "manager.py",
    SRC / "ui.py",
    SRC / "extension.py",
]

HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# WARNING: этот файл сгенерирован автоматически build.py
# Не редактируйте его вручную — вносите изменения в src/*.py и пересобирайте.

"""


def build() -> None:
    if not MODULES:
        raise SystemExit(
            "MODULES пуст. Сначала создайте модули в src/ и перечислите их в build.py."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Резервное копирование старой версии, если есть
    if OUT_FILE.exists():
        backup = OUT_FILE.with_suffix(".py.bak")
        shutil.copy2(OUT_FILE, backup)

    with OUT_FILE.open("w", encoding="utf-8") as out:
        out.write(HEADER)

        module_names = {m.stem for m in MODULES}

        for module in MODULES:
            if not module.exists():
                raise FileNotFoundError(f"Module not found: {module}")

            rel = module.relative_to(ROOT)
            out.write(f"# ===== BEGIN {rel} =====\n\n")

            code = module.read_text(encoding="utf-8")

            # вырезаем блоки `if __name__ == "__main__":`
            # чтобы в итоговом файле они не выполнялись при загрузке расширения Nemo.
            lines = code.splitlines()
            skip_main = False
            for line in lines:
                stripped = line.strip()

                # Удаляем внутрипроектные импорты вида `from icons import TagIconGenerator`,
                # т.к. после склейки все классы оказываются в одном файле.
                is_intra_import = any(
                    stripped.startswith(f"from {name} import ")
                    or stripped.startswith(f"import {name}")
                    for name in module_names
                )
                if is_intra_import:
                    continue

                if stripped.startswith('if __name__ == "__main__"'):
                    skip_main = True
                    continue
                if skip_main:
                    # пропускаем строки до конца файла
                    # (при желании можно сделать аккуратный парсер по отступам)
                    continue

                out.write(line + "\n")

            out.write(f"\n# ===== END {rel} =====\n\n")

    print(f"Built: {OUT_FILE}")


if __name__ == "__main__":
    build()
