"""
MediaFire Batch Downloader  v3
==============================
Simplified, user-controlled download flow.

How it works
------------
1. Reads every link from the .txt file.
2. For each link:
     - Opens the MediaFire page in Chrome (incognito).
     - Clicks the Download button automatically.
     - The native "Save As" dialog appears — YOU choose where to save it.
     - After you confirm the save, press ENTER in this console to move
       to the next link.
3. After ALL links have been processed, the console asks:
       "Finish downloads and close browser? [y/N]"
   The browser stays open until you type  y  and press ENTER.
   This guarantees every in-progress download has time to complete.

Usage
-----
    python downloader.py                   # prompts for file path
    python downloader.py links.txt
    python downloader.py links.txt --timeout 60
"""

import sys
import os
import argparse
import logging
import time
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)
from webdriver_manager.chrome import ChromeDriverManager


# ─────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────────
LOG_FILE     = "download_log.txt"
PAGE_TIMEOUT = 30    # seconds to wait for the MediaFire page to load
HEADLESS     = False # never set True — user needs to see the Save As dialog

# CSS selectors tried in order to find the MediaFire download button
DOWNLOAD_BUTTON_SELECTORS = [
    "a#downloadButton",
    "a[id='downloadButton']",
    "a.download_link",
    "div.download_link a",
    "a[aria-label*='Download']",
]

INVALID_PAGE_TEXTS = [
    "invalid or deleted",
    "file not found",
    "this file has been deleted",
    "unavailable",
    "error occurred",
]


# ─────────────────────────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────────────────────────
def setup_logger() -> logging.Logger:
    logger = logging.getLogger("mf_downloader")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s  [%(levelname)s]  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    fh = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger


logger = setup_logger()


# ─────────────────────────────────────────────────────────────────
#  CHROME SETUP
# ─────────────────────────────────────────────────────────────────
def build_driver() -> webdriver.Chrome:
    """
    Launch Chrome incognito WITHOUT any auto-download prefs.
    This allows the native Save As dialog to appear for each file,
    giving the user full control over filename and save location.
    """
    options = Options()
    options.add_argument("--incognito")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # NOTE: We intentionally do NOT set download.prompt_for_download = False
    # and do NOT call Browser.setDownloadBehavior — both would suppress the
    # Save As dialog. We WANT it to appear so the user can name each file.

    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(PAGE_TIMEOUT)
    return driver


# ─────────────────────────────────────────────────────────────────
#  TAB / POPUP HELPERS
# ─────────────────────────────────────────────────────────────────
def close_popup_tabs(driver: webdriver.Chrome, keep_handle: str) -> None:
    """Close every tab except keep_handle (kills ad popups)."""
    for handle in list(driver.window_handles):
        if handle != keep_handle:
            try:
                driver.switch_to.window(handle)
                driver.close()
                logger.debug("  [popup] Closed extra tab: %s", handle)
            except WebDriverException:
                pass
    try:
        driver.switch_to.window(keep_handle)
    except WebDriverException:
        pass


# ─────────────────────────────────────────────────────────────────
#  PAGE HELPERS
# ─────────────────────────────────────────────────────────────────
def is_page_invalid(driver: webdriver.Chrome) -> bool:
    return any(p in driver.page_source.lower() for p in INVALID_PAGE_TEXTS)


def find_download_button(driver: webdriver.Chrome):
    for selector in DOWNLOAD_BUTTON_SELECTORS:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, selector)
            if btn.is_displayed():
                return btn
        except NoSuchElementException:
            continue
    return None


# ─────────────────────────────────────────────────────────────────
#  SINGLE-LINK ROUTINE
# ─────────────────────────────────────────────────────────────────
def process_link(
    driver:      webdriver.Chrome,
    url:         str,
    main_handle: str,
) -> tuple[bool, str]:
    """
    Navigate to the MediaFire page, click Download, and return.
    The Save As dialog will appear — the caller waits for user input
    before calling this function again.
    """
    # Load the page
    try:
        driver.get(url)
    except TimeoutException:
        return False, "Page load timed out"
    except WebDriverException as exc:
        return False, f"WebDriver error: {exc.msg}"

    # Kill any popup tabs that opened during page load
    close_popup_tabs(driver, main_handle)

    # Validate the page
    if is_page_invalid(driver):
        return False, "MediaFire reports file as invalid or deleted"

    # Wait for the download button
    try:
        WebDriverWait(driver, PAGE_TIMEOUT).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, DOWNLOAD_BUTTON_SELECTORS[0])
            )
        )
    except TimeoutException:
        pass  # fall through to manual search

    btn = find_download_button(driver)
    if btn is None:
        return False, "Download button not found on page"

    # Click — this triggers the Save As dialog in the browser
    try:
        btn.click()
    except Exception as exc:
        return False, f"Could not click download button: {exc}"

    # Small pause so the Save As dialog has time to appear before
    # the console prints its "press ENTER" prompt
    time.sleep(1.5)

    # Kill any ad popup that opened alongside the dialog
    close_popup_tabs(driver, main_handle)

    return True, "OK"


# ─────────────────────────────────────────────────────────────────
#  ARGUMENT PARSING
# ─────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Batch-download MediaFire links with user-controlled Save As."
    )
    p.add_argument("links_file", nargs="?", default=None,
                   help="Path to .txt file with one MediaFire URL per line.")
    p.add_argument("--timeout", type=int, default=PAGE_TIMEOUT,
                   help=f"Page-load timeout in seconds (default: {PAGE_TIMEOUT}).")
    return p.parse_args()


# ─────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────
def main():
    args = parse_args()

    global PAGE_TIMEOUT
    PAGE_TIMEOUT = args.timeout

    # Resolve links file
    links_file = args.links_file
    if not links_file:
        links_file = input("Enter path to links .txt file: ").strip()
    if not os.path.isfile(links_file):
        print(f"ERROR: File not found: {links_file}")
        sys.exit(1)

    # Read links
    with open(links_file, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    links = [
        (i + 1, line.strip())
        for i, line in enumerate(raw_lines)
        if line.strip()
    ]
    total = len(links)

    logger.info("=" * 60)
    logger.info("Session started  |  Links to process: %d", total)
    logger.info("=" * 60)
    print()
    print("  Each link will open in Chrome and click Download automatically.")
    print("  A Save As dialog will appear — choose your folder and filename.")
    print("  After saving, come back here and press ENTER to continue.")
    print()

    if total == 0:
        logger.warning("No links found in file. Exiting.")
        sys.exit(0)

    # Launch Chrome — single tab reused for all links
    driver      = build_driver()
    main_handle = driver.current_window_handle

    success_count = 0
    failed_links  = []

    try:
        for idx, (line_no, url) in enumerate(links, start=1):
            print(f"─" * 60)
            logger.info("[%d/%d] Line %d: %s", idx, total, line_no, url)

            success, reason = process_link(driver, url, main_handle)

            if success:
                success_count += 1
                # ── Wait for user to handle the Save As dialog ──
                print()
                print(f"  ► Save As dialog is open in Chrome.")
                print(f"    Choose your save location, then come back here.")
                input("  ► Press ENTER when you have saved the file (or skipped it)... ")
                print()
            else:
                logger.warning("  ✘  FAILED — %s", reason)
                failed_links.append((line_no, url, reason))
                print()
                input("  ► Press ENTER to continue to the next link... ")
                print()

    except KeyboardInterrupt:
        print()
        logger.warning("Interrupted by user.")

    # ── FIX: Never close the browser automatically ──
    # All links have been processed but downloads may still be running.
    # The browser stays open until the user explicitly says so.
    print()
    print("=" * 60)
    print("  All links have been processed.")
    print("  The browser will stay open so your downloads can finish.")
    print()

    while True:
        answer = input("  Finish downloads and close browser? [y/N]: ").strip().lower()
        if answer == "y":
            break
        elif answer in ("n", ""):
            print("  Still waiting... (check your downloads in Chrome)")
        else:
            print("  Please type  y  to close or just press ENTER to keep waiting.")

    driver.quit()
    print()
    logger.info("Browser closed by user.")

    # ─────────────────────────────────────────
    #  SUMMARY
    # ─────────────────────────────────────────
    failed_count = len(failed_links)
    processed    = success_count + failed_count
    timestamp    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    summary_lines = [
        "",
        "╔══════════════════════════════════════════════════╗",
        "║               DOWNLOAD SESSION SUMMARY           ║",
        "╚══════════════════════════════════════════════════╝",
        f"  Completed at          : {timestamp}",
        f"  Links file            : {links_file}",
        f"  Total links in file   : {total}",
        f"  Links processed       : {processed}",
        f"  Successful clicks     : {success_count}",
        f"  Failed / broken links : {failed_count}",
    ]

    if failed_links:
        summary_lines.append("")
        summary_lines.append("  ── Failed Links ──")
        for ln, lurl, reason in failed_links:
            summary_lines.append(f"    Line {ln:>4}: {lurl}")
            summary_lines.append(f"             Reason : {reason}")

    summary_lines += ["─" * 52, ""]
    summary_text = "\n".join(summary_lines)

    print(summary_text)
    with open(LOG_FILE, "a", encoding="utf-8") as lf:
        lf.write(summary_text)

    logger.info("Log saved to: %s", LOG_FILE)


if __name__ == "__main__":
    main()
