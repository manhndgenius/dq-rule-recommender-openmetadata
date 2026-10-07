from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseDatasource(ABC):
    @abstractmethod
    def list_databases(self) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def list_schemas(self, database: str) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def list_tables(self, database: str, schema: str) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def get_columns(self, database: str, schema: str, table: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def execute_readonly_query(self, sql: str) -> List[Dict[str, Any]]:
        raise NotImplementedError
