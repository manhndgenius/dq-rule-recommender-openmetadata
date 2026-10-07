from backend.datasource.base import BaseDatasource


class SchemaReader:
    def __init__(self, datasource: BaseDatasource) -> None:
        self.datasource = datasource

    def read_columns(self, database: str, schema: str, table: str):
        return self.datasource.get_columns(database, schema, table)
