"""
Pattern Registry cho Regex Basic Rules.
Chứa format aliases và regex patterns cho column name detection.
"""

# =============================================================================
# Format Aliases: Column name → Format ID
# =============================================================================
# Dùng exact match sau khi normalize (lowercase, strip)
# Không dùng substring match để tránh false positive

FORMAT_ALIASES: dict[str, str] = {
    # EMAIL formats
    "email": "EMAIL",
    "email_address": "EMAIL",

    # URL formats
    "url": "URL_HTTP",
    "website": "URL_HTTP",
    "website_url": "URL_HTTP",

    # First Name
    "first_name": "FIRST_NAME_CAPITALIZED",
}

# =============================================================================
# Regex Patterns: Format ID → Pattern Metadata
# =============================================================================

REGEX_PATTERNS: dict[str, dict] = {
    "EMAIL": {
        "regex": r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
        "description": "Email format validation",
        "om_test_type": "columnValuesToMatchRegex",
        "limitations": [
            "ASCII-only domain",
            "No RFC complete validation",
            "No Unicode support"
        ],
        "requires_human_review": False,
    },
    "URL_HTTP": {
        "regex": r"^https?://[A-Za-z0-9.-]+\.[A-Za-z]{2,}(:[0-9]{1,5})?([/?#][^[:space:]]*)?$",
        "description": "HTTP/HTTPS URL validation",
        "om_test_type": "columnValuesToMatchRegex",
        "limitations": [
            "ASCII-only domain",
            "No localhost/IP URLs",
            "No IDN support"
        ],
        "requires_human_review": False,
    },
    "FIRST_NAME_CAPITALIZED": {
        "regex": r"^[[:upper:]][[:lower:]]*$",
        "description": "First letter uppercase, remaining lowercase (single word)",
        "om_test_type": "columnValuesToMatchRegex",
        "limitations": [
            "Single word only",
            "No spaces, hyphens, apostrophes",
            "Locale-dependent Unicode (PostgreSQL POSIX classes)"
        ],
        "requires_human_review": True,
    },
}


# =============================================================================
# Helper Functions
# =============================================================================

def normalize_column_name(name: str) -> str:
    """
    Normalize column name: lowercase, strip spaces.
    Không thay đổi underscore (_) vì đây là valid identifier.
    """
    return name.strip().lower()


def detect_format(column_name: str) -> str | None:
    """
    Detect format ID từ column name.
    Returns format_id hoặc None nếu không khớp.
    """
    normalized = normalize_column_name(column_name)
    return FORMAT_ALIASES.get(normalized)


def get_pattern(format_id: str) -> dict | None:
    """
    Get pattern metadata by format ID.
    Returns pattern dict hoặc None nếu không tìm thấy.
    """
    return REGEX_PATTERNS.get(format_id)


def get_all_formats() -> list[str]:
    """Get list of all supported format IDs."""
    return list(REGEX_PATTERNS.keys())
