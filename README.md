# HN Daily Digest

매일 아침 Hacker News 인기 글을 수집하고 한글로 요약하여 Slack으로 전송합니다.

## 기능

- HN Top Stories 상위 30개 수집 후 점수 기준 상위 20개 선별
- TOP 3 글은 상세 요약 + HN 커뮤니티 반응 분석
- 나머지 글은 카테고리별 분류 (개발/보안/빅테크/기타)
- **메인 메시지 + 스레드 답글 구조**로 깔끔한 정보 전달
- GitHub Actions로 매일 오전 9시(KST) 자동 실행

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

## 설정 방법

### 1. 저장소 Clone

```bash
git clone https://github.com/ssj5037/hn-summary.git
cd hn-summary
```

### 2. Slack Bot 생성

1. [Slack API](https://api.slack.com/apps)에서 새 앱 생성
2. **OAuth & Permissions**에서 Bot Token Scopes 추가:
   - `chat:write`
3. **Install to Workspace** 클릭
4. Bot User OAuth Token (xoxb-...) 복사
5. Slack 채널에서 `/invite @봇이름`으로 봇 초대
6. 채널 ID 확인 (채널 우클릭 > 링크 복사 > URL에서 C로 시작하는 ID)

### 3. GitHub Secrets 설정

GitHub 저장소 Settings > Secrets and variables > Actions에서:

| 이름 | 설명 |
|------|------|
| `ANTHROPIC_API_KEY` | Anthropic Claude API 키 |
| `SLACK_BOT_TOKEN` | Slack Bot Token (xoxb-...) |
| `SLACK_CHANNEL_ID` | Slack 채널 ID (C...) |

### 4. Anthropic API 키 발급

1. [Anthropic Console](https://console.anthropic.com/)에서 계정 생성
2. API Keys 메뉴에서 새 키 생성
3. GitHub Secret에 등록

## 로컬 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일 편집하여 실제 값 입력

# 실행
python hn_digest.py
```

## 수동 실행

GitHub Actions 탭에서 "Run workflow" 버튼으로 수동 실행 가능

## 커스터마이징

`hn_digest.py`에서 다음 값 조정 가능:

```python
TOP_STORIES_COUNT = 30    # 수집할 스토리 개수
MIN_SCORE = 50            # 최소 점수 기준
COMMENT_FETCH_COUNT = 30  # 분석할 댓글 개수
```

## 라이선스

MIT
