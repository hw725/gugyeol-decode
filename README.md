# gugyeol-decode

> 한국 古典·국어학 PDF에서 깨진 글자(구결자·옛한글)를 자동 복원하는 Python CLI 도구. Claude Code 스킬로도 사용 가능.

**처음 사용하시나요? → [GETTING_STARTED.md](GETTING_STARTED.md) 부터 읽어주세요**

빠른 시작:
```bash
git clone <repo>
cd gugyeol-decode
pip install pymupdf
python setup.py                            # 1회 setup (5-10분)
python scripts/decode.py <PDF경로>           # PDF → 깨끗한 markdown
```

## 문제

한국 학술 PDF는 **옛한글**(ᄒᆞ나니라의 ᄒᆞ, ㅿ 반치음, ㅸ 순경음 비읍 등)과 **구결자**(口訣字 — 厓→ㄱ, 隱→ㄴ 같은 漢字 약식 토 표지)를 표준 Unicode 부호점이 없어 폰트의 PUA 영역(U+E000-F8FF)에 임의 매핑한다.

`pdfplumber`/`pdftotext` 등 일반 도구는 이들을 `(cid:N)` 또는 빈칸으로 떨어뜨려서:

- 위키·DB·논문에 옮길 때 원전이 손실됨
- 통계 분석 시 실험군/대조군 매칭 오류 가능
- 인용 시 사실상 위변조 위험

## 해결

본 스킬은 다음 워크플로를 자동화한다:

1. **추출**: `PyMuPDF`로 PDF의 모든 PUA 글자를 (codepoint, font, 위치, 컨텍스트)로 인덱싱
2. **렌더링**: 각 (codepoint, font) 조합당 첫 등장 위치를 5배 확대 PNG로 저장
3. **시각 판독**: Claude Code의 멀티모달 vision으로 글자별 시각 식별 (사용자 검토 가능)
4. **분류**: 폰트 단서(`TT70xx` → 옛한글, `*명조` → 구결자)로 1차 분류
5. **매핑 테이블**: `mapping.json` 작성 (PUA → 표준 Unicode + 현대 한글 + 메모)
6. **본문 정규화**: 매핑을 PDF 전체 본문에 적용해 깨끗한 markdown 산출

## 설치

```bash
# 1. 의존성
pip install pymupdf

# 2. 스킬 디렉터리 (Claude Code 자동 감지)
git clone <repo> ~/.claude/skills/gugyeol-decode

# 3. (선택) 한글 옛한글 표시용 폰트
# https://hangeul.naver.com/font 에서 함초롬 폰트 다운로드
```

## 사용

### 0. 1회 setup: 표준 매핑 다운로드 (필수)

```bash
# 1. hypua 옛한글 PUA → IPF Unicode jamo (5660건, public domain)
#    크레딧: kiwiyou/hypua (Unlicense)
curl -L "https://raw.githubusercontent.com/kiwiyou/hypua/master/table" \
  -o reference/hypua_table.csv

# 2. AKS 한국학중앙연구원 표준 (구결자 + 옛한글 카테고리)
python scripts/fetch_aks_gukyul.py
python scripts/fetch_aks_oldhan.py

# 3. (선택) Unihan K source 한자 → 합자 구결자 후보 풀
python scripts/fetch_unihan_korean.py
```

이들 캐시가 **시각 판독을 거의 대체**:
- 옛한글 PUA → hypua 100% 자동 → IPF Unicode jamo 결합형
- 구결자 PUA → AKS 자동 → 음가
- 합자 구결자(표준 Unicode CJK) → Unihan K source 후보 풀에서 검증 후 hapja_kugyeol.json에 등록

자세한 라이선스·출처는 `ATTRIBUTION.md` 참조.

### 자연어 트리거

Claude Code 세션에서 다음과 같이 요청하면 스킬이 활성화된다:

- "이 논문 PDF에서 옛한글이 깨져 나와 — 복원해줘"
- "(cid:6) 이런 게 잔뜩 있는데 PUA 풀어줘"
- "구결자 식별해서 정규화 테이블 만들어줘"
- "한국 고전 PDF 추출 결과가 이상해"

### CLI 직접 사용

```bash
# Step 1: PUA 글자 추출 + PNG 렌더링
python scripts/extract_pua.py path/to/paper.pdf

# 출력:
# path/to/_pua/U<HEX>_p<페이지>_<폰트>.png  ← 시각 판독용
# path/to/_pua/_contexts.txt                 ← 컨텍스트 정보
# path/to/_pua/mapping_skeleton.json         ← 채울 템플릿

# Step 2: PNG를 보면서 mapping_skeleton.json을 mapping.json으로 채워넣기
# (Claude Code 세션에서 Read 툴로 PNG 읽고, type/value/modern 입력)

# Step 3: 매핑 적용 → 깨끗한 markdown
python scripts/apply_mapping.py path/to/paper.pdf path/to/_pua/mapping.json \
    --out path/to/paper_normalized.md \
    --mode both
```

## 매핑 테이블 형식

```json
{
  "font_aliases": {
    "*¸íÁ¶": "*명조",
    "TT7064o00": "한양신명조"
  },
  "mappings": {
    "TT7064o00|F537": {
      "type": "old_hangul",
      "value": "ᄒᆞ",
      "modern": "하",
      "note": "verb stem 하-, 가장 빈번"
    },
    "*¸íÁ¶|F6D0": {
      "type": "kugyeol",
      "value": "<unknown>",
      "modern": "의",
      "note": "句讀解法 助辭訓釋 中#2 '의(?)' 마크"
    }
  },
  "verified_by": "researcher@example.com",
  "verified_at": "2026-05-09",
  "pdf": "최식2011_漢文讀法의韓國的特殊性.pdf"
}
```

`type`:
- `old_hangul` — 아래아·반치음·순경음 등 옛한글
- `kugyeol` — 漢字 약식 토 표지 (구결자)
- `other` — 위 둘이 아닌 PUA (특수 부호 등)
- `unknown` — 시각 판독 불가

`value`: 표준 Unicode form (가능하면 Hangul Jamo 결합형 또는 漢字)
`modern`: 현대 한글 또는 음가
`note`: 컨텍스트·단서·미식별 사유

## 폰트별 1차 분류 휴리스틱

| 폰트 패턴 | 추정 종류 |
|----------|----------|
| `TT7064`, `TT7019`, `TT7017` 등 (한양정보통신 계열) | **옛한글** |
| `*명조`, `*신명조`, `Hancom 명조` | **구결자** (특히 漢文 인용 컨텍스트) |
| `함초롬바탕`, `함초롬돋움` | 옛한글 표시용 (PUA 거의 없음, 표준 Unicode 사용) |
| `HCI-*`, `Times`, `Arial` | 무시 (라틴/숫자) |

폰트명 mojibake (`*ÇÑ¾ç½Å¸íÁ¶`)는 `font_alias.py`로 복원 가능:
```bash
python scripts/font_alias.py "*ÇÑ¾ç½Å¸íÁ¶"
# → *한양신명조 (family: 한양신명조)
```

## 구조

```
gugyeol-decode/
  SKILL.md                       # Claude Code 스킬 정의
  README.md                      # 이 파일
  ATTRIBUTION.md                 # 외부 라이브러리·데이터 출처 명시
  reference/
    구결자.md                     # 한국 古典 구결자 표준 form 표
    옛한글.md                     # 옛한글 자모·결합·Unicode 매핑
    hypua_table.csv              # ⭐ 한양 PUA → IPF Unicode (kiwiyou/hypua, Unlicense, 5660건)
    aks_gukyul_pua.json          # AKS 구결자 표준 매핑 (fetch 후 생성, 255건)
    aks_oldhan_pua.json          # AKS 옛한글 카테고리 매핑 (fetch 후 생성, 5299건)
    hapja_kugyeol.json           # 검증된 합자 구결자 (兯 등, incremental 확장)
    unihan_korean.json           # Unihan K2~K6 한국 source 한자 후보 풀 (fetch 후 생성, 10,919건)
    verified_mappings.json       # 작업 누적용 검증된 매핑 캐시
  scripts/
    fetch_aks_gukyul.py          # Setup: AKS 구결자 매핑 다운로드 (1회)
    fetch_aks_oldhan.py          # Setup: AKS 옛한글 매핑 다운로드 (1회)
    fetch_unihan_korean.py       # Setup: Unihan K source 한자 다운로드 (1회, 합자 후보)
    extract_pua.py               # Step 1: PDF → PUA 추출 + PNG + 자동 룩업 + 합자 스캔
    apply_mapping.py             # Step 3: 매핑 적용 → 정규화 markdown
    font_alias.py                # 폰트명 mojibake 복원 유틸 (cp949 → UTF-8)
```

## 한계

- **OCR 기반 PDF**: 텍스트 레이어가 OCR 결과면 PUA 글자가 부정확하게 인식되어 있을 수 있음. 원본 이미지 OCR이 필요하면 별도 도구 사용 (Naver Clova OCR, Tesseract+옛한글 모델).
- **폰트 임베딩 부재**: 일부 PDF는 PUA 글자에 폰트 정보가 없거나 mojibake 폰트명만 남는다. 폰트별 클러스터링 불가, 시각 판독에만 의존.
- **희귀 구결자**: 학파별·시기별 약식 form 차이로 시각만으로 식별 불가능한 경우가 있다. `unknown`으로 두고 후속 검토.
- **동일 codepoint 다른 글자**: 폰트 서브셋 PDF에서 가끔 같은 PUA 부호점에 다른 글자가 매핑되어 충돌. 폰트별 mapping이 본질적으로 필요한 이유.
- **합자 구결자(合字)**: 兯(U+516F = 한, 隹+隱) 같이 두 글자가 합쳐진 합자 구결은 표준 Unicode CJK 영역에 있고 PUA에 없음. **본 스킬은 PUA만 스캔**하므로 합자 구결은 자동 탐지되지 않는다. 한양 PUA의 한계. 합자 구결이 본문에 등장하면 일반 漢字로 추출되어 사용자가 직접 식별·매핑 필요. `reference/구결자.md`의 합자 섹션 참조.

## 라이선스

본 스킬 자체: **MIT** — 자유롭게 사용·수정·배포 가능.

본 스킬이 의존하는 외부 자료:
- **hypua (kiwiyou/hypua)**: Unlicense (public domain). https://github.com/kiwiyou/hypua
- **AKS 한국학중앙연구원 한국역사정보통합시스템**: 공공누리(KOGL) 학술·교육·비영리 자유 이용
- **Unihan database**: Unicode License (with attribution)

자세한 출처·인용 형식은 [ATTRIBUTION.md](ATTRIBUTION.md) 참조. 학술 작업에 사용 시 인용 권장.

한국 古典 디지털화 커뮤니티에서 `verified_mappings.json`과 `hapja_kugyeol.json` 캐시를 공유하면 더 효율적이다.

## 기여

- 새로운 폰트의 PUA 매핑을 식별하면 `examples/` 디렉터리에 추가 PR
- 구결자 reference 표 보완 (학파별 차이, 새로운 약식 form)
- PDF 라이브러리 개선 (스캔 PDF 처리 등)

## 참고

- 한국구결학회 — `kugyol.or.kr`
- 國立國語院 한국어 어문 규범 — 옛한글 표기
- 한양정보통신 옛한글 PUA 표준 (HanyangPUA)
- Unicode Hangul Jamo (U+1100-U+11FF), Extended-A (U+A960-U+A97F), Extended-B (U+D7B0-U+D7FF)
