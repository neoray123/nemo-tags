import itertools
import threading
from pathlib import Path
from typing import List, Callable, Optional

import shutil
import subprocess

from gi.repository import GdkPixbuf, Gtk, GLib

from header import EMBLEMS_DIR


class TagIconGenerator:
    """Generate colored circle icons for tags"""
    
    # Кеш для отслеживания уже созданных эмблем
    _created_emblems = set()
    _lock = threading.Lock()

    # Флаг, что обновление кеша уже запланировано
    _cache_update_scheduled = False

    @staticmethod
    def hex_to_rgb(hex_color: str) -> tuple:
        """Convert #RRGGBB to (r, g, b) float tuple"""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    @staticmethod
    def create_tag_icon(color: str, size: int = 16) -> str:
        """Return path to SVG emblem for a single-color tag.

        Для UI (панель тегов, контекстное меню) просто используем SVG-эмблему
        с одним кружком и даём GTK самому масштабировать её до нужного размера.
        """
        emblem_name = TagIconGenerator.create_emblem_icon([color])
        emblem_path = EMBLEMS_DIR / f"{emblem_name}.svg"
        return str(emblem_path)

    @staticmethod
    def pregenerate_all_combinations(tags: List[dict], callback: Optional[Callable] = None):
        """Предварительно генерируем все возможные комбинации эмблем тегов.
        
        Генерация теперь идёт в главном GTK-потоке маленькими порциями через GLib.idle_add,
        чтобы не использовать GTK из фонового потока и не создавать гонки при записи файлов.
        
        Args:
            tags: Список тегов
            callback: Функция, которая будет вызвана после завершения генерации (в главном потоке GTK)
        """
        if not tags:
            if callback:
                GLib.idle_add(callback)
            return

        colors = [tag["color"] for tag in tags if "color" in tag]
        if not colors:
            if callback:
                GLib.idle_add(callback)
            return

        # Строим список всех комбинаций заранее
        combos: List[List[str]] = []
        for r in range(1, min(4, len(colors) + 1)):
            for combo in itertools.combinations(colors, r):
                combos.append(list(combo))

        if not combos:
            if callback:
                GLib.idle_add(callback)
            return

        print(f"[TagIconGenerator] Pregenerating emblems for {len(colors)} tags ({len(combos)} combos)...")

        iterator = iter(combos)

        def process_batch(it):
            # Обрабатываем по несколько комбинаций за один проход, чтобы не блокировать UI
            try:
                for _ in range(5):  # до 5 эмблем за один idle
                    colors_list = next(it)
                    TagIconGenerator.create_emblem_icon(colors_list, skip_cache_update=True)
                return True  # продолжить вызывать idle
            except StopIteration:
                print("[TagIconGenerator] Pregeneration complete!")

                def on_done():
                    # Планируем единичное обновление кеша после завершения генерации
                    TagIconGenerator.schedule_icon_cache_update()
                    if callback:
                        callback()
                    return False

                GLib.idle_add(on_done)
                return False  # остановить idle

        GLib.idle_add(process_batch, iterator)

    @staticmethod
    def create_emblem_icon(colors: List[str], skip_cache_update: bool = False) -> str:
        """Create elegant stacked emblem icon SVG for file/folder badges
        
        Args:
            colors: Список цветов для эмблемы
            skip_cache_update: Если True, не обновляет кеш GTK (используется при массовой генерации)
        """
        EMBLEMS_DIR.mkdir(parents=True, exist_ok=True)

        colors_to_use = colors[-3:] if len(colors) > 3 else colors

        color_signature = "-".join([c.replace("#", "") for c in colors_to_use])
        emblem_name = f"nemo-tag-emblem-{color_signature}"
        
        # Проверяем кеш - если эмблема уже создана, не создаём повторно
        with TagIconGenerator._lock:
            if emblem_name in TagIconGenerator._created_emblems:
                return emblem_name
        
        emblem_path = EMBLEMS_DIR / f"{emblem_name}.svg"

        size = 16
        radius = 3
        num_circles = len(colors_to_use)

        svg_circles = []

        if num_circles == 1:
            svg_circles.append(
                f'<circle cx="{size / 2}" cy="{size / 2}" r="{radius}" fill="{colors_to_use[0]}"/>'
            )

        elif num_circles == 2:
            offset = 2.5
            positions = [(size / 2 - offset, size / 2), (size / 2 + offset, size / 2)]

            for i, color in enumerate(colors_to_use):
                svg_circles.append(
                    f'<circle cx="{positions[i][0]}" cy="{positions[i][1]}" r="{radius}" fill="{color}"/>'
                )

        else:
            offset_x = 2.2
            offset_y = 1.8
            positions = [
                (size / 2 - offset_x, size / 2 + offset_y),
                (size / 2 + offset_x, size / 2 + offset_y),
                (size / 2, size / 2 - offset_y),
            ]

            for i, color in enumerate(colors_to_use):
                svg_circles.append(
                    f'<circle cx="{positions[i][0]}" cy="{positions[i][1]}" r="{radius}" fill="{color}"/>'
                )

        with open(emblem_path, "w", encoding="utf-8") as f:
            f.write(f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
{"".join(svg_circles)}
</svg>''')

        # Регистрируем эмблему как builtin-иконку в GTK
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(emblem_path), 16, 16, True
            )
            Gtk.IconTheme.add_builtin_icon(emblem_name, 16, pixbuf)
            
            print(
                f"[TagIconGenerator] Registered emblem: {emblem_name} (colors: {len(colors_to_use)})"
            )
        except Exception as e:
            print(f"Error registering builtin emblem {emblem_name}: {e}")

        # Копируем SVG в актуальную тему иконок
        TagIconGenerator._copy_to_theme(emblem_path, emblem_name)
        
        # Планируем обновление кеша иконок (только если не пропускаем)
        if not skip_cache_update:
            TagIconGenerator.schedule_icon_cache_update()
        
        # Добавляем в кеш созданных эмблем
        with TagIconGenerator._lock:
            TagIconGenerator._created_emblems.add(emblem_name)

        return emblem_name
    
    @staticmethod
    def delete_emblems_with_color(color: str):
        """Удаляет все эмблемы, содержащие указанный цвет.
        
        Удаляет как одноцветные эмблемы, так и многоцветные комбинации,
        содержащие этот цвет.
        
        Args:
            color: Цвет в формате #RRGGBB
        """
        color_sig = color.replace("#", "")
        home = Path.home()
        
        # Получаем список всех директорий с эмблемами
        theme_roots = []
        
        try:
            settings = Gtk.Settings.get_default()
            theme_name = (
                settings.props.gtk_icon_theme_name if settings is not None else None
            )
        except Exception:
            theme_name = None

        if theme_name:
            user_theme_root = home / ".local" / "share" / "icons" / theme_name
            for sub in ("16/emblems", "22/emblems", "scalable/emblems"):
                theme_roots.append(user_theme_root / sub)

        fallback_root = home / ".icons" / "hicolor"
        theme_roots.append(fallback_root / "scalable" / "emblems")
        theme_roots.append(EMBLEMS_DIR)
        
        deleted_count = 0
        
        # Удаляем файлы эмблем, содержащие цвет
        for emblems_dir in theme_roots:
            if not emblems_dir.exists():
                continue
                
            try:
                # Ищем все файлы эмблем с этим цветом
                for emblem_file in emblems_dir.glob(f"nemo-tag-emblem-*{color_sig}*.svg"):
                    try:
                        emblem_file.unlink()
                        deleted_count += 1
                        print(f"[TagIconGenerator] Deleted emblem: {emblem_file.name}")
                        
                        # Удаляем из кеша
                        emblem_name = emblem_file.stem
                        with TagIconGenerator._lock:
                            TagIconGenerator._created_emblems.discard(emblem_name)
                            
                    except Exception as e:
                        print(f"Error deleting emblem {emblem_file}: {e}")
                        
            except Exception as e:
                print(f"Error scanning directory {emblems_dir}: {e}")
        
        if deleted_count > 0:
            print(f"[TagIconGenerator] Deleted {deleted_count} emblem(s) with color {color}")
            # Планируем обновление кеша иконок после удаления
            TagIconGenerator.schedule_icon_cache_update()
    
    @staticmethod
    def _copy_to_theme(emblem_path: Path, emblem_name: str):
        """Копирует эмблему в директории тем иконок"""
        theme_roots = set()
        home = Path.home()

        try:
            settings = Gtk.Settings.get_default()
            theme_name = (
                settings.props.gtk_icon_theme_name if settings is not None else None
            )
        except Exception:
            theme_name = None

        if theme_name:
            user_theme_root = home / ".local" / "share" / "icons" / theme_name
            theme_roots.add(user_theme_root)

            for sub in ("16/emblems", "22/emblems", "scalable/emblems"):
                target_dir = user_theme_root / sub
                try:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy(emblem_path, target_dir / f"{emblem_name}.svg")
                except Exception:
                    pass

        fallback_root = home / ".icons" / "hicolor"
        theme_roots.add(fallback_root)
        fallback_emblems = fallback_root / "scalable" / "emblems"
        try:
            fallback_emblems.mkdir(parents=True, exist_ok=True)
            shutil.copy(emblem_path, fallback_emblems / f"{emblem_name}.svg")
        except Exception:
            pass
    
    @staticmethod
    def _update_icon_cache():
        """Обновляет кеш иконок GTK (вызывать только из главного потока).
        
        Обычно не вызывается напрямую, используйте schedule_icon_cache_update,
        чтобы отложить обновление и коалесцировать несколько запросов.
        """
        home = Path.home()
        theme_roots = set()
        
        try:
            settings = Gtk.Settings.get_default()
            theme_name = (
                settings.props.gtk_icon_theme_name if settings is not None else None
            )
        except Exception:
            theme_name = None

        if theme_name:
            user_theme_root = home / ".local" / "share" / "icons" / theme_name
            theme_roots.add(user_theme_root)

        fallback_root = home / ".icons" / "hicolor"
        theme_roots.add(fallback_root)

        for root in theme_roots:
            if root.exists():
                try:
                    subprocess.run(
                        ["gtk-update-icon-cache", "-f", str(root)],
                        capture_output=True,
                        timeout=5
                    )
                except Exception:
                    pass

    @staticmethod
    def schedule_icon_cache_update(delay_ms: int = 1000):
        """Планирует единичное обновление кеша иконок с задержкой.

        - Всегда выполняется в главном GTK-потоке (через GLib.timeout_add).
        - Если обновление уже запланировано, повторные вызовы ничего не делают.
        Это исключает ситуацию, когда gtk-update-icon-cache вызывается раньше
        фактической записи SVG-файлов и уменьшает количество запусков утилиты.
        """
        with TagIconGenerator._lock:
            if TagIconGenerator._cache_update_scheduled:
                return

            TagIconGenerator._cache_update_scheduled = True

        def do_update():
            try:
                TagIconGenerator._update_icon_cache()
                TagIconGenerator.refresh_icon_theme()
            finally:
                with TagIconGenerator._lock:
                    TagIconGenerator._cache_update_scheduled = False

            return False

        # Отложенный запуск, чтобы гарантировать завершение всех записей файлов
        GLib.timeout_add(delay_ms, do_update)

    @staticmethod
    def clear_cache():
        """Очищает кеш созданных эмблем (для тестирования или при изменении цвета)"""
        with TagIconGenerator._lock:
            TagIconGenerator._created_emblems.clear()
    
    @staticmethod
    def refresh_icon_theme():
        """Принудительно обновляет тему иконок GTK"""
        try:
            icon_theme = Gtk.IconTheme.get_default()
            if icon_theme:
                icon_theme.rescan_if_needed()
        except Exception as e:
            print(f"Error refreshing icon theme: {e}")
