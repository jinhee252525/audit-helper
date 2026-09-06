"""경량 PII 마스킹 (공개 감사자료 전용).

공개자료는 기관이 이미 비실명화·공개했으므로 **성명 등은 건드리지 않는다**.
여기서는 만에 하나 원문에 남아 있을 수 있는 정형 식별번호만 정규식으로 마스킹한다:
주민등록번호 · 사업자등록번호 · 전화번호 · 계좌번호(추정) · 이메일.

사용:
    from pipeline.pii import mask
    safe = mask(text)
"""
from __future__ import annotations
import re

# 주민등록번호: 6자리-7자리 (뒷자리 첫 글자 1~4 성별코드)
_RRN = re.compile(r"\b(\d{6})[-\s]?([1-4]\d{6})\b")
# 사업자등록번호: 3-2-5
_BIZ = re.compile(r"\b(\d{3})-(\d{2})-(\d{5})\b")
# 전화번호: 0으로 시작하는 국번(휴대폰/지역/대표번호). 02-XXXX-XXXX, 0XX-XXX(X)-XXXX
_PHONE = re.compile(r"\b0\d{1,2}[-\s]\d{3,4}[-\s]\d{4}\b")
# 이메일
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# 계좌번호(추정): 하이픈으로 3그룹 이상 연결된 숫자(예: 123-45-678901, 1234-56-789012).
# 날짜(2026. 3. 11)는 점/공백 구분이라 걸리지 않는다. 사업자·전화가 먼저 처리되므로 잔여만.
_ACCT = re.compile(r"\b\d{2,6}-\d{2,6}-\d{2,7}(?:-\d{2,7})?\b")
# YYYY-MM-DD 하이픈 날짜 오탐 방지(예: 2024-08-01 → 계좌번호로 치환 금지).
_DATE_HYPHEN = re.compile(r"^(19|20)\d\d-(0?[1-9]|1[0-2])-(0?[1-9]|[12]\d|3[01])$")


def _acct_sub(m: re.Match) -> str:
    s = m.group(0)
    if _DATE_HYPHEN.match(s):   # 날짜면 원문 유지
        return s
    return "[계좌번호]"


def mask(text: str) -> str:
    """정형 식별번호만 마스킹한 텍스트 반환. 성명·기관명 등은 유지."""
    if not text:
        return text
    text = _RRN.sub("******-*******", text)
    text = _EMAIL.sub("[이메일]", text)
    text = _BIZ.sub("***-**-*****", text)
    text = _PHONE.sub("[전화번호]", text)
    text = _ACCT.sub(_acct_sub, text)
    return text


if __name__ == "__main__":
    sample = (
        "담당자 홍길동(주민 900101-1234567), 사업자 123-45-67890, "
        "연락처 010-1234-5678, 계좌 110-234-567890, 메일 a.b@korea.kr, "
        "감사일 2026. 3. 11. 제30조 위반"
    )
    print(mask(sample))
