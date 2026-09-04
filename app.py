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

from aquaflow_api import check_bill, get_history

import os

from linebot.v3 import WebhookHandler  # type: ignore
from linebot.v3.messaging import (  # type: ignore
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    ImageMessage,
    FlexMessage,
    FlexContainer
)

from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    FollowEvent
)  # type: ignore

from linebot.v3.exceptions import InvalidSignatureError  # type: ignore


load_dotenv()

app = Flask(__name__)
init_db()


# =========================
# LINE CONFIGURATION
# =========================

configuration = Configuration(
    access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
)

handler = WebhookHandler(
    os.getenv("LINE_CHANNEL_SECRET")
)


# Public URL used by LINE to access our Flask Webview
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")

# Real AquaFlow API URL
AQUAFLOW_BASE_URL = os.getenv(
    "AQUAFLOW_BASE_URL",
    "https://aquaflow.sitthisaktdev.com"
)


# =========================
# HELPER FUNCTIONS
# =========================

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


def send_image_reply(reply_token, image_url):
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)

        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    ImageMessage(
                        original_content_url=image_url,
                        preview_image_url=image_url
                    )
                ]
            )
        )


def send_history_flex_reply(reply_token, history_url):
    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "ประวัติบิลย้อนหลัง",
                    "weight": "bold",
                    "size": "lg"
                },
                {
                    "type": "text",
                    "text": "ดูรายการบิลย้อนหลังของคุณได้ที่ปุ่มด้านล่าง",
                    "size": "sm",
                    "color": "#888888",
                    "wrap": True,
                    "margin": "md"
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "action": {
                        "type": "uri",
                        "label": "ดูประวัติย้อนหลัง",
                        "uri": history_url
                    }
                }
            ]
        }
    }

    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)

        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    FlexMessage(
                        alt_text="ดูประวัติบิลย้อนหลัง",
                        contents=FlexContainer.from_dict(bubble)
                    )
                ]
            )
        )


def get_status_text(status):
    """
    Convert AquaFlow API status into Thai text.
    """

    status_map = {
        "pending": "รอชำระ",
        "partial": "ชำระบางส่วน",
        "overdue": "ค้างชำระ",
        "paid": "จ่ายแล้ว",
        "waived": "ยกเว้น",
        "cancelled": "ยกเลิก"
    }

    return status_map.get(status, status)


def send_bill_flex_reply(reply_token, meter_number, bill):

    status = bill.get("status", "")
    status_text = get_status_text(status)

    is_overdue = status in ["pending", "partial", "overdue"]

    badge_color = "#c0392b" if is_overdue else "#2f8f4e"

    def row(label, value):
        return {
            "type": "box",
            "layout": "horizontal",
            "margin": "md",
            "contents": [
                {
                    "type": "text",
                    "text": label,
                    "size": "sm",
                    "color": "#888888",
                    "flex": 3
                },
                {
                    "type": "text",
                    "text": str(value),
                    "size": "sm",
                    "color": "#233044",
                    "flex": 5,
                    "wrap": True
                }
            ]
        }

    body_contents = [
        {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": "บิลน้ำประปา",
                    "weight": "bold",
                    "size": "lg",
                    "flex": 5
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": badge_color,
                    "cornerRadius": "20px",
                    "paddingAll": "6px",
                    "paddingStart": "12px",
                    "paddingEnd": "12px",
                    "flex": 3,
                    "contents": [
                        {
                            "type": "text",
                            "text": status_text,
                            "size": "xs",
                            "color": "#ffffff",
                            "align": "center",
                            "weight": "bold"
                        }
                    ]
                }
            ]
        },

        {
            "type": "separator",
            "margin": "md"
        },

        row("เลขผู้ใช้น้ำ", meter_number),

        row(
            "ยอดบิล",
            f"{bill.get('total_amount', 0)} บาท"
        ),

        row(
            "ยอดคงเหลือ",
            f"{bill.get('remaining', 0)} บาท"
        ),

        row(
            "กำหนดชำระ",
            bill.get("due_date_thai", bill.get("due_date", "-"))
        )
    ]

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents
        }
    }

    # Show QR button only when AquaFlow says QR is available
    if bill.get("qr_available"):

        bubble["footer"] = {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#2f6bb0",
                    "action": {
                        "type": "message",
                        "label": "ดู QR ชำระเงิน",
                        "text": "ดู QR"
                    }
                }
            ]
        }

    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)

        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    FlexMessage(
                        alt_text=(
                            f"สถานะบิล: {status_text} "
                            f"ยอดคงเหลือ {bill.get('remaining', 0)} บาท"
                        ),
                        contents=FlexContainer.from_dict(bubble)
                    )
                ]
            )
        )


# =========================
# LINE WEBHOOK
# =========================

@app.route("/callback", methods=["POST"])
def callback():

    signature = request.headers.get("X-Line-Signature")

    if not signature:
        abort(400)

    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)

    except InvalidSignatureError:
        abort(400)

    return "OK"


# =========================
# FOLLOW EVENT
# =========================

@handler.add(FollowEvent)
def handle_follow(event):

    send_reply(
        event.reply_token,
        "ขอบคุณที่เพิ่มเราเป็นเพื่อน\n"
        "กรุณาพิมพ์เลขผู้ใช้น้ำของคุณเพื่อดำเนินการต่อ"
    )


# =========================
# MESSAGE HANDLER
# =========================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    print("NEW HANDLER RECEIVED:", event.message.text)

    line_user_id = event.source.user_id
    user_message = event.message.text.strip()

    saved_meter = get_meter_number(line_user_id)


    # ==================================================
    # USER ALREADY HAS A SAVED METER NUMBER
    # ==================================================

    if saved_meter is not None:

        # ----------------------------------------------
        # CHECK BILL
        # ----------------------------------------------

        if user_message == "เช็คบิลของฉัน":

            try:
                data = check_bill(saved_meter)

            except Exception as e:
                print("AquaFlow API error:", e)

                send_reply(
                    event.reply_token,
                    "ไม่สามารถเชื่อมต่อระบบ AquaFlow ได้ในขณะนี้ "
                    "กรุณาลองใหม่อีกครั้ง"
                )
                return

            if data is None or data.get("bill") is None:

                send_reply(
                    event.reply_token,
                    "ไม่พบข้อมูลบิลล่าสุด"
                )
                return

            bill = data["bill"]

            send_bill_flex_reply(
                event.reply_token,
                saved_meter,
                bill
            )

            return


        # ----------------------------------------------
        # SHOW QR
        # ----------------------------------------------

        if user_message == "ดู QR":

            try:
                data = check_bill(saved_meter)

            except Exception as e:
                print("AquaFlow API error:", e)

                send_reply(
                    event.reply_token,
                    "ไม่สามารถเชื่อมต่อระบบ AquaFlow ได้ในขณะนี้ "
                    "กรุณาลองใหม่อีกครั้ง"
                )
                return

            if data is None or data.get("bill") is None:

                send_reply(
                    event.reply_token,
                    "ไม่พบข้อมูลบิล"
                )
                return

            bill = data["bill"]

            if not bill.get("qr_available"):

                send_reply(
                    event.reply_token,
                    "ไม่มี QR สำหรับบิลนี้ "
                    "(บิลนี้จ่ายแล้ว หรือยังไม่เปิดให้ชำระ)"
                )
                return

            # Use the REAL AquaFlow QR endpoint
            qr_url = (
                f"{AQUAFLOW_BASE_URL}/api/v1/public/qr/"
                f"{bill['id']}.png"
            )

            send_image_reply(
                event.reply_token,
                qr_url
            )

            return


        # ----------------------------------------------
        # HISTORY
        # ----------------------------------------------

        if user_message == "ประวัติย้อนหลัง":

            history_url = (
                f"{PUBLIC_BASE_URL}/webview/history"
                f"?meter={saved_meter}"
            )

            send_history_flex_reply(
                event.reply_token,
                history_url
            )

            return


        # ----------------------------------------------
        # CHANGE METER NUMBER
        # ----------------------------------------------

        if user_message == "เปลี่ยนเลขผู้ใช้น้ำ":

            delete_meter_number(line_user_id)

            send_reply(
                event.reply_token,
                "กรุณาพิมพ์เลขผู้ใช้น้ำใหม่ที่ต้องการบันทึก"
            )

            return


        # ----------------------------------------------
        # UNKNOWN MESSAGE
        # ----------------------------------------------

        send_reply(
            event.reply_token,
            f"เลขผู้ใช้น้ำที่บันทึกไว้: {saved_meter}\n"
            "พิมพ์ 'เช็คบิลของฉัน', "
            "'ประวัติย้อนหลัง' หรือ "
            "'เปลี่ยนเลขผู้ใช้น้ำ'"
        )

        return


    # ==================================================
    # NO SAVED METER NUMBER
    # ==================================================

    pending = get_pending(line_user_id)


    # ==================================================
    # PENDING METER CONFIRMATION
    # ==================================================

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
            f"พบเลขผู้ใช้น้ำ {pending['meter_number']} ในระบบ "
            "ยืนยันว่าถูกต้องหรือไม่?\n"
            "พิมพ์ 'ใช่' หรือ 'ไม่ใช่'"
        )

        return


    # ==================================================
    # NEW METER NUMBER
    # ==================================================

    try:
        data = check_bill(user_message)

    except Exception as e:
        print("AquaFlow API error:", e)

        send_reply(
            event.reply_token,
            "ไม่สามารถเชื่อมต่อระบบ AquaFlow ได้ในขณะนี้ "
            "กรุณาลองใหม่อีกครั้ง"
        )

        return


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
        f"พบเลขผู้ใช้น้ำ {user_message} ในระบบ "
        "ยืนยันว่าถูกต้องหรือไม่?\n"
        "พิมพ์ 'ใช่' หรือ 'ไม่ใช่'"
    )


# =========================
# HISTORY WEBVIEW
# =========================

@app.route("/webview/history")
def webview_history():

    meter_number = request.args.get("meter")

    if not meter_number:
        return "ไม่พบเลขผู้ใช้น้ำ", 400


    try:
        data = check_bill(meter_number)

    except Exception as e:
        print("AquaFlow API error:", e)

        return "ไม่สามารถเชื่อมต่อระบบ AquaFlow ได้", 503


    if data is None:
        return "ไม่พบข้อมูลผู้ใช้น้ำ", 404


    try:
        history_data = get_history(meter_number)

    except Exception as e:
        print("AquaFlow history API error:", e)

        return "ไม่สามารถโหลดประวัติบิลได้", 503


    if history_data is None:
        return "ไม่พบประวัติบิล", 404


    bills = history_data.get("bills", [])


    return render_template(
        "history.html",
        meter_number=meter_number,
        bills=bills
    )


# =========================
# START APPLICATION
# =========================

if __name__ == "__main__":
    print(app.url_map)
    app.run(port=5000)

