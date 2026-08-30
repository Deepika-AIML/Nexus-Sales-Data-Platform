"""
Upload validation tests (TEST 6 & TEST 7, spec section 35).
Run with: pytest tests/test_upload_validation.py -v
"""
import pytest

from app.core.exceptions import FileValidationError
from app.services import storage_service


def test_valid_csv_passes_validation():
    content = b"Order ID,Sales\nA-1,100\n"
    storage_service.validate_upload("orders.csv", content)  # should not raise


def test_non_csv_extension_rejected():
    """TEST 7: a non-CSV file must be rejected at upload time with a clear message."""
    with pytest.raises(FileValidationError, match="Unsupported file type"):
        storage_service.validate_upload("orders.xlsx", b"not a csv")


def test_empty_file_rejected():
    with pytest.raises(FileValidationError):
        storage_service.validate_upload("empty.csv", b"")


def test_oversized_file_rejected():
    """TEST 6: a file over the 25 MB limit must be rejected at upload time."""
    oversized = b"a" * (26 * 1024 * 1024)
    with pytest.raises(FileValidationError, match="25 MB"):
        storage_service.validate_upload("huge.csv", oversized)


def test_file_at_exactly_the_limit_is_accepted():
    at_limit = b"x" * (25 * 1024 * 1024)
    storage_service.validate_upload("at_limit.csv", at_limit)  # should not raise on size


def test_unreadable_csv_raises_clean_error():
    garbage = bytes([0xFF, 0xFE, 0x00, 0x00, 0x01, 0x02]) * 100
    with pytest.raises(FileValidationError):
        storage_service.detect_encoding_and_read(garbage)


def test_sanitize_filename_strips_path_traversal():
    assert storage_service.sanitize_filename("../../etc/passwd") == "passwd"
    assert storage_service.sanitize_filename("weird name!.csv") == "weird_name_.csv"
