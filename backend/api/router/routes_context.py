from fastapi import APIRouter

from backend.config.settings import settings
from backend.contracts.table_context import TableContext
from backend.integrations.openmetadata.client import openmetadata_client


router = APIRouter(prefix=settings.api_prefix, tags=["context"])


@router.get("/context/{table_name}", response_model=TableContext)
def get_table_context(table_name: str) -> TableContext:
    return openmetadata_client.get_table_context(table_name)
