"""수집 (collect) — API 키 없이 공개 자료를 직접 읽어 원문 텍스트를 모은다.

원칙:
- 감사자료 수집에는 인증키를 쓰지 않는다. 공개 페이지·파일·PDF를 직접 읽는다.
- 정적 페이지/파일: requests 로 충분.
- JS 렌더링 사이트(예: 감사데이터 개방 포털): 브라우저형 수집(Claude in Chrome 등) 필요.
- 결과는 raw_docs/ 에 저장하고 structure.py 로 넘긴다.

TODO(개발): 소스별 어댑터를 하나씩 붙인다. PoC는 1개 소스부터.
  - ALIO 지적사항(정형 웹)      : 가장 쉬움
  - 국회 결산 시정요구(공개 파일): 쉬움
  - 감사원 공개 보고서(PDF)     : PDF 파싱 필요
  - 적극행정 면책/사전컨설팅    : 감사원 길라잡이·인사혁신처 ON
"""
from pathlib import Path
import json

RAW = Path(__file__).resolve().parent.parent / "data" / "raw_docs"
RAW.mkdir(parents=True, exist_ok=True)


def collect_source(source_key: str) -> list[dict]:
    """한 소스에서 원문 문서 목록을 수집해 반환한다. (TODO: 실제 구현)"""
    raise NotImplementedError(f"{source_key} 어댑터 미구현 — 소스별로 붙이세요")


if __name__ == "__main__":
    print("collect.py — 소스 어댑터를 구현한 뒤 실행하세요. raw_docs/ 에 저장됩니다.")
