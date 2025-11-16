import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from header import VIEWS_DIR
from database import TagDatabase


class TagManager:
    def __init__(self, db_path: Optional[Path] = None):
        self.db = TagDatabase(db_path)

    def create_tag(self, name: str, color: str) -> str:
        return self.db.add_tag(name, color)

    def delete_tag(self, tag_id: str):
        return self.db.remove_tag(tag_id)

    def update_tag(self, tag_id: str, name: str, color: str) -> bool:
        """Обновляет имя и/или цвет тега"""
        return self.db.update_tag(tag_id, name, color)

    def reorder_tags(self, tag_ids: List[str]) -> bool:
        """Изменяет порядок тегов"""
        return self.db.reorder_tags(tag_ids)

    def assign_tag_to_file(self, tag_id: str, file_path: str):
        self.db.assign_tag(tag_id, file_path)

    def unassign_tag_from_file(self, tag_id: str, file_path: str):
        self.db.unassign_tag(tag_id, file_path)

    def get_tags(self) -> List[Dict]:
        return self.db.get_tags()

    def get_tag_by_id(self, tag_id: str) -> Optional[Dict]:
        return self.db.get_tag_by_id(tag_id)

    def get_files_by_tag(self, tag_id: str) -> List[str]:
        return self.db.files_by_tag(tag_id)

    def get_tags_for_file(self, file_path: str) -> List[Dict]:
        return self.db.tags_for_file(file_path)

    def is_file_tagged(self, tag_id: str, file_path: str) -> bool:
        return self.db.is_tagged(tag_id, file_path)

    def flush_db(self):
        self.db.flush()

    def create_tag_view(self, tag_id: str, tag_name: str) -> Optional[str]:
        files = self.get_files_by_tag(tag_id)
        if not files:
            return None

        VIEWS_DIR.mkdir(parents=True, exist_ok=True)
        view_dir = VIEWS_DIR / f"tag-{tag_id}"

        if view_dir.exists():
            shutil.rmtree(view_dir)

        view_dir.mkdir()

        for file_path in files:
            if not os.path.exists(file_path):
                continue

            filename = os.path.basename(file_path)
            link_path = view_dir / filename

            counter = 1
            while link_path.exists():
                name, ext = os.path.splitext(filename)
                link_path = view_dir / f"{name}_{counter}{ext}"
                counter += 1

            try:
                os.symlink(file_path, link_path)
            except Exception as e:
                print(f"Error creating symlink: {e}")

        return str(view_dir)
