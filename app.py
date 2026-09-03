from flask import Flask, request, abort, render_template
from dotenv import load_dotenv  # type: ignore
from db import init_db, get_meter_number, save_meter_number
from mock_aquaflow import check_bill_mock,get_history_mock
import os
import logging

from linebot.v3 import WebhookHandler  # type: ignore[import-not-found]
from linebot.v3.messaging import (  # type: ignore[import-not-found]
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)

from linebot.v3.webhooks import MessageEvent, TextMessageContent  # type: ignore[import-not-found]
from linebot.v3.exceptions import InvalidSignatureError  # type: ignore[import-not-found]

load_dotenv()

app = Flask(__name__)
init_db()

configuration = Configuration(
    access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
)

handler = WebhookHandler(
    os.getenv("LINE_CHANNEL_SECRET")
)

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", )

    if not signature:
        abort(400,)

    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    user_message = event.message.text

    reply = f"You said: {user_message}"

    with ApiClient(configuration) as api_client:

        messaging_api = MessagingApi(api_client)

        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text=reply)
                ]
            )
        )

@app.route("/webview/history")
def webview_history():
    meter_number = request.args.get("meter")

    if not meter_number:
        return "ไม่พบเลขผู้ใช้น้ำ", 400

    data = check_bill_mock(meter_number)

    if data is None:
        return "ไม่พบข้อมูลผู้ใช้น้ำ", 404

    bills = get_history_mock(meter_number)

    if bills is None:
        return "ไม่พบประวัติบิล", 404

    return render_template(
        "history.html",
        meter_number=meter_number,
        bills=bills
    )


print(app.url_map)

if __name__ == "__main__":
    app.run(port=5000)