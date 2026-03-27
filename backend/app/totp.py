import pyotp


def verify_totp(code: str, secret: str) -> bool:
    if not code or len(code) != 6 or not code.isdigit():
        return False
    totp = pyotp.TOTP(secret, interval=300)
    return totp.verify(code, valid_window=1)
