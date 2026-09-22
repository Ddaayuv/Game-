TELEGRAM QR BOT - RAILWAY

المتطلبات:
- حساب Railway
- Telegram Bot Token من @BotFather

المشروع:
- PHP 8.3
- Apache
- Dockerfile
- Railway config
- Telegram Webhook
- QR PNG حقيقي

خطوات Railway:

1) ارفع المشروع إلى GitHub.
2) في Railway اختر New Project ثم Deploy from GitHub Repo.
3) اختر المستودع.
4) Railway سيكتشف Dockerfile تلقائياً.
5) من Variables أضف:
   BOT_TOKEN = توكن البوت
   PUBLIC_URL = رابط Railway العام

مثال PUBLIC_URL:
https://your-app.up.railway.app

6) بعد Deploy، افتح:
   https://your-app.up.railway.app/health.php
   يجب أن تظهر:
   Telegram QR Bot is running.

7) بعد معرفة PUBLIC_URL، افتح:
   https://your-app.up.railway.app/webhook.php

إذا ظهر:
{"ok":true,"result":true}
فقد تم ربط Webhook.

بعدها افتح البوت وأرسل /start ثم أي نص أو رابط.

مهم:
PUBLIC_URL يجب أن يكون HTTPS وأن يكون رابط Railway العام، بدون / في النهاية.

QR:
يتم إنشاء صورة PNG حقيقية بواسطة QR Server API ثم إرسالها إلى Telegram.
