from backend.datasource.base import BaseDatasource


class SqlServerDatasource(BaseDatasource):
    """SQL Server connector boundary; optional in the current POC."""

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
