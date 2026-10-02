# HN Daily Digest

매일 아침 Hacker News 인기 글을 수집하고 한글로 요약하여 Slack으로 전송합니다.

## 기능

- HN Top Stories 상위 30개 수집 후 점수 기준 상위 20개 선별
- TOP 3 글은 상세 요약 + HN 커뮤니티 반응 분석
- 나머지 글은 카테고리별 분류 (개발/보안/빅테크/기타)
- **메인 메시지 + 스레드 답글 구조**로 깔끔한 정보 전달
- Claude Code cloud routine으로 매일 오전 9시(KST) 자동 실행 (Claude 구독 사용량 사용, API 크레딧 불필요)

## 출력 형식

### 메인 메시지
```
HN Daily - 2025년 01월 28일

1. 제목 (점수/댓글수)
2. 제목 (점수/댓글수)
3. 제목 (점수/댓글수)

────────────

개발자 픽
• 제목 (점수)
• 제목 (점수)

보안/인프라
• 제목 (점수)

...

────────────
상세 요약 + HN 반응은 스레드에서 확인하세요
```

### 스레드 답글 (TOP 3 각각)
```
1. 제목
원문: URL
HN 토론: URL

내용 요약
3~5문장 요약

HN 반응
긍정적 반응:
• 의견
• 의견

부정적/우려:
• 의견

흥미로운 의견:
• 의견
```

## 동작 구조

[Claude Code routine](https://code.claude.com/docs/en/routines)이 매일 클라우드 세션을 띄워 아래 순서로 실행합니다.

| 단계 | 수행 주체 | 내용 |
|------|-----------|------|
| 1. 수집 | 스크립트 | `python hn_digest.py collect /tmp/hn_data.json` |
| 2. 요약/분류 | routine의 Claude | `categorize_stories`, `analyze_story_with_comments` 안의 프롬프트를 지침으로 읽고 `/tmp/hn_result.json` 작성 (함수 자체는 실행하지 않음) |
| 3. 전송 | 스크립트 | `python hn_digest.py send /tmp/hn_data.json /tmp/hn_result.json` |

요약 규칙(JSON 스키마, 카테고리 기준 등)을 바꾸려면 위 두 함수의 프롬프트 문구만 수정해 main에 반영하면 다음 실행부터 적용됩니다. 함수 이름이나 JSON 스키마를 바꿀 때는 routine 프롬프트도 함께 수정해야 합니다.

## 설정 방법

### 1. Slack Bot 생성

1. [Slack API](https://api.slack.com/apps)에서 새 앱 생성
2. **OAuth & Permissions**에서 Bot Token Scopes 추가:
   - `chat:write`
3. **Install to Workspace** 클릭
4. Bot User OAuth Token (xoxb-...) 복사
5. Slack 채널에서 `/invite @봇이름`으로 봇 초대
6. 채널 ID 확인 (채널 우클릭 > 링크 복사 > URL에서 C로 시작하는 ID)

### 2. Cloud 환경 설정

[claude.ai/code](https://claude.ai/code)에서 메시지 입력창 위 환경 선택기 > **Cloud** > 사용할 환경의 설정 아이콘을 눌러 편집합니다.

- **Network access**: **Custom** 선택
  - Allowed domains: `hacker-news.firebaseio.com`
  - **Also include default list of common package managers** 체크 (`pip install` 용)
- **Environment variables**:
  ```
  SLACK_CHANNEL_ID=C로시작하는채널ID
  SLACK_BOT_TOKEN=proxy-injected
  ```
  `SLACK_BOT_TOKEN`은 자리표시자입니다. 실제 토큰을 넣지 않습니다.
- **API credentials** > **Add credential** (Pro/Max 플랜)
  - Credential type: **Bearer**
  - Allowed websites: `slack.com`
  - Custom headers: Name `Authorization`, Prefix `Bearer`, Value에 실제 `xoxb-...` 토큰

실제 토큰은 API credential에만 저장되어 프록시가 `slack.com` 요청에 붙입니다. 세션 안의 Claude와 명령어에는 노출되지 않습니다. 스크립트는 `SLACK_BOT_TOKEN`이 `proxy-injected`이면 `Authorization` 헤더를 보내지 않습니다.

마지막에 **Save changes**를 눌러야 네트워크와 환경변수 설정이 저장됩니다.

### 3. Routine 생성

[claude.ai/code/routines](https://claude.ai/code/routines)에서 생성하거나 Claude Code에서 `/schedule`로 만듭니다.

| 항목 | 값 |
|------|----|
| 저장소 | `https://github.com/ssj5037/hn-summary` |
| 일정 | `0 0 * * *` (UTC, 매일 09:00 KST) |
| 모델 | `claude-sonnet-5-5` |
| 환경 | 2번에서 설정한 환경 |
| 허용 도구 | `Bash`, `Read`, `Write` |
| MCP 커넥터 | 없음 (HN 댓글 등 외부 텍스트를 읽으므로 불필요한 커넥터는 붙이지 않음) |

<details>
<summary>Routine 프롬프트</summary>

```
You are running the daily HN Daily Digest for the repo ssj5037/hn-summary, which is checked out in the current directory. You (Claude) do the Korean summarization yourself. Do NOT call the Anthropic API, and NEVER run `python hn_digest.py` without arguments (that path uses API credits).

Steps:
1. Install deps: `pip install -r requirements.txt`
2. Collect data: `python hn_digest.py collect /tmp/hn_data.json`. It contains `stories` (score-sorted, up to 20) and `comments` (keyed by str(story id), for the first 3 stories).
3. Read `hn_digest.py` (functions `categorize_stories` and `analyze_story_with_comments`) and `/tmp/hn_data.json`. Write `/tmp/hn_result.json` with exactly this shape:
   {"categorize": <the JSON object that the prompt in categorize_stories() asks for, using stories[0:3] as TOP 3 and stories[3:] as the rest>,
    "analyses": [<3 objects, in TOP 3 order, each the JSON object that the prompt in analyze_story_with_comments() asks for, using that story and comments[str(id)]>]}
   Follow every rule in those two prompts (categories dev/security/bigtech/misc, max 3 per category, Korean text with technical terms kept in English, empty arrays where nothing applies). Use only story ids that exist in the data; base summaries only on the titles, URLs and comments provided, do not invent facts.
4. Validate before sending: load the file with `python -c "import json; json.load(open('/tmp/hn_result.json'))"`, and check that categorize.top3 has 3 entries whose ids equal stories[0:3] ids in order, and analyses has 3 entries each with title_kr, summary, reactions.positive/negative/interesting. Fix and re-validate if needed.
5. Send to Slack once: `python hn_digest.py send /tmp/hn_data.json /tmp/hn_result.json`.

Rules: do not commit, push, or open PRs. Do not modify repository files. If step 5 fails after the main message was posted, do NOT re-run it (that would post duplicates); just report the error. If any earlier step fails, stop and report the error without posting to Slack. Finish with a one-line report: number of stories, and whether Slack sending succeeded.
```

</details>

## 수동 실행

[claude.ai/code/routines](https://claude.ai/code/routines)의 routine 화면에서 즉시 실행하거나, Claude Code에서 `/schedule`로 routine 실행을 요청합니다. 실제 Slack에 게시됩니다.

## 로컬 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일 편집하여 실제 값 입력

# 수집만 (Slack 전송 없음)
python hn_digest.py collect /tmp/hn_data.json

# 결과 파일로 전송
python hn_digest.py send /tmp/hn_data.json /tmp/hn_result.json
```

## Anthropic API 방식 (기존)

인자 없이 실행하면 Anthropic API로 요약하는 기존 경로가 동작합니다. API 크레딧이 필요합니다.

```bash
python hn_digest.py
```

GitHub Actions 워크플로(`.github/workflows/hn-digest.yml`)는 이 경로를 사용하며 현재 비활성화되어 있습니다. 다시 쓰려면 저장소 Secrets에 `ANTHROPIC_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`를 등록하고 워크플로를 활성화합니다. routine과 동시에 켜면 중복 게시됩니다.

```bash
gh workflow enable "HN Daily Digest" --repo ssj5037/hn-summary
```

## 커스터마이징

`hn_digest.py`에서 다음 값 조정 가능:

```python
TOP_STORIES_COUNT = 30    # 수집할 스토리 개수
MIN_SCORE = 50            # 최소 점수 기준
COMMENT_FETCH_COUNT = 30  # 분석할 댓글 개수
```

## 라이선스

MIT
