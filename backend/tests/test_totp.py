import pyotp
from app.totp import verify_totp

SECRET = "JBSWY3DPEHPK3PXP"


def test_valid_current_code():
    totp = pyotp.TOTP(SECRET, interval=300)
    code = totp.now()
    assert verify_totp(code, SECRET) is True


def test_invalid_code():
    assert verify_totp("000000", SECRET) is False


def test_wrong_length_rejected():
    assert verify_totp("12345", SECRET) is False
    assert verify_totp("1234567", SECRET) is False


def test_non_numeric_rejected():
    assert verify_totp("abcdef", SECRET) is False
