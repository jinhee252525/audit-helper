# -*- coding: utf-8 -*-
import os, re
from pathlib import Path

base = Path(os.environ["USERPROFILE"]) / "Desktop" / "audit-helper" / "docs" / "proposals" / "2026-09-06-situation-memo"
path = base / "design-system.md"
text = path.read_text(encoding="utf-8")

new_section = """## 10. 컬러 확정 (2026-09-06 · 녹색 계통 고정)

**채택 방향: Sage / dusty green matte (녹색 계통)**  
파랑·보라 실험은 폐기. 히트맵·기여도 격자 UI 모방 금지. 레이아웃은 **근거 레인 / 거리 비교 / 메모 독**.

| 토큰 | Hex | 용도 |
|------|-----|------|
| page | `#F7F8F7` | 캔버스 |
| surface | `#F0F2F1` | 보조 카드·필드 |
| sage-soft | `#F0F4F1` | 본문 확보 하이라이트 |
| primary | `#5B7C73` | CTA·활성 내비·칩 |
| primary-soft | `#8DA399` | 차트 보조·앰비언트 |
| deep | `#3F5D50` | 리본·강조 라벨·딥 바 |
| tip | `#EBE8DA` | 한 줄 정리 카드 |
| border | `#E0E3E2` | 카드 보더 |
| ink | `#333840` | 본문 |
| muted | `#7A8087` | 보조 텍스트 |

**품질 배지**
- 목록만 → slate/surface
- 본문 확보 → sage-soft + deep 텍스트
- 근거 대조 완료 → deep fill / 밝은 텍스트

**금지**: 태극·국장, 선명한 sky `#0ea5e9`, 블루바이올렛 `#5B6B99`, 유료 디자인 생성.

## 11. Figma + 폰트
- Figma 파일: https://www.figma.com/design/70Kdd4EIOKabz4Zl32gwGd
- 폰트: Pretendard 우선. Figma에 없으면 Noto Sans KR 임시.
- 화면: `01 판단 지원 워크스페이스`, `02 인사이트 대시보드`
- 2026-09-06 저녁: Starter MCP 한도로 Figma 즉시 재칠 불가 → 문서·로컬 목업을 녹색으로 먼저 고정. 한도 회복 후 Figma 동기화.
"""

if re.search(r"^## 10\.", text, flags=re.M):
    text = re.split(r"^## 10\.", text, maxsplit=1, flags=re.M)[0].rstrip() + "\n\n" + new_section
else:
    text = text.rstrip() + "\n\n" + new_section

path.write_text(text, encoding="utf-8")

note = base / "palette-lock.md"
note.write_text("""# 팔레트 고정 (2026-09-06)

디자인 방향 **녹색 계통(sage/dusty green matte)** 으로 확정.

- primary `#5B7C73` / soft `#8DA399` / deep `#3F5D50`
- page `#F7F8F7` / tip `#EBE8DA`
- 레이아웃: 근거 레인 · 거리 비교 · 메모 독 (히트맵 모방 금지)
- Figma: https://www.figma.com/design/70Kdd4EIOKabz4Zl32gwGd (MCP 한도 후 동기화)
""", encoding="utf-8")

print("updated", path)
print("wrote", note)
print("size", path.stat().st_size)
