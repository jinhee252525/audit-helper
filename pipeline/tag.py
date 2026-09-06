"""재사용 태깅 모듈 — 원문(텍스트/마크다운) → finding.schema.json 레코드.

절차(SKILL: audit-tagging):
1. parse_document(text, meta): 규칙기반 분해 — audit_org·audit_type 추출, 항목별 분해,
   source_excerpt=원문 그대로, disposition=괄호∩codebook(없으면 null),
   legal_basis=「」/｢｣ 인용(law_type 판정).
2. assign_codes(text): pluggable 의미분류 — 기본은 규칙(키워드)로 codebook 코드 배정.
   애매하면 work_type='19', sector=None. (LLM 훅은 env TAG_LLM 로 후속 확장)
3. build_record(...): 필수필드 조립. id 안정적, added_at 고정, pii.mask 적용.
4. merge_incremental(records): state.json(seen_ids·seen_hashes) 멱등 병합.

원칙: 근거 없는 값 생성 금지. 코드북 밖 값 금지. 위법 단정 금지.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
from datetime import date
from pathlib import Path

from pipeline.pii import mask

ROOT = Path(__file__).resolve().parent.parent
CODEBOOK = json.loads((ROOT / "data" / "codebook.json").read_text(encoding="utf-8"))
FINDINGS = ROOT / "data" / "findings.json"
STATE = ROOT / "data" / "state.json"
ADDED_AT = "2026-09-05"

DISPOSITIONS = CODEBOOK["disposition_처분"]            # 폐쇄형 처분 목록
AUDIT_TYPES = CODEBOOK["audit_type_감사종류"]           # 폐쇄형 감사종류
WORK_TYPES = CODEBOOK["work_type_관련기능"]             # 19종
SECTORS = CODEBOOK["sector_발생분야"]                   # 28종

# ── 법령 인용 추출 (「」『』｢｣ 모든 각괄호) ────────────────────────────────
_BR = r"[「『｢]([^」』｣]{2,50}?)[」』｣]"
LAW_TAIL = "(?:법|법률|시행령|시행규칙|령|규칙|규정|조례|지침|기준|훈령|예규|고시|요령|준칙|규약)"
LAW_RE = re.compile(_BR)
ART_RE = re.compile(r"제\s*\d+\s*조(?:\s*의\s*\d+)?")


def _law_type(name: str) -> str:
    if "조례" in name or "규칙" in name and "자치" in name:
        return "자치법규"
    if "조례" in name:
        return "자치법규"
    if any(k in name for k in ["규정", "지침", "훈령", "예규", "고시", "요령", "준칙", "기준", "규칙", "규약"]):
        return "행정규칙"
    return "법령"


# 원문 PDF OCR 오탈자 정정(법령명 등 파생값에만 적용 — source_excerpt는 verbatim 유지)
_OCR_FIX = {"그론자": "근로자"}


def _fix_ocr(s: str) -> str:
    for a, b in _OCR_FIX.items():
        s = s.replace(a, b)
    return s


def extract_laws(text: str) -> list[dict]:
    """각괄호 인용 법령 추출. 닫는 괄호 뒤 제N조(들)을 article 로 결합."""
    laws: list[dict] = []
    seen: set[str] = set()
    for m in LAW_RE.finditer(text or ""):
        name = _fix_ocr(re.sub(r"\s+", " ", m.group(1)).strip())  # 공백정리 + OCR오탈자 정정
        # 각괄호 안이 법령명 꼴이 아니면 제외(예: 「검토 결과」 같은 라벨)
        if not re.search(LAW_TAIL + r"$", name):
            continue
        if name in seen:
            continue
        seen.add(name)
        tail = text[m.end():m.end() + 40]
        arts = ART_RE.findall(tail)
        article = ", ".join(a.replace(" ", "") for a in arts[:3]) if arts else None
        laws.append({"law": name, "article": article, "law_type": _law_type(name), "field": None})
    return laws


def _disposition_from(bracket_text: str) -> str | None:
    """괄호 내 토큰 중 codebook disposition 에 있는 것만. 텍스트 등장 순서 우선."""
    if not bracket_text:
        return None
    hits = [(bracket_text.find(d), d) for d in DISPOSITIONS if d in bracket_text]
    if not hits:
        return None
    hits.sort()
    return hits[0][1]


def _audit_type_from(text: str) -> str | None:
    """문서 상단에서 codebook 감사종류 정확 일치만 채움(없으면 None)."""
    head = text[:1500]
    for at in AUDIT_TYPES:
        if at in head:
            return at
    return None


# ── 감사원 보고서 표지 출처 추출(source_title·posted_date·audit_type) ─────────
# 표지는 세로 레이아웃이라 "감사보고서"·"감사원"·발간일이 낱글자로 흩어진다.
# 낱글자 노이즈를 걷어내고 제목(대시 사이 텍스트)·발간일·감사종류만 복원한다.
_COVER_NOISE = {
    "감사", "보", "고서", "감사보고서", "보고서", "감", "사원", "원", "사", "감사원", "감 사원",
}
_COVER_CUT_MARKERS = [
    "# 목", "목\t차", "목 차", "목차", "표 목차", "일러두기", "제1절", "제 1 절",
    "\n<table", "\n※", "# Ⅰ", "## Ⅰ", "### Ⅰ", "# I.", "## I.",
]
_DATE_COMBINED = re.compile(r"(20\d\d)\.\s*(\d{1,2})\.")
_YEAR_ONLY = re.compile(r"^(20\d\d)\.$")
_MONTH_ONLY = re.compile(r"^(\d{1,2})\.$")


def _cover_region(text: str) -> str:
    """표지 영역만 잘라낸다(목차·본문 표·장 제목 이전, 최대 1500자)."""
    end = len(text)
    for mk in _COVER_CUT_MARKERS:
        p = text.find(mk)
        if p != -1:
            end = min(end, p)
    return text[: min(end, 1500)]


def _cover_source_title(cover: str) -> str | None:
    """표지에서 제목 복원. 대시 사이 텍스트 우선, 낱글자 노이즈 제거."""
    frags: list[str] = []
    for raw in cover.splitlines():
        s = re.sub(r"^#+", "", raw).strip()          # 마크다운 헤딩 마커 제거
        s = re.sub(r"^[-–—\s]+", "", s).strip()       # 앞 대시/공백
        s = re.sub(r"[-–—\s]+$", "", s).strip()       # 뒤 대시/공백
        if not s or s.startswith("![") or s.startswith("|") or s.startswith("※"):
            continue
        if re.search(r"</?[a-zA-Z]", s):               # HTML 표 잔재(<table><tr><td> 등)
            continue
        if set(s) <= set("-–—| \t"):                  # 대시/표 구분선만
            continue
        if "···" in s or "…" in s or "ㆍㆍㆍ" in s:      # 목차 점선
            continue
        if s in _COVER_NOISE:                          # 낱글자 노이즈
            continue
        if _YEAR_ONLY.match(s) or _MONTH_ONLY.match(s) or _DATE_COMBINED.search(s):
            continue                                   # 발간일 조각
        frags.append(s)
    title = re.sub(r"\s+", " ", " ".join(frags)).strip()
    title = re.sub(r"\s+[-–—]\s+", " ", title).strip()  # 공백에 둘러싸인 구분 대시만 정리(토큰 내 하이픈 유지)
    title = re.sub(r"\s+", " ", title).strip()
    return title or None


def _cover_posted_date(cover: str) -> str | None:
    """표지 발간표기 'YYYY. M.' → 'YYYY-MM-01'. 조각나 있으면 연·월 조립. 없으면 None."""
    m = _DATE_COMBINED.search(cover)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-01"
    year: str | None = None
    for raw in cover.splitlines():
        s = re.sub(r"^#+", "", raw).strip()
        my = _YEAR_ONLY.match(s)
        if my:
            year = my.group(1)
            continue
        mm = _MONTH_ONLY.match(s)
        if year and mm:
            return f"{year}-{int(mm.group(1)):02d}-01"
    return None


def _cover_audit_type(cover: str) -> str | None:
    """표지 감사종류. 첫 파이프표 셀(예 '| 기관정기감사 |') 우선, 없으면 codebook 스캔."""
    m = re.search(r"^\|\s*([^|]+?)\s*\|", cover, re.M)
    if m:
        cand = m.group(1).strip()
        if 2 <= len(cand) <= 12 and cand.endswith(("감사", "검사")):
            return cand
    for at in sorted(AUDIT_TYPES, key=len, reverse=True):
        if at in cover:
            return at
    return None


def parse_cover_meta(text: str) -> dict:
    """감사원 보고서 표지 → {source_title, posted_date, audit_type}. 없으면 각 None."""
    cover = _cover_region(text)
    return {
        "source_title": _cover_source_title(cover),
        "posted_date": _cover_posted_date(cover),
        "audit_type": _cover_audit_type(cover),
    }


# ── 의미분류(pluggable): 기본 규칙 ──────────────────────────────────────────
# work_type(관련기능) 키워드 → 코드. 우선순위 순서대로 첫 매치.
_WORK_RULES: list[tuple[str, list[str]]] = [
    ("02", ["계약", "수의계약", "입찰", "발주", "낙찰", "용역", "위촉계약"]),
    # 주의: 바 "공사"는 '○○공사'(회사명) 오탐 → 시공/설계/감리 등 건설 맥락 키워드만.
    ("04", ["시공", "설계", "감리", "준공", "건설사업관리", "공사감독", "공사비", "착공"]),
    ("11", ["인사", "승진", "채용", "임용", "전보", "징계", "특별승진", "복무", "겸직", "근태",
            "육아휴직", "병가", "공가", "청원휴가", "연차", "시간외근무", "초과근무", "휴가",
            "서류전형", "경력평정", "당연퇴직", "출근", "근무지"]),
    ("17", ["예산", "회계", "결산", "정산", "지출", "집행", "보수", "급여", "수당", "여비", "출납"]),
    ("15", ["보조금", "보조사업", "지원금", "포상", "보상"]),
    ("06", ["부과", "징수", "환급", "부담금", "과세", "세금"]),
    ("10", ["인가", "허가", "승인", "특허", "면허"]),
    ("05", ["신고", "등록", "등재", "발급", "교부"]),
    ("08", ["심사", "심의", "평가위원", "선정위원"]),
    ("14", ["점검", "단속", "지도", "감독", "조사"]),
    ("13", ["검사", "검수", "행정조사"]),
    ("18", ["위탁수수료", "위탁 시행", "민간위탁", "위·수탁", "위탁", "위임", "대행"]),
    ("09", ["대부", "보증", "여신", "수신", "융자"]),
    ("01", ["검정", "감정", "인증", "지정"]),
    ("03", ["계획", "배정", "조정"]),
]
# finding_type 세부(a/b/c/d) 힌트 — work_type 별
_FT_HINT: dict[str, list[tuple[str, str]]] = {
    "02": [("a", ["공사계약"]), ("b", ["매매", "매각", "처분"]), ("c", ["물품"]), ("d", ["용역", "위촉"])],
    "04": [("a", ["감리", "준공"]), ("b", ["설계"]), ("c", ["시공", "감독"])],
    "11": [("a", ["교육", "훈련"]), ("b", ["상훈", "징계"]), ("c", ["승진", "전보"]), ("d", ["채용", "임용"])],
    "10": [("a", ["승인"]), ("b", ["인가", "허가"]), ("c", ["특허"])],
    "05": [("a", ["등록", "등재"]), ("b", ["발급", "교부"]), ("c", ["신고"])],
    "14": [("a", ["단속"]), ("b", ["수사", "조사"]), ("c", ["점검"]), ("d", ["지도", "감독"])],
}
# sector(발생분야) 키워드 → 코드. 분야 근거가 '강하게' 드러날 때만 배정(억지 금지→없으면 None).
# 느슨한 단어(교육·근로·농업 등 단일어)는 오배정 위험이 커서 제외한다.
_SECTOR_RULES: list[tuple[str, list[str]]] = [
    ("14", ["정보시스템", "정보통신", "전산시스템", "소프트웨어", "개인정보", "시스템 구축", "정보화"]),
    ("25", ["토목", "산업단지", "택지", "단지 조성", "도로 건설", "철도부지"]),
    ("26", ["건축물", "주택", "아파트", "공동주택"]),
    ("27", ["국유재산", "국유지", "농지전용", "용지 매입", "토지 보상"]),
    ("18", ["폐기물", "대기오염", "수질오염", "환경영향평가"]),
    ("15", ["의약품", "식품위생", "의료기관", "감염병"]),
    ("16", ["요양급여", "장애인", "기초생활", "돌봄"]),
    ("10", ["관광단지", "관광지", "문화재"]),
]


def _rule_assign(text: str) -> dict:
    t = text or ""
    work = "19"
    for code, kws in _WORK_RULES:
        if any(k in t for k in kws):
            work = code
            break
    ft = "z"
    for sub_code, kws in _FT_HINT.get(work, []):
        if any(k in t for k in kws):
            ft = sub_code
            break
    sector = None
    for code, kws in _SECTOR_RULES:
        if any(k in t for k in kws):
            sector = code
            break
    return {"work_type": work, "sector": sector, "finding_type": work + ft}


def assign_codes(text: str) -> dict:
    """pluggable 의미분류. env TAG_LLM 설정 시 LLM 훅 자리(후속). 기본은 규칙."""
    if os.environ.get("TAG_LLM"):
        # 후속: LLM 어댑터 연결 지점. 현재는 규칙으로 폴백.
        pass
    return _rule_assign(text)


# ── 원문 분해(parse) ────────────────────────────────────────────────────────
def _alio_block_item(block: str) -> dict:
    head = block.split("\n", 1)[0]
    parens = re.findall(r"[（(]([^（()）]*)[)）]", head)
    disp = None
    for pt in reversed(parens):
        disp = _disposition_from(pt)
        if disp:
            break
    return {"source_excerpt": block, "disposition": disp, "legal_basis": extract_laws(block)}


def _parse_alio(text: str, meta: dict) -> list[dict]:
    """ALIO rtitle 분해. '○' 항목형과 '1. 2.' 번호형을 모두 지원.
    항목이 없으면(단일 제목형) 전체를 1건으로."""
    items: list[dict] = []
    # 1) ○ 항목형
    if re.search(r"^\s*○", text, re.M):
        for b in re.split(r"(?=^\s*○)", text, flags=re.M):
            b = b.strip()
            if b.startswith("○"):
                items.append(_alio_block_item(b))
        if items:
            return items
    # 2) 번호형 '1. ... 2. ...' (첫 헤더 라인은 지적이 아니면 스킵)
    numbered = list(re.finditer(r"(?m)^\s*(\d{1,2})\.\s+.+", text))
    if len(numbered) >= 2:
        spans = [m.start() for m in numbered] + [len(text)]
        for i in range(len(numbered)):
            block = text[spans[i]:spans[i + 1]].strip()
            if len(block) >= 5:
                items.append(_alio_block_item(block))
        if items:
            return items
    # 3) 단일 제목형 — 전체 rtitle 1건
    t = text.strip()
    if t:
        items.append(_alio_block_item(t))
    return items


def _parse_report(text: str, meta: dict) -> list[dict]:
    """감사원 감사보고서(markdown): 목차 '(N) 제목[처분]' 로 분해."""
    # 목차 라인: (1) 제목[통보(시정완료)] ······ 7
    toc_re = re.compile(
        r"^\s*\((\d+)\)\s*(.+?)\s*([\[(][^\n]*?[\])])\s*[·.…ㆍ]{3,}\s*\d+\s*$",
        re.M,
    )
    items: list[dict] = []
    for m in toc_re.finditer(text):
        title = m.group(2).strip()
        bracket = m.group(3)
        disp = _disposition_from(bracket)
        excerpt = _find_body_excerpt(text, title, m.end())
        org = _find_org_name(text, title, m.end())
        items.append({
            "source_excerpt": excerpt,
            "title": title,
            "disposition": disp,
            "legal_basis": extract_laws(excerpt),
            "org_name": org,
        })
    return items


_ORG_CELL_RE = re.compile(r"소관기관</td><td[^>]*>(.*?)</td>", re.S)


def _find_org_name(text: str, title: str, toc_end: int) -> str | None:
    """지적 상세표의 '소관기관' 셀에서 피감기관명 추출(지적별로 다름)."""
    detail = text.find(f'>{title}</td>', toc_end)
    if detail == -1:
        return None
    m = _ORG_CELL_RE.search(text, detail, detail + 800)
    if not m:
        return None
    name = re.sub(r"<[^>]+>", " ", m.group(1))
    # ①A ②B 처럼 복수 기관이면 " , " 로 분리(붙여읽기 방지). 단일이면 그대로.
    name = re.sub(r"[①②③④⑤⑥⑦⑧⑨⑩]", "|", name)
    parts = [re.sub(r"\s+", " ", p).strip() for p in name.split("|")]
    # 가드: 기관명 아닌 조각 제거(빈값·'등'·주석/표 잔재·조치/내용 등 키워드·너무 짧음)
    _BADPART = re.compile(r"(조치기관|조치할|내용|업무개요|사건개요|제\s*목|^등$|^및$)")
    parts = [p for p in parts if p and len(p) >= 2 and not _BADPART.search(p)]
    parts = [p.rstrip(" 등") for p in parts]              # 꼬리 '등' 정리
    parts = [p for p in dict.fromkeys(parts) if p]        # 중복 제거·순서 유지
    return ", ".join(parts) or None


def org_type_of(name: str | None) -> str:
    """기관명 → org_type 휴리스틱(코드북 org_type 폐쇄형)."""
    if not name:
        return "기타"
    n = name.replace(" ", "")
    if "교육청" in n:
        return "교육"
    if re.search(r"(특별시|광역시|특별자치시|특별자치도)$", n) or n.endswith("도") and len(n) <= 4:
        return "광역"
    if re.search(r"[시군구]$", n) and "청" not in n:
        return "기초"
    if re.search(r"(부|처|청|위원회|국세청|관세청)$", n) and not any(
        k in n for k in ["공사", "공단", "진흥원", "재단", "본부", "협회", "연구원", "기술원", "유통원"]):
        return "중앙"
    return "공공기관"


_PROBLEM_RE = re.compile(
    r"(그런데|그러나|하는데도|하여야 하는데|부적정|부당|위반|아니하|하지 않|미흡|소홀|"
    r"초래|우려|누락|과다|과소|없이|않은 채|않았)"
)


def _find_body_excerpt(text: str, title: str, toc_end: int) -> str:
    """본문에서 title 상세부의 '지적 핵심 문장'을 verbatim 발췌. 없으면 title."""
    # 1) 총괄 '(title) ...' 원형 블록(가장 깨끗)
    key = f"({title})"
    idx = text.find(key, toc_end)
    if idx != -1:
        return _trim_sentence(text[idx: idx + 500])
    # 2) 상세표 '제 목 | title' 뒤 서술부에서 지적 문장 탐색
    detail = text.find(f'>{title}</td>', toc_end)
    if detail == -1:
        detail = text.find(title, toc_end)
    if detail != -1:
        region = text[detail: detail + 4000]
        # 표 마크업이 있으면 표 종료 이후로 이동
        after_table = region.find("</table>")
        narrative = region[after_table + len("</table>"):] if after_table != -1 else region
        # 지적 핵심 문장: 문제어 등장 지점부터 종결까지
        pm = _PROBLEM_RE.search(narrative)
        if pm:
            # 문장 시작(직전 문장부호/줄 이후)부터
            start = max(narrative.rfind("\n\n", 0, pm.start()),
                        narrative.rfind(". ", 0, pm.start()))
            start = start + 1 if start > 0 else pm.start()
            seg = narrative[start: start + 500]
            seg = _trim_sentence(seg)
            if len(seg) > 40 and "<t" not in seg[:15]:
                return seg
        # 폴백: 표 이후 첫 서술 400자
        clean = narrative.strip()
        if clean and "<t" not in clean[:15]:
            return _trim_sentence(clean[:450])
    return title


# 앞머리 각주/표주석 마커(각주 "- 1)", 표주석 "주:/자료:/출처:", "※", 페이지수 등)
_LEADING_NOTE_RE = re.compile(
    r"^\s*(?:[-–—]\s*\d+\)|주\s*\d*\s*[:：)]|주\)|각주|자료\s*[:：]|출처\s*[:：]|※|\d+\)\s|\d+\s*$)"
)
# 발췌 뒤에 붙는 각주("- 1)")·부속 소제목("가. 관계법령…")을 잘라낼 지점
_TAIL_CUT_RE = re.compile(r"\n\s*(?:[-–—]\s*\d+\)|[가-힣]\.\s*관계\s*법령|관계법령 및 판단기준|주\s*[:：])")
# 지적 본문의 핵심 라벨: (○○ 필요/부적정/부당/개선/미흡/소홀/위반/누락 …)
_CORE_LABEL_RE = re.compile(r"\([^()\n]{3,40}(?:필요|부적정|부당|개선|미흡|소홀|위반|누락|미비|과다|과소|지연)\)")


def _strip_leading_notes(seg: str) -> str:
    """발췌 앞머리의 각주·표주석을 걷어내 '지적 본문'부터 시작하게 정리(verbatim: 뒤 부분문자열 유지)."""
    seg = seg.strip()
    # 1) 핵심 라벨 '(○○ 필요)'가 앞쪽(120자 이내)에 있으면 거기부터 시작
    m = _CORE_LABEL_RE.search(seg[:200])
    if m and m.start() <= 120:
        return seg[m.start():].strip()
    # 2) 앞줄이 각주/주석 마커면 그 줄을 제거(최대 3줄)
    for _ in range(3):
        if _LEADING_NOTE_RE.match(seg):
            nl = seg.find("\n")
            if nl == -1:
                break
            seg = seg[nl + 1:].strip()
        else:
            break
    return seg


def _trim_sentence(seg: str) -> str:
    """발췌를 문장 경계로 정리(verbatim 유지: 앞머리 각주 제거 + 뒤 자름)."""
    seg = _strip_leading_notes(seg)
    seg = seg.strip()
    # 다음 목차/불릿/표 시작 전까지
    for stop in ["\n- -", "\n＜", "\n<table", "\n<tr", "\n※"]:
        p = seg.find(stop)
        if p > 60:
            seg = seg[:p]
    # 뒤에 붙는 각주("- 1)")·부속 소제목("가. 관계법령") 절단
    tm = _TAIL_CUT_RE.search(seg)
    if tm and tm.start() > 60:
        seg = seg[:tm.start()]
    # 마지막 한국어 종결/마침표에서 절단
    ends = [seg.rfind(e) for e in ["다.", "됨", "함", "음", "요.", "임.", ".", "우려", "필요"]]
    cut = max(ends)
    if cut > 60:
        # 종결어미 길이 보정
        seg = seg[:cut + 1]
    return seg.strip()


_CASE_BOUNDARY = ["감사원 컨설팅 사례", "### 신청 배경", "신청 배경",
                  "타 기관 사전컨설팅", "타 기관", "별첨", "# 검토"]


def _parse_consult(text: str, meta: dict) -> list[dict]:
    """사전컨설팅 사례집: '검토 결과 및 의견' 라벨 뒤의 최종 회신 문단 = 사례 1건.
    (kordoc/fitz 공통 — 라벨 뒤 회신을 다음 사례 시작 전까지로 한정)"""
    parts = re.split(r"#?\s*검토 결과 및 의견", text)
    items: list[dict] = []
    for i in range(len(parts) - 1):
        post = parts[i + 1]
        bound = post
        for b in _CASE_BOUNDARY:
            p = bound.find(b)
            if p > 30:
                bound = bound[:p]
        concl = _consult_conclusion(bound)
        if not concl or len(concl) < 25:
            continue
        # 표/마크다운 잔재가 섞인 발췌는 제외(깨끗한 회신만) — 무근거·오추출 차단
        if any(tok in concl for tok in ["|", "---", "###", "<t"]) or concl.startswith("-"):
            continue
        # 관련 법령: 같은 사례의 회신(라벨 이후) 구간에서만 인용 → 발췌와 사례 정합 보장.
        # (다른 사례 법령 혼입 방지. 회신에 인용 없으면 null — 억지 부여 금지)
        laws = extract_laws(bound)
        items.append({
            "source_excerpt": concl,
            "disposition": None,
            "legal_basis": laws,
        })
    return items


_CONCL_END = re.compile(r"(사료됨|판단됨|보입니다|보임|타당함|가능함|가능할 것으로 보임|필요함)\.?")


def _consult_conclusion(chunk: str) -> str:
    """청크 말미의 결론 문단만 추출. '검토 결과 및 의견' 라벨 직전 = 최종 회신.
    2단 레이아웃 잔재를 피하려 마지막 ● 불릿 이후 문단을 우선한다."""
    tail = chunk[-1500:]
    # 마지막 ● 불릿 이후 = 결론(불릿 없는 종합의견). 없으면 tail 전체.
    seg = tail.rsplit("●", 1)[-1]
    # 결론 종결어미가 있어야 결론으로 인정
    ends = list(_CONCL_END.finditer(seg))
    if not ends:
        return ""
    end_pos = ends[-1].end()
    text = seg[:end_pos]
    # 결론 시작점: 최종 결론 종결 직전의 '앞 문장 종결어미' 경계 뒤부터(연속문 제거)
    boundary = 0
    for bm in re.finditer(r"(?:됨|음|함|임|다\.|음\.|\.)\s*\n\s*", text[:end_pos - 6]):
        boundary = bm.end()
    if boundary == 0:
        # 줄바꿈이 없으면 종결어미+공백 경계
        for bm in re.finditer(r"(?:됨|음|함|임|다\.)\s+", text[:end_pos - 6]):
            boundary = bm.end()
    text = text[boundary:].strip()
    return re.sub(r"\s+", " ", text).strip()


def parse_document(text: str, meta: dict) -> list[dict]:
    """원문 → 부분레코드 리스트(source_excerpt·disposition·legal_basis[·title]).
    meta['doc_kind'] in {'alio','report','consult'} 로 분기."""
    kind = meta.get("doc_kind", "report")
    if kind == "alio":
        return _parse_alio(text, meta)
    if kind == "consult":
        return _parse_consult(text, meta)
    return _parse_report(text, meta)


# ── 레코드 조립 ──────────────────────────────────────────────────────────────
def _dockey(meta: dict) -> str:
    dk = meta.get("dockey")
    if dk:
        return re.sub(r"[^0-9A-Za-z가-힣]", "", str(dk))[:24]
    base = (meta.get("source_url", "") + meta.get("org_name", "")).encode("utf-8")
    return hashlib.sha256(base).hexdigest()[:10]


def build_record(item: dict, meta: dict, idx: int, codes: dict | None = None) -> dict:
    """부분레코드+메타+코드 → 완성 레코드(필수필드 전부, pii 적용)."""
    excerpt = mask(item["source_excerpt"])
    codes = codes or assign_codes(item["source_excerpt"])
    rid = f"{meta['source']}-{meta.get('year','')}-{_dockey(meta)}-{idx}"
    rec = {
        "id": rid,
        "record_type": meta.get("record_type", "finding"),
        "source": meta["source"],
        "org_type": meta["org_type"],
        "org_name": meta["org_name"],
        "audit_org": meta.get("audit_org"),
        "work_type": codes["work_type"],
        "sector": codes.get("sector"),
        "audit_type": meta.get("audit_type"),
        "finding_type": codes.get("finding_type", codes["work_type"] + "z"),
        "document_url": meta.get("document_url"),
        "source_title": meta.get("source_title"),
        "posted_date": meta.get("posted_date"),
        "summary": mask(item.get("summary")) if item.get("summary") else None,
        "source_excerpt": excerpt,
        "legal_basis": item.get("legal_basis", []),
        "disposition": item.get("disposition"),
        "year": meta["year"],
        "source_url": meta["source_url"],
        "added_at": ADDED_AT,
    }
    if meta.get("record_type") == "immunity":
        rec["immunity"] = item.get("immunity") or {"outcome": "인정", "requirements": []}
    return rec


# ── 증분 병합 ────────────────────────────────────────────────────────────────
def _content_hash(rec: dict) -> str:
    base = (rec.get("source_excerpt", "") + rec.get("id", "")).encode("utf-8")
    return hashlib.sha256(base).hexdigest()[:16]


def _load_state() -> dict:
    if STATE.exists():
        s = json.loads(STATE.read_text(encoding="utf-8"))
    else:
        s = {}
    s.setdefault("last_run", None)
    s.setdefault("seen_ids", [])
    s.setdefault("seen_hashes", [])
    return s


def merge_incremental(records: list[dict], seen_source_ids: list[str] | None = None) -> dict:
    """id·내용해시 기준 멱등 병합. state.json 갱신. return 통계."""
    existing = json.loads(FINDINGS.read_text(encoding="utf-8")) if FINDINGS.exists() else []
    state = _load_state()
    seen_ids = set(state["seen_ids"])
    seen_hashes = set(state["seen_hashes"])
    id_in_file = {r["id"] for r in existing}

    added = []
    for r in records:
        h = _content_hash(r)
        if r["id"] in id_in_file or r["id"] in seen_ids or h in seen_hashes:
            continue
        added.append(r)
        id_in_file.add(r["id"])
        seen_hashes.add(h)

    FINDINGS.write_text(json.dumps(existing + added, ensure_ascii=False, indent=2), encoding="utf-8")
    # seen_ids: 소스 문서 식별자(예: ALIO submissionNo) 축적(수집 증분용)
    if seen_source_ids:
        seen_ids.update(str(x) for x in seen_source_ids)
    state["seen_ids"] = sorted(seen_ids)
    state["seen_hashes"] = sorted(seen_hashes)
    state["last_run"] = date.today().isoformat()
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"added": len(added), "total": len(existing) + len(added), "skipped": len(records) - len(added)}


if __name__ == "__main__":
    print("tag.py — parse_document / assign_codes / build_record / merge_incremental")
