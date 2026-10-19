import logging
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
import requests

from backend.config.settings import settings
from backend.contracts.nt_execution import NTRuleResult
from backend.contracts.table_context import TableContext, ColumnContext, ColumnProfile, ProfileSource, ProfileScope

logger = logging.getLogger("openmetadata_client")

HEALTHCARE_TABLE_DESCRIPTIONS: Dict[str, str] = {
    "patients": "Bảng hồ sơ định danh và thông tin nhân khẩu học/lâm sàng của bệnh nhân (họ tên, ngày sinh, ngày tử vong, số an sinh xã hội SSN, địa chỉ và tổng chi phí khám chữa bệnh tích lũy).",
    "encounters": "Bảng lịch sử các đợt khám bệnh, cấp cứu, khám định kỳ và điều trị nội trú/ngoại trú của bệnh nhân tại các cơ sở y tế (thời gian tiếp nhận, lý do khám, khoa phòng điều trị).",
    "claims": "Bảng hồ sơ yêu cầu chi trả và bồi thường viện phí từ bảo hiểm y tế hoặc đơn vị bảo trợ (tổng số tiền yêu cầu bồi thường, số tiền được bảo hiểm chi trả, tình trạng phê duyệt đơn).",
    "claims_transactions": "Bảng chi tiết các giao dịch tài chính, thanh toán viện phí từng đợt và các khoản khấu trừ trực tiếp theo từng hồ sơ yêu cầu bồi thường bảo hiểm.",
    "conditions": "Bảng ghi nhận các bệnh lý, chẩn đoán xác định, tiền sử bệnh và tình trạng sức khỏe hiện tại của bệnh nhân theo chuẩn phân loại bệnh tật quốc tế ICD-10 và SNOMED-CT.",
    "medications": "Bảng danh mục đơn thuốc, lịch trình cấp phát thuốc, liều dùng, đường dùng và hướng dẫn điều trị bằng dược phẩm cho bệnh nhân.",
    "allergies": "Bảng theo dõi tiền sử dị ứng thuốc, dị ứng thức ăn và các tác nhân môi trường của bệnh nhân, phân loại mức độ nghiêm trọng và phản ứng lâm sàng tương ứng.",
    "careplans": "Bảng phác đồ điều trị, kế hoạch chăm sóc dài hạn và các mục tiêu can thiệp y tế đối với các bệnh mãn tính hoặc phục hồi chức năng sau phẫu thuật.",
    "procedures": "Bảng ghi nhận các thủ thuật y tế, phẫu thuật can thiệp, xét nghiệm chuyên sâu và chẩn đoán chức năng đã thực hiện trên bệnh nhân.",
    "observations": "Bảng lưu trữ các chỉ số sinh hiệu (huyết áp, nhịp tim, thân nhiệt, chỉ số BMI, SpO2) và kết quả xét nghiệm định lượng/định tính trong phòng thí nghiệm y khoa.",
    "immunizations": "Bảng quản lý lịch sử tiêm chủng vắc-xin phòng ngừa của bệnh nhân (tên loại vắc-xin, ngày tiêm, liều lượng, trạng thái tiêm và khuyến cáo tái chủng).",
    "devices": "Bảng quản lý các thiết bị y tế cấy ghép, máy tạo nhịp tim, nẹp cố định hoặc thiết bị hỗ trợ điều trị được gắn cho bệnh nhân.",
    "imaging_studies": "Bảng theo dõi các ca chẩn đoán hình ảnh chuyên sâu (chụp X-quang, cắt lớp vi tính CT, cộng hưởng từ MRI, siêu âm) và báo cáo kết luận của bác sĩ chẩn đoán hình ảnh.",
    "organizations": "Bảng danh mục các bệnh viện, trung tâm y tế, phòng khám đa khoa, chuỗi cơ sở chăm sóc sức khỏe và đơn vị vận hành y tế trong hệ thống.",
    "payers": "Bảng danh mục các công ty bảo hiểm y tế, quỹ bảo trợ xã hội và cơ quan quản lý chi trả viện phí chính thức.",
    "payer_transitions": "Bảng lịch sử chuyển đổi gói bảo hiểm hoặc chuyển quyền bảo trợ chi trả viện phí của bệnh nhân giữa các giai đoạn.",
    "providers": "Bảng danh bạ y bác sĩ, điều dưỡng, chuyên viên chăm sóc sức khỏe và nhân viên y tế phụ trách thăm khám, chỉ định điều trị.",
    "supplies": "Bảng quản lý vật tư y tế tiêu hao, thiết bị hỗ trợ và dụng cụ dùng trong quá trình khám chữa bệnh tại cơ sở y tế."
}

class OpenMetadataClient:
    """
    Client kết nối và trích xuất dữ liệu Schema & Profiling từ OpenMetadata REST API.
    Tuân thủ đầy đủ tài liệu D:\\VSF\\OPENMETADATA_WEB_INTEGRATION.md.
    Hỗ trợ caching 3 phút, parallel column profile fetching, và deriveTableProfile fallback.
    """

    def __init__(self, server_url: Optional[str] = None, token: Optional[str] = None):
        self.server_url = (server_url or settings.openmetadata_base_url).rstrip("/")
        self.token = token if token is not None else settings.openmetadata_jwt_token
        self.timeout = 10  # 10s timeout
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 180  # 3 phút cache

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get_from_cache(self, key: str) -> Optional[Any]:
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["ts"] < self._cache_ttl:
                return entry["data"]
            del self._cache[key]
        return None

    def _set_cache(self, key: str, data: Any):
        self._cache[key] = {"data": data, "ts": time.time()}

    def check_connection(self) -> bool:
        """Kiểm tra OpenMetadata server có online và phản hồi HTTP 200 không"""
        try:
            resp = requests.get(f"{self.server_url}/system/version", headers=self._get_headers(), timeout=5)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Lỗi kiểm tra kết nối OpenMetadata: {e}")
            return False

    def list_services(self) -> List[Dict[str, Any]]:
        """Lấy danh sách Database Services (Section 5.1)"""
        cache_key = "services"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.server_url}/services/databaseServices?limit=100"
            resp = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
            if resp.status_code == 200:
                services = resp.json().get("data", [])
                self._set_cache(cache_key, services)
                return services
        except Exception as e:
            logger.warning(f"Lỗi gọi list_services: {e}")

        return [{"name": "healthcare_postgres", "fullyQualifiedName": "healthcare_postgres", "serviceType": "Postgres"}]

    def list_databases(self, service_fqn: str = "healthcare_postgres") -> List[Dict[str, Any]]:
        """Lấy danh sách Databases thuộc Service (Section 5.2)"""
        cache_key = f"databases_{service_fqn}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.server_url}/databases?service={urllib.parse.quote(service_fqn)}&limit=100"
            resp = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
            if resp.status_code == 200:
                databases = resp.json().get("data", [])
                self._set_cache(cache_key, databases)
                return databases
        except Exception as e:
            logger.warning(f"Lỗi gọi list_databases: {e}")

        return [{"name": "HealthCare", "fullyQualifiedName": "healthcare_postgres.HealthCare"}]

    def list_schemas(self, database_fqn: str = "healthcare_postgres.HealthCare") -> List[Dict[str, Any]]:
        """Lấy danh sách Schemas thuộc Database (Section 5.3)"""
        cache_key = f"schemas_{database_fqn}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.server_url}/databaseSchemas?database={urllib.parse.quote(database_fqn)}&limit=100"
            resp = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
            if resp.status_code == 200:
                schemas = resp.json().get("data", [])
                self._set_cache(cache_key, schemas)
                return schemas
        except Exception as e:
            logger.warning(f"Lỗi gọi list_schemas: {e}")

        return [{"name": "public", "fullyQualifiedName": "healthcare_postgres.HealthCare.public"}]

    def list_tables(self, schema_fqn: str = "healthcare_postgres.HealthCare.public") -> List[Dict[str, Any]]:
        """Lấy danh sách Tables thuộc Schema, hỗ trợ pagination (Section 5.4 & 9)"""
        cache_key = f"tables_{schema_fqn}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        tables: List[Dict[str, Any]] = []
        after_cursor = None

        try:
            while True:
                url = f"{self.server_url}/tables?databaseSchema={urllib.parse.quote(schema_fqn)}&limit=100"
                if after_cursor:
                    url += f"&after={urllib.parse.quote(after_cursor)}"

                resp = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
                if resp.status_code != 200:
                    break

                body = resp.json()
                data = body.get("data", [])
                for t in data:
                    t_name = t.get("name", "")
                    table_desc = (t.get("description") or "").strip()
                    if not table_desc:
                        table_desc = HEALTHCARE_TABLE_DESCRIPTIONS.get(t_name.lower(), f"Bảng dữ liệu y tế {t_name} thuộc cơ sở dữ liệu HealthCare.")
                    tables.append({
                        "id": t.get("id"),
                        "name": t_name,
                        "fullyQualifiedName": t.get("fullyQualifiedName"),
                        "description": table_desc,
                        "tableType": t.get("tableType", "Regular")
                    })

                paging = body.get("paging", {})
                after_cursor = paging.get("after")
                if not after_cursor or len(data) == 0:
                    break

            if tables:
                self._set_cache(cache_key, tables)
                return tables
        except Exception as e:
            logger.warning(f"Lỗi gọi list_tables: {e}")

        # Fallback 18 healthcare tables + demo tables
        fallback_tables = [
            "allergies", "careplans", "claims", "claims_transactions", "conditions",
            "devices", "encounters", "imaging_studies", "immunizations", "medications",
            "observations", "organizations", "patients", "payers", "payer_transitions",
            "procedures", "providers", "supplies"
        ]
        return [
            {
                "name": name,
                "fullyQualifiedName": f"healthcare_postgres.HealthCare.public.{name}",
                "description": HEALTHCARE_TABLE_DESCRIPTIONS.get(name.lower(), f"Bảng dữ liệu y tế {name} thuộc cơ sở dữ liệu HealthCare."),
                "tableType": "Regular"
            }
            for name in fallback_tables
        ]

    def _list_entities_paginated(
        self,
        endpoint: str,
        parent_param: str,
        parent_fqn: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch every catalog entity page without demo fallbacks.

        Bulk jobs must fail visibly when OpenMetadata cannot enumerate a scope;
        silently returning the healthcare demo tables could target wrong assets.
        """
        entities: List[Dict[str, Any]] = []
        after: Optional[str] = None
        while True:
            params: Dict[str, Any] = {
                parent_param: parent_fqn,
                "limit": limit,
            }
            if after:
                params["after"] = after
            response = requests.get(
                f"{self.server_url}/{endpoint}",
                params=params,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"OpenMetadata {endpoint} returned HTTP {response.status_code}"
                )
            payload = response.json()
            page = payload.get("data", [])
            entities.extend(page)
            after = payload.get("paging", {}).get("after")
            if not after or not page:
                break
        return entities

    def _list_collection_paginated(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch an entire OpenMetadata collection without fallbacks."""
        entities: List[Dict[str, Any]] = []
        after: Optional[str] = None
        while True:
            page_params: Dict[str, Any] = dict(params or {})
            page_params["limit"] = limit
            if after:
                page_params["after"] = after
            response = requests.get(
                f"{self.server_url}/{endpoint}",
                params=page_params,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"OpenMetadata {endpoint} returned HTTP {response.status_code}"
                )
            payload = response.json()
            page = payload.get("data", [])
            entities.extend(page)
            after = payload.get("paging", {}).get("after")
            if not after or not page:
                break
        return entities

    def list_schemas_paginated(self, database_fqn: str) -> List[Dict[str, Any]]:
        return self._list_entities_paginated(
            endpoint="databaseSchemas",
            parent_param="database",
            parent_fqn=database_fqn,
        )

    def list_tables_paginated(self, schema_fqn: str) -> List[Dict[str, Any]]:
        return self._list_entities_paginated(
            endpoint="tables",
            parent_param="databaseSchema",
            parent_fqn=schema_fqn,
        )

    def list_database_tables_for_nt(
        self,
        database_fqn: str,
    ) -> List[Dict[str, Any]]:
        """Enumerate every table in a database for cross-schema NT checks."""
        tables: List[Dict[str, Any]] = []
        for schema in self.list_schemas_paginated(database_fqn):
            schema_fqn = schema.get("fullyQualifiedName")
            if not schema_fqn:
                raise RuntimeError(
                    "OpenMetadata schema response has no fullyQualifiedName"
                )
            for table in self.list_tables_paginated(schema_fqn):
                normalized = dict(table)
                normalized.setdefault("databaseSchema", schema)
                tables.append(normalized)
        return tables

    def resolve_table_fqn_strict(self, table_fqn: str) -> str:
        encoded = urllib.parse.quote(table_fqn, safe="")
        response = requests.get(
            f"{self.server_url}/tables/name/{encoded}",
            params={"fields": "columns"},
            headers=self._get_headers(),
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"OpenMetadata table lookup returned HTTP {response.status_code}"
            )
        payload = response.json()
        resolved = payload.get("fullyQualifiedName")
        if not resolved:
            raise RuntimeError("OpenMetadata table response has no fullyQualifiedName")
        return resolved

    def _get_latest_column_profile_for_nt(
        self,
        column_fqn: str,
    ) -> Optional[Dict[str, Any]]:
        """Load a real profile snapshot for NT checks without mock fallback."""
        encoded_fqn = urllib.parse.quote(column_fqn, safe="")
        response = requests.get(
            f"{self.server_url}/tables/{encoded_fqn}/columnProfile",
            params={
                "startTs": 0,
                "endTs": 2_000_000_000_000,
                "limit": 100,
            },
            headers=self._get_headers(),
            timeout=self.timeout,
        )
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise RuntimeError(
                "OpenMetadata column profile lookup for "
                f"{column_fqn} returned HTTP {response.status_code}"
            )
        profiles = response.json().get("data", [])
        if not profiles:
            return None
        return max(profiles, key=lambda item: int(item.get("timestamp", 0)))

    def get_table_metadata_for_nt(
        self,
        table_fqn: str,
        include_column_profiles: bool = True,
    ) -> Dict[str, Any]:
        """Return only metadata actually stored in OpenMetadata for NT rules.

        Unlike ``get_catalog_table`` this method is strict: it never substitutes
        demo assets or synthesizes descriptions, domains, owners, tags, or
        profiles when OpenMetadata is unavailable or a field is empty.
        """
        encoded_fqn = urllib.parse.quote(table_fqn, safe="")
        response = requests.get(
            f"{self.server_url}/tables/name/{encoded_fqn}",
            params={
                "fields": (
                    "columns,owners,tags,domains,tableConstraints,profile,"
                    "service,database,databaseSchema"
                )
            },
            headers=self._get_headers(),
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"OpenMetadata table lookup returned HTTP {response.status_code}"
            )
        table = response.json()
        resolved_fqn = table.get("fullyQualifiedName")
        if not resolved_fqn:
            raise RuntimeError("OpenMetadata table response has no fullyQualifiedName")

        columns = [dict(column) for column in table.get("columns") or []]
        if include_column_profiles and columns:
            with ThreadPoolExecutor(max_workers=min(8, len(columns))) as executor:
                futures = {
                    executor.submit(
                        self._get_latest_column_profile_for_nt,
                        column["fullyQualifiedName"],
                    ): column
                    for column in columns
                    if column.get("fullyQualifiedName")
                }
                for future in as_completed(futures):
                    profile = future.result()
                    if profile is not None:
                        futures[future]["profile"] = profile

        return {
            "id": table.get("id"),
            "name": table.get("name"),
            "fullyQualifiedName": resolved_fqn,
            "tableType": table.get("tableType"),
            "description": table.get("description"),
            "service": table.get("service"),
            "database": table.get("database"),
            "databaseSchema": table.get("databaseSchema"),
            "owners": table.get("owners") or [],
            "domains": table.get("domains") or [],
            "tags": table.get("tags") or [],
            "columns": columns,
            "tableConstraints": table.get("tableConstraints") or [],
            "profile": table.get("profile"),
        }

    def _fetch_single_column_profile(self, column_fqn: str) -> Optional[Dict[str, Any]]:
        """Lấy latest ColumnProfile theo Column FQN (Section 5.7)"""
        try:
            encoded_fqn = urllib.parse.quote(column_fqn, safe="")
            url = f"{self.server_url}/tables/{encoded_fqn}/columnProfile?startTs=0&endTs=2000000000000"
            resp = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
            if resp.status_code == 200:
                p_list = resp.json().get("data", [])
                if p_list:
                    # Lấy profile có timestamp mới nhất
                    return max(p_list, key=lambda x: x.get("timestamp", 0))
        except Exception as e:
            logger.debug(f"Lỗi lấy profile cho column {column_fqn}: {e}")
        return None

    def get_column_profile_history(
        self,
        column_fqn: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return newest unique OpenMetadata profiles for a column.

        This is intentionally separate from ``_fetch_single_column_profile``:
        the existing table context still carries only the latest snapshot for
        rule evaluation/LLM input, while this method serves API display data.
        """
        if limit <= 0:
            return []

        try:
            encoded_fqn = urllib.parse.quote(column_fqn, safe="")
            url = (
                f"{self.server_url}/tables/{encoded_fqn}/columnProfile"
                "?startTs=0&endTs=2000000000000&limit=100"
            )
            resp = requests.get(
                url,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                logger.warning(
                    "Cannot load column profile history for %s: HTTP %s",
                    column_fqn,
                    resp.status_code,
                )
                return []

            profiles = resp.json().get("data", [])
            profiles.sort(key=lambda item: int(item.get("timestamp", 0)), reverse=True)

            # Guard against duplicated historical rows from repeated profiler
            # ingestion: the UI needs one point per profiling timestamp.
            unique_profiles: List[Dict[str, Any]] = []
            seen_timestamps = set()
            for profile in profiles:
                timestamp = profile.get("timestamp")
                if timestamp is None or timestamp in seen_timestamps:
                    continue
                seen_timestamps.add(timestamp)
                unique_profiles.append(profile)
                if len(unique_profiles) == limit:
                    break
            return unique_profiles
        except Exception as exc:
            logger.warning(
                "Cannot load column profile history for %s: %s",
                column_fqn,
                exc,
            )
            return []

    def get_catalog_table(self, table_id_or_name: str) -> Dict[str, Any]:
        """
        Lấy chi tiết Table, danh sách Columns, và Column Profiles (Section 5.5, 5.7, 6, 8).
        Sử dụng ThreadPoolExecutor để query song song các cột.
        Áp dụng deriveTableProfile nếu tableProfile rỗng.
        """
        cache_key = f"catalog_table_{table_id_or_name}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        table_detail: Optional[Dict[str, Any]] = None

        # 1. Thử lấy bằng ID hoặc name
        try:
            if "-" in table_id_or_name and len(table_id_or_name) == 36:
                # UUID format
                url = f"{self.server_url}/tables/{table_id_or_name}?fields=columns,owners,tags"
            elif "." in table_id_or_name:
                # FQN
                url = f"{self.server_url}/tables/name/{urllib.parse.quote(table_id_or_name, safe='')}?fields=columns,owners,tags"
            else:
                # Tìm ID trong danh sách tables của HealthCare.public
                tables = self.list_tables()
                matched = next((t for t in tables if t.get("name") == table_id_or_name), None)
                if matched and matched.get("id"):
                    url = f"{self.server_url}/tables/{matched['id']}?fields=columns,owners,tags"
                else:
                    fqn = f"healthcare_postgres.HealthCare.public.{table_id_or_name}"
                    url = f"{self.server_url}/tables/name/{urllib.parse.quote(fqn, safe='')}?fields=columns,owners,tags"

            resp = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
            if resp.status_code == 200:
                table_detail = resp.json()
        except Exception as e:
            logger.warning(f"Lỗi lấy table detail {table_id_or_name}: {e}")

        # Nếu không lấy được từ server (hoặc bảng demo orders/customers), dùng fallback
        if not table_detail:
            context = self._get_fallback_context(table_id_or_name)
            return {
                "id": f"table_{table_id_or_name}",
                "name": context.table_name,
                "fqn": f"postgres.{context.database_name}.{context.schema_name}.{context.table_name}",
                "type": "Regular",
                "profile": {
                    "timestamp": int(time.time() * 1000),
                    "rowCount": context.row_count,
                    "columnCount": len(context.columns)
                },
                "columns": [
                    {
                        "name": col.name,
                        "fqn": f"{context.table_name}.{col.name}",
                        "dataType": col.data_type,
                        "constraint": "PRIMARY_KEY" if col.is_primary_key else None,
                        "profile": {
                            "timestamp": int(time.time() * 1000),
                            "valuesCount": col.profile.row_count,
                            "nullCount": col.profile.null_count,
                            "nullProportion": col.profile.null_ratio,
                            "distinctCount": col.profile.distinct_count,
                            "distinctProportion": col.profile.distinct_ratio,
                            "min": col.profile.min_value,
                            "max": col.profile.max_value
                        }
                    }
                    for col in context.columns
                ]
            }

        # 2. Lấy profile các cột song song bằng ThreadPoolExecutor (Section 9: giới hạn 8 workers)
        raw_columns = table_detail.get("columns", [])
        column_profiles: Dict[str, Dict[str, Any]] = {}

        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_col = {
                executor.submit(self._fetch_single_column_profile, col["fullyQualifiedName"]): col["name"]
                for col in raw_columns
                if col.get("fullyQualifiedName")
            }
            for future in as_completed(future_to_col):
                c_name = future_to_col[future]
                try:
                    prof = future.result()
                    if prof:
                        column_profiles[c_name] = prof
                except Exception as e:
                    logger.debug(f"Error fetching profile for {c_name}: {e}")

        # 3. Tính toán TableProfile: deriveTableProfile fallback (Section 8)
        row_counts = [
            int(p.get("valuesCount", 0) + p.get("nullCount", 0))
            for p in column_profiles.values()
            if p.get("valuesCount") is not None and p.get("nullCount") is not None
        ]
        derived_row_count = max(row_counts) if row_counts else 0
        derived_ts = max(
            [p.get("timestamp", 0) for p in column_profiles.values()],
            default=int(time.time() * 1000)
        )

        catalog_columns = []
        for col in raw_columns:
            c_name = col.get("name")
            p_data = column_profiles.get(c_name)
            catalog_columns.append({
                "name": c_name,
                "fqn": col.get("fullyQualifiedName"),
                "dataType": col.get("dataTypeDisplay") or col.get("dataType", "STRING"),
                "constraint": col.get("constraint"),
                "description": col.get("description", ""),
                "profile": p_data
            })

        t_name = table_detail.get("name") or table_id_or_name
        detail_desc = (table_detail.get("description") or "").strip()
        if not detail_desc:
            detail_desc = HEALTHCARE_TABLE_DESCRIPTIONS.get(t_name.lower(), f"Bảng dữ liệu y tế {t_name} thuộc cơ sở dữ liệu HealthCare.")

        result = {
            "id": table_detail.get("id"),
            "name": t_name,
            "fqn": table_detail.get("fullyQualifiedName"),
            "type": table_detail.get("tableType", "Regular"),
            "description": detail_desc,
            "profile": {
                "timestamp": derived_ts,
                "rowCount": derived_row_count,
                "columnCount": len(raw_columns)
            },
            "columns": catalog_columns
        }

        self._set_cache(cache_key, result)
        return result

    def get_table_context(self, table_name: str) -> TableContext:
        """
        Trích xuất TableContext chuẩn hóa từ OpenMetadata để tích hợp trực tiếp
        vào BasicRuleEngine, Data Profiler, Schema View và Observability View.
        """
        catalog = self.get_catalog_table(table_name)
        
        # Parse database & schema name từ FQN
        # FQN format: service.database.schema.table
        fqn_parts = (catalog.get("fqn") or "").split(".")
        db_name = fqn_parts[1] if len(fqn_parts) >= 4 else "HealthCare"
        schema_name = fqn_parts[2] if len(fqn_parts) >= 4 else "public"

        row_count = catalog.get("profile", {}).get("rowCount", 0)
        
        columns: List[ColumnContext] = []
        for c in catalog.get("columns", []):
            c_name = c["name"]
            c_type = c["dataType"]
            c_desc = c.get("description", "")
            is_pk = "PRIMARY_KEY" in (c.get("constraint") or "")
            
            p = c.get("profile") or {}
            null_count = int(p.get("nullCount") or 0)
            null_ratio = float(p.get("nullProportion") or 0.0)
            distinct_count = int(p.get("distinctCount") or 0)
            distinct_ratio = float(p.get("distinctProportion") or 0.0)
            min_val = p.get("min")
            max_val = p.get("max")
            min_len = p.get("minLength")
            max_len = p.get("maxLength")

            # Sample values nếu có
            top_vals = []
            if min_val is not None:
                top_vals.append({"value": str(min_val)})
            if max_val is not None and max_val != min_val:
                top_vals.append({"value": str(max_val)})

            # Statistical metrics from OpenMetadata profiler
            values_count = p.get("valuesCount")
            valid_count = p.get("validCount")
            mean_val = p.get("mean")
            median_val = p.get("median")
            stddev_val = p.get("stddev")
            q1_val = p.get("firstQuartile") or p.get("q1")
            q3_val = p.get("thirdQuartile") or p.get("q3")
            iqr_val = p.get("interQuartileRange") or p.get("iqr")
            skew_val = p.get("nonParametricSkew") or p.get("non_parametric_skew")

            # Profile metadata
            profile_ts = p.get("timestamp")
            # Determine source: real OM data vs fallback/mock
            if p.get("mean") is not None or p.get("median") is not None:
                profile_source = ProfileSource.OPENMETADATA
            elif p.get("valuesCount") is not None or p.get("distinctCount") is not None:
                profile_source = ProfileSource.OPENMETADATA
            else:
                profile_source = ProfileSource.UNKNOWN

            column_profile = ColumnProfile(
                row_count=row_count,
                null_count=null_count,
                null_ratio=null_ratio,
                distinct_count=distinct_count,
                distinct_ratio=distinct_ratio,
                min_value=min_val,
                max_value=max_val,
                min_length=min_len,
                max_length=max_len,
                top_values=top_vals,
                # Statistical metrics
                values_count=values_count,
                valid_count=valid_count,
                mean=mean_val,
                median=median_val,
                stddev=stddev_val,
                q1=q1_val,
                q3=q3_val,
                iqr=iqr_val,
                non_parametric_skew=skew_val,
                # Profile metadata
                profile_timestamp=profile_ts,
                profile_source=profile_source,
                profile_scope=ProfileScope.UNKNOWN,
            )

            columns.append(ColumnContext(
                name=c_name,
                data_type=c_type,
                nullable=null_count > 0 or not is_pk,
                description=c_desc,
                is_primary_key=is_pk,
                profile=column_profile
            ))

        # Phân loại Domain & Tier cho Healthcare tables
        t_clean_name = (catalog.get("name") or table_name).lower()
        t_desc = (catalog.get("description") or "").strip()
        if not t_desc:
            t_desc = HEALTHCARE_TABLE_DESCRIPTIONS.get(t_clean_name, f"Bảng dữ liệu y tế {table_name} thuộc cơ sở dữ liệu HealthCare.")

        # Lay PK columns tu column constraints
        pk_columns = [col.name for col in columns if col.is_primary_key]

        # Lay FK info tu OM (neu co)
        om_fks = catalog.get("foreignKeys", []) or []
        from backend.contracts.table_context import ForeignKeyInfo
        fk_list = []
        for fk in om_fks:
            from_col = fk.get("fromColumns", [])
            to_ref = fk.get("toColumn", {})
            if from_col and to_ref:
                ref_table = to_ref.get("fullyQualifiedName", "")
                ref_col = to_ref.get("name", "")
                fk_list.append(ForeignKeyInfo(
                    column_name=from_col[0],
                    referenced_table=ref_table.split(".")[-1] if ref_table else "",
                    referenced_column=ref_col,
                    constraint_name=fk.get("name"),
                ))

        return TableContext(
            datasource_id="openmetadata-live",
            table_fqn=catalog.get("fqn") or table_name,
            database_name=db_name,
            schema_name=schema_name,
            table_name=catalog.get("name") or table_name,
            table_description=t_desc,
            row_count=row_count,
            tier="Tier.Tier1" if t_clean_name in ["patients", "encounters", "claims", "medications", "conditions"] else "Tier.Tier2",
            domain="Healthcare & Clinical",
            owner={"name": "DataOps Healthcare Team", "role": "Data Steward"},
            tags=[{"name": "Healthcare"}, {"name": "Clinical Data"}],
            columns=columns,
            primary_keys=pk_columns,
            foreign_keys=fk_list,
        )

    def _get_fallback_context(self, table_name: str) -> TableContext:
        """Dữ liệu dự phòng chuẩn OpenMetadata structure khi chưa có server thật"""
        if table_name == "customers":
            return TableContext(
                datasource_id="openmetadata-cache",
                database_name="ecommerce_db",
                schema_name="public",
                table_name="customers",
                table_description="Danh sách thông tin định danh và hồ sơ khách hàng đã đăng ký",
                row_count=8920,
                columns=[
                    ColumnContext(
                        name="customer_id",
                        data_type="VARCHAR(64)",
                        nullable=False,
                        is_primary_key=True,
                        profile=ColumnProfile(
                            row_count=8920, null_count=0, null_ratio=0.0,
                            distinct_count=8920, distinct_ratio=1.0, min_length=12, max_length=12
                        )
                    ),
                    ColumnContext(
                        name="email",
                        data_type="VARCHAR(255)",
                        nullable=False,
                        profile=ColumnProfile(
                            row_count=8920, null_count=0, null_ratio=0.0,
                            distinct_count=8920, distinct_ratio=1.0, min_length=8, max_length=45
                        )
                    ),
                    ColumnContext(
                        name="age",
                        data_type="INTEGER",
                        nullable=True,
                        profile=ColumnProfile(
                            row_count=8920, null_count=120, null_ratio=0.0134,
                            distinct_count=68, distinct_ratio=0.0076, min_value=18, max_value=85
                        )
                    )
                ]
            )

        # Fallback mặc định: orders
        return TableContext(
            datasource_id="openmetadata-cache",
            database_name="ecommerce_db",
            schema_name="public",
            table_name="orders",
            table_description="Bảng lưu trữ thông tin đơn hàng của khách hàng trên sàn thương mại điện tử",
            row_count=15420,
            columns=[
                ColumnContext(
                    name="order_id",
                    data_type="VARCHAR(64)",
                    nullable=False,
                    is_primary_key=True,
                    profile=ColumnProfile(
                        row_count=15420, null_count=0, null_ratio=0.0,
                        distinct_count=15420, distinct_ratio=1.0, min_length=16, max_length=16
                    )
                ),
                ColumnContext(
                    name="customer_id",
                    data_type="VARCHAR(64)",
                    nullable=True,
                    profile=ColumnProfile(
                        row_count=15420, null_count=15, null_ratio=0.001,
                        distinct_count=3210, distinct_ratio=0.208
                    )
                ),
                ColumnContext(
                    name="total_amount",
                    data_type="NUMERIC(14,2)",
                    nullable=False,
                    profile=ColumnProfile(
                        row_count=15420, null_count=0, null_ratio=0.0,
                        distinct_count=8450, distinct_ratio=0.548, min_value=10000.0, max_value=48500000.0
                    )
                ),
                ColumnContext(
                    name="order_status",
                    data_type="VARCHAR(20)",
                    nullable=False,
                    profile=ColumnProfile(
                        row_count=15420, null_count=0, null_ratio=0.0,
                        distinct_count=5, distinct_ratio=0.0003,
                        top_values=[
                            {"value": "PENDING"}, {"value": "PROCESSING"},
                            {"value": "SHIPPED"}, {"value": "COMPLETED"}, {"value": "CANCELLED"}
                        ]
                    )
                ),
                ColumnContext(
                    name="created_at",
                    data_type="TIMESTAMP",
                    nullable=False,
                    profile=ColumnProfile(
                        row_count=15420, null_count=0, null_ratio=0.0,
                        distinct_count=15410, distinct_ratio=0.999
                    )
                ),
                ColumnContext(
                    name="delivered_at",
                    data_type="TIMESTAMP",
                    nullable=True,
                    profile=ColumnProfile(
                        row_count=15420, null_count=1850, null_ratio=0.12,
                        distinct_count=13200, distinct_ratio=0.856
                    )
                )
            ]
        )

    # =========================================================================
    # Test Case Methods
    # =========================================================================

    def list_nt_test_definitions(
        self,
        prefix: str = "NT",
    ) -> List[Dict[str, Any]]:
        """Return every enabled/disabled NT definition with pagination."""
        definitions = self._list_collection_paginated(
            "dataQuality/testDefinitions"
        )
        return [
            definition
            for definition in definitions
            if str(definition.get("name") or "").startswith(prefix)
        ]

    def get_table_nt_test_cases(
        self,
        table_fqn: str,
        prefix: str = "NT",
    ) -> List[Dict[str, Any]]:
        """Return all existing NT Test Cases attached to one table."""
        test_cases = self._list_collection_paginated(
            "dataQuality/testCases",
            params={
                "entityLink": f"<#E::table::{table_fqn}>",
                "includeAllTests": True,
                "fields": "testDefinition,parameterValues",
            },
        )

        def definition_name(test_case: Dict[str, Any]) -> str:
            definition = test_case.get("testDefinition") or {}
            if isinstance(definition, dict):
                return str(
                    definition.get("name")
                    or definition.get("fullyQualifiedName")
                    or ""
                )
            return str(definition)

        return [
            test_case
            for test_case in test_cases
            if definition_name(test_case).startswith(prefix)
        ]

    def get_test_suite_nt_test_cases(
        self,
        test_suite_fqn: str,
        prefix: str = "NT",
    ) -> List[Dict[str, Any]]:
        """Return native NT Test Cases that belong to a logical Test Suite."""
        encoded_fqn = urllib.parse.quote(test_suite_fqn, safe="")
        response = requests.get(
            f"{self.server_url}/dataQuality/testSuites/name/{encoded_fqn}",
            headers=self._get_headers(),
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise RuntimeError(
                "OpenMetadata Test Suite lookup returned HTTP "
                f"{response.status_code}: {response.text}"
            )
        suite_id = response.json().get("id")
        if not suite_id:
            raise RuntimeError("OpenMetadata Test Suite response has no id")

        test_cases = self._list_collection_paginated(
            "dataQuality/testCases",
            params={
                "testSuiteId": suite_id,
                "includeAllTests": True,
                "fields": "testDefinition,parameterValues",
            },
        )

        def definition_name(test_case: Dict[str, Any]) -> str:
            definition = test_case.get("testDefinition") or {}
            if isinstance(definition, dict):
                return str(
                    definition.get("name")
                    or definition.get("fullyQualifiedName")
                    or ""
                )
            return str(definition)

        return [
            test_case
            for test_case in test_cases
            if definition_name(test_case).startswith(prefix)
        ]

    def add_test_case_result(
        self,
        test_case_fqn: str,
        result: NTRuleResult,
        timestamp_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Publish an NT result to an existing OpenMetadata Test Case."""
        if not test_case_fqn:
            raise ValueError("test_case_fqn is required")
        payload = {
            "timestamp": (
                timestamp_ms
                if timestamp_ms is not None
                else int(time.time() * 1000)
            ),
            "testCaseStatus": result.openmetadata_status,
            "result": result.message,
            "testResultValue": result.test_result_values(),
        }
        encoded_fqn = urllib.parse.quote(test_case_fqn, safe="")
        response = requests.post(
            f"{self.server_url}/dataQuality/testCases/testCaseResults/{encoded_fqn}",
            json=payload,
            headers=self._get_headers(),
            timeout=self.timeout,
        )
        if response.status_code not in (200, 201):
            detail = response.text
            try:
                error_payload = response.json()
                detail = error_payload.get("message") or detail
            except ValueError:
                pass
            raise RuntimeError(
                "OpenMetadata TestCaseResult publish returned HTTP "
                f"{response.status_code}: {detail}"
            )
        return response.json()

    def get_test_definitions(self, prefix: str = "NT") -> List[Dict[str, Any]]:
        """
        Lấy danh sách Test Definitions từ OpenMetadata.

        Args:
            prefix: Lọc theo prefix tên (mặc định 'NT' cho governance rules)

        Returns:
            List of test definition objects
        """
        try:
            url = f"{self.server_url}/dataQuality/testDefinitions?limit=100"
            resp = requests.get(url, headers=self._get_headers(), timeout=self.timeout)

            if resp.status_code == 200:
                data = resp.json()
                definitions = []

                for item in data.get("data", []):
                    name = item.get("name", "")
                    # Filter theo prefix
                    if name.startswith(prefix):
                        definitions.append({
                            "id": item.get("id"),
                            "name": name,
                            "fullyQualifiedName": item.get("fullyQualifiedName", name),
                            "displayName": item.get("displayName", name),
                            "description": item.get("description", ""),
                            "sqlExpression": item.get("sqlExpression"),
                            "entityType": item.get("entityType"),
                            "parameterDefinition": item.get("parameterDefinition") or [],
                            "enabled": item.get("enabled", True),
                        })

                return definitions

            logger.warning(f"Lỗi get_test_definitions: {resp.status_code}")
        except Exception as e:
            logger.error(f"Lỗi gọi get_test_definitions: {e}")

        return []

    def get_table_test_cases(self, table_fqn: str) -> Dict[str, Any]:
        """Return Test Cases currently attached to a table in OpenMetadata."""
        try:
            url = f"{self.server_url}/dataQuality/testCases"
            resp = requests.get(
                url,
                params={
                    "entityLink": f"<#E::table::{table_fqn}>",
                    "includeAllTests": True,
                    "fields": "testDefinition,parameterValues",
                    "limit": 100,
                },
                headers=self._get_headers(),
                timeout=self.timeout,
            )

            if resp.status_code == 200:
                payload = resp.json()
                return {
                    "success": True,
                    "data": payload.get("data", []),
                    "total": payload.get("total", 0),
                }

            return {
                "success": False,
                "data": [],
                "total": 0,
                "error": f"HTTP {resp.status_code}",
            }
        except Exception as exc:
            logger.error(f"Failed to get Test Cases for {table_fqn}: {exc}")
            return {
                "success": False,
                "data": [],
                "total": 0,
                "error": str(exc),
            }

    def create_test_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tạo một Test Case trên OpenMetadata.

        Args:
            test_case: Test case payload

        Returns:
            Created test case object hoặc error info
        """
        try:
            url = f"{self.server_url}/dataQuality/testCases"
            resp = requests.post(url, json=test_case, headers=self._get_headers(), timeout=self.timeout)

            if resp.status_code in (200, 201):
                return {
                    "success": True,
                    "data": resp.json()
                }

            # Parse error response
            error_data = resp.json() if resp.text else {}
            return {
                "success": False,
                "error": error_data.get("message", f"HTTP {resp.status_code}"),
                "status_code": resp.status_code
            }

        except Exception as e:
            logger.error(f"Lỗi tạo test_case: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def upsert_test_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a Test Case by its fully qualified identity."""
        try:
            url = f"{self.server_url}/dataQuality/testCases"
            resp = requests.put(
                url,
                json=test_case,
                headers=self._get_headers(),
                timeout=self.timeout,
            )

            if resp.status_code in (200, 201):
                return {
                    "success": True,
                    "data": resp.json(),
                    "status_code": resp.status_code,
                }

            error_data = resp.json() if resp.text else {}
            return {
                "success": False,
                "error": error_data.get("message", f"HTTP {resp.status_code}"),
                "status_code": resp.status_code,
            }
        except Exception as e:
            logger.error(f"Lỗi upsert test_case: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def replace_table_name_in_sql(self, sql_template: str, table_name: str) -> str:
        """
        Thay {{ table_name }} trong SQL template bằng tên table thực.

        Args:
            sql_template: SQL template có {{ table_name }}
            table_name: Tên table thực

        Returns:
            SQL đã replace
        """
        if not sql_template:
            return ""
        return sql_template.replace("{{ table_name }}", table_name)


openmetadata_client = OpenMetadataClient()
