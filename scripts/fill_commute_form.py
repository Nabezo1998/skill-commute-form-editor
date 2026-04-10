"""
Commute Route Application Form Filler (通勤経路申請書)

Reusable helper script for filling Japanese PDF commute forms.
Adapt the FIELD_COORDS dict for different form templates.

Usage:
    python fill_commute_form.py --pdf <input.pdf> --output <output.pdf> --config <config.json>

Or import and use as a library:
    from fill_commute_form import CommmuteFormFiller
    filler = CommuteFormFiller("input.pdf")
    filler.analyze_layout()
    filler.fill(config)
    filler.save("output.pdf")
"""

import fitz
import json
import sys
import os
import platform


def get_japanese_font_path() -> str:
    """Return the path to a Japanese font for the current OS."""
    system = platform.system()
    candidates = []

    if system == "Windows":
        candidates = [
            "C:/Windows/Fonts/meiryo.ttc",
            "C:/Windows/Fonts/msgothic.ttc",
            "C:/Windows/Fonts/YuGothR.ttc",
        ]
    elif system == "Darwin":  # macOS
        candidates = [
            "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
    else:  # Linux
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        ]

    for path in candidates:
        if os.path.exists(path):
            return path

    raise FileNotFoundError(
        f"No Japanese font found on {system}. "
        f"Searched: {candidates}"
    )


class CommuteFormFiller:
    """Fill a 通勤経路申請書 PDF form."""

    def __init__(self, pdf_path: str):
        self.doc = fitz.open(pdf_path)
        self.page = self.doc[0]
        self.font_path = get_japanese_font_path()
        self.font = fitz.Font(fontfile=self.font_path)
        self.tw = fitz.TextWriter(self.page.rect)
        self.layout = {}

    def analyze_layout(self) -> dict:
        """Extract text positions and table grid from the PDF.

        Returns a dict with:
          - text_spans: list of {bbox, text, size}
          - table_columns: list of x-coordinates (vertical lines)
          - table_rows: list of y-coordinates (horizontal lines)
          - checkboxes: list of {char, bbox} for ▢ characters
          - seal_position: {x, y} of 印 character
        """
        spans = []
        checkboxes = []
        seal_pos = None

        blocks = self.page.get_text('dict')['blocks']
        for b in blocks:
            if b['type'] != 0:
                continue
            for line in b['lines']:
                for span in line['spans']:
                    text = span['text'].strip()
                    bbox = span['bbox']
                    if not text:
                        continue
                    spans.append({
                        'bbox': bbox,
                        'text': text,
                        'size': span['size']
                    })
                    if '▢' in text or '□' in text:
                        checkboxes.append({'char': text, 'bbox': bbox})
                    if text == '印':
                        seal_pos = {
                            'x': (bbox[0] + bbox[2]) / 2,
                            'y': (bbox[1] + bbox[3]) / 2
                        }

        # Extract table grid from drawings
        drawings = self.page.get_drawings()
        v_lines = []  # vertical (column boundaries)
        h_lines = []  # horizontal (row boundaries)

        for d in drawings:
            for item in d.get('items', []):
                if item[0] == 'l':  # line
                    p1, p2 = item[1], item[2]
                    if abs(p1.x - p2.x) < 1:  # vertical
                        v_lines.append(p1.x)
                    elif abs(p1.y - p2.y) < 1:  # horizontal
                        h_lines.append(p1.y)

        v_lines = sorted(set(round(x, 1) for x in v_lines))
        h_lines = sorted(set(round(y, 1) for y in h_lines))

        self.layout = {
            'text_spans': spans,
            'table_columns': v_lines,
            'table_rows': h_lines,
            'checkboxes': checkboxes,
            'seal_position': seal_pos,
        }
        return self.layout

    def center_text(self, x_left: float, x_right: float, y: float,
                    text: str, size: float = 11):
        """Append text centered horizontally within [x_left, x_right]."""
        text_w = self.font.text_length(text, fontsize=size)
        x = x_left + (x_right - x_left - text_w) / 2
        self.tw.append(fitz.Point(x, y), text, font=self.font, fontsize=size)

    def add_checkmark(self, box_bbox: tuple, size: float = 10):
        """Add a ✓ inside a checkbox bounding box."""
        x0, y0, x1, y1 = box_bbox
        cw = self.font.text_length("✓", fontsize=size)
        cx = x0 + ((x1 - x0) - cw) / 2
        cy = y1 - 1
        self.tw.append(fitz.Point(cx, cy), "✓", font=self.font, fontsize=size)

    def insert_seal(self, image_path: str, center_x: float, center_y: float,
                    seal_size: float = 36):
        """Insert a seal/stamp image centered at the given position."""
        rect = fitz.Rect(
            center_x - seal_size / 2, center_y - seal_size / 2,
            center_x + seal_size / 2, center_y + seal_size / 2
        )
        self.page.insert_image(rect, filename=image_path)

    def commit_text(self):
        """Write all accumulated text to the page.

        IMPORTANT: This must be called BEFORE insert_seal() if both are used,
        because insert_image modifies the page content stream.
        """
        self.page.write_text(writers=[self.tw])

    def save(self, output_path: str):
        """Save the modified PDF."""
        self.doc.save(output_path)
        self.doc.close()

    def generate_preview(self, output_path: str, scale: float = 2.0,
                         clip: tuple = None):
        """Render the page as a PNG preview image."""
        doc2 = fitz.open(output_path)
        mat = fitz.Matrix(scale, scale)
        clip_rect = fitz.Rect(*clip) if clip else None
        pix = doc2[0].get_pixmap(matrix=mat, clip=clip_rect)
        preview_path = output_path.replace('.pdf', '_preview.png')
        pix.save(preview_path)
        doc2.close()
        return preview_path


def fill_from_config(pdf_path: str, config: dict, output_path: str):
    """Fill a commute form from a config dict.

    Expected config structure:
    {
        "start_date": {"year": "2026", "month": "4", "day": "1"},
        "application_date": {"year": "2026", "month": "4", "day": "1"},
        "postal_code": {"first": "242", "last": "0007"},
        "address": "神奈川県大和市中央林間1丁目18-13 ...",
        "name": "鍋倉　隆造",
        "change_reason": "その他",
        "reason_detail": "運賃改定",
        "routes": [
            {
                "transit": "東急田園都市線",
                "from": "中央林間",
                "to": "渋谷",
                "one_way_fare": "390円",
                "monthly_pass": "14,170円"
            }
        ],
        "total": "20,410円",
        "seal_image": "path/to/hanko.png"
    }
    """
    filler = CommuteFormFiller(pdf_path)
    layout = filler.analyze_layout()

    # The actual coordinate mapping depends on the specific form template.
    # Use filler.analyze_layout() to determine coordinates, then call:
    #   filler.center_text(x_left, x_right, y, text, size)
    #   filler.add_checkmark(bbox)
    #   filler.commit_text()
    #   filler.insert_seal(image_path, x, y)
    #   filler.save(output_path)

    print(f"Layout analysis complete. Found:")
    print(f"  - {len(layout['text_spans'])} text spans")
    print(f"  - {len(layout['table_columns'])} column boundaries")
    print(f"  - {len(layout['table_rows'])} row boundaries")
    print(f"  - {len(layout['checkboxes'])} checkboxes")
    print(f"  - Seal position: {layout['seal_position']}")

    return filler, layout


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python fill_commute_form.py <input.pdf> <config.json>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    config_path = sys.argv[2]

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    output_path = config.get('output', pdf_path.replace('.pdf', '_filled.pdf'))
    filler, layout = fill_from_config(pdf_path, config, output_path)
    print("Layout analysis done. Adapt coordinates to this template.")
