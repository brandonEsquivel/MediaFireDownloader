# MediaFire Batch Downloader

A small Selenium-based utility for batch-downloading files from MediaFire. Point it at a text file full of links, and it handles opening each page and clicking the download button. Everything else — where files go, what they're named — stays under your control.

---

## Background

Built out of a practical need: downloading large multi-part archives from MediaFire where manually opening 20+ tabs and clicking through each one is tedious and error-prone. The script handles the repetitive navigation while keeping the user in the loop for each save decision. The browser never closes on its own, so in-progress transfers are never interrupted.

---

## Requirements

- Python 3.10 or newer
- Google Chrome (keep it updated)
- Windows 10/11 — also runs on macOS and Linux

---

## Setup

Clone the repository and install dependencies:

```bash
git clone https://github.com/your-username/mediafire-batch-downloader.git
cd mediafire-batch-downloader
pip install -r requirements.txt
```

`webdriver-manager` handles ChromeDriver automatically — it detects your Chrome version and downloads the matching driver on first run. Nothing to configure manually.

If `pip` throws an error, try:

```bash
python -m pip install -r requirements.txt
```

---

## File layout

```
mediafire-batch-downloader/
├── downloader.py       # main script
├── requirements.txt    # dependencies
├── links.txt           # your link list (you create this)
└── download_log.txt    # written automatically after each run
```

---

## Preparing the links file

One URL per line, nothing else required:

```
https://www.mediafire.com/file/abc123/archive.part01.rar/file
https://www.mediafire.com/file/def456/archive.part02.rar/file
https://www.mediafire.com/file/ghi789/archive.part03.rar/file
```

Blank lines are skipped.

---

## Running it

No arguments — the script will ask for the file path:
```bash
python downloader.py
```

Pass the file directly:
```bash
python downloader.py links.txt
```

Increase the page-load timeout for slow connections (default is 30s):
```bash
python downloader.py links.txt --timeout 60
```

---

## What happens when it runs

The script processes each link sequentially. For every URL it opens the MediaFire page in an incognito Chrome tab, dismisses any ad popups that appear, and clicks the download button. At that point Chrome shows its native Save As dialog — you pick the destination folder and filename, then return to the terminal and hit Enter to move on.

Console output looks like this:

```
Session started  |  Links to process: 24
────────────────────────────────────────────────────────────
[1/24] Line 1: https://www.mediafire.com/file/...

  ► Save As dialog is open in Chrome.
    Choose your save location, then come back here.
  ► Press ENTER when you have saved the file (or skipped it)...
```

Once all links have been processed:

```
════════════════════════════════════════════════════════════
  All links have been processed.
  The browser will stay open so your downloads can finish.

  Finish downloads and close browser? [y/N]:
```

Pressing Enter (or typing `n`) keeps Chrome open. Type `y` only when Chrome's download bar shows everything is done — the browser closes immediately on confirmation.

---

## Log file

`download_log.txt` is created on the first run and appended to on every subsequent one. It captures any links that failed along with the reason, and ends with a session summary:

```
╔══════════════════════════════════════════════════╗
║               DOWNLOAD SESSION SUMMARY           ║
╚══════════════════════════════════════════════════╝
  Completed at          : 2026-02-22 14:35:10
  Links file            : links.txt
  Total links in file   : 24
  Links processed       : 24
  Successful clicks     : 23
  Failed / broken links : 1

  ── Failed Links ──
    Line   11: https://www.mediafire.com/file/...
               Reason : MediaFire reports file as invalid or deleted
────────────────────────────────────────────────────
```

Failures don't stop the run — the script logs the issue and moves to the next link.

---

## Configuration

Constants at the top of `downloader.py` can be adjusted without touching any logic:

| Constant | Default | Notes |
|---|---|---|
| `PAGE_TIMEOUT` | `30` | Seconds before a page load is considered failed |
| `LOG_FILE` | `download_log.txt` | Log filename |
| `DOWNLOAD_BUTTON_SELECTORS` | *(list)* | CSS selectors for the download button, tried in order |
| `INVALID_PAGE_TEXTS` | *(list)* | Strings that indicate a missing or deleted file |

---

## Troubleshooting

**`python` is not recognized**
Python wasn't added to PATH during installation. Reinstall and tick "Add Python to PATH" on the installer's first screen, or add it manually through System Environment Variables.

**Save As dialog doesn't appear**
Chrome has a default download folder configured, which bypasses the dialog. Fix it under Chrome Settings → Downloads → enable "Ask where to save each file before downloading".

**Download button not found**
MediaFire updates their frontend occasionally. Open one of the links in Chrome, right-click the download button, hit Inspect, and look at the element's `id` or `class` attribute. Add the new selector to `DOWNLOAD_BUTTON_SELECTORS` in `downloader.py`.

**Chrome crashes on launch**
Usually a version mismatch between Chrome and ChromeDriver. Update Chrome first, then delete the cached driver in `~/.wdm/` so `webdriver-manager` fetches a fresh one.

---

## Dependencies

```
selenium>=4.18.0
webdriver-manager>=4.0.1
```

---

## License

MIT
