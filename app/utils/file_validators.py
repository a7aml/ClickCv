"""
utils/file_validators.py

Validates uploaded CV files before any processing begins.
Checks: allowed extension, file size, and magic bytes integrity
to confirm the file is not corrupted or disguised as another type.

Returns a consistent (is_valid, error_message) tuple so the
analysis route can handle errors uniformly — same pattern as
(user, error) used in auth_service.py.
"""

import os


# ── Constants ─────────────────────────────────────────────────────────────────

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB hard limit

ALLOWED_EXTENSIONS = {"pdf", "docx"}

# Magic byte signatures — first raw bytes that identify the true file type,
# regardless of what the filename extension claims.
MAGIC_SIGNATURES = {
    # All valid PDFs begin with the literal bytes %PDF
    "pdf":  b"%PDF",
    # DOCX is internally a ZIP archive — all ZIP files start with PK
    "docx": b"PK\x03\x04",
}


# ── Public API ────────────────────────────────────────────────────────────────

def validate_cv_file(file) -> tuple:
    """
    Run all validation checks on an uploaded FileStorage object.

    Mirrors the (user, error) pattern from auth_service.py so the
    analysis route handles errors the same way across the codebase:

        is_valid, error = validate_cv_file(file)
        if not is_valid:
            return jsonify({'error': error}), 400

    Checks run in order — first failure short-circuits the rest so
    the user gets one clear, actionable error message at a time.

    Args:
        file: Werkzeug FileStorage object from request.files

    Returns:
        (True, None)           — file passed all checks
        (False, error_string)  — file failed, error explains why
    """
    # 1. Extension — cheapest check, no file reading needed
    is_valid, error = _check_extension(file.filename)
    if not is_valid:
        return False, error

    ext = _get_extension(file.filename)

    # 2. Size — seek to end, count bytes, reset to start
    is_valid, error = _check_size(file)
    if not is_valid:
        return False, error

    # 3. Magic bytes — read first 8 bytes to verify the true file type
    is_valid, error = _check_magic_bytes(file, ext)
    if not is_valid:
        return False, error

    # Reset stream to position 0 so extraction_service can read from beginning
    file.seek(0)

    return True, None


# ── Private helpers ───────────────────────────────────────────────────────────

def _get_extension(filename: str) -> str:
    """
    Extract the lowercase extension from a filename.
    Uses rsplit so filenames like 'my.resume.final.pdf' work correctly.

    Args:
        filename: raw filename string from FileStorage.filename

    Returns:
        Lowercase extension without the dot, e.g. 'pdf' or 'docx'.
        Empty string if no extension exists.
    """
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def _check_extension(filename: str) -> tuple:
    """
    Reject files with a missing, empty, or disallowed extension.
    Never reads the file — inspects the filename string only.

    Args:
        filename: raw filename string from FileStorage.filename

    Returns:
        (True, None) or (False, error_message)
    """
    if not filename or filename.strip() == "":
        return False, "No file was provided."

    ext = _get_extension(filename)

    if not ext:
        return False, (
            "The uploaded file has no extension. "
            "Please upload a PDF or DOCX file."
        )

    if ext not in ALLOWED_EXTENSIONS:
        return False, (
            f"'.{ext}' files are not supported. "
            "Please upload a PDF or DOCX file."
        )

    return True, None


def _check_size(file) -> tuple:
    """
    Reject files that are empty or exceed the 5 MB limit.

    Seeks to the end of the stream to read the byte count, then
    resets to position 0. No file content is loaded into memory.

    Args:
        file: Werkzeug FileStorage object

    Returns:
        (True, None) or (False, error_message)
    """
    file.seek(0, os.SEEK_END)    # Move cursor to end of stream
    size_bytes = file.tell()     # Cursor position = total byte count
    file.seek(0)                 # Reset cursor to start

    if size_bytes == 0:
        return False, (
            "The uploaded file is empty. "
            "Please upload a valid CV."
        )

    if size_bytes > MAX_FILE_SIZE_BYTES:
        size_mb = size_bytes / (1024 * 1024)
        return False, (
            f"File size ({size_mb:.1f} MB) exceeds the 5 MB limit. "
            "Please compress your file and try again."
        )

    return True, None


def _check_magic_bytes(file, ext: str) -> tuple:
    """
    Read the first 8 bytes of the file and compare against known
    magic byte signatures for the declared extension.

    Why this matters: a user could rename a .exe or malicious .html
    to .pdf and bypass the extension check. Magic bytes catch this
    because they are written into the file by the program that
    created it — renaming a file never changes its magic bytes.

    Examples:
        Valid PDF start:   b'%PDF-1.7...'   matches b'%PDF'       OK
        Valid DOCX start:  b'PK\\x03\\x04...' matches b'PK\\x03\\x04' OK
        Renamed script:    b'<html>...'      does NOT match %PDF   FAIL

    Args:
        file: Werkzeug FileStorage object with cursor at position 0
        ext:  lowercase extension string, e.g. 'pdf' or 'docx'

    Returns:
        (True, None) or (False, error_message)
    """
    expected_sig = MAGIC_SIGNATURES.get(ext)

    if not expected_sig:
        # No signature defined for this extension — skip the check
        return True, None

    header = file.read(8)   # Read first 8 bytes only
    file.seek(0)            # Always reset after reading

    if not header.startswith(expected_sig):
        return False, (
            f"The file does not appear to be a valid {ext.upper()}. "
            "It may be corrupted or renamed from a different file type. "
            "Please re-export your CV and try again."
        )

    return True, None