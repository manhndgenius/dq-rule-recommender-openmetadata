from backend.datasource.base import BaseDatasource


class PostgresDatasource(BaseDatasource):
    """PostgreSQL connector boundary; implementation will be added with direct DB access."""

    def list_databases(self):
        raise NotImplementedError

    def list_schemas(self, database: str):
        raise NotImplementedError

    def list_tables(self, database: str, schema: str):
        raise NotImplementedError

    def get_columns(self, database: str, schema: str, table: str):
        raise NotImplementedError

    def execute_readonly_query(self, sql: str):
        raise NotImplementedError
