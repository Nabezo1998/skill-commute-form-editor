# commute-form-editor

Claude Code skill for filling Japanese commute route application forms (通勤経路申請書).

## Features

- Download PDFs from Google Drive
- Analyze PDF layout (text positions, table grid, checkboxes)
- Write Japanese text with center alignment
- Add checkmarks to checkboxes
- Insert digital seal images (印鑑)
- Look up current transit fares automatically
- Cross-platform: Windows / macOS / Linux

## Setup

```bash
pip install pymupdf
```

## Usage

Install as a Claude Code skill by copying to `~/.claude/skills/commute-form-editor/`.

Then ask Claude:
> 「通勤経路申請書を記入して」

## Structure

```
commute-form-editor/
├── SKILL.md                        # Skill instructions
├── scripts/
│   └── fill_commute_form.py        # Reusable Python helper
└── README.md
```
