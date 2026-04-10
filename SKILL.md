---
name: commute-form-editor
description: >
  Edit and fill in Japanese commute route application forms (通勤経路申請書).
  Use this skill whenever the user wants to fill out, update, or edit a 通勤経路申請書 PDF,
  including entering route information, looking up train fares, placing a digital seal (印鑑),
  or making any changes to a commute application form. Also triggers when the user mentions
  通勤経路, 定期券申請, commute route form, or wants to update transit pass information
  on a PDF form.
---

# Commute Route Application Form Editor (通勤経路申請書)

Fill in and edit 通勤経路申請書 PDF forms with Japanese text, transit fares,
checkmarks, and digital seals. This skill handles the full workflow from
downloading the PDF to producing a filled, print-ready document.

## Overview

The workflow has these phases:

1. **Acquire the PDF** — download from Google Drive or locate on disk
2. **Analyze layout** — extract text positions, table grid, and checkbox locations
3. **Gather data** — look up current transit fares via web search
4. **Fill the form** — write text, check boxes, insert seal image
5. **Verify** — render a preview image and show the user

## Phase 1: Acquire the PDF

For Google Drive shared links, extract the file ID and download with curl:

```bash
# Extract ID from: https://drive.google.com/file/d/<ID>/view?usp=sharing
curl -L "https://drive.google.com/uc?export=download&id=<FILE_ID>" \
  -o "<output_path>.pdf"
```

Verify the download with `file <path>` — it should report "PDF document".

## Phase 2: Analyze PDF Layout

Use PyMuPDF (fitz) to understand the form's structure. Install if needed:
`pip install pymupdf`

### Extract text positions

```python
import fitz

doc = fitz.open(pdf_path)
page = doc[0]
blocks = page.get_text('dict')['blocks']
for b in blocks:
    if b['type'] == 0:
        for line in b['lines']:
            for span in line['spans']:
                # span['bbox'] gives (x0, y0, x1, y1)
                # span['text'] gives the character/text
                # span['size'] gives font size
```

Write positions to a file (use encoding='utf-8' to avoid cp932 errors on Windows).

### Extract table structure from drawings

The table grid is defined by line drawings, not form fields:

```python
drawings = page.get_drawings()
# Vertical lines (columns): items with same x for start and end points
# Horizontal lines (rows): items with same y for start and end points
```

Key measurements to extract:
- **Column boundaries** (vertical lines) — defines 使用交通機関, 出発駅, 到着駅, 片道運賃, 1ヶ月通勤定期代
- **Row boundaries** (horizontal lines) — defines header row, data rows, 合計 row
- **Checkbox positions** — ▢ characters in the text with their bounding boxes

### Generate a preview image for reference

```python
mat = fitz.Matrix(2, 2)  # 2x scale for readability
pix = page.get_pixmap(matrix=mat)
pix.save('preview.png')
```

## Phase 3: Gather Transit Fare Data

Use WebSearch and WebFetch to look up current fares:

- **One-way fares** (片道運賃): search `"[出発駅] [到着駅] 運賃"`
- **Monthly pass** (1ヶ月通勤定期代): search `"[出発駅] [到着駅] 定期券 料金"`
- ekitan.com is a reliable source for both private rail and JR fares
- Be aware of JR fare revisions — always verify the fare is current

Calculate totals for all segments.

## Phase 4: Fill the Form

This is the most critical phase. The form has no fillable fields — text must
be drawn directly onto the page at precise coordinates.

### Critical: Use TextWriter with page.write_text()

PyMuPDF's `insert_text()` does NOT render Japanese characters reliably on
existing PDF pages. Always use the TextWriter pattern:

```python
import platform, os

# Pick Japanese font for the current OS
def get_japanese_font_path():
    system = platform.system()
    if system == "Windows":
        candidates = ["C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/msgothic.ttc"]
    elif system == "Darwin":  # macOS
        candidates = ["/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"]
    else:  # Linux
        candidates = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
    for p in candidates:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("No Japanese font found")

font = fitz.Font(fontfile=get_japanese_font_path())
tw = fitz.TextWriter(page.rect)

tw.append(fitz.Point(x, y), text, font=font, fontsize=size)

# CORRECT — renders Japanese text properly:
page.write_text(writers=[tw])

# WRONG — text will not appear on existing pages:
# tw.write_text(page)        # <-- DO NOT USE THIS
# page.insert_text(...)      # <-- Japanese chars won't render
```

This is the single most important technical detail in this skill.
`page.write_text(writers=[tw])` is the only method that reliably renders
Japanese text on existing PDF pages. The other methods silently fail for
CJK characters.

### Center-align text in fields

```python
def center_text(tw, font, x_left, x_right, y, text, size=11):
    """Place text centered horizontally within a field."""
    text_w = font.text_length(text, fontsize=size)
    x = x_left + (x_right - x_left - text_w) / 2
    tw.append(fitz.Point(x, y), text, font=font, fontsize=size)
```

Use the column/field boundaries from Phase 2 as x_left and x_right.
The y coordinate is the text baseline (typically near the bottom of the
cell, e.g. cell_top + cell_height * 0.8).

### Add checkmarks to checkboxes

Find the ▢ character's bounding box from the text analysis, then insert
a ✓ character centered inside it:

```python
# box_rect is the ▢ bounding box (x0, y0, x1, y1)
check_size = 10
cw = font.text_length("✓", fontsize=check_size)
cx = box_x0 + (box_width - cw) / 2
cy = box_y1 - 1  # baseline near bottom of box
tw.append(fitz.Point(cx, cy), "✓", font=font, fontsize=check_size)
```

### Insert a seal image (印鑑)

Download the seal image (PNG) and place it over the 印 designation:

```python
# Find the 印 character position from text analysis
# Center a square rect around it
seal_size = 36  # points, adjust to match seal
seal_rect = fitz.Rect(
    center_x - seal_size/2, center_y - seal_size/2,
    center_x + seal_size/2, center_y + seal_size/2
)
page.insert_image(seal_rect, filename=seal_image_path)
```

### Font sizes

Use slightly larger than the template's base font for readability:
- Normal text (dates, name, postal code): 11pt
- Table cells: 10pt
- Long text (address): 9-10pt

### Standard form fields (通勤経路申請書)

A typical form has these fields — coordinates vary per template, so always
analyze first, but the general structure is:

| Field | Content |
|---|---|
| 通勤開始日 | 年月日 — when the route takes effect |
| 申請日 | 年月日 — submission date |
| 申請者住所 | Postal code (〒) + address (may span 2 lines) |
| 氏名 | Full name |
| 変更理由 | Checkbox: 引っ越し / 案件変更 / 案件先の最寄り駅変更 / その他 |
| 経路テーブル | 使用交通機関, 出発駅, 到着駅, 片道運賃, 1ヶ月通勤定期代 |
| 合計 | Sum of all monthly pass costs |

## Phase 5: Save and Verify

```python
doc.save(output_path)
doc.close()

# Generate high-res preview
doc2 = fitz.open(output_path)
pix = doc2[0].get_pixmap(matrix=fitz.Matrix(2, 2))
pix.save('preview.png')

# Zoom into specific areas for verification
pix_table = doc2[0].get_pixmap(
    matrix=fitz.Matrix(3, 3),
    clip=fitz.Rect(70, 480, 525, 660)
)
pix_table.save('preview_table.png')
```

Always show the user:
1. A full-page preview
2. Zoomed views of the table, checkmarks, and seal placement

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| Japanese text not appearing | Used `insert_text()` or `tw.write_text(page)` | Use `page.write_text(writers=[tw])` |
| File save "Permission denied" | Previous PDF open in viewer | Save with a different filename |
| Text misaligned | Wrong baseline y coordinate | Baseline y ≈ cell_bottom - 2pt |
| Checkmark looks wrong | Drew lines instead of text | Use "✓" character via TextWriter |
| cp932 encoding error | Windows console can't print Japanese | Write to file with encoding='utf-8' |

## Helper Script

A reusable Python script is available at `scripts/fill_commute_form.py`.
Read it for the complete implementation pattern. Adapt coordinates to
the specific form template being edited.
