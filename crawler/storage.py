import json
import csv
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class Storage:
    def __init__(self, output_dir: str = "data"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        self.jsonl_path = os.path.join(output_dir, "results.jsonl")
        self.csv_path = os.path.join(output_dir, "results.csv")
        self._count = 0

        # Очищаем файлы при каждом запуске краулера
        open(self.jsonl_path, "w").close()
        open(self.csv_path, "w").close()
        logger.info("Папка data очищена, начинаем запись заново")

    def save(self, data: dict):
        data["crawled_at"] = datetime.now().isoformat()
        self._save_jsonl(data)
        self._save_csv(data)
        self._count += 1

    def _save_jsonl(self, data: dict):
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def _save_csv(self, data: dict):
        flat = {
            "url": data.get("url"),
            "title": data.get("title"),
            "meta_description": data.get("meta_description"),
            "h1": "; ".join(data.get("headings", {}).get("h1", [])),
            "h2": "; ".join(data.get("headings", {}).get("h2", [])),
            "links_count": data.get("links_count"),
            "images_count": data.get("images_count"),
            "text_length": data.get("text_length"),
            "crawled_at": data.get("crawled_at"),
        }
        # Если файл пустой — пишем заголовок, иначе просто добавляем строку
        file_empty = os.path.getsize(self.csv_path) == 0
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=flat.keys())
            if file_empty:
                writer.writeheader()
            writer.writerow(flat)

    @property
    def count(self):
        return self._count