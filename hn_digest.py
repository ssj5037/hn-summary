"""
HN Daily Digest - Hacker News 인기 글을 수집하고 한글로 요약하여 Slack으로 전송
"""

import os
import json
import requests
from datetime import datetime
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
TOP_STORIES_COUNT = 30
MIN_SCORE = 50


def fetch_top_story_ids():
    """HN Top Stories ID 목록을 가져온다"""
    response = requests.get(f"{HN_API_BASE}/topstories.json", timeout=10)
    response.raise_for_status()
    return response.json()[:TOP_STORIES_COUNT]


def fetch_item(item_id):
    """개별 아이템 상세 정보를 가져온다"""
    response = requests.get(f"{HN_API_BASE}/item/{item_id}.json", timeout=10)
    response.raise_for_status()
    return response.json()


def fetch_top_stories():
    """상위 스토리들을 수집하고 점수 기준으로 필터링한다"""
    story_ids = fetch_top_story_ids()
    stories = []

    for story_id in story_ids:
        try:
            item = fetch_item(story_id)
            if item and item.get("type") == "story" and item.get("score", 0) >= MIN_SCORE:
                stories.append({
                    "id": item.get("id"),
                    "title": item.get("title", ""),
                    "url": item.get("url", f"https://news.ycombinator.com/item?id={item.get('id')}"),
                    "score": item.get("score", 0),
                    "descendants": item.get("descendants", 0),
                    "by": item.get("by", ""),
                })
        except requests.RequestException:
            continue

    # 점수 기준 내림차순 정렬
    stories.sort(key=lambda x: x["score"], reverse=True)
    return stories[:20]


def categorize_and_summarize(stories):
    """Claude API를 사용하여 스토리를 카테고리별로 분류하고 요약한다"""
    client = Anthropic()

    # TOP 3와 나머지 분리
    top3 = stories[:3]
    rest = stories[3:]

    top3_text = "\n\n".join([
        f"ID: {s['id']}\n제목: {s['title']}\n점수: {s['score']}점, 댓글: {s['descendants']}개"
        for s in top3
    ])

    rest_text = "\n\n".join([
        f"ID: {s['id']}\n제목: {s['title']}\n점수: {s['score']}점, 댓글: {s['descendants']}개"
        for s in rest
    ])

    prompt = f"""다음은 오늘의 Hacker News 인기 글 목록입니다.

## TOP 3 (상세 요약 필요)
{top3_text}

## 나머지 글 (카테고리 분류 필요)
{rest_text}

다음 JSON 형식으로 응답해주세요:

{{
  "top3": [
    {{
      "id": 글ID,
      "title_kr": "한글 제목",
      "summary": "2문장 이내 요약. 첫 문장은 팩트, 두번째는 의미/임팩트"
    }}
  ],
  "categories": {{
    "dev": [
      {{
        "id": 글ID,
        "title_kr": "한글 제목",
        "one_liner": "10자 내외 한줄 설명"
      }}
    ],
    "security": [...],
    "bigtech": [...],
    "misc": [...]
  }}
}}

카테고리 분류 기준:
- dev (개발자 픽): AI, 코딩, 개발도구, 프로그래밍 언어, 오픈소스
- security (보안/인프라): 취약점, 데이터 유출, 시스템, DevOps, Linux
- bigtech (빅테크/스타트업): 회사 뉴스, 인수합병, 제품 출시, 비즈니스
- misc (기타): 과학, 역사, 사회, 법률 등 위 카테고리에 안 맞는 것

규칙:
- 각 카테고리당 최대 3개까지만 (점수 높은 순)
- 해당 글이 없는 카테고리는 빈 배열로
- 반드시 유효한 JSON만 출력 (마크다운 코드블록 없이)
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    response_text = message.content[0].text.strip()
    # JSON 파싱
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]

    return json.loads(response_text), top3, rest


def get_hn_link(item_id):
    """HN 토론 페이지 링크를 반환한다"""
    return f"https://news.ycombinator.com/item?id={item_id}"


def format_slack_message(result, top3_stories, rest_stories):
    """Slack 메시지 형식으로 포맷팅한다"""
    today = datetime.now().strftime("%Y년 %m월 %d일")

    # TOP 3 ID -> 원본 스토리 매핑
    story_map = {s["id"]: s for s in top3_stories + rest_stories}

    # TOP 3 섹션
    medals = ["1", "2", "3"]
    top3_lines = []
    for i, item in enumerate(result["top3"]):
        story = story_map.get(item["id"], {})
        score = story.get("score", 0)
        comments = story.get("descendants", 0)
        hn_link = get_hn_link(item["id"])
        top3_lines.append(
            f"*{medals[i]}. {item['title_kr']}* ({score}점/{comments}댓글)\n"
            f"{item['summary']}\n"
            f"<{hn_link}|HN 토론 보기>"
        )

    top3_text = "\n\n".join(top3_lines)

    # 카테고리 섹션
    category_config = [
        ("dev", "개발자 픽"),
        ("security", "보안/인프라"),
        ("bigtech", "빅테크/스타트업"),
        ("misc", "기타 흥미로운 것"),
    ]

    category_sections = []
    for key, label in category_config:
        items = result["categories"].get(key, [])
        if not items:
            continue

        lines = []
        for item in items[:3]:
            story = story_map.get(item["id"], {})
            score = story.get("score", 0)
            hn_link = get_hn_link(item["id"])
            lines.append(f"• {item['title_kr']} - {item['one_liner']} ({score}점) <{hn_link}|링크>")

        category_sections.append(f"*{label}*\n" + "\n".join(lines))

    categories_text = "\n\n".join(category_sections)

    # Slack 메시지 구성
    message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"HN Daily - {today}",
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": top3_text
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": categories_text
                }
            }
        ]
    }

    return message


def send_to_slack(message):
    """Slack Webhook으로 메시지를 전송한다"""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("SLACK_WEBHOOK_URL 환경변수가 설정되지 않았습니다")

    response = requests.post(
        webhook_url,
        json=message,
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    response.raise_for_status()
    return response


def main():
    """메인 실행 함수"""
    print("HN 스토리 수집 중...")
    stories = fetch_top_stories()
    print(f"{len(stories)}개 스토리 수집 완료")

    if not stories:
        print("수집된 스토리가 없습니다")
        return

    print("Claude API로 카테고리 분류 및 요약 생성 중...")
    result, top3, rest = categorize_and_summarize(stories)
    print("요약 생성 완료")

    print("Slack 메시지 포맷팅 중...")
    message = format_slack_message(result, top3, rest)

    print("Slack으로 전송 중...")
    send_to_slack(message)
    print("전송 완료!")


if __name__ == "__main__":
    main()
