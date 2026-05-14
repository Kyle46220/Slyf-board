#!/usr/bin/env python3
"""
Automated Captcha Solver for Signal Registration
Attempts to solve captchas using various approaches
"""

import time
import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def generate_captcha_token_manual():
    """Generate captcha token by providing instructions for manual solving"""
    print("=== Manual Captcha Generation ===")
    print("1. Open this URL in your browser:")
    print("   https://signalcaptchas.org/registration/generate.html")
    print("2. Solve the captcha challenge")
    print("3. Right-click the 'Open Signal' link and copy the URL")
    print("4. The URL should look like:")
    print("   signalcaptcha://signal-hcaptcha-short.5fad97ac-7d06-4e44-b18a-b950b20148ff.registration.YOUR_TOKEN")
    print("")
    token = input("Paste the signalcaptcha:// URL here: ").strip()
    return token

def try_api_captcha_generation():
    """Try to generate captcha token via API"""
    try:
        # Try Signal's captcha API
        url = "https://signalcaptchas.org/registration/generate"
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        response = requests.post(url, headers=headers, timeout=10)

        if response.status_code == 200:
            print("API response:", response.text)
            # Try to extract captcha token from response
            if "signalcaptcha://" in response.text:
                start = response.text.find("signalcaptcha://")
                end = response.text.find('"', start)
                if end == -1:
                    end = response.text.find("'", start)
                if end != -1:
                    return response.text[start:end]

        return None
    except Exception as e:
        print(f"API captcha generation failed: {e}")
        return None

def try_selenium_captcha():
    """Try to use Selenium for captcha solving"""
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

        driver = webdriver.Chrome(options=chrome_options)

        try:
            driver.get("https://signalcaptchas.org/registration/generate.html")

            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Try to find captcha elements
            time.sleep(5)

            # Get page source
            page_source = driver.page_source

            # Look for signalcaptcha URLs
            if "signalcaptcha://" in page_source:
                start = page_source.find("signalcaptcha://")
                end = page_source.find('"', start)
                if end == -1:
                    end = page_source.find("'", start)
                if end != -1:
                    captcha_token = page_source[start:end]
                    print(f"Found captcha token: {captcha_token[:50]}...")
                    return captcha_token

            print("No captcha token found in page")
            return None

        finally:
            driver.quit()

    except Exception as e:
        print(f"Selenium captcha solving failed: {e}")
        return None

def main():
    print("Signal Captcha Solver")
    print("====================")

    # Try automated methods first
    print("Trying API captcha generation...")
    token = try_api_captcha_generation()
    if token:
        print(f"Success! Got token: {token[:50]}...")
        return token

    print("Trying Selenium captcha solving...")
    token = try_selenium_captcha()
    if token:
        print(f"Success! Got token: {token[:50]}...")
        return token

    # Fall back to manual method
    print("Automated methods failed, falling back to manual method...")
    token = generate_captcha_token_manual()

    if token and token.startswith("signalcaptcha://"):
        print(f"Valid captcha token obtained: {token[:50]}...")
        return token
    else:
        print("Invalid captcha token format")
        return None

if __name__ == "__main__":
    token = main()
    if token:
        print(f"\nFinal captcha token: {token}")
        print("Use this token with: signal-cli register --captcha '{token}'")
    else:
        print("Failed to obtain captcha token")
