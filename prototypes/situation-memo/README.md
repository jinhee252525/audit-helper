# 상황 메모 히어로 프로토타입 (situation-memo)

「감사 선례 도우미」 MVP 히어로 화면 — **상황입력 → 선례 연결 → 확보된 근거 / 거리 비교 / 결재용 검토메모** 1화면.

## 파일

| 파일 | 역할 |
|------|------|
| `index.html` | 레이아웃 골격 (탑바 · 상황 히어로 · 3레인) |
| `styles.css` | sage green 잠금 팔레트 + Pretendard |
| `app.js` | `sample.json` 로드, CTA, 배지, 하이라이트, 메모 복사 |
| `sample.json` | 계약·용역 변경 시나리오 샘플 |
| `shot-before.png` / `shot-after.png` | CTA 전·후 UI 캡처 |

## 팔레트 (고정)

- page `#F7F8F7` · surface `#F0F2F1` · sage-soft `#F0F4F1`
- primary `#5B7C73` · soft `#8DA399` · deep `#3F5D50` · tip `#EBE8DA`
- 폰트: Pretendard CDN, Noto Sans KR 폴백
- **태극·국장 없음**

## 동작

1. 페이지 로드 시 `sample.json`을 읽어 상황 문구·메모 필드 골격 표시
2. **「선례 연결하기」** → 근거 카드(품질 배지 `목록만` / `본문 확보` / `근거 대조 완료`), 거리 패널, 메모 초안 채움
3. `목록만` 카드는 **「메모에 근거 추가」 비활성** (본문 미확보 정책)
4. `본문 확보`·`근거 대조 완료` 카드에 **온디맨드 원문 하이라이트** 버튼
5. 메모 초안 수정 후 **메모 복사**

## 로컬 실행

`file://`에서는 `fetch(sample.json)`이 막힐 수 있습니다. 정적 서버로 여세요.

```bash
cd prototypes/situation-memo
python3 -m http.server 8765
# → http://127.0.0.1:8765/
```

## 성공 기준

- 위 파일 전부 존재
- `shot-after.png`에 3레인 녹색 히어로 + 샘플 콘텐츠 표시
