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
import requests

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
    channel_secret = 'f14f0b2b60c46355df297e112dfa348f'
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

    # 檢查是否是特殊命令
    if user_message.lower() == "清除歷史":
        if user_id in conversation_history:
            conversation_history.pop(user_id)
        ai_response = "已清除您的對話歷史記錄！"
    # 檢查是否是天氣查詢
    elif "天氣" in user_message:
        # 嘗試提取地點
        location = extract_location(user_message)
        if location:
            weather_info = get_weather(location)
            ai_response = weather_info
        else:
            ai_response = "請提供您想查詢的地點，例如：「台北天氣」、「高雄天氣如何」等。"
    # 檢查是否是幫助命令
    elif user_message.lower() in ["幫助", "help", "指令"]:
        ai_response = "【指令說明】\n" + \
                     "1. 天氣查詢：輸入「XX天氣」，例如「台北天氣」\n" + \
                     "2. 清除歷史：輸入「清除歷史」\n" + \
                     "3. 一般對話：直接輸入您想問的問題\n" + \
                     "4. 查看歷史：可透過API查詢，或輸入「歷史記錄」"
    # 檢查是否是查詢歷史記錄
    elif user_message.lower() in ["歷史記錄", "歷史", "history"]:
        if user_id in conversation_history and len(conversation_history[user_id]) > 0:
            history_text = "【您的對話歷史】\n"
            for i, msg in enumerate(conversation_history[user_id]):
                role = "您" if msg["role"] == "user" else "AI"
                content = msg["content"]
                if len(content) > 50:  # 截斷過長的訊息
                    content = content[:47] + "..."
                history_text += f"{i+1}. {role}: {content}\n"
            ai_response = history_text
        else:
            ai_response = "您目前沒有對話歷史記錄。"
    else:
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


# 提取地點函數
def extract_location(text):
    # 這裡可以實現更複雜的地點提取邏輯
    # 簡單示例：假設地點在"天氣"前面
    locations = ["台北", "台中", "高雄", "新北", "桃園", "台南"]
    for loc in locations:
        if loc in text:
            return loc
    return None

# 獲取天氣資訊函數
def get_weather(location):
    # 這裡使用氣象API獲取天氣資訊
    # 替換為您的氣象API金鑰
    api_key = "CWA-99B5891C-3560-4EAD-8A40-779E7C09684E"
    url = f"https://opendata.cwb.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={api_key}&locationName={location}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        # 解析API回應並格式化天氣資訊
        weather_elements = data["records"]["location"][0]["weatherElement"]
        weather_state = weather_elements[0]["time"][0]["parameter"]["parameterName"]
        min_temp = weather_elements[2]["time"][0]["parameter"]["parameterName"]
        max_temp = weather_elements[4]["time"][0]["parameter"]["parameterName"]
        
        return f"{location}目前天氣狀況「{weather_state}」，溫度 {min_temp} 到 {max_temp} 度"
    except Exception as e:
        return f"抱歉，無法獲取{location}的天氣資訊：{str(e)}"
    
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