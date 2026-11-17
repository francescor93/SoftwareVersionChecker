#!/usr/bin/env python3
import os
import platform
import subprocess
import requests
import re
import traceback
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import time
import random
import sys

# Read a numeric environment setting, using a default when it is unset.
def env_number(name, default, cast=int):
    """Read a numeric setting from the environment, falling back to a default when unset."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return cast(raw)
    except ValueError:
        raise ValueError(f"Invalid value for {name}: '{raw}'")

# Log a message with a timestamp to the console and the log file.
def log(msg):
    """Write a timestamped log message to both the console and the log file."""
    timestamped = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(timestamped)
    with open(LOG_FILE, "a") as f:
        f.write(timestamped + "\n")

# Extract the first version-like value from a string.
def extract_version(text):
    """Return the first semantic-like version from a string, or 'N/A' if no match exists."""
    m = re.search(r"\d+(?:\.\d+){0,2}", text)
    if m:
        return m.group(0)
    log(f"No version found in output: {text.strip()[:200]!r}")
    return "N/A"

# Run a shell command safely and capture its output.
def safe_getoutput(cmd):
    """Run a shell command and return its trimmed output, logging any execution failure."""
    try:
        result = subprocess.getoutput(cmd)
        return result.strip()
    except Exception as e:
        log(f"Error while executing '{cmd}': {e}")
        return "(error)"

# Collect the current versions for the configured server stack.
def get_versions():
    """Collect the current versions of the configured server stack and timestamp the check."""
    system = platform.system().lower()
    apache_executable = ""
    if system == "windows":
        apache_executable = "httpd"
    else:
        apache_executable = "sudo apache2"
    versions = {
        "Apache": extract_version(safe_getoutput(f"{apache_executable} -v | grep version | awk '{{print $3}}' | cut -d/ -f2")),
        "PHP": extract_version(safe_getoutput("php -v | head -n1 | awk '{print $2}'")),
        "MariaDB": extract_version(safe_getoutput("mysql -V | awk '{print $5}' | tr -d ','")),
        "Node.js": extract_version(safe_getoutput("node -v")),
        "NPM": extract_version(safe_getoutput("npm -v")),
        "Python": platform.python_version(),
        "Last Check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return versions

# Resolve the Confluence credentials and URL for the active environment mode.
def get_confluence_auth():
    """Resolve the Confluence base URL, user, and token based on the MODE defined in .env."""
    mode = (os.getenv("MODE") or "").strip().upper()
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid MODE: '{mode}' (allowed values: {', '.join(VALID_MODES)})")

    base_url = os.getenv(f"CONF_{mode}_BASE_URL")
    token = os.getenv(f"CONF_{mode}_TOKEN")
    user = os.getenv("CONF_USER")

    required = {
        "CONF_USER": user,
        f"CONF_{mode}_BASE_URL": base_url,
        f"CONF_{mode}_TOKEN": token,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(f"Missing variables in .env for MODE={mode}: {', '.join(missing)}")

    return mode, base_url.rstrip("/"), user, token

class ConfluenceHTTPError(RuntimeError):
    """Confluence HTTP error with the status code exposed so the retry logic can decide whether to retry."""

    # Initialize the exception with the HTTP response details.
    def __init__(self, res):
        self.status_code = res.status_code
        super().__init__(
            f"HTTP {res.status_code} on {res.request.method} {res.url}: {res.text[:500]}"
        )

# Validate the HTTP response and raise a detailed Confluence error when needed.
def check_response(res):
    """Act like raise_for_status but include the response body for easier debugging of scope and auth failures."""
    if not res.ok:
        raise ConfluenceHTTPError(res)

# Check whether a failure should be retried automatically.
def is_retryable(exc):
    """Return True for version conflicts, rate limiting, server errors, and network problems."""
    if isinstance(exc, ConfluenceHTTPError):
        return exc.status_code in RETRYABLE_STATUS
    return isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))

# Update the target Confluence table with the current software versions.
def update_confluence_table(versions):
    """Fetch the Confluence page, update the target version column, and write the modified HTML back."""
    page_id = os.getenv("CONF_PAGE_ID")
    column_name = os.getenv("SERVER_NAME")
    if not all([page_id, column_name]):
        raise ValueError("Missing CONF_PAGE_ID or SERVER_NAME in .env")

    mode, base_url, user_email, api_token = get_confluence_auth()
    log(f"Authentication mode: {mode}")

    auth = (user_email, api_token)
    headers = {"Accept": "application/json"}

    # Get the page from Confluence.
    url = f"{base_url}/wiki/rest/api/content/{page_id}?expand=body.storage,version"
    res = requests.get(url, headers=headers, auth=auth, timeout=HTTP_TIMEOUT)
    check_response(res)
    data = res.json()
    html = data["body"]["storage"]["value"]

    # Parse the table.
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        raise RuntimeError("No table found in the Confluence page")

    headers_row = [th.get_text(strip=True) for th in table.find_all("th")]
    if column_name not in headers_row:
        raise RuntimeError(f"No column '{column_name}' found in the table")

    col_index = headers_row.index(column_name)

    # Update existing cells.
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        key = cells[0].get_text(strip=True)
        if key in versions and len(cells) > col_index:
            cells[col_index].string = versions[key]

    # Update the page in Confluence.
    new_html = str(soup)
    new_version = data["version"]["number"] + 1
    payload = {
        "id": page_id,
        "type": "page",
        "title": data["title"],
        "body": {"storage": {"value": new_html, "representation": "storage"}},
        "version": {"number": new_version},
    }

    put_res = requests.put(f"{base_url}/wiki/rest/api/content/{page_id}", json=payload, auth=auth, timeout=HTTP_TIMEOUT)
    check_response(put_res)

    log(f"Update completed on '{column_name}' at {versions['Last Check']}")

# Retry the whole update process until a recoverable error is resolved or exhausted.
def update_with_retry():
    """Retry the full update cycle after recoverable errors. Returns True if the update succeeds."""
    versions = get_versions()
    total_attempts = MAX_RETRIES + 1

    for attempt in range(1, total_attempts + 1):
        try:
            update_confluence_table(versions)
            return True
        except Exception as e:
            log(f"Attempt {attempt}/{total_attempts} failed: {e}")

            if not is_retryable(e):
                log(traceback.format_exc())
                log("Non-recoverable error: no further attempts will be made.")
                return False
            if attempt == total_attempts:
                log(traceback.format_exc())
                log("Retry attempts exhausted.")
                return False

            delay = RETRY_DELAY + random.uniform(0, RETRY_JITTER)
            log(f"Retrying in {delay:.0f}s...")
            time.sleep(delay)

    return False

# Determine the script folder dynamically.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# Load the .env file from the same folder.
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Read configuration values from the environment with defaults and type casting.
HTTP_TIMEOUT = env_number("HTTP_TIMEOUT", 30, float)
MAX_RETRIES = env_number("MAX_RETRIES", 5)
RETRY_DELAY = env_number("RETRY_DELAY", 60, float)
RETRY_JITTER = env_number("RETRY_JITTER", 10, float)
RETRYABLE_STATUS = {409, 429, 500, 502, 503, 504}
VALID_MODES = ("CLASSIC", "SCOPED")

# Custom log file (same path as the script).
LOG_FILE = os.path.join(BASE_DIR, "software_versions.log")

# Main entry point.
if __name__ == "__main__":
    log("=" * 70)
    log("Starting version check...")
    ok = update_with_retry()
    log("Execution finished.\n")
    sys.exit(0 if ok else 1)
