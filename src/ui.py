import os
import subprocess

from gi.repository import GdkPixbuf, Gtk, Gdk, GLib, Nemo

from icons import TagIconGenerator
from manager import TagManager


class TagDialog(Gtk.Dialog):
    def __init__(self, parent=None, edit_mode=False, initial_name="", initial_color="#3498db"):
        title = "Edit Tag" if edit_mode else "Create Tag"
        Gtk.Dialog.__init__(
            self,
            title=title,
            transient_for=parent,
            flags=Gtk.DialogFlags.MODAL,
        )
        self.set_default_size(300, 150)

        self.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("_OK", Gtk.ResponseType.OK)

        box = self.get_content_area()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_border_width(12)
        box.add(vbox)

        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name_label = Gtk.Label(label="Tag name:")
        name_label.set_xalign(0.0)
        self.name_entry = Gtk.Entry()
        self.name_entry.set_text(initial_name)
        name_box.pack_start(name_label, False, False, 0)
        name_box.pack_start(self.name_entry, True, True, 0)
        vbox.pack_start(name_box, False, False, 0)

        color_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        color_label = Gtk.Label(label="Color:")
        color_label.set_xalign(0.0)
        self.color_button = Gtk.ColorButton()
        
        # Установка начального цвета
        rgba = Gdk.RGBA()
        rgba.parse(initial_color)
        self.color_button.set_rgba(rgba)
        
        color_box.pack_start(color_label, False, False, 0)
        color_box.pack_start(self.color_button, False, False, 0)
        vbox.pack_start(color_box, False, False, 0)

        self.show_all()

    def run_dialog(self):
        response = self.run()
        name = self.name_entry.get_text().strip()
        color_hex = None

        if response == Gtk.ResponseType.OK and name:
            rgba = self.color_button.get_rgba()
            r = int(rgba.red * 255)
            g = int(rgba.green * 255)
            b = int(rgba.blue * 255)
            color_hex = "#{:02X}{:02X}{:02X}".format(r, g, b)

        self.destroy()
        if response == Gtk.ResponseType.OK and name and color_hex:
            return name, color_hex

        return None, None


class RenameTagDialog(Gtk.Window):
    """Плавающее окно для переименования тега"""
    def __init__(self, initial_name=""):
        Gtk.Window.__init__(self, title="Rename Tag")
        self.set_default_size(300, 100)
        self.set_resizable(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_keep_above(True)
        
        # Для тайлинговых WM
        self.set_decorated(True)
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_border_width(15)
        
        # Поле ввода
        self.name_entry = Gtk.Entry()
        self.name_entry.set_text(initial_name)
        self.name_entry.set_placeholder_text("Enter tag name")
        self.name_entry.connect("activate", lambda w: self.on_ok())
        vbox.pack_start(self.name_entry, True, True, 0)
        
        # Кнопки
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_halign(Gtk.Align.END)
        
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda w: self.on_cancel())
        button_box.pack_start(cancel_btn, False, False, 0)
        
        ok_btn = Gtk.Button(label="OK")
        ok_btn.get_style_context().add_class("suggested-action")
        ok_btn.connect("clicked", lambda w: self.on_ok())
        button_box.pack_start(ok_btn, False, False, 0)
        
        vbox.pack_start(button_box, False, False, 0)
        
        self.add(vbox)
        self.result = None
        
    def on_ok(self):
        self.result = self.name_entry.get_text().strip()
        self.destroy()
        Gtk.main_quit()
        
    def on_cancel(self):
        self.result = None
        self.destroy()
        Gtk.main_quit()
    
    def run(self):
        self.show_all()
        self.name_entry.grab_focus()
        Gtk.main()
        return self.result


class ColorPickerDialog(Gtk.ColorChooserDialog):
    """Диалог выбора цвета"""
    def __init__(self, initial_color="#3498db"):
        Gtk.ColorChooserDialog.__init__(self, title="Choose Color")
        
        rgba = Gdk.RGBA()
        rgba.parse(initial_color)
        self.set_rgba(rgba)
        
    def run_dialog(self):
        response = self.run()
        color_hex = None
        
        if response == Gtk.ResponseType.OK:
            rgba = self.get_rgba()
            r = int(rgba.red * 255)
            g = int(rgba.green * 255)
            b = int(rgba.blue * 255)
            color_hex = "#{:02X}{:02X}{:02X}".format(r, g, b)
        
        self.destroy()
        return color_hex


class TagReorderDialog(Gtk.Dialog):
    """Диалог для изменения порядка тегов"""
    def __init__(self, parent, manager: TagManager):
        Gtk.Dialog.__init__(
            self,
            title="Reorder Tags",
            transient_for=parent,
            flags=Gtk.DialogFlags.MODAL,
        )
        self.manager = manager
        self.set_default_size(400, 300)
        
        # Кнопки
        self.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        save_button = self.add_button("_Save", Gtk.ResponseType.OK)
        save_button.get_style_context().add_class("suggested-action")
        
        # Контент
        box = self.get_content_area()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_border_width(12)
        box.add(vbox)
        
        # Инструкция
        label = Gtk.Label(label="Drag tags to reorder them:")
        label.set_xalign(0.0)
        vbox.pack_start(label, False, False, 0)
        
        # ScrolledWindow для TreeView
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        
        # TreeView для списка тегов
        self.store = Gtk.ListStore(str, str, str)  # id, name, color
        self.treeview = Gtk.TreeView(model=self.store)
        self.treeview.set_reorderable(True)
        
        # Колонка с иконкой и именем
        renderer_pixbuf = Gtk.CellRendererPixbuf()
        renderer_text = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Tag")
        column.pack_start(renderer_pixbuf, False)
        column.pack_start(renderer_text, True)
        column.set_cell_data_func(renderer_pixbuf, self._render_icon)
        column.add_attribute(renderer_text, "text", 1)
        self.treeview.append_column(column)
        
        # Заполняем список тегами
        tags = self.manager.get_tags()
        for tag in tags:
            self.store.append([tag["id"], tag["name"], tag["color"]])
        
        scrolled.add(self.treeview)
        vbox.pack_start(scrolled, True, True, 0)
        
        self.show_all()
    
    def _render_icon(self, _column, cell, model, iter, _data):
        """Рендерит иконку тега в TreeView"""
        color = model.get_value(iter, 2)
        icon_path = TagIconGenerator.create_tag_icon(color, 24)
        
        if os.path.exists(icon_path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_path, 24, 24, True)
                cell.set_property("pixbuf", pixbuf)
            except Exception as e:
                print(f"Error loading icon: {e}")
                cell.set_property("pixbuf", None)
        else:
            cell.set_property("pixbuf", None)
    
    def get_ordered_tag_ids(self):
        """Возвращает список ID тегов в текущем порядке"""
        tag_ids = []
        iter = self.store.get_iter_first()
        while iter:
            tag_id = self.store.get_value(iter, 0)
            tag_ids.append(tag_id)
            iter = self.store.iter_next(iter)

        return tag_ids


class TagLocationWidget(Gtk.Box):
    def __init__(self, manager: TagManager, extension):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.manager = manager
        self.extension = extension
        self.drag_source_button = None
        self.drag_source_tag_id = None

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        label_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        label_box.set_margin_start(12)
        label_box.set_margin_end(8)
        label_box.set_margin_top(4)
        label_box.set_margin_bottom(4)

        tag_icon = Gtk.Image.new_from_icon_name("tag", Gtk.IconSize.MENU)
        label_box.pack_start(tag_icon, False, False, 0)

        label = Gtk.Label(label="Tags:")
        label_box.pack_start(label, False, False, 0)
        
        self.main_box.pack_start(label_box, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scrolled.set_size_request(-1, 40)

        self.tags_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.tags_box.set_margin_top(4)
        self.tags_box.set_margin_bottom(4)
        self.tags_box.set_margin_start(4)
        self.tags_box.set_margin_end(8)

        scrolled.add(self.tags_box)
        self.main_box.pack_start(scrolled, True, True, 0)
        
        # Кнопка настроек
        self.settings_button = Gtk.Button()
        self.settings_button.set_relief(Gtk.ReliefStyle.NONE)
        self.settings_button.set_tooltip_text("Reorder tags")
        
        settings_icon = Gtk.Image.new_from_icon_name("view-continuous-symbolic", Gtk.IconSize.BUTTON)
        self.settings_button.set_image(settings_icon)
        
        self.settings_button.set_margin_end(8)
        self.settings_button.set_margin_top(4)
        self.settings_button.set_margin_bottom(4)
        self.settings_button.connect("clicked", self.on_settings_clicked)
        
        self.main_box.pack_end(self.settings_button, False, False, 0)

        self.pack_start(self.main_box, True, True, 0)

        self.separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(self.separator, False, False, 0)

        self.refresh()
    
    def on_settings_clicked(self, button):
        """Обработчик нажатия на кнопку настроек"""
        # Получаем родительское окно
        parent_window = self.get_toplevel()
        if not isinstance(parent_window, Gtk.Window):
            parent_window = None
        
        dialog = TagReorderDialog(parent_window, self.manager)
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK:
            # Получаем новый порядок тегов
            new_order = dialog.get_ordered_tag_ids()
            
            # Сохраняем новый порядок
            if self.manager.reorder_tags(new_order):
                # Обновляем все виджеты
                for widget in self.extension.location_widgets:
                    widget.refresh()
        
        dialog.destroy()

    def refresh(self):
        for child in self.tags_box.get_children():
            self.tags_box.remove(child)

        tags = self.manager.get_tags()
        
        # Скрываем виджет если тегов нет
        if not tags:
            self.hide()
            return
        else:
            self.show_all()
            
        # Скрываем кнопку настроек если тегов меньше 2
        if len(tags) < 2:
            self.settings_button.hide()
        else:
            self.settings_button.show()

        for tag in tags:
            # EventBox для обработки событий
            event_box = Gtk.EventBox()
            
            btn = Gtk.Button(label=tag["name"])
            btn.set_relief(Gtk.ReliefStyle.NONE)

            # Увеличенный размер иконки тега (24px вместо 16px)
            icon_path = TagIconGenerator.create_tag_icon(tag["color"], 24)
            if os.path.exists(icon_path):
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    icon_path, 24, 24, True
                )
                image = Gtk.Image.new_from_pixbuf(pixbuf)
                btn.set_image(image)
                btn.set_always_show_image(True)

            btn.connect("clicked", self.on_tag_clicked, tag["id"], tag["name"])
            btn.connect(
                "button-press-event", self.on_tag_button_press, tag["id"], tag["name"], tag["color"]
            )

            event_box.add(btn)
            
            # Настройка Drag & Drop для EventBox
            event_box.drag_source_set(
                Gdk.ModifierType.BUTTON1_MASK,
                [],
                Gdk.DragAction.MOVE
            )
            event_box.drag_source_add_text_targets()
            event_box.connect("drag-begin", self.on_drag_begin, tag["id"])
            event_box.connect("drag-data-get", self.on_drag_data_get, tag["id"])
            event_box.connect("drag-end", self.on_drag_end)

            event_box.drag_dest_set(
                Gtk.DestDefaults.ALL,
                [],
                Gdk.DragAction.MOVE
            )
            event_box.drag_dest_add_text_targets()
            event_box.connect("drag-data-received", self.on_drag_data_received, tag["id"])
            event_box.connect("drag-motion", self.on_drag_motion)

            self.tags_box.pack_start(event_box, False, False, 0)
            event_box.show_all()

    def on_drag_begin(self, _widget, _context, tag_id):
        self.drag_source_tag_id = tag_id

    def on_drag_data_get(self, _widget, _context, data, _info, _time, tag_id):
        data.set_text(str(tag_id), -1)

    def on_drag_end(self, _widget, _context):
        self.drag_source_tag_id = None

    def on_drag_motion(self, _widget, context, _x, _y, time):
        Gdk.drag_status(context, Gdk.DragAction.MOVE, time)
        return True

    def on_drag_data_received(self, _widget, context, _x, _y, data, _info, time, target_tag_id):
        source_tag_id = data.get_text()
        if not source_tag_id or source_tag_id == target_tag_id:
            context.finish(False, False, time)
            return

        # Получаем текущий порядок тегов
        tags = self.manager.get_tags()
        tag_ids = [tag["id"] for tag in tags]
        
        if source_tag_id not in tag_ids or target_tag_id not in tag_ids:
            context.finish(False, False, time)
            return

        # Перемещаем тег
        source_index = tag_ids.index(source_tag_id)
        target_index = tag_ids.index(target_tag_id)
        
        tag_ids.pop(source_index)
        tag_ids.insert(target_index, source_tag_id)

        # Обновляем порядок в базе данных
        self.manager.reorder_tags(tag_ids)
        
        context.finish(True, False, time)
        
        # Обновляем все виджеты
        for w in self.extension.location_widgets:
            w.refresh()

    def _get_file_info_for_path(self, file_path):
        """Получаем Nemo.FileInfo для файла по пути"""
        try:
            from gi.repository import Gio
            file = Gio.File.new_for_path(file_path)
            return Nemo.FileInfo.create_for_uri(file.get_uri())
        except Exception as e:
            print(f"Error getting file info for {file_path}: {e}")
            return None

    def _delayed_invalidate_path(self, file_path):
        """Отложенная инвалидация файла для обновления эмблемы"""
        file_info = self._get_file_info_for_path(file_path)
        if file_info:
            file_info.invalidate_extension_info()
        return False  # Возвращаем False, чтобы timeout выполнился только один раз

    def on_tag_button_press(self, _button, event, tag_id, tag_name, tag_color):
        if event.button == 3:  # ПКМ
            menu = Gtk.Menu()

            # Пункт "Rename tag"
            rename_item = Gtk.MenuItem(label="Rename tag")
            rename_item.connect("activate", self.on_rename_tag, tag_id, tag_name, tag_color)
            menu.append(rename_item)

            # Пункт "Change color"
            color_item = Gtk.MenuItem(label="Change color")
            color_item.connect("activate", self.on_change_color, tag_id, tag_name, tag_color)
            menu.append(color_item)

            # Разделитель
            separator = Gtk.SeparatorMenuItem()
            menu.append(separator)

            # Пункт "Delete tag"
            delete_item = Gtk.MenuItem(label="Delete tag")
            delete_item.connect("activate", self.on_delete_tag, tag_id, tag_name, tag_color)
            menu.append(delete_item)

            menu.show_all()
            menu.popup(None, None, None, None, event.button, event.time)
            return True
        return False

    def on_rename_tag(self, _menu_item, tag_id, tag_name, tag_color):
        dialog = RenameTagDialog(initial_name=tag_name)
        new_name = dialog.run()
        
        if new_name and new_name != tag_name:
            self.manager.update_tag(tag_id, new_name, tag_color)
            
            # Обновляем все виджеты
            for widget in self.extension.location_widgets:
                widget.refresh()

    def on_change_color(self, _menu_item, tag_id, tag_name, tag_color):
        dialog = ColorPickerDialog(initial_color=tag_color)
        new_color = dialog.run_dialog()
        
        if new_color and new_color != tag_color:
            # Получаем все файлы с этим тегом ДО обновления
            files = self.manager.get_files_by_tag(tag_id)
            
            # Обновляем цвет тега
            self.manager.update_tag(tag_id, tag_name, new_color)
            
            # Создаём новую иконку для тега
            TagIconGenerator.create_tag_icon(new_color, 24)
            
            # Пересоздаём эмблемы для всех файлов с этим тегом
            for file_path in files:
                if not os.path.exists(file_path):
                    continue
                    
                # Получаем обновлённый список тегов для файла
                tags_for_file = self.manager.get_tags_for_file(file_path)
                colors = [t["color"] for t in tags_for_file if "color" in t]
                
                # Генерируем новую эмблему с обновлённым цветом
                if colors:
                    TagIconGenerator.create_emblem_icon(colors)
                
                # Асинхронная задержка 1000мс перед инвалидацией
                GLib.timeout_add(1000, self._delayed_invalidate_path, file_path)
            
            # Обновляем тему иконок GTK
            GLib.timeout_add(1000, self.extension.refresh_all_visible_files)
            
            # Обновляем все виджеты
            for widget in self.extension.location_widgets:
                widget.refresh()

    def on_delete_tag(self, _menu_item, tag_id, tag_name, tag_color):
        dialog = Gtk.MessageDialog(
            transient_for=None,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Delete tag '{tag_name}'?",
        )
        dialog.format_secondary_text(
            "This will remove the tag from all files. This action cannot be undone."
        )

        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            # Получаем все файлы с этим тегом ДО удаления
            files = self.manager.get_files_by_tag(tag_id)
            
            # Удаляем тег
            self.manager.delete_tag(tag_id)
            
            # Удаляем все эмблемы, содержащие этот цвет
            TagIconGenerator.delete_emblems_with_color(tag_color)
            
            # Пересоздаём эмблемы для всех файлов, которые имели этот тег
            for file_path in files:
                if not os.path.exists(file_path):
                    continue
                    
                # Получаем оставшиеся теги для файла
                tags_for_file = self.manager.get_tags_for_file(file_path)
                colors = [t["color"] for t in tags_for_file if "color" in t]
                
                # Генерируем эмблему для оставшихся тегов (или удаляем если тегов не осталось)
                if colors:
                    TagIconGenerator.create_emblem_icon(colors)
                
                # Асинхронная задержка 1000мс перед инвалидацией
                GLib.timeout_add(1000, self._delayed_invalidate_path, file_path)
            
            # Обновляем тему иконок GTK
            GLib.timeout_add(1000, self.extension.refresh_all_visible_files)
            
            # Обновляем все виджеты
            for widget in self.extension.location_widgets:
                widget.refresh()

    def on_tag_clicked(self, _button, tag_id, tag_name):
        view_dir = self.manager.create_tag_view(tag_id, tag_name)
        if view_dir:
            try:
                subprocess.Popen(["nemo", "--existing-window", "-t", view_dir])
            except Exception as e:
                print(f"Error opening Nemo tab: {e}")

                # Fallback: открываем новое окно
                try:
                    subprocess.Popen(["nemo", view_dir])
                except Exception as e2:
                    print(f"Error opening Nemo window: {e2}")
        else:
            dialog = Gtk.MessageDialog(
                transient_for=None,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text=f"No files tagged with '{tag_name}'",
            )
            dialog.run()
            dialog.destroy()
