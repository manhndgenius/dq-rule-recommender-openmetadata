from backend.datasource.base import BaseDatasource


class TableProfiler:
    """Runs read-only profiling queries through a datasource adapter."""

    def __init__(self, datasource: BaseDatasource) -> None:
        self.datasource = datasource
