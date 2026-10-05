# Easy German Study Assistant — A2 Sprint v5

목표: **2026-10-05 ~ 2026-12-10** 동안 Easy German A2 플레이리스트를 월–금 기준으로 빠르게 완주하고, 필요한 영상만 선택해서 AI lesson을 생성한다.

A2 playlist:
`https://www.youtube.com/playlist?list=PLk1fjOl39-5201BUdhtOM_x23poNvLouT`

## 핵심 구조

이 시스템은 **human-in-the-loop 반자동화**다.

1. 전체 A2 영상을 Notion Calendar에 미리 배치한다.
2. 학습자는 그날의 영상을 직접 시청한다.
3. AI 복습이 필요한 영상만 `Lesson Request`를 체크한다.
4. Windows에서 `EasyGermanLesson.bat`를 더블클릭한다.
5. **YouTube 자막은 사용자의 PC/가정용 인터넷에서만 추출**한다.
6. transcript가 자동으로 GitHub에 push된다.
7. GitHub Actions가 OpenAI lesson을 생성하고 Notion 페이지에 저장한다.

즉 GitHub Actions는 더 이상 YouTube 자막을 직접 요청하지 않는다.

---

# 1. Notion DB

Database: `Easy German Study`

Data Source ID:
`6878c89b-220b-4dc4-96a1-ae021d37a2b3`

## 핵심 속성

### Study Status
- `To Watch` — 아직 볼 영상
- `Watched` — 시청 완료
- `Skipped` — 이미 알거나 lesson이 필요 없는 영상
- `Carry Over` — 그날 못 보고 backlog로 넘긴 영상

### Lesson Request
AI lesson이 필요한 영상만 체크한다.

### Lesson Status
- `Not Requested`
- `Requested`
- `Generated`
- `Failed`

### Lesson Generated At
lesson이 성공적으로 생성된 시각.

### Watch on YouTube
각 영상으로 바로 이동하는 클릭 가능한 YouTube 링크.

기존 `Status`, `Lesson`, `Transcript` 필드는 이전 MVP 기록과 호환성을 위해 유지한다.

## Views
- `A2 Sprint Calendar` — 날짜별 시청 영상
- `Lesson Queue` — Lesson Request가 체크된 영상
- `Carry Over` — 못 본 영상 backlog

---

# 2. 전체 A2 일정

`Actions → Build A2 Sprint Schedule → Run workflow`

전체 playlist metadata를 읽어 2026-10-05 ~ 2026-12-10 평일에 배치하고 Notion DB를 업데이트한다.

관련 파일:
- `00_build_playlist.py`
- `01_sync_notion.py`
- `build_a2_schedule.py`

---

# 3. 매일 사용하는 방법 — One Click

## Step 1. Notion에서 영상 시청

각 영상 시청 후:
- 봤으면 → `Study Status = Watched`
- 너무 쉬워 복습 불필요 → `Study Status = Skipped`
- 못 봤으면 → `Study Status = Carry Over`
- AI lesson이 필요하면 → `Lesson Request = checked`

## Step 2. 바탕화면에서 실행

로컬 repo 안의 `EasyGermanLesson.bat`를 바탕화면 바로가기로 만들어 사용한다.

더블클릭하면 자동으로:

`Notion Lesson Queue`
→ `로컬 PC에서 YouTube transcript 추출`
→ `transcript 파일 저장`
→ `git commit + push`
→ `GitHub Actions 자동 시작`
→ `OpenAI lesson 생성`
→ `Notion 페이지 업데이트`

사용자가 GitHub Actions에서 Run workflow를 누를 필요가 없다.

---

# 4. 최초 1회 로컬 설정

로컬 repo를 최신 상태로 만든다.

```bash
git pull
```

`.env.example`을 복사해 `.env`를 만든다.

필수 값:

```env
NOTION_TOKEN=secret_xxx
NOTION_DATA_SOURCE_ID=6878c89b-220b-4dc4-96a1-ae021d37a2b3
YOUTUBE_BROWSER=chrome
```

`OPENAI_API_KEY`는 로컬 실행에 필요하지 않다. OpenAI는 GitHub Actions의 Secret을 사용한다.

`EasyGermanLesson.bat`는 첫 실행 시 `.venv`가 없으면 자동 생성하고 requirements를 설치한다.

필수 프로그램:
- Python 3.12+
- Git
- Node.js (yt-dlp의 YouTube JS challenge 대응용)

GitHub push 인증은 로컬 Git에 미리 로그인되어 있어야 한다.

브라우저 cookie fallback이 필요할 때 Chrome을 사용한다. 환경에 따라 Chrome이 cookie DB를 잠그는 경우 브라우저를 완전히 종료한 뒤 다시 실행하면 된다. Firefox나 Edge를 쓰려면 `.env`의 `YOUTUBE_BROWSER`를 변경한다.

---

# 5. 새 파일 역할

## `fetch_requested_transcripts_local.py`
로컬 전용.

- Notion에서 `Lesson Request = true` 조회
- YouTube transcript를 **로컬 PC**에서 추출
- transcript를 `data/requested_lessons/transcripts/`에 저장
- Notion의 `Transcript = Ready`, `Lesson Status = Requested` 업데이트
- transcript 파일만 git commit/push
- OpenAI를 호출하지 않음

## `EasyGermanLesson.bat`
Windows one-click launcher.

## `generate_lessons_from_transcripts.py`
GitHub Actions 전용.

- YouTube에 접속하지 않음
- 이미 push된 transcript만 읽음
- `03_generate_lesson.py`로 OpenAI lesson 생성
- `04_update_notion_lesson.py`로 Notion 업데이트

## `.github/workflows/generate_requested_lessons.yml`
`data/requested_lessons/transcripts/*.txt`가 main에 push되면 자동 실행.

---

# 6. A2 Fast Track lesson 형식

한 영상당 약 5–10분 복습을 목표로 한다.

### 1. Video in 3 Lines
영상 핵심 한국어 2–3문장.

### 2. Must-Know Expressions
실제 transcript에 근거한 재사용 가능한 표현 5개.

### 3. Vocabulary
A2→B1 전환에 유용한 단어 5–7개. 너무 기본적인 A1 단어는 우선순위를 낮춘다.

### 4. One Grammar Point
실제 영상에서 학습 가치가 있을 때만 최대 1개.

### 5. Listen Again
실제 transcript에서 다시 들어볼 문장 3개.

### 6. Say It Yourself
영상 주제로 직접 말해볼 German prompt 2개.

AI는 영상에서 나왔다고 주장하는 문장을 임의로 만들지 않고 transcript에 근거하도록 프롬프트되어 있다.

---

# 7. GitHub Secrets

GitHub Actions 필수:
- `NOTION_TOKEN`
- `OPENAI_API_KEY`

`YOUTUBE_COOKIES_B64`는 **새 lesson workflow에서는 사용하지 않는다.**
YouTube 접근이 필요한 transcript 단계가 로컬 PC로 이동했기 때문이다.

---

# 8. Workflows

## `Build A2 Sprint Schedule`
전체 playlist → Notion Calendar. 필요할 때만 수동 실행.

## `Generate Requested Lessons`
기본적으로 **transcript push 시 자동 실행**.
수동 `workflow_dispatch`도 비상용으로 남겨둔다.

## `Legacy Daily Lesson - Manual Only`
9월 MVP 테스트용. 새 학습 루틴에서는 사용하지 않는다.

---

# 9. Sprint 철학

1. A2 전체 듣기 노출량 확보
2. 이해한 영상은 빠르게 통과
3. 필요한 표현만 선택적으로 깊게 복습
4. 12월 중 A2 sprint 종료
5. 1월 B1 단계로 이동

**모든 영상에서 lesson을 만드는 것이 목표가 아니다.**
