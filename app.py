from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, StickerMessage, ImageMessage, 
    VideoMessage, LocationMessage, TextSendMessage, StickerSendMessage
)
from google import genai
import os
import json
import base64
import hashlib
import hmac

app = Flask(__name__)

# LINE Bot API設定
line_bot_api = LineBotApi('jwtR0XP77tYeS/TLH+mMy17zPQo+dyGXzengt4FBpE/d13GhfAS+gwHOftZzVpHSbNEWIK+oylXgy6MqnSGKzj4lUW5ubNiiwSoUR7uHj6/T/vu1JL+wC8SvXSTGEj+cswwglKmfiFlfsJy692kABAdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('f14f0b2b60c46355df297e112dfa348f')

# Gemini API設定
client = genai.Client(api_key="AIzaSyCZVRwyR7PP9vQltot84y9uFvMhhpm0dus")

# 儲存對話歷史的字典
conversation_history = {}

@app.after_request
def log_response(response):
    print(f"回應狀態碼: {response.status_code}")
    return response

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    # 手動驗證簽名（用於調試）
    channel_secret = 'f14f0b2b60c46355df297e112dfa348f'  # 替換為您的Channel Secret
    hash = hmac.new(channel_secret.encode('utf-8'),
                   body.encode('utf-8'), hashlib.sha256).digest()
    signature_calculated = base64.b64encode(hash).decode('utf-8')
    signature_received = request.headers['X-Line-Signature']
    
    print(f"Calculated signature: {signature_calculated}")
    print(f"Received signature: {signature_received}")
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_id = event.source.user_id
    user_message = event.message.text
    print(f"User ID: {user_id}")
    # 儲存用戶訊息到歷史記錄
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    
    conversation_history[user_id].append({"role": "user", "content": user_message})
    
    # 使用Gemini API生成回應
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[user_message]
        )
        ai_response = response.text
    except Exception as e:
        ai_response = f"抱歉，處理您的請求時出現錯誤: {str(e)}"

    
    # 儲存AI回應到歷史記錄
    conversation_history[user_id].append({"role": "model", "content": ai_response})
    
    # 回覆用戶
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=ai_response)
    )

@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker_message(event):
    # 回覆貼圖
    line_bot_api.reply_message(
        event.reply_token,
        StickerSendMessage(package_id=11537, sticker_id=52002734)
    )

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    user_id = event.source.user_id
    
    # 儲存用戶訊息到歷史記錄
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    
    conversation_history[user_id].append({"role": "user", "content": "[使用者傳送了一張圖片]"})
    
    # 回覆用戶
    response_text = "我收到了您的圖片！"
    
    # 儲存AI回應到歷史記錄
    conversation_history[user_id].append({"role": "model", "content": response_text})
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response_text)
    )

@handler.add(MessageEvent, message=VideoMessage)
def handle_video_message(event):
    user_id = event.source.user_id
    
    # 儲存用戶訊息到歷史記錄
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    
    conversation_history[user_id].append({"role": "user", "content": "[使用者傳送了一段影片]"})
    
    # 回覆用戶
    response_text = "我收到了您的影片！"
    
    # 儲存AI回應到歷史記錄
    conversation_history[user_id].append({"role": "model", "content": response_text})
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response_text)
    )

@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    user_id = event.source.user_id
    latitude = event.message.latitude
    longitude = event.message.longitude
    address = event.message.address
    
    # 儲存用戶訊息到歷史記錄
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    
    conversation_history[user_id].append({"role": "user", "content": f"[使用者分享了位置: {address}]"})
    
    # 回覆用戶
    response_text = f"您的位置是：{address}，座標：({latitude}, {longitude})"
    
    # 儲存AI回應到歷史記錄
    conversation_history[user_id].append({"role": "model", "content": response_text})
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response_text)
    )

# RESTful API for conversation history
@app.route("/history/<user_id>", methods=['GET'])
def get_history(user_id):
    if user_id in conversation_history:
        return jsonify(conversation_history[user_id])
    return jsonify([])

@app.route("/history/<user_id>", methods=['DELETE'])
def delete_history(user_id):
    if user_id in conversation_history:
        conversation_history.pop(user_id)
    return "History deleted"

if __name__ == "__main__":
    app.run(debug=True, port=8000)