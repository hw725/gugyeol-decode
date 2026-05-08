#!/usr/bin/env python3
"""
gugyeol-decode — Step 3: 매핑 테이블을 적용해 PDF 본문을 정규화

PDF를 다시 글리프 단위로 추출하면서, mapping.json에 정의된 PUA 글자를
표준 Unicode (옛한글 자모 결합 / 구결자 모자 등)로 치환한다.

사용법:
  python scripts/apply_mapping.py <PDF경로> <mapping.json> [--out <output.md>] [--mode value|modern|both]

--mode:
  value  : 표준 Unicode form 우선 (예: ᄒᆞ, 厓)
  modern : 현대 한글 form 우선 (예: 하, ㄱ)
  both   : "value(modern)" 형태로 둘 다 표기 (기본)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="매핑 테이블 적용 → 정규화 텍스트")
    parser.add_argument("pdf", type=Path, help="입력 PDF 경로")
    parser.add_argument("mapping", type=Path, help="mapping.json 경로")
    parser.add_argument("--out", type=Path, default=None,
                        help="출력 .md 경로 (기본: <pdf>.normalized.md)")
    parser.add_argument("--mode", choices=["value", "modern", "both"],
                        default="both", help="치환 방식")
    args = parser.parse_args()

    try:
        import fitz
    except ImportError:
        print("ERROR: PyMuPDF가 필요합니다. 설치: pip install pymupdf", file=sys.stderr)
        return 1

    if not args.pdf.exists():
        print(f"ERROR: PDF 없음: {args.pdf}", file=sys.stderr)
        return 1
    if not args.mapping.exists():
        print(f"ERROR: mapping 없음: {args.mapping}", file=sys.stderr)
        return 1

    mapping_data = json.loads(args.mapping.read_text(encoding="utf-8"))
    raw_mappings = mapping_data.get("mappings", {})

    # key 형식 "font|HEX" → (codepoint, font) 룩업
    lookup: dict[tuple[int, str], dict] = {}
    for key, val in raw_mappings.items():
        if "|" not in key:
            continue
        font, hex_str = key.rsplit("|", 1)
        try:
            cp = int(hex_str, 16)
        except ValueError:
            continue
        lookup[(cp, font)] = val

    out_path = args.out or args.pdf.with_suffix(".normalized.md")

    doc = fitz.open(args.pdf)
    output_lines: list[str] = []
    unmapped_warnings: list[str] = []

    for page_idx, page in enumerate(doc):
        text_dict = page.get_text("dict")
        output_lines.append(f"\n## Page {page_idx + 1}\n")
        for block in text_dict.get("blocks", []):
            if "lines" not in block:
                continue
            for line in block["lines"]:
                buf: list[str] = []
                for span in line["spans"]:
                    text = span.get("text", "")
                    font = span.get("font", "")
                    for ch in text:
                        cp = ord(ch)
                        if 0xE000 <= cp <= 0xF8FF:
                            entry = lookup.get((cp, font))
                            if entry is None:
                                buf.append(f"⟨U+{cp:04X}?⟩")
                                unmapped_warnings.append(
                                    f"page {page_idx + 1}: U+{cp:04X} font={font}")
                            else:
                                value = entry.get("value", "")
                                modern = entry.get("modern", "")
                                if args.mode == "value":
                                    buf.append(value or modern or f"⟨U+{cp:04X}⟩")
                                elif args.mode == "modern":
                                    buf.append(modern or value or f"⟨U+{cp:04X}⟩")
                                else:  # both
                                    if value and modern and value != modern:
                                        buf.append(f"{value}({modern})")
                                    else:
                                        buf.append(value or modern or f"⟨U+{cp:04X}⟩")
                        else:
                            buf.append(ch)
                output_lines.append("".join(buf))

    out_path.write_text("\n".join(output_lines), encoding="utf-8")
    print(f"저장: {out_path}")
    print(f"  매핑 적용 글자 수: {len(lookup)} 종류")
    print(f"  미매핑 (occurrence): {len(unmapped_warnings)}")
    if unmapped_warnings:
        print("  처음 5개 미매핑:")
        for w in unmapped_warnings[:5]:
            print(f"    {w}")
    doc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
