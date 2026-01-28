"""
HN Daily Digest - Hacker News 인기 글을 수집하고 한글로 요약하여 Slack으로 전송
메인 메시지 + 스레드 답글 구조로 상세 요약과 HN 반응 제공
"""

import os
import re
import json
import time
import requests
from datetime import datetime
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
TOP_STORIES_COUNT = 30
MIN_SCORE = 50
COMMENT_FETCH_COUNT = 30


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
                    "kids": item.get("kids", []),
                })
        except requests.RequestException:
            continue

    stories.sort(key=lambda x: x["score"], reverse=True)
    return stories[:20]


def fetch_comments(story):
    """스토리의 상위 댓글들을 가져온다"""
    comment_ids = story.get("kids", [])[:COMMENT_FETCH_COUNT]
    comments = []

    for cid in comment_ids:
        try:
            time.sleep(0.1)  # rate limit 고려
            comment = fetch_item(cid)
            if comment and comment.get("text") and not comment.get("deleted"):
                # HTML 태그 제거
                text = re.sub(r"<[^>]+>", "", comment["text"])
                text = text.replace("&#x27;", "'").replace("&quot;", '"').replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")
                comments.append(text)
        except requests.RequestException:
            continue

    return comments


def get_hn_link(item_id):
    """HN 토론 페이지 링크를 반환한다"""
    return f"https://news.ycombinator.com/item?id={item_id}"


def categorize_stories(stories):
    """Claude API를 사용하여 스토리를 카테고리별로 분류한다"""
    client = Anthropic()

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

## TOP 3
{top3_text}

## 나머지 글
{rest_text}

다음 JSON 형식으로 응답해주세요:

{{
  "top3": [
    {{
      "id": 글ID,
      "title_kr": "한글 제목"
    }}
  ],
  "categories": {{
    "dev": [
      {{
        "id": 글ID,
        "title_kr": "한글 제목"
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
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]

    return json.loads(response_text), top3, rest


def analyze_story_with_comments(story, comments):
    """Claude API를 사용하여 스토리 내용과 댓글을 분석한다"""
    client = Anthropic()

    comments_text = "\n\n---\n\n".join(comments[:20]) if comments else "댓글 없음"

    prompt = f"""다음은 Hacker News 글과 해당 댓글들입니다.

## 글 정보
제목: {story['title']}
URL: {story['url']}
점수: {story['score']}점
댓글 수: {story['descendants']}개

## 댓글들
{comments_text}

다음 JSON 형식으로 응답해주세요:

{{
  "title_kr": "한글 제목",
  "summary": "3~5문장으로 글의 핵심 내용 요약. 제목과 댓글 내용을 바탕으로 이 글이 무엇에 대한 것인지 설명",
  "reactions": {{
    "positive": ["긍정적 의견 1", "긍정적 의견 2"],
    "negative": ["부정적/우려 의견 1", "부정적/우려 의견 2"],
    "interesting": ["흥미로운 의견 1", "흥미로운 의견 2"]
  }}
}}

규칙:
- summary는 한국어로 작성, 기술 용어는 영어 유지 가능
- reactions의 각 항목은 한국어로 한 문장으로 요약
- 해당 반응이 없으면 빈 배열로
- 댓글이 없으면 reactions는 모두 빈 배열로
- 반드시 유효한 JSON만 출력 (마크다운 코드블록 없이)
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]

    return json.loads(response_text)


def format_main_message(result, top3_stories, rest_stories):
    """메인 Slack 메시지를 포맷팅한다"""
    today = datetime.now().strftime("%Y년 %m월 %d일")
    story_map = {s["id"]: s for s in top3_stories + rest_stories}

    # TOP 3 섹션
    medals = ["1.", "2.", "3."]
    top3_lines = []
    for i, item in enumerate(result["top3"]):
        story = story_map.get(item["id"], {})
        score = story.get("score", 0)
        comments = story.get("descendants", 0)
        hn_link = get_hn_link(item["id"])
        top3_lines.append(
            f"*{medals[i]} {item['title_kr']}* ({score}점/{comments}댓글)\n"
            f"   {hn_link}"
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
            lines.append(f"• {item['title_kr']} ({score}점) {hn_link}")

        category_sections.append(f"*{label}*\n" + "\n".join(lines))

    categories_text = "\n\n".join(category_sections)

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
            },
            {
                "type": "divider"
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "상세 요약 + HN 반응은 스레드에서 확인하세요"
                    }
                ]
            }
        ]
    }

    return message


def format_thread_message(rank, story, analysis):
    """스레드 답글 메시지를 포맷팅한다"""
    rank_emoji = ["1", "2", "3"][rank]
    hn_link = get_hn_link(story["id"])

    # 반응 섹션 구성
    reactions_parts = []

    if analysis["reactions"].get("positive"):
        positive_lines = "\n".join([f"• {r}" for r in analysis["reactions"]["positive"]])
        reactions_parts.append(f"*긍정적 반응:*\n{positive_lines}")

    if analysis["reactions"].get("negative"):
        negative_lines = "\n".join([f"• {r}" for r in analysis["reactions"]["negative"]])
        reactions_parts.append(f"*부정적/우려:*\n{negative_lines}")

    if analysis["reactions"].get("interesting"):
        interesting_lines = "\n".join([f"• {r}" for r in analysis["reactions"]["interesting"]])
        reactions_parts.append(f"*흥미로운 의견:*\n{interesting_lines}")

    reactions_text = "\n\n".join(reactions_parts) if reactions_parts else "아직 주요 댓글이 없습니다."

    text = f"""*{rank_emoji}. {analysis['title_kr']}*
원문: {story['url']}
HN 토론: {hn_link}

*내용 요약*
{analysis['summary']}

*HN 반응*
{reactions_text}"""

    return {"text": text}


def send_slack_message(message, thread_ts=None):
    """Slack API로 메시지를 전송한다"""
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    channel_id = os.getenv("SLACK_CHANNEL_ID")

    if not bot_token:
        raise ValueError("SLACK_BOT_TOKEN 환경변수가 설정되지 않았습니다")
    if not channel_id:
        raise ValueError("SLACK_CHANNEL_ID 환경변수가 설정되지 않았습니다")

    payload = {
        "channel": channel_id,
        **message
    }

    if thread_ts:
        payload["thread_ts"] = thread_ts

    response = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={
            "Authorization": f"Bearer {bot_token}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=10
    )
    response.raise_for_status()

    result = response.json()
    if not result.get("ok"):
        raise ValueError(f"Slack API 오류: {result.get('error')}")

    return result


def main():
    """메인 실행 함수"""
    print("HN 스토리 수집 중...")
    stories = fetch_top_stories()
    print(f"{len(stories)}개 스토리 수집 완료")

    if not stories:
        print("수집된 스토리가 없습니다")
        return

    print("카테고리 분류 중...")
    result, top3_stories, rest_stories = categorize_stories(stories)
    print("분류 완료")

    print("메인 메시지 전송 중...")
    main_message = format_main_message(result, top3_stories, rest_stories)
    main_response = send_slack_message(main_message)
    thread_ts = main_response["ts"]
    print(f"메인 메시지 전송 완료 (ts: {thread_ts})")

    # TOP 3 상세 분석 및 스레드 답글
    for i, story in enumerate(top3_stories):
        print(f"TOP {i+1} 댓글 수집 중...")
        comments = fetch_comments(story)
        print(f"  {len(comments)}개 댓글 수집")

        print(f"TOP {i+1} 분석 중...")
        analysis = analyze_story_with_comments(story, comments)

        print(f"TOP {i+1} 스레드 답글 전송 중...")
        thread_message = format_thread_message(i, story, analysis)
        send_slack_message(thread_message, thread_ts)
        print(f"TOP {i+1} 전송 완료")

        time.sleep(1)  # Slack rate limit 고려

    print("모든 작업 완료!")


if __name__ == "__main__":
    main()
