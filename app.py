from flask import Flask, request, abort, render_template
from dotenv import load_dotenv  # type: ignore
from db import (
    init_db,
    get_meter_number,
    save_meter_number,
    delete_meter_number,
    save_pending,
    get_pending,
    clear_pending
)
from mock_aquaflow import check_bill_mock, get_history_mock
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

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")

def send_reply(reply_token, text):
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)

        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(text=text)
                ]
            )
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
    print("NEW HANDLER RECEIVED:", event.message.text)

    line_user_id = event.source.user_id
    user_message = event.message.text.strip()

    saved_meter = get_meter_number(line_user_id)

    if saved_meter is not None:

        if user_message == "เช็คบิลของฉัน":

            data = check_bill_mock(saved_meter)

            if data is None or data.get("bill") is None:
                send_reply(
                    event.reply_token,
                    "ไม่พบข้อมูลบิลล่าสุด"
                )
                return

            bill = data["bill"]
            resident = data["resident"]
            garbage_fee = resident.get("garbage_fee", 0.0)

            reply = (
                f"เลขผู้ใช้น้ำ: {saved_meter}\n"
                f"สถานะ: {bill['status']}\n"
                f"ยอด: {bill['amount']} บาท\n"
                f"ค่าขยะ: {garbage_fee} บาท\n"
                f"กำหนดชำระ: {bill['due_date']}"
            )

            if bill.get("qr_available"):
                reply += "\n\nQR Code พร้อมใช้งาน"

            send_reply(event.reply_token, reply)
            return

        if user_message == "ประวัติย้อนหลัง":

            history_url = (
                f"{PUBLIC_BASE_URL}/webview/history?meter={saved_meter}"
            )

            send_reply(
                event.reply_token,
                f"ดูประวัติบิลย้อนหลังได้ที่:\n{history_url}"
            )
            return

        if user_message == "เปลี่ยนเลขผู้ใช้น้ำ":

            delete_meter_number(line_user_id)

            send_reply(
                event.reply_token,
                "กรุณาพิมพ์เลขผู้ใช้น้ำใหม่ที่ต้องการบันทึก"
            )
            return

        send_reply(
            event.reply_token,
            f"เลขผู้ใช้น้ำที่บันทึกไว้: {saved_meter}\n"
            "พิมพ์ 'เช็คบิลของฉัน', "
            "'ประวัติย้อนหลัง' หรือ "
            "'เปลี่ยนเลขผู้ใช้น้ำ'"
        )
        return

    pending = get_pending(line_user_id)

    if pending is not None:

        if user_message == "ใช่":

            save_meter_number(
                line_user_id,
                pending["meter_number"]
            )

            clear_pending(line_user_id)

            send_reply(
                event.reply_token,
                f"บันทึกเรียบร้อย สวัสดีคุณ "
                f"{pending['resident_name']}\n"
                "พิมพ์ 'เช็คบิลของฉัน' "
                "เพื่อดูสถานะบิล"
            )
            return

        if user_message == "ไม่ใช่":

            clear_pending(line_user_id)

            send_reply(
                event.reply_token,
                "ไม่ได้บันทึกข้อมูล "
                "กรุณาพิมพ์เลขผู้ใช้น้ำใหม่อีกครั้ง"
            )
            return

        send_reply(
            event.reply_token,
            f"นี่คือบัญชีของ {pending['resident_name']} ใช่ไหม?\n"
            "พิมพ์ 'ใช่' หรือ 'ไม่ใช่'"
        )
        return

    data = check_bill_mock(user_message)

    if data is None:

        send_reply(
            event.reply_token,
            "ไม่พบเลขผู้ใช้น้ำนี้ "
            "กรุณาลองพิมพ์ใหม่อีกครั้ง"
        )
        return

    resident_name = data["resident"]["full_name"]

    save_pending(
        line_user_id,
        user_message,
        resident_name
    )

    send_reply(
        event.reply_token,
        f"นี่คือบัญชีของ {resident_name} ใช่ไหม?\n"
        "พิมพ์ 'ใช่' หรือ 'ไม่ใช่'"
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