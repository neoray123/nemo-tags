import os
from pathlib import Path
from typing import List

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Nemo

from header import VIEWS_DIR
from icons import TagIconGenerator
from manager import TagManager
from ui import TagDialog
from ui import TagLocationWidget


class NemoTagsExtension(
    GObject.GObject, Nemo.MenuProvider, Nemo.LocationWidgetProvider, Nemo.InfoProvider
):
    def __init__(self):
        GObject.Object.__init__(self)
        self.manager = TagManager()
        self.icon_generator = TagIconGenerator()
        self.location_widgets = []
        tags = self.manager.get_tags()

        # Предварительно генерируем все возможные комбинации эмблем.
        # Обновление кеша и темы иконок произойдёт внутри TagIconGenerator
        # после завершения фоновой генерации.
        TagIconGenerator.pregenerate_all_combinations(tags)
        self.refresh_all_visible_files()

    def refresh_all_visible_files(self):
        TagIconGenerator.refresh_icon_theme()
        for widget in self.location_widgets:
            widget.refresh()

    def _get_tag_id_from_view_path(self, path: str) -> str:
        """Извлекает tag_id из пути к файлу в виртуальной папке тега"""
        path_obj = Path(path)
        # Проверяем, находится ли файл в директории views
        try:
            relative = path_obj.relative_to(VIEWS_DIR)
            # Первая часть пути - это папка tag-{id}
            tag_folder = relative.parts[0]
            if tag_folder.startswith("tag-"):
                return tag_folder[4:]  # Убираем префикс "tag-"
        except (ValueError, IndexError):
            pass
        return None

    def update_file_info(self, file_info: Nemo.FileInfo):
        if file_info.get_uri_scheme() != "file":
            return Nemo.OperationResult.COMPLETE
        path = file_info.get_location().get_path()
        if not path:
            return Nemo.OperationResult.COMPLETE

        # Проверяем, находится ли файл в виртуальной папке тега
        tag_id = self._get_tag_id_from_view_path(path)

        if tag_id:
            # Файл находится в виртуальной папке тега
            tag = self.manager.get_tag_by_id(tag_id)
            if tag and "color" in tag:
                emblem_name = TagIconGenerator.create_emblem_icon([tag["color"]])
                file_info.add_emblem(emblem_name)
        else:
            # Обычный файл - показываем все его теги
            tags = self.manager.get_tags_for_file(path)
            if tags:
                colors = [tag["color"] for tag in tags if "color" in tag]
                if colors:
                    emblem_name = TagIconGenerator.create_emblem_icon(colors)
                    file_info.add_emblem(emblem_name)

        return Nemo.OperationResult.COMPLETE

    def get_file_items(self, window, files: List[Nemo.FileInfo]):
        menu_items = []
        target_files = [f for f in files if f.get_uri_scheme() == "file"]

        if not target_files:
            return []

        single_file = len(target_files) == 1
        file_path = target_files[0].get_location().get_path() if single_file else None
        submenu = Nemo.Menu()
        tags = self.manager.get_tags()

        if tags:
            for tag in tags:
                is_assigned = False
                if single_file and file_path:
                    is_assigned = self.manager.is_file_tagged(tag["id"], file_path)
                label = f"✓ {tag['name']}" if is_assigned else tag["name"]
                tag_item = Nemo.MenuItem(
                    name=f"NemoTags::toggle_tag_{tag['id']}",
                    label=label,
                )
                icon_path = self.icon_generator.create_tag_icon(tag["color"], 16)
                if os.path.exists(icon_path):
                    tag_item.set_property("icon", icon_path)
                if is_assigned:
                    tag_item.connect(
                        "activate", self.remove_tag, target_files, tag["id"]
                    )
                else:
                    tag_item.connect(
                        "activate", self.apply_tag, target_files, tag["id"]
                    )
                submenu.append_item(tag_item)
        if tags:
            sep = Nemo.MenuItem(
                name="NemoTags::separator", label="─────────", sensitive=False
            )
            submenu.append_item(sep)
        create_item = Nemo.MenuItem(
            name="NemoTags::create_tag",
            label="Create Tag",
            icon="list-add",
        )
        create_item.connect("activate", self.create_tag, target_files, window)
        submenu.append_item(create_item)
        tags_menu = Nemo.MenuItem(
            name="NemoTags::assign_tag_main",
            label="Assign Tag",
            icon="tag",
        )
        tags_menu.set_submenu(submenu)
        menu_items.append(tags_menu)
        return menu_items

    def get_widget(self, _uri, _window):
        widget = TagLocationWidget(self.manager, self)
        self.location_widgets.append(widget)
        return widget

    def _delayed_invalidate(self, file_info):
        file_info.invalidate_extension_info()
        return False

    def apply_tag(self, _menu, files, tag_id: str):
        for f in files:
            loc = f.get_location()
            if loc is None:
                continue
            path = loc.get_path()
            if not path:
                continue
            self.manager.assign_tag_to_file(tag_id, path)
            tags_for_file = self.manager.get_tags_for_file(path)
            colors = [t["color"] for t in tags_for_file if "color" in t]
            if colors:
                TagIconGenerator.create_emblem_icon(colors)
            self.refresh_all_visible_files()
            GLib.timeout_add(1000, self._delayed_invalidate, f)

    def remove_tag(self, menu, files, tag_id: str):
        for f in files:
            loc = f.get_location()
            if loc is None:
                continue

            path = loc.get_path()
            if not path:
                continue

            self.manager.unassign_tag_from_file(tag_id, path)
            tags_for_file = self.manager.get_tags_for_file(path)
            colors = [t["color"] for t in tags_for_file if "color" in t]

            # Эмблема без удалённого цвета
            if colors:
                TagIconGenerator.create_emblem_icon(colors)
            
            # Если файл вообще остался без тегов, можно "удалить" эмблему путем инвалидации
            self.refresh_all_visible_files()
            GLib.timeout_add(1000, self._delayed_invalidate, f)

        # Теперь пересоздаём эмблемы для всех возможных комбинаций без удалённого цвета
        tags = self.manager.get_tags()
        colors = [tag["color"] for tag in tags if "color" in tag]
        TagIconGenerator.pregenerate_all_combinations(tags)
        self.refresh_all_visible_files()

    def create_tag(self, menu, files, window):
        dialog = TagDialog(parent=window)
        name, color = dialog.run_dialog()

        if not (name and color):
            return
        
        tag_id = self.manager.create_tag(name, color)
        tags = self.manager.get_tags()
        TagIconGenerator.create_tag_icon(color, 16)
        TagIconGenerator.pregenerate_all_combinations(tags)
        self.refresh_all_visible_files()
        for f in files:
            loc = f.get_location()

            if loc is None:
                continue

            path = loc.get_path()
            if not path:
                continue

            self.manager.assign_tag_to_file(tag_id, path)
            tags_for_file = self.manager.get_tags_for_file(path)
            colors = [t["color"] for t in tags_for_file if "color" in t]

            if colors:
                TagIconGenerator.create_emblem_icon(colors)

            GLib.timeout_add(1000, self._delayed_invalidate, f)

        for widget in self.location_widgets:
            widget.refresh()
            
        self.refresh_all_visible_files()
