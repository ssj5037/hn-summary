# HN Daily Digest

매일 아침 Hacker News 인기 글을 수집하고 한글로 요약하여 Slack으로 전송합니다.

## 기능

- HN Top Stories 상위 30개 수집
- 50점 이상 글만 필터링하여 상위 20개 선별
- Claude API로 각 글을 한글 요약
- Slack Webhook으로 결과 전송
- GitHub Actions로 매일 오전 9시(KST) 자동 실행

## 설정 방법

### 1. 저장소 Fork 또는 Clone

```bash
git clone <your-repo-url>
cd hn-summary
```

### 2. GitHub Secrets 설정

GitHub 저장소 Settings > Secrets and variables > Actions에서 다음 시크릿 추가:

| 이름 | 설명 |
|------|------|
| `ANTHROPIC_API_KEY` | Anthropic Claude API 키 |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL |

### 3. Slack Webhook 생성

1. [Slack API](https://api.slack.com/apps)에서 새 앱 생성
2. Incoming Webhooks 활성화
3. 원하는 채널에 Webhook 추가
4. Webhook URL 복사하여 GitHub Secret에 등록

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
TOP_STORIES_COUNT = 30  # 수집할 스토리 개수
MIN_SCORE = 50          # 최소 점수 기준
```

## 라이선스

MIT
