#!/usr/bin/env python3
"""
gugyeol-decode 1-step 통합 명령 — PDF → 깨끗한 markdown 텍스트

내부적으로 extract_pua.py + apply_mapping.py를 자동 연속 실행.
PUA 자동 매핑이 100%면 한 번에 끝나고, 일부 미매핑 시 PNG와 함께 안내.

사용:
  python scripts/decode.py <PDF경로>                    # 기본: <PDF>.normalized.md
  python scripts/decode.py <PDF> --out output.md        # 출력 경로 지정
  python scripts/decode.py <PDF> --mode value           # 표준 Unicode form (학술)
  python scripts/decode.py <PDF> --mode modern          # 현대 한글 form
  python scripts/decode.py <PDF> --mode both            # 둘 다 (기본)
  python scripts/decode.py <PDF> --keep-intermediate    # 중간 파일 보존
  python scripts/decode.py <PDF> --no-hapja             # 합자 구결 스캔 끄기
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def colored(text: str, color: str) -> str:
    codes = {"green": "32", "yellow": "33", "red": "31", "cyan": "36", "bold": "1"}
    if not sys.stdout.isatty():
        return text
    return f"\033[{codes.get(color, '0')}m{text}\033[0m"


def run(cmd: list[str]) -> int:
    """Wrapper: stdout/stderr 그대로 흐르게."""
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PDF → 깨끗한 markdown (PUA 옛한글·구결자 자동 복원)")
    parser.add_argument("pdf", type=Path, help="입력 PDF 경로")
    parser.add_argument("--out", type=Path, default=None,
                        help="출력 markdown 경로 (기본: <PDF>.normalized.md)")
    parser.add_argument("--mode", choices=["value", "modern", "both"],
                        default="both",
                        help="치환 형식 (기본: both = '표준(현대)' 결합)")
    parser.add_argument("--no-hapja", action="store_true",
                        help="합자 구결자 스캔 비활성화")
    parser.add_argument("--keep-intermediate", action="store_true",
                        help="중간 파일(_pua/ 디렉터리) 보존")
    args = parser.parse_args()

    pdf = args.pdf.resolve()
    if not pdf.exists():
        print(colored(f"ERROR: PDF not found: {pdf}", "red"), file=sys.stderr)
        return 1

    out = args.out or pdf.with_suffix(".normalized.md")
    pua_dir = pdf.parent / f"_pua_{pdf.stem}"

    print(colored(f"\n[1/2] PUA 글자 추출 + 자동 매핑 ({pdf.name})", "cyan"))
    extract_cmd = [
        sys.executable, str(ROOT / "scripts" / "extract_pua.py"),
        str(pdf), "--out", str(pua_dir),
    ]
    if not args.no_hapja:
        extract_cmd.append("--scan-hapja")
    rc = run(extract_cmd)
    if rc != 0:
        print(colored(f"\nextract_pua.py 실패 (exit {rc})", "red"), file=sys.stderr)
        return rc

    skeleton = pua_dir / "mapping_skeleton.json"
    mapping = pua_dir / "mapping.json"
    if not skeleton.exists():
        print(colored(f"\nmapping_skeleton.json 미생성. PUA 글자가 없는 PDF로 추정.",
                      "yellow"))
        # PUA 없어도 본문은 추출 가능 — 빈 mapping으로 진행
        mapping.write_text('{"mappings":{}}', encoding="utf-8")
    else:
        # skeleton을 mapping으로 그대로 사용 (자동 매핑 결과 신뢰)
        if not mapping.exists():
            shutil.copy(skeleton, mapping)

    print(colored(f"\n[2/2] PDF 전체 텍스트 추출 + PUA 치환", "cyan"))
    apply_cmd = [
        sys.executable, str(ROOT / "scripts" / "apply_mapping.py"),
        str(pdf), str(mapping),
        "--out", str(out),
        "--mode", args.mode,
    ]
    rc = run(apply_cmd)
    if rc != 0:
        print(colored(f"\napply_mapping.py 실패 (exit {rc})", "red"), file=sys.stderr)
        return rc

    print(colored(f"\n✓ 완료: {out}", "green"))

    if not args.keep_intermediate:
        try:
            shutil.rmtree(pua_dir)
            print(colored(f"  중간 파일 삭제: {pua_dir}", "cyan"))
        except OSError:
            pass
    else:
        print(colored(f"  중간 파일 보존: {pua_dir}/", "cyan"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
