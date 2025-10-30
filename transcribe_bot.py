import os
import requests
import sys
import whisper  # الذكاء الاصطناعي الذي يقوم بالتفريغ
import json # <-- إضافة مهمة لمعالجة الأخطاء

# --- 1. الإعدادات ---
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']
except KeyError:
    print("!!! خطأ فادح: لم يتم العثور على BOT_TOKEN.")
    print("يرجى التأكد من إضافته إلى GitHub Secrets في المستودع الجديد.")
    sys.exit(1)

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
OFFSET_FILE = "update_offset.txt" # ملف نصي بسيط لحفظ "أين توقفنا"

# --- 2. دوال مساعدة (تيليجرام) ---

def get_offset():
    """قراءة آخر update_id قمنا بمعالجته"""
    try:
        with open(OFFSET_FILE, 'r') as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return 0 # ابدأ من الصفر إذا كان الملف غير موجود
    except ValueError:
        return 0 # ابدأ من الصفر إذا كان الملف فارغاً أو تالفاً

def save_offset(new_offset):
    """حفظ آخر update_id للتشغيل القادم (بعد 5 دقائق)"""
    with open(OFFSET_FILE, 'w') as f:
        f.write(str(new_offset))

def send_telegram_message(chat_id, text, reply_to_message_id):
    """إرسال رسالة نصية كرد"""
    payload = {
        'chat_id': chat_id,
        'text': text,
        'reply_to_message_id': reply_to_message_id
    }
    try:
        response = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)
        response.raise_for_status() # التأكد من عدم وجود خطأ 400 أو 500
        print(f"أرسل بنجاح رسالة إلى {chat_id}")
    except requests.exceptions.RequestException as e:
        print(f"!!! فشل إرسال الرسالة: {e}")
        try:
            # محاولة طباعة رسالة الخطأ من تيليجرام إذا أمكن
            print(f"تفاصيل الخطأ من تيليجرام: {e.response.text}")
        except Exception:
            pass # فشل في طباعة التفاصيل

def get_file_path(file_id):
    """الحصول على المسار المؤقت للملف الصوتي من تيليجرام"""
    try:
        response = requests.get(f"{TELEGRAM_API_URL}/getFile?file_id={file_id}")
        response.raise_for_status()
        file_path = response.json()['result']['file_path']
        return file_path
    except Exception as e:
        print(f"!!! فشل الحصول على مسار الملف: {e}")
        return None

def download_audio_file(file_path):
    """تحميل الملف الصوتي وحفظه كـ 'audio.ogg'"""
    try:
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        response = requests.get(file_url)
        response.raise_for_status()
        with open("audio.ogg", "wb") as f:
            f.write(response.content)
        print("...تم تحميل الملف الصوتي بنجاح.")
        return "audio.ogg"
    except Exception as e:
        print(f"!!! فشل تحميل الملف الصوتي: {e}")
        return None

# --- 3. دالة التفريغ (الذكاء الاصطناعي) ---

def transcribe_audio(file_path):
    """المهمة الثقيلة: استخدام Whisper لتحويل الصوت إلى نص"""
    print("...جارٍ تحميل نموذج الذكاء الاصطناعي (base)...")
    # نستخدم نموذج "base"، وهو صغير وسريع ومناسب لخوادم GitHub
    model = whisper.load_model("base")
    print("...بدء عملية التفريغ الصوتي...")
    
    try:
        result = model.transcribe(file_path, fp16=False) # fp16=False لمزيد من التوافق
        transcribed_text = result["text"]
        print("...اكتمل التفريغ الصوتي بنجاح.")
        return transcribed_text
    except Exception as e:
        print(f"!!! فشل التفريغ الصوتي (Whisper): {e}")
        return None
    finally:
        # تنظيف الملف الصوتي بعد الانتهاء
        if os.path.exists(file_path):
            os.remove(file_path)

# --- 4. "العقل" الرئيسي (الذي يعمل كل 5 دقائق) ---

def main():
    print("--- بدء 'بوت التفريغ الصوتي' (v1.1) ---")
    current_offset = get_offset()
    
    print(f"جاري فحص 'صندوق البريد' (الرسائل بعد: {current_offset})...")
    
    try:
        # زيادة مهلة الانتظار (long polling) إلى 30 ثانية
        response = requests.get(f"{TELEGRAM_API_URL}/getUpdates?offset={current_offset + 1}&timeout=30", timeout=40)
        response.raise_for_status()
        updates = response.json().get('result', [])
    except Exception as e:
        print(f"!!! فشل الاتصال بتيليجرام (getUpdates): {e}")
        return # توقف إذا لم نتمكن من الاتصال

    if not updates:
        print("...لا توجد رسائل جديدة. الخروج.")
        return

    print(f"تم العثور على {len(updates)} رسالة/رسائل جديدة. جاري المعالجة...")
    
    new_max_offset = current_offset
    
    for update in updates:
        # التأكد من أن المفتاح موجود قبل استخدامه
        if 'update_id' in update:
            new_max_offset = update['update_id'] # تحديث المعرف الأخير الذي رأيناه
        
        message = update.get('message')
        if not message:
            continue
            
        chat_id = message['chat']['id']
        message_id = message['message_id']
        voice = message.get('voice')

        if voice:
            print(f"تم العثور على رسالة صوتية من {chat_id} (المدة: {voice['duration']} ثانية)")
            
            # الخطوة 1: إرسال رسالة "تأكيد" (لأن المهمة ثقيلة)
            send_telegram_message(
                chat_id,
                f"✅ تم استلام رسالتك الصوتية (المدة: {voice['duration']} ثانية).\nجاري المعالجة... قد يستغرق هذا 5 دقائق (حسب وقت استيقاظ البوت).",
                message_id
            )

            # الخطوة 2: تحميل الملف
            file_id = voice['file_id']
            file_path_from_tg = get_file_path(file_id)
            if not file_path_from_tg:
                continue
                
            local_audio_file = download_audio_file(file_path_from_tg)
            if not local_audio_file:
                continue
                
            # الخطوة 3: التفريغ (المهمة الثقيلة)
            transcribed_text = transcribe_audio(local_audio_file)
            
            if transcribed_text and transcribed_text.strip():
                # الخطوة 4: إرسال النتيجة
                send_telegram_message(
                    chat_id,
                    f"🎉 اكتمل التفريغ الصوتي:\n\n---\n{transcribed_text}\n---",
                    message_id
                )
            else:
                send_telegram_message(
                    chat_id,
                    "❌ عذراً، لم أتمكن من تفريغ هذا الملف الصوتي. (ربما كان صامتاً؟)",
                    message_id
                )
        
    # حفظ آخر معرف رأيناه للتشغيل القادم
    save_offset(new_max_offset)
    print("--- اكتملت دورة الفحص. ---")

if __name__ == "__main__":
    main()

