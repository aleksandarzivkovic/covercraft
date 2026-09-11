"""CoverCraft cover/tracklist PDF generator.

Given a Tidal album ID, logs into Tidal, downloads the cover art and track
metadata, and renders a double-sided A4 PDF:

  Page 1 (front): three cutout squares -
    - cover art
    - tracklist
    - artist / album / year + a QR code linking to the Tidal album page
      (scan it with your phone to grab the URL, then paste it into your
      RFID tag-writer app)

  Page 2 (back): a small square showing where to stick the RFID tag, placed
    so it lands on the back of the tracklist square once the sheet is cut out
    and folded/laminated.

Usage:
    python make_cover.py <tidal_album_id> [--output-dir DIR] [--session-file PATH]

The first run opens a browser for Tidal login and caches the session to
--session-file (default: .config/tidal_session.json next to this script) so
later runs are silent.
"""

import argparse
import io
import os
import re
import sys
from pathlib import Path

import qrcode
import requests
import tidalapi
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# ============================================================
# CONFIGURATION
# ============================================================

DPI = 600

PAGE_WIDTH_MM, PAGE_HEIGHT_MM = 210.0, 297.0

# Cover / tracklist cutout squares (left column)
IMAGE_SIZE_MM = 120.0
ROW_GAP_MM = 20.0
COLUMN_X0_MM = 30.0  # left edge of the cover/tracklist column

# Info square (artist / album / year + QR code), to the right of the tracklist
INFO_SIZE_MM = 40.0
INFO_GAP_MM = 6.0

# RFID tag placement square, printed on the back page behind the cover square
RFID_SQUARE_MM = 20.0
# Nudge the back-page square to line up with your printer's duplex flip.
# Print a test sheet, hold it up to the light, and adjust these in mm.
BOX_CALIB_X_MM = 0.0
BOX_CALIB_Y_MM = 0.0

LINE_WIDTH_MM = 0.05
GUIDE_MARGIN_MM = 10.0  # how far the full-page cover/tracklist guide lines extend

FONT_REGULAR = r"C:\Windows\Fonts\calibri.ttf"
FONT_BOLD = r"C:\Windows\Fonts\calibrib.ttf"

# Running as a plain script (dev/terminal use from the repo): keep everything
# self-contained next to make_cover.py. Running as a packaged/installed exe
# (see gui.py + the release workflow): use conventional per-user Windows
# locations instead, since the exe's own folder may be read-only or get
# wiped/replaced on update.
FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    CONFIG_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "CoverCraft"
    DEFAULT_OUTPUT_DIR = Path.home() / "Documents" / "CoverCraft"
else:
    SCRIPT_DIR = Path(__file__).resolve().parent
    CONFIG_DIR = SCRIPT_DIR / ".config"
    DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output"

DEFAULT_SESSION_FILE = CONFIG_DIR / "tidal_session.json"


# ============================================================
# HELPERS
# ============================================================

def mm_to_px(value_mm, dpi=DPI):
    return round(value_mm * dpi / 25.4)


def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()


def format_duration(total_seconds):
    total_seconds = int(total_seconds or 0)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"


def fit_text_to_width(draw, text, font_path, max_width_px, start_size_px, min_size_px):
    """Shrink font size until text fits; if still too wide at min size, ellipsize."""
    size = start_size_px
    font = ImageFont.truetype(font_path, size)
    while size > min_size_px and draw.textlength(text, font=font) > max_width_px:
        size -= 1
        font = ImageFont.truetype(font_path, size)

    if draw.textlength(text, font=font) <= max_width_px:
        return font, text

    truncated = text
    while len(truncated) > 1 and draw.textlength(truncated + "\u2026", font=font) > max_width_px:
        truncated = truncated[:-1]
    return font, (truncated + "\u2026" if truncated != text else text)


# ============================================================
# TIDAL DATA FETCH
# ============================================================

def login(session_file: Path, log=print) -> tidalapi.Session:
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session = tidalapi.Session()
    if session_file.exists() and session.login_session_file(session_file):
        log(f"Loaded saved Tidal session from {session_file}")
    else:
        log("No usable saved session found, opening browser for Tidal login...")
        session.login_oauth_simple(fn_print=log)
        session.save_session_to_file(session_file)
        log(f"Session saved to {session_file}")
    return session


def fetch_album_data(session: tidalapi.Session, album_id: int) -> dict:
    album = session.album(album_id)

    artist_name = album.artist.name
    album_name = album.name
    year = album.year
    release_date = album.release_date
    release_date_str = release_date.strftime("%b %e, %Y").replace("  ", " ") if release_date else ""
    company = album.copyright or "Copyright unknown"
    share_url = album.share_url or f"https://tidal.com/browse/album/{album_id}"

    multi_volume = (album.num_volumes or 1) > 1

    tracks = []
    for t in album.tracks():
        if len(t.artists) > 1:
            track_artist = ", ".join(a.name for a in t.artists)
        else:
            track_artist = t.artist.name
        num = f"{t.volume_num}.{t.track_num}" if multi_volume else str(t.track_num)
        tracks.append({
            "num": num,
            "title": t.full_name,
            "artist": track_artist,
            "time": f"{t.duration // 60}:{t.duration % 60:02d}",
            "duration": t.duration or 0,
        })

    total_duration = album.duration or sum(t["duration"] for t in tracks)

    return {
        "id": album_id,
        "artist": artist_name,
        "album": album_name,
        "year": year,
        "release_date_str": release_date_str,
        "company": company,
        "share_url": share_url,
        "tracks": tracks,
        "num_tracks": len(tracks),
        "total_duration": total_duration,
        "cover_url": album.image("origin"),
        "cover_url_fallback": album.image(1280),
    }


def download_cover(data: dict) -> bytes:
    try:
        resp = requests.get(data["cover_url"], timeout=30)
        resp.raise_for_status()
        return resp.content
    except requests.RequestException:
        resp = requests.get(data["cover_url_fallback"], timeout=30)
        resp.raise_for_status()
        return resp.content


# ============================================================
# IMAGE RENDERING
# ============================================================

def render_cover_image(cover_bytes: bytes, size_mm: float) -> Image.Image:
    size_px = mm_to_px(size_mm)
    img = Image.open(io.BytesIO(cover_bytes)).convert("RGB")
    img = img.resize((size_px, size_px), Image.LANCZOS)
    return img


def render_tracklist_image(tracks, footer_text, company_text, size_mm: float) -> Image.Image:
    width_raw = height_raw = mm_to_px(size_mm)
    line_w_raw = mm_to_px(0.3)
    header_line_y = 5 * height_raw / 100
    footer_line_y = 92 * height_raw / 100
    header_txt_y = 4 * height_raw / 100

    img = Image.new("RGB", (width_raw, height_raw), "white")
    draw = ImageDraw.Draw(img)

    draw.line((3 * width_raw / 100, header_line_y, 97 * width_raw / 100, header_line_y), fill="black", width=line_w_raw)

    font_header = ImageFont.truetype(FONT_BOLD, mm_to_px(3))

    def max_font_height(available_h_px, num_tracks):
        return min(available_h_px / max(num_tracks, 1), mm_to_px(3))

    font_height_px_max = max_font_height(footer_line_y - header_line_y, len(tracks))

    def max_track_width(_tracks, _font, _column_name):
        _max_len = 0
        for _trk in _tracks:
            _len = draw.textlength(str(_trk[_column_name]) + "o", font=_font)
            if _len > _max_len:
                _max_len = _len
        return int(_max_len)

    available_width_px = int(97 * width_raw / 100 - 3 * width_raw / 100)
    while True:
        font_cells = ImageFont.truetype(FONT_BOLD, max(int(font_height_px_max), 1))
        max_num_len_px = max_track_width(tracks, font_cells, "num")
        max_title_len_px = max_track_width(tracks, font_cells, "title")
        max_artist_len_px = max_track_width(tracks, font_cells, "artist")
        max_time_len_px = max_track_width(tracks, font_cells, "time")

        row_width_px = max_num_len_px + max_title_len_px + max_artist_len_px + max_time_len_px
        if row_width_px < available_width_px or font_height_px_max <= 1:
            break
        font_height_px_max -= 1

    font_padding_percent = (footer_line_y - header_line_y - font_height_px_max * len(tracks)) / (
        font_height_px_max * (len(tracks) + 1)
    )

    y = header_txt_y
    draw.text((3 * width_raw / 100, y), "#", font=font_header, fill="black", anchor="ld")
    draw.text((3 * width_raw / 100 + max_num_len_px, y), "TITLE", font=font_header, fill="black", anchor="ld")
    draw.text((3 * width_raw / 100 + max_num_len_px + max_title_len_px, y), "ARTIST", font=font_header, fill="black", anchor="ld")
    draw.text((97 * width_raw / 100, y), "TIME", font=font_header, fill="black", anchor="rd")

    y = header_line_y + font_height_px_max * font_padding_percent
    for trk in tracks:
        draw.text((3 * width_raw / 100, int(y)), str(trk["num"]), font=font_cells, fill="black", anchor="la")
        draw.text((3 * width_raw / 100 + max_num_len_px, int(y)), trk["title"], font=font_cells, fill="black", anchor="la")
        draw.text((3 * width_raw / 100 + max_num_len_px + max_title_len_px, int(y)), trk["artist"], font=font_cells, fill="black", anchor="la")
        draw.text((97 * width_raw / 100, int(y)), trk["time"], font=font_cells, fill="black", anchor="ra")
        y += font_height_px_max * (1 + font_padding_percent)

    draw.line((3 * width_raw / 100, footer_line_y, 97 * width_raw / 100, footer_line_y), fill="black", width=line_w_raw)
    draw.text((3 * width_raw / 100, 93 * height_raw / 100), footer_text, font=font_header, fill="black")

    company = company_text
    for i in range(20, len(company)):
        if draw.textlength(company[:i], font=font_header) > 94 * width_raw / 100:
            company = company[: i - 2] + "..."
            break
    draw.text((3 * width_raw / 100, 96 * height_raw / 100), company, font=font_header, fill="black")

    return img


def generate_qr_image(data: str, target_px: int) -> Image.Image:
    qr = qrcode.QRCode(border=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    modules = qr.modules_count + 2 * qr.border
    qr.box_size = max(1, target_px // modules)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    if img.size[0] != target_px:
        img = img.resize((target_px, target_px), Image.NEAREST)
    return img


def render_info_image(artist, album_title, year, qr_data, size_mm: float) -> Image.Image:
    size_px = mm_to_px(size_mm)
    pad_px = mm_to_px(2.5)
    max_w = size_px - 2 * pad_px

    img = Image.new("RGB", (size_px, size_px), "white")
    draw = ImageDraw.Draw(img)

    font1, artist_txt = fit_text_to_width(draw, artist, FONT_BOLD, max_w, mm_to_px(3.4), mm_to_px(1.8))
    album_line = f"{album_title} ({year})" if year else album_title
    font2, album_txt = fit_text_to_width(draw, album_line, FONT_REGULAR, max_w, mm_to_px(3.0), mm_to_px(1.6))

    y = pad_px
    draw.text((size_px / 2, y), artist_txt, font=font1, fill="black", anchor="ma")
    y += font1.size + mm_to_px(0.8)
    draw.text((size_px / 2, y), album_txt, font=font2, fill="black", anchor="ma")
    y += font2.size + mm_to_px(1.8)

    remaining_h = size_px - pad_px - y
    qr_px = int(min(max_w, remaining_h))
    qr_px = max(qr_px, 1)
    qr_img = generate_qr_image(qr_data, qr_px)
    qr_x = (size_px - qr_px) / 2
    qr_y = y + (remaining_h - qr_px) / 2
    img.paste(qr_img, (int(qr_x), int(qr_y)))

    return img


# ============================================================
# LAYOUT
# ============================================================

def compute_layout():
    """Returns box rects (x0, y0, x1, y1) in mm, measured from the page's
    bottom-left corner (reportlab convention)."""
    col_x0 = COLUMN_X0_MM
    col_x1 = col_x0 + IMAGE_SIZE_MM

    total_col_h = IMAGE_SIZE_MM * 2 + ROW_GAP_MM
    col_y0 = (PAGE_HEIGHT_MM - total_col_h) / 2  # bottom of tracklist box

    tracklist_box = (col_x0, col_y0, col_x1, col_y0 + IMAGE_SIZE_MM)
    cover_box = (
        col_x0,
        col_y0 + IMAGE_SIZE_MM + ROW_GAP_MM,
        col_x1,
        col_y0 + 2 * IMAGE_SIZE_MM + ROW_GAP_MM,
    )

    info_x0 = col_x1 + INFO_GAP_MM
    info_x1 = info_x0 + INFO_SIZE_MM
    tracklist_cy = (tracklist_box[1] + tracklist_box[3]) / 2
    info_box = (info_x0, tracklist_cy - INFO_SIZE_MM / 2, info_x1, tracklist_cy + INFO_SIZE_MM / 2)

    if info_x1 > PAGE_WIDTH_MM - 4:
        print(
            f"WARNING: info box right edge ({info_x1:.1f}mm) is close to the page edge "
            f"({PAGE_WIDTH_MM}mm) - it may print outside your printer's margins.",
            file=sys.stderr,
        )

    return {"cover": cover_box, "tracklist": tracklist_box, "info": info_box}


def compute_rfid_square(layout):
    cx0, cy0, cx1, cy1 = layout["tracklist"]
    front_cx = (cx0 + cx1) / 2
    front_cy = (cy0 + cy1) / 2
    back_cx = PAGE_WIDTH_MM - front_cx + BOX_CALIB_X_MM
    back_cy = front_cy + BOX_CALIB_Y_MM
    half = RFID_SQUARE_MM / 2
    return (back_cx - half, back_cy - half, back_cx + half, back_cy + half)


# ============================================================
# PDF GENERATION
# ============================================================

def build_pdf(output_path: Path, cover_img, tracklist_img, info_img, layout, dry_run=False):
    c = canvas.Canvas(str(output_path), pagesize=(PAGE_WIDTH_MM * mm, PAGE_HEIGHT_MM * mm))
    c.setLineWidth(LINE_WIDTH_MM * mm)

    # ---------------- Page 1: front ----------------
    boxes = [("tracklist", tracklist_img), ("info", info_img)]
    if dry_run:
        # Skip the (ink-heavy) cover photo - just outline the box and label it,
        # so you can still check the cut lines / QR / RFID alignment cheaply.
        cx0, cy0, cx1, cy1 = layout["cover"]
        c.rect(cx0 * mm, cy0 * mm, (cx1 - cx0) * mm, (cy1 - cy0) * mm, stroke=1, fill=0)
        c.setFont("Helvetica", 10)
        c.drawCentredString((cx0 + cx1) / 2 * mm, (cy0 + cy1) / 2 * mm, "COVER (dry run - not printed)")
    else:
        boxes.append(("cover", cover_img))

    for name, img in boxes:
        x0, y0, x1, y1 = layout[name]
        c.drawImage(
            ImageReader(img),
            x0 * mm,
            y0 * mm,
            width=(x1 - x0) * mm,
            height=(y1 - y0) * mm,
            preserveAspectRatio=True,
        )

    # Full-page guide lines around the cover/tracklist column (straight-edge cuts)
    col_x0, _, col_x1, _ = layout["tracklist"]
    for x in (col_x0, col_x1):
        c.line(x * mm, GUIDE_MARGIN_MM * mm, x * mm, (PAGE_HEIGHT_MM - GUIDE_MARGIN_MM) * mm)
    for box_name in ("cover", "tracklist"):
        _, y0, _, y1 = layout[box_name]
        for y in (y0, y1):
            c.line(GUIDE_MARGIN_MM * mm, y * mm, (PAGE_WIDTH_MM - GUIDE_MARGIN_MM) * mm, y * mm)

    # Info box is small - just outline it directly
    ix0, iy0, ix1, iy1 = layout["info"]
    c.rect(ix0 * mm, iy0 * mm, (ix1 - ix0) * mm, (iy1 - iy0) * mm, stroke=1, fill=0)

    c.showPage()

    # ---------------- Page 2: back (RFID placement) ----------------
    c.setLineWidth(LINE_WIDTH_MM * mm)
    rx0, ry0, rx1, ry1 = compute_rfid_square(layout)
    c.rect(rx0 * mm, ry0 * mm, (rx1 - rx0) * mm, (ry1 - ry0) * mm, stroke=1, fill=0)

    c.showPage()
    c.save()


# ============================================================
# CORE PIPELINE (shared by the CLI and the GUI)
# ============================================================

def generate_pdf(album_id, output_dir=None, session_file=None, dry_run=False, log=print) -> Path:
    """Fetch an album from Tidal and write its cover/tracklist PDF.

    Returns the path to the generated PDF. Raises tidalapi.exceptions.ObjectNotFound
    if the album ID doesn't exist.
    """
    output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    session_file = Path(session_file) if session_file else DEFAULT_SESSION_FILE

    session = login(session_file, log=log)

    log(f"Fetching album {album_id} from Tidal...")
    data = fetch_album_data(session, album_id)

    artist_name = sanitize_filename(data["artist"])
    album_name = sanitize_filename(data["album"])
    year_str = str(data["year"]) if data["year"] else "Unknown Year"

    # Intermediate/debug files are side files, not deliverables - keep them out
    # of output_dir (which should only ever contain the generated PDFs).
    cache_dir = CONFIG_DIR / "cache" / f"{artist_name} - {album_name}"
    cache_dir.mkdir(parents=True, exist_ok=True)

    layout = compute_layout()
    cover_img = None
    if dry_run:
        log("Dry run: skipping cover art download/render.")
    else:
        log("Downloading cover art...")
        cover_bytes = download_cover(data)
        (cache_dir / "cover_original.jpg").write_bytes(cover_bytes)
        cover_img = render_cover_image(cover_bytes, IMAGE_SIZE_MM)
        cover_img.save(cache_dir / "cover.jpg", "JPEG", quality=95, dpi=(DPI, DPI))

    log("Rendering cutout images...")
    footer_text = f"{data['release_date_str']} \u2022 {data['num_tracks']} tracks ({format_duration(data['total_duration'])})"
    tracklist_img = render_tracklist_image(data["tracks"], footer_text, data["company"], IMAGE_SIZE_MM)

    info_img = render_info_image(data["artist"], data["album"], data["year"], data["share_url"], INFO_SIZE_MM)

    tracklist_img.save(cache_dir / "tracklist.jpg", "JPEG", quality=95, dpi=(DPI, DPI))
    info_img.save(cache_dir / "info.jpg", "JPEG", quality=95, dpi=(DPI, DPI))
    (cache_dir / "url.txt").write_text(
        f"{data['artist']}\n{data['album']}\n{data['share_url']}\n", encoding="utf-8"
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = " - dry-run" if dry_run else ""
    pdf_path = output_dir / f"{artist_name} - {album_name} - {year_str}{suffix}.pdf"
    log(f"Building PDF at {pdf_path} ...")
    build_pdf(pdf_path, cover_img, tracklist_img, info_img, layout, dry_run=dry_run)

    log(f"Done. Print '{pdf_path}' double-sided (flip on long edge).")
    return pdf_path


# ============================================================
# CLI ENTRY POINT
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Generate a CoverCraft cover/tracklist PDF from a Tidal album ID.")
    parser.add_argument("album_id", type=int, help="Tidal album ID")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Where to write the generated files")
    parser.add_argument("--session-file", type=Path, default=DEFAULT_SESSION_FILE, help="Tidal session cache file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip the cover photo (outline + label only) to test cut/QR/RFID positions without burning toner",
    )
    args = parser.parse_args()
    generate_pdf(args.album_id, args.output_dir, args.session_file, args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except tidalapi.exceptions.ObjectNotFound:
        print("Album not found on Tidal.", file=sys.stderr)
        sys.exit(1)
