# Easy German Study Assistant — MVP 2

이 프로젝트는 두 단계로 구성됩니다.

## MVP 1 — 플레이리스트 메타데이터 동기화

`Easy German A2 Playlist`
→ `yt-dlp`
→ 제목 / Video ID / URL / 길이
→ `Notion Easy German Study`

사용 파일:
- `00_build_playlist.py`
- `01_sync_notion.py`
- `run_mvp_sync.py`

## MVP 2 — 당일 학습자료 자동 생성

`Notion에서 오늘 공부할 영상 조회`
→ `독일어 자막 추출`
→ `OpenAI로 학습자료 생성`
→ `Notion 페이지 본문에 lesson append`
→ `Transcript / Lesson 상태 업데이트`

사용 파일:
- `02_extract_transcript.py`
- `03_generate_lesson.py`
- `04_update_notion_lesson.py`
- `run_daily_lesson.py`

---

## 현재 Notion Data Source ID

`6878c89b-220b-4dc4-96a1-ae021d37a2b3`

---

# 1) 필요한 Secrets

## GitHub Actions Secrets

저장소에서 다음 두 개는 꼭 추가:

- `NOTION_TOKEN`
- `OPENAI_API_KEY`

추가로 모델명을 바꾸고 싶으면 workflow에서 `OPENAI_MODEL` 값을 수정하면 됩니다.

---

# 2) Notion Integration 연결

Notion의 `Easy German` 페이지 또는 `Easy German Study` DB에
사용 중인 Integration이 연결되어 있어야 합니다.

경로 예시:

`Easy German 페이지 열기 → ... → Connections / 연결 → Integration 추가`

---

# 3) 먼저 한 번 실행할 순서

## Step A. 플레이리스트 메타데이터 채우기

```bash
python run_mvp_sync.py
```

또는 GitHub:

`Actions → Easy German MVP - Sync Playlist → Run workflow`

이 단계가 끝나면 A2 #01–#06 row에 실제 제목 / Video ID / URL / 길이가 채워집니다.

---

## Step B. 특정 날짜의 lesson 생성

예: 화요일(2026-09-29) 2개 영상의 학습자료 생성

```bash
python run_daily_lesson.py --study-date 2026-09-29
```

또는 GitHub:

`Actions → Easy German Daily Lesson → Run workflow`

`study_date`에 `2026-09-29` 입력

---

# 4) 결과로 Notion에서 어떻게 보이나?

각 영상 row의 페이지에 아래 구조가 append 됩니다.

- AI Lesson Pack
- 오늘 영상 핵심
- 핵심 단어
- 주요 표현
- 문법
- Listening Point
- Speaking Practice
- Today’s Core

그리고 속성도 바뀝니다.

- `Transcript`: `Pending` → `Ready` 또는 `Failed`
- `Lesson`: `Pending` → `Generated`

---

# 5) 로컬 실행 준비

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

설치:

```bash
pip install -r requirements.txt
```

`.env.example`을 `.env`로 복사한 뒤 값 입력:

- `NOTION_TOKEN`
- `NOTION_DATA_SOURCE_ID`
- `A2_PLAYLIST_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

---

# 6) 파일 설명

## `02_extract_transcript.py`
독일어 자막 추출

우선순위:
1. `youtube-transcript-api`
2. `yt-dlp` VTT subtitle fallback

출력:
- plain text transcript

## `03_generate_lesson.py`
자막을 기반으로 OpenAI가 JSON lesson pack 생성

출력 예시:
- 한국어 요약 3문장
- 핵심 단어 8–12개
- 주요 표현 5–8개
- 문법 1–2개
- Listening Point 2–3개
- Speaking 질문 3개
- 오늘 핵심 단어/표현/문법

## `04_update_notion_lesson.py`
lesson JSON을 읽어 Notion 페이지에 append하고
`Transcript`, `Lesson` 속성을 업데이트

## `run_daily_lesson.py`
하루 실행용 메인 스크립트

1. Notion에서 `Study Date = 지정 날짜` row 조회  
2. 자막 추출  
3. lesson 생성  
4. Notion 업데이트

---

# 7) 추천 실행 순서 (내일 아침용)

1. `run_mvp_sync.py` 먼저 실행  
2. `run_daily_lesson.py --study-date 2026-09-29` 실행  
3. Notion에서 화요일 영상 2개 페이지 확인  
4. 학습자료의 양이 너무 많거나 적은지 확인  
5. 프롬프트 튜닝 후 수요일부터 계속 사용

---

# 8) 주의점

- `04_update_notion_lesson.py`는 현재 **페이지 본문에 lesson을 append**합니다.
  즉, 여러 번 반복 실행하면 lesson pack이 여러 번 붙을 수 있습니다.
- 재실행 전에 Notion에서 기존 appended section을 지우거나,
  나중에 “기존 AI Lesson Pack 교체” 로직을 따로 추가할 수 있습니다.
- 자동 schedule은 UTC 기준입니다. 현재 workflow는
  `05:10 UTC`에 돌아가므로 CEST 기간에는 독일 시간 `07:10`입니다.

---

# 다음에 붙이면 좋은 기능

- 기존 AI Lesson Pack 덮어쓰기
- 복습용 문제 자동 생성
- `Status = Done`이면 `Review Date` 자동 계산
- B1 playlist 전체 확장
- 하루 20분 규칙 기반 스케줄 자동 생성
