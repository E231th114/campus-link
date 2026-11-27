"""Explicitly seed Campus Link with presentation data.

Run locally with ``python scripts/seed_demo.py``. Azure requires ``--azure``.
The script never runs as part of Flask startup or CI.
"""
import argparse
import io
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

import app  # noqa: E402
from services.discussion import RECOMMENDED  # noqa: E402

DEMO_ID = "campus-link-demo-v1"
JST = timezone(timedelta(hours=9))

TOPICS = {
    "勉強": [
        ("定期テスト、何から復習してる？", "そら", "間違えた問題だけを小さいノートにまとめて、次の日にもう一度解いています。"),
        ("英単語がなかなか覚えられません", "みなと", "朝の通学中に10個ずつ見ています。書くのと声に出すの、どっちが覚えやすいですか？"),
        ("数学の苦手を克服したい", "ゆず", "二次関数でいつも止まります。おすすめの練習の進め方があれば知りたいです。"),
        ("集中力が続く方法ありますか？", "あおい", "25分だけタイマーをかけると少しやりやすかったです。みんなの方法も聞きたいです。"),
        ("使いやすい参考書を教えて", "ノート", "高校一年生です。授業の復習に向いている、説明がわかりやすい本を探しています。"),
    ],
    "課題": [
        ("レポートのまとめ方がわからない", "ひなた", "調べたことを並べるだけになってしまいます。段落の作り方のコツを教えてください。"),
        ("Python課題のエラー相談", "コード好き", "リストの中身を順番に表示したいのですが、結果が空になります。考え方だけ教えてほしいです。"),
        ("グループワークの役割分担", "みつき", "得意なことが違うメンバーで、最初に決めておくとよいことはありますか？"),
        ("プレゼン資料の文字量について", "レモン", "1枚に文章を詰めすぎてしまいます。発表用ならどれくらいが見やすいでしょうか。"),
        ("課題の予定をどう管理してる？", "たくみ", "提出日を忘れがちなので、部活がある日でも続けやすい方法を探しています。"),
    ],
    "進路": [
        ("大学と専門学校の違いを知りたい", "りん", "学び方や卒業後の進路がどう違うのか、実際に調べた人の話を聞きたいです。"),
        ("オープンキャンパスの選び方", "ふうか", "気になる学校がいくつかあります。設備以外に見ておくポイントはありますか？"),
        ("面接の練習、何を話せばいい？", "はる", "志望理由を話すと長くなります。短くまとめる練習方法を知りたいです。"),
        ("情報系に進むなら今やること", "りく", "プログラミングを始めたばかりです。高校生のうちに勉強しておくとよい分野はありますか？"),
        ("資格は取ったほうがいい？", "かえで", "興味のある資格が二つあります。学校の勉強と両立した人の時間配分を聞きたいです。"),
    ],
    "部活動": [
        ("勉強と部活を両立するコツ", "あき", "帰宅が遅い日の勉強時間が短くなります。朝に勉強している人はいますか？"),
        ("練習メニューを変えたい", "スパイク", "同じ練習が続いているので、短時間でも集中できるメニューを相談したいです。"),
        ("大会前の緊張をどうしてる？", "しおり", "本番で頭が真っ白になります。試合前にやっているルーティンがあれば教えてください。"),
        ("部活選びで迷っています", "みどり", "運動部と文化部で迷っています。見学ではどんなところを見ましたか？"),
        ("引退後の時間の使い方", "かなた", "急に時間が増えて少し落ち着きません。受験や趣味に切り替えた方法を聞きたいです。"),
    ],
    "相談": [
        ("クラスで話しかけるきっかけ", "こはる", "休み時間に何を話せばよいか迷います。自然に会話を始める方法はありますか？"),
        ("人前で話すのが苦手です", "ひかり", "発表の順番が近づくと緊張します。少し楽になった練習があれば知りたいです。"),
        ("学校生活の時間管理", "つむぎ", "やりたいことが多くて寝る時間が遅くなります。予定を詰めすぎない工夫を教えてください。"),
        ("新しい友達の作り方", "あんず", "クラス替えをきっかけに話せる人を増やしたいです。最初の一言が難しいです。"),
        ("やる気が出ない日の過ごし方", "なぎ", "何もしたくない日に最低限やることを決めている人がいたら聞きたいです。"),
    ],
    "雑談": [
        ("文化祭でできそうな企画", "まつり", "教室を使って、準備が大変すぎない企画を考えています。去年好評だったものはありますか？"),
        ("最近よく聴く音楽ある？", "イヤホン", "勉強の合間に聴ける曲を探しています。歌詞ありでも集中できる曲が知りたいです。"),
        ("昼休みは何して過ごす？", "おにぎり", "教室で話す以外の過ごし方も知りたいです。短時間でできることありますか？"),
        ("学校生活で便利なアプリ", "アプリ部", "予定を忘れないために使っているアプリがあれば、使い方と一緒に教えてください。"),
        ("休日の過ごし方がマンネリ", "休日派", "お金をかけずに気分転換できることを探しています。みんなの定番を教えてください。"),
    ],
}

ANSWERS = [
    ("みなみ", "まず小さく区切ると続けやすかったです。"),
    ("はるき", "自分は紙に書き出してから順番を決めています。"),
    ("ことね", "それなら一度試して、合うかどうかで決めるのがよさそうです。"),
    ("そら", "ありがとう、今日からやってみます！"),
]


def image_bytes(label):
    image = Image.new("RGB", (1200, 700), "#f4f4f4")
    draw = ImageDraw.Draw(image)
    draw.rectangle((70, 70, 1130, 630), outline="#171717", width=4)
    draw.text((110, 110), "Campus Link / demo", fill="#171717")
    draw.text((110, 290), label, fill="#171717")
    output = io.BytesIO()
    image.save(output, "JPEG", quality=88)
    return output.getvalue()


def seed(store, count_per_category=None):
    now = int(time.time())
    total = 0
    answer_total = 0
    for category, topics in TOPICS.items():
        for index, (title, author, text) in enumerate(topics[:count_per_category or len(topics)]):
            key = f"demo-{category}-{index}"
            # Re-running is idempotent because the same partition/row is used.
            posted = now - ((index * 19 + len(category) * 3) * 3600)
            deadline = 0
            paused = False
            if index == 1:
                deadline = now + 3 * 86400
            elif index == 2:
                deadline = now + 20 * 60
            elif index == 3:
                deadline = now - 3600
            elif index == 4:
                paused = True
            store.put("board", key, {
                "title": title, "name": author, "text": text, "category": category,
                "owner": "demo-owner", "posted_at": datetime.fromtimestamp(posted, JST).strftime("%Y/%m/%d %H:%M:%S"),
                "image": category in ("課題", "雑談") and index == 0,
                "demo": DEMO_ID, "deadline": deadline,
            })
            store.put("deadlines", key, {"deadline": deadline, "paused": paused, "demo": DEMO_ID})
            if category in ("課題", "雑談") and index == 0:
                store.picture(key, image_bytes("demo: " + title))
            for answer_index in range((index + len(category)) % 4):
                answer_key = f"demo-{category}-{index}-answer-{answer_index}"
                store.put("comment", answer_key, {"post": key, "name": ANSWERS[answer_index][0],
                    "text": ANSWERS[answer_index][1], "posted_at": datetime.fromtimestamp(posted + (answer_index + 1) * 900, JST).strftime("%Y/%m/%d %H:%M:%S"), "demo": DEMO_ID})
                answer_total += 1
            for like_index in range((index * 7 + len(category)) % 31):
                store.put("like", f"{key}-demo-like-{like_index}", {"post": key, "demo": DEMO_ID})
            if index % 3 == 0:
                code = list(RECOMMENDED)[index % len(RECOMMENDED)]
                for reaction_index in range(1 + index % 4):
                    owner = f"demo-viewer-{reaction_index}"
                    store.put("emoji-" + key, f"{owner}-{code}-1", {"owner": owner, "emoji": code, "revision": 1, "active": True, "created": posted, "demo": DEMO_ID})
            if index == 0 and category in ("勉強", "進路"):
                store.put("resolved", key, {"post": key, "demo": DEMO_ID})
            total += 1
    return total, answer_total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--azure", action="store_true", help="use Azure Storage instead of local SQLite")
    parser.add_argument("--count", type=int, choices=range(5, 9), help="posts per category")
    args = parser.parse_args()
    if args.azure and not os.getenv("AZURE_STORAGE_CONNECTION_STRING") and not os.getenv("AZURE_STORAGE_ACCOUNT"):
        parser.error("Azure credentials are missing")
    if not args.azure and app.cloud:
        parser.error("App Service detected. Use --azure explicitly to seed cloud data.")
    store = app.Azure() if args.azure else app.Local(app.directory)
    total, answers = seed(store, args.count)
    print(f"demo seed complete: {total} posts, {answers} answers")


if __name__ == "__main__":
    main()
