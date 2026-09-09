# Cloudflare Pages로 `app/` 배포 (사용자명 없는 URL)

GitHub Pages 기본 주소는 `https://jinhee252525.github.io/audit-helper/`처럼 **GitHub 사용자명이 URL에 들어갑니다.**  
도메인을 사지 않고도, Cloudflare Pages의 `*.pages.dev` 주소로 **짧은 공개 URL**을 쓸 수 있습니다.

> GitHub Pages 설정(`docs/PAGES.md`)은 그대로 유지해도 됩니다. 두 배포를 병행해도 충돌하지 않습니다.

## 한 줄 다음 단계

Cloudflare 대시보드 → **Workers & Pages** → **Create** → **Pages** → **Connect to Git** → `jinhee252525/audit-helper` 선택 → **Root directory = `app`**, Framework preset = **None** → Save and Deploy.

## 상세 절차

1. [Cloudflare Pages](https://pages.cloudflare.com/)에 로그인(무료 플랜으로 충분).
2. **Create a project** → **Connect to Git** → GitHub에서 `audit-helper` 저장소 연결.
3. 빌드 설정:
   - **Production branch:** `main`
   - **Framework preset:** None (정적 파일)
   - **Build command:** (비움)
   - **Build output directory:** `app`  
     (또는 Root directory를 `app`으로 두고 output을 `/`로)
4. Deploy 후 받는 URL 예: `https://audit-helper-xxxx.pages.dev`  
   → 사용자명(`jinhee252525`)이 **URL에 없습니다.**
5. 확인: `/` · `/dashboard.html` · `/search.html` · `/status.html`

## 참고

- 배포 범위는 GitHub Pages와 동일하게 **`app/`만**입니다. `data/findings*.json` · `app/data/index/` 샤드는 gitignore라 포함되지 않습니다.
- 커스텀 도메인(예: `audit.example.com`)은 나중에 Pages 프로젝트 → Custom domains에서 추가하면 됩니다. **지금은 구매 불필요.**
- 바닐라 정적 파일만 사용합니다. 신규 CDN/라이브러리 없음.
