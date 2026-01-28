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


def summarize_stories(stories):
    """Claude API를 사용하여 스토리들을 한글로 요약한다"""
    client = Anthropic()

    stories_text = "\n\n".join([
        f"제목: {s['title']}\nURL: {s['url']}\n점수: {s['score']}점, 댓글: {s['descendants']}개"
        for s in stories
    ])

    prompt = f"""다음은 오늘의 Hacker News 인기 글 목록입니다.
각 글의 제목을 보고 한글로 간단히 요약해주세요.

요약 형식:
- 각 글마다 1-2줄로 핵심 내용을 설명
- 기술적인 용어는 그대로 유지
- 개발자가 관심 가질만한 포인트 강조

글 목록:
{stories_text}

각 글을 다음 형식으로 요약해주세요:
1. [제목 한글 번역/설명] - 간단한 설명 (점수/댓글수)
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return message.content[0].text


def format_slack_message(summary, stories):
    """Slack 메시지 형식으로 포맷팅한다"""
    today = datetime.now().strftime("%Y년 %m월 %d일")

    # 상위 5개 글의 링크 포함
    top_links = "\n".join([
        f"• <{s['url']}|{s['title']}> ({s['score']}점)"
        for s in stories[:5]
    ])

    message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"HN Daily Digest - {today}",
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*오늘의 인기 글 TOP 5*"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": top_links
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*요약*\n{summary}"
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

    print("Claude API로 요약 생성 중...")
    summary = summarize_stories(stories)
    print("요약 생성 완료")

    print("Slack 메시지 포맷팅 중...")
    message = format_slack_message(summary, stories)

    print("Slack으로 전송 중...")
    send_to_slack(message)
    print("전송 완료!")


if __name__ == "__main__":
    main()
