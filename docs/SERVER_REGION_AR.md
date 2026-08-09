# ملاحظة مهمة بخصوص منطقة السيرفر و Quotex

إذا ظهر عند تسجيل الدخول خطأ مثل:

```text
Service unavailable: Quotex is not available in your region (United States)
```

فهذا ليس خطأ في التطبيق، بل لأن الـ Backend منشور في سيرفر داخل الولايات المتحدة مثل Render/Railway US.

## الحل الصحيح

لازم تنشر الـ Backend في سيرفر/VPS بمنطقة مسموحة من Quotex، مثل:

- Germany
- France
- Netherlands
- UK
- أو أي دولة يشتغل فيها Quotex مع حسابك

## لماذا؟

تسجيل الدخول إلى Quotex يتم من الـ Backend وليس من الهاتف. لذلك Quotex يرى IP السيرفر، وليس IP هاتفك.

## كيف تستعمل سيرفرك الخاص؟

1. ارفع المستودع على السيرفر.
2. ثبت Docker.
3. شغل:

```bash
docker build -t quotex-bot-app .
docker run -d --name quotex-bot-app -p 8000:8000 quotex-bot-app
```

4. افتح:

```text
http://YOUR_SERVER_IP:8000/health
```

5. في التطبيق افتح Settings وضع:

```text
http://YOUR_SERVER_IP:8000
```

أو إذا عندك دومين و SSL:

```text
https://your-domain.com
```

## ملاحظة

Render/Railway إذا كانت منطقتهم United States قد لا تصلح لتسجيل الدخول في Quotex.
