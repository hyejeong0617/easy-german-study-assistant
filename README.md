# Easy German Study Assistant — A2 Sprint v4

목표: **2026-10-05 ~ 2026-12-10** 동안 Easy German A2 플레이리스트를 월–금 기준으로 빠르게 완주하고, 필요한 영상만 선택해서 AI lesson을 생성한다.

A2 playlist:
`https://www.youtube.com/playlist?list=PLk1fjOl39-5201BUdhtOM_x23poNvLouT`

## 핵심 원칙

이 시스템은 완전자동이 아니라 **human-in-the-loop 반자동화**다.

1. 전체 A2 영상을 Notion Calendar에 미리 배치한다.
2. 학습자는 그날의 영상을 직접 시청한다.
3. 영상마다 `Study Status`를 선택한다.
4. 복습이 필요한 영상만 `Lesson Request`를 체크한다.
5. `Generate Requested Lessons` workflow를 실행하면 체크된 영상만 AI lesson이 생성된다.

날짜가 왔다고 lesson을 자동 생성하지 않는다.

---

# 1. Notion DB

Database: `Easy German Study`

Data Source ID:
`6878c89b-220b-4dc4-96a1-ae021d37a2b3`

## 새 핵심 속성

### Study Status
- `To Watch` — 아직 볼 영상
- `Watched` — 시청 완료
- `Skipped` — 이미 알거나 lesson이 필요 없는 영상
- `Carry Over` — 그날 못 보고 backlog로 넘긴 영상

### Lesson Request
체크박스. **AI lesson이 필요한 영상만 체크**한다.

### Lesson Status
- `Not Requested`
- `Requested`
- `Generated`
- `Failed`

### Lesson Generated At
lesson이 성공적으로 생성된 시각.

기존 `Status`, `Lesson`, `Transcript` 필드는 9월 MVP 기록과 호환성을 위해 당분간 유지한다.

## Views

- `A2 Sprint Calendar` — 날짜별 시청 영상
- `Lesson Queue` — Lesson Request가 체크되었고 아직 Generated가 아닌 영상
- `Carry Over` — 못 본 영상 backlog

---

# 2. 전체 A2 일정 만들기

GitHub:

`Actions → Build A2 Sprint Schedule → Run workflow`

이 workflow는:

1. Easy German A2 playlist 전체 metadata를 읽고
2. 2026-10-05 ~ 2026-12-10 사이 평일을 계산하고
3. 전체 영상을 날짜별로 최대한 균등하게 배분하고
4. Notion DB에 새 row를 만들거나 기존 row를 업데이트한다.

현재 기간은 평일 약 49일이다. 영상이 약 200개라면 대부분 하루 4개, 일부 날짜는 5개 정도가 된다.

실행 파일:
- `00_build_playlist.py`
- `01_sync_notion.py`
- `build_a2_schedule.py`

`01_sync_notion.py`는 idempotent하게 설계되어 있어서 같은 스케줄을 다시 실행해도 기존 페이지를 찾아 업데이트한다. 이미 생성된 lesson과 사용자가 설정한 새 진행 상태는 가능한 한 보존한다.

---

# 3. 매일 학습 방법

Notion의 `A2 Sprint Calendar`에서 오늘 날짜를 연다.

각 영상 시청 후:

- 봤으면 → `Study Status = Watched`
- 너무 쉬워 별도 복습 불필요 → `Study Status = Skipped`
- 못 봤으면 → `Study Status = Carry Over`
- AI 정리가 필요하면 → `Lesson Request = checked`

`Carry Over` 영상의 Study Date는 자동으로 밀지 않는다. 별도 `Carry Over` view에서 backlog로 관리한다.

---

# 4. 요청한 영상만 AI lesson 만들기

영상 시청 후 필요한 영상에 `Lesson Request`를 체크한다.

그 다음 GitHub:

`Actions → Generate Requested Lessons → Run workflow`

workflow는 다음 조건만 조회한다.

- `Lesson Request = true`
- `Lesson Status != Generated`

처리 순서:

`Notion Lesson Queue`
→ `YouTube transcript 추출`
→ `OpenAI lesson 생성`
→ `해당 Notion 페이지에 append`
→ `Lesson Status = Generated`
→ `Lesson Request = false`

실행 파일:
- `02_extract_transcript.py`
- `03_generate_lesson.py`
- `04_update_notion_lesson.py`
- `generate_requested_lessons.py`

실패하면:
- `Lesson Status = Failed`
- `Transcript = Failed`
- `Lesson Request`는 그대로 유지되어 재시도 가능

실패 로그를 Notion 본문에 계속 append하지 않는다.

---

# 5. A2 Fast Track lesson 형식

목표는 한 영상당 약 5–10분 복습이다.

### 1. Video in 3 Lines
영상 핵심을 한국어 2–3문장으로 정리.

### 2. Must-Know Expressions
실제 transcript에 근거한 재사용 가능한 표현 약 5개.

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

# 6. GitHub Secrets

필수:
- `NOTION_TOKEN`
- `OPENAI_API_KEY`

선택적이지만 YouTube 차단 fallback에 사용:
- `YOUTUBE_COOKIES_B64`

`cookies.txt`를 Base64로 변환하는 Windows PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("cookies.txt")) | Set-Clipboard
```

GitHub:
`Settings → Secrets and variables → Actions`

Secret name:
`YOUTUBE_COOKIES_B64`

YouTube cookies는 회전/만료될 수 있으므로 영구적인 해결책으로 간주하지 않는다. Lesson generation은 사용자가 요청한 영상에만 수행되어 자동 요청량을 최소화한다.

---

# 7. Workflows

## `Build A2 Sprint Schedule`
- 수동 실행
- 전체 playlist → Notion Calendar
- 일반적으로 sprint 시작 전 한 번 실행

## `Generate Requested Lessons`
- 수동 실행
- Lesson Request가 체크된 영상만 처리

## `Legacy Daily Lesson - Manual Only`
- 9월 MVP 테스트용
- 자동 schedule 제거됨
- 새 학습 루틴에서는 사용하지 않는다

---

# 8. Local run

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

전체 일정:

```bash
python build_a2_schedule.py
```

요청 lesson 처리:

```bash
python generate_requested_lessons.py
```

---

# 9. Sprint 철학

이 프로젝트의 우선순위는:

1. A2 전체 듣기 노출량 확보
2. 이해한 영상은 빠르게 통과
3. 필요한 표현만 선택적으로 깊게 복습
4. 12월 중 A2 sprint 종료
5. 1월 B1 단계로 이동

즉 **모든 영상에서 lesson을 만드는 것이 목표가 아니다.**
