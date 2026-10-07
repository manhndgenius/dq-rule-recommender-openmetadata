from backend.integrations.openmetadata.client import OpenMetadataClient
from backend.contracts.table_context import TableContext


class ContextBuilder:
    """Builds the shared TableContext contract from the active metadata adapter."""

    def __init__(self, metadata_client: OpenMetadataClient) -> None:
        self.metadata_client = metadata_client

    def build(self, table_name: str) -> TableContext:
        return self.metadata_client.get_table_context(table_name)
