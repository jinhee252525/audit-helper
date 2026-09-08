# GitHub Pages 설정 (감사 선례 도우미)

목표 URL: **https://jinhee252525.github.io/audit-helper/**

배포 범위: **`app/`만** (히어로·검색·피드 + demo/hero-sample).  
`data/findings*.json` · `app/data/index/` 샤드는 gitignore라 **배포되지 않습니다**.

보안: 바닐라 정적 파일만. 신규 CDN/라이브러리 없음. 샘플·합성 예시 포함 — 실데이터 전체 검색은 노트북 인덱스 필요.

> 참고: private 저장소의 **비공개** Pages는 GitHub Pro/Team이 필요할 수 있습니다.  
> Source를 GitHub Actions로 두면, 플랜에 따라 사이트가 **공개 URL**이 될 수 있으니 공개 가능 여부만 한 번 확인하세요.

---

## 1) 워크플로 파일 추가 (API로는 `.github/workflows` 생성이 막혀 있어 수동 1회)

GitHub 앱/웹에서:

1. 저장소 `audit-helper` → **Add file** → **Create new file**
2. 경로: `.github/workflows/deploy-pages.yml`
3. 아래 내용 그대로 붙여넣기 → Commit to `main`

```yaml
name: Deploy GitHub Pages

on:
  push:
    branches: [main]
    paths:
      - "app/**"
      - ".github/workflows/deploy-pages.yml"
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Configure Pages
        uses: actions/configure-pages@v5

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: app

      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

## 2) Pages 소스 연결

**Settings → Pages → Build and deployment → Source: GitHub Actions**

## 3) 실행

- 커밋 후 Actions에서 `Deploy GitHub Pages`가 초록이면 위 URL로 접속.
- 안 뜨면 Actions → 해당 워크플로 → **Run workflow**.

## 4) 확인

- `/` 히어로 · `/search.html` · `/feed.html`
- 합성/샘플 경고가 보이면 정상(전체 findings 아님).
