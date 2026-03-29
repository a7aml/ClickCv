# test_validators.py  (put this in your project root)
import io

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.utils.file_validators import validate_cv_file
class MockFile:
    """Mimics Werkzeug FileStorage for testing without Flask"""
    def __init__(self, filename, content):
        self.filename = filename
        self._stream = io.BytesIO(content)

    def read(self, n=-1):
        return self._stream.read(n)

    def seek(self, pos, whence=0):
        return self._stream.seek(pos, whence)

    def tell(self):
        return self._stream.tell()


def run_tests():
    print("Running file_validators tests...\n")
    passed = 0
    failed = 0

    def check(label, file, expected_valid, expected_error_contains=None):
        nonlocal passed, failed
        is_valid, error = validate_cv_file(file)
        if is_valid != expected_valid:
            print(f"  FAIL  {label}")
            print(f"        expected valid={expected_valid}, got valid={is_valid}, error={error}")
            failed += 1
            return
        if expected_error_contains and expected_error_contains.lower() not in (error or "").lower():
            print(f"  FAIL  {label}")
            print(f"        expected error containing '{expected_error_contains}', got: {error}")
            failed += 1
            return
        print(f"  PASS  {label}")
        passed += 1

    # ── Extension checks ──
    check("No filename",            MockFile("", b"%PDF content"),        False, "No file")
    check("No extension",           MockFile("myresume", b"%PDF"),        False, "extension")
    check("Wrong extension .txt",   MockFile("cv.txt", b"%PDF content"),  False, "not supported")
    check("Wrong extension .exe",   MockFile("cv.exe", b"MZ content"),    False, "not supported")

    # ── Size checks ──
    check("Empty file",             MockFile("cv.pdf", b""),              False, "empty")
    check("File over 5MB",          MockFile("cv.pdf", b"%PDF" + b"x" * (5 * 1024 * 1024 + 1)), False, "5 MB")

    # ── Magic bytes checks ──
    check("PDF with wrong bytes",   MockFile("cv.pdf",  b"<html>fake</html>"),    False, "valid PDF")
    check("DOCX with wrong bytes",  MockFile("cv.docx", b"<html>fake</html>"),    False, "valid DOCX")
    check("Renamed EXE as PDF",     MockFile("cv.pdf",  b"MZ\x90\x00fake"),       False, "valid PDF")

    # ── Valid files ──
    valid_pdf  = b"%PDF-1.4 fake pdf content that is valid size"
    valid_docx = b"PK\x03\x04fake docx content that is valid size"
    check("Valid PDF",              MockFile("resume.pdf",  valid_pdf),   True)
    check("Valid DOCX",             MockFile("resume.docx", valid_docx),  True)
    check("Valid PDF uppercase",    MockFile("RESUME.PDF",  valid_pdf),   True)

    print(f"\n{passed} passed — {failed} failed")


if __name__ == "__main__":
    run_tests()