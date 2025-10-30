name: Audio Transcription Bot (v1.0 - 5min check)

on:
  workflow_dispatch: # يتيح لك التشغيل اليدوي (للاختبار)
  
  schedule:
    # هذا هو "المُشغّل التلقائي" (خدعة صندوق البريد)
    # هو "يستيقظ" كل 5 دقائق
    - cron: '*/5 * * * *'

jobs:
  build:
    runs-on: ubuntu-latest

    env:
      # هذا يقرأ "الرمز" السري الذي أضفته
      BOT_TOKEN: ${{ secrets.BOT_TOKEN }}

    steps:
      - name: 1. Checkout Repository
        uses: actions/checkout@v4

      - name: 2. Set up Python 3.10
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      # هذه الخطوة "حاسمة" جداً
      # مكتبة Whisper (الذكاء الاصطناعي) تحتاج إلى "ffmpeg" لقراءة الملفات الصوتية
      - name: 3. Install ffmpeg
        run: sudo apt-get update && sudo apt-get install -y ffmpeg

      - name: 4. Install Python Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: 5. Run the Transcription Bot Script
        run: python transcribe_bot.py
