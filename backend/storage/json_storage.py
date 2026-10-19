"""JSON File Storage Service cho Advanced Rules.

Lưu trữ tạm thời Advanced Rules vào file JSON.
- Generate lại → ghi đè file
- Load → đọc từ file
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("json_storage")


class JSONStorageService:
    """Service để lưu/trữ Advanced Rules vào file JSON."""

    def __init__(self, storage_dir: str = "data"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.advanced_rules_file = self.storage_dir / "advanced_rules.json"

    def save_advanced_rules(self, table_name: str, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Lưu Advanced Rules vào file JSON.
        Ghi đè toàn bộ nội dung file.

        Args:
            table_name: Tên bảng
            rules: Danh sách rules

        Returns:
            Dict với số lượng đã lưu
        """
        try:
            data = {
                "table_name": table_name,
                "saved_at": datetime.utcnow().isoformat() + "Z",
                "total_rules": len(rules),
                "rules": rules
            }

            with open(self.advanced_rules_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"Saved {len(rules)} advanced rules to {self.advanced_rules_file}")
            return {'saved': len(rules), 'file': str(self.advanced_rules_file)}

        except Exception as e:
            logger.error(f"Failed to save advanced rules: {e}")
            raise

    def get_advanced_rules(self, table_name: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Đọc Advanced Rules từ file JSON.

        Args:
            table_name: Tên bảng (để verify, optional)

        Returns:
            Danh sách rules hoặc None nếu file không tồn tại
        """
        if not self.advanced_rules_file.exists():
            logger.info("No advanced rules file found")
            return None

        try:
            with open(self.advanced_rules_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Verify table_name if provided
            if table_name and data.get('table_name') != table_name:
                logger.warning(f"Table name mismatch: expected {table_name}, got {data.get('table_name')}")
                return None

            rules = data.get('rules', [])
            logger.info(f"Loaded {len(rules)} advanced rules from {self.advanced_rules_file}")
            return rules

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in advanced rules file: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to read advanced rules: {e}")
            return None

    def has_advanced_rules(self) -> bool:
        """Kiểm tra xem file có dữ liệu không."""
        return self.advanced_rules_file.exists() and self.advanced_rules_file.stat().st_size > 10

    def get_file_info(self) -> Optional[Dict[str, Any]]:
        """Lấy thông tin về file đã lưu."""
        if not self.advanced_rules_file.exists():
            return None

        stat = self.advanced_rules_file.stat()
        try:
            with open(self.advanced_rules_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return {
                'exists': True,
                'file': str(self.advanced_rules_file),
                'size_bytes': stat.st_size,
                'table_name': data.get('table_name'),
                'saved_at': data.get('saved_at'),
                'total_rules': data.get('total_rules', 0)
            }
        except Exception as e:
            return {
                'exists': True,
                'file': str(self.advanced_rules_file),
                'size_bytes': stat.st_size,
                'error': str(e)
            }

    def delete_advanced_rules(self) -> bool:
        """Xóa file lưu trữ."""
        try:
            if self.advanced_rules_file.exists():
                self.advanced_rules_file.unlink()
                logger.info(f"Deleted {self.advanced_rules_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete advanced rules file: {e}")
            return False


# Singleton instance
json_storage = JSONStorageService()
