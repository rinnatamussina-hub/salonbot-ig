import os, json, requests, re
from flask import Flask, request
from openai import OpenAI

# ----------- Config -----------
VERIFY_TOKEN      = os.getenv("VERIFY_TOKEN", "rinnata_verify")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")  # set later in Render
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")

BOOKING_LINK = "https://dikidi.ru/946726?p=2.pi-po-ssm&o=7"
MAPS_LINK    = "https://maps.app.goo.gl/wT6cVGeWgWH2XHeF7"
ADDRESS      = "Bağlarbaşı mahallesi Atatürk caddesi Omay pasajı No:56 A blok Daire 50 Maltepe/İstanbul, Turkey"
WORK_HOURS   = "Мы открыты с понедельника по субботу с 10:00 до 20:00"
PHONE        = "+90 538 251 09 23"

# Create OpenAI client (NO proxies arg)
client = OpenAI(api_key=OPENAI_API_KEY)

# =======================
# Language detection & texts
# =======================
def detect_lang(text: str) -> str:
    t = text.lower()
    # If contains Cyrillic -> ru
    if re.search(r"[а-яё]", t):
        return "ru"
    # Turkish specific letters/words
    if re.search(r"[çğıöşüİ]", t) or any(w in t for w in [
        "merhaba", "selam", "randevu", "fiyat", "adres", "çalışma", "saat", "müsait", "boş", "masaj"
    ]):
        return "tr"
    # Default policy: try Turkish first (per studio rule)
    return "tr"

def T(key: str, lang: str) -> str:
    RU = {
        "greet": (
            "Добрый день 🌿 Вас приветствует Yelena Heal Aura Studio!\n"
            "Добро пожаловать 🤍\n"
            "Пожалуйста, задайте свой вопрос — мы поделимся всей нужной информацией.\n\n"
            f"📌 Записаться к нам: {BOOKING_LINK}\n"
            f"📍 Где мы находимся: {ADDRESS}\n"
            f"👉 {MAPS_LINK}\n"
            f"📞 Связаться с нами: {PHONE}"
        ),
        "booking": f"Для записи, цен и свободных окошек используйте онлайн-запись 👉 {BOOKING_LINK}",
        "services": f"Все услуги и описания доступны в онлайн-записи 👉 {BOOKING_LINK}",
        "prices":   f"Актуальные цены смотрите в онлайн-записи 👉 {BOOKING_LINK}",
        "reviews":  f"Отзывы клиентов доступны по ссылке онлайн-записи 👉 {BOOKING_LINK}",
        "address":  f"Адрес: {ADDRESS}\nКарта 👉 {MAPS_LINK}",
        "hours":    WORK_HOURS,
        "thanks":   "Спасибо вам 🤍 Ждём снова в Yelena Heal Aura Studio.",
        "fallback": f"Записаться онлайн и посмотреть цены/свободные окошки можно здесь 👉 {BOOKING_LINK}",
    }
    TR = {
        "greet": (
            "Merhaba 🌿 Yelena Heal Aura Studio'ya hoş geldiniz! 🤍\n"
            "Sorularınızı bize yazabilirsiniz.\n\n"
            f"📌 Randevu: {BOOKING_LINK}\n"
            f"📍 Adresimiz: {ADDRESS}\n"
            f"👉 {MAPS_LINK}\n"
            f"📞 İletişim: {PHONE}"
        ),
        "booking": f"Randevu, fiyatlar ve boş saatler için çevrim içi sayfayı kullanın 👉 {BOOKING_LINK}",
        "services": f"Tüm hizmetlerimiz ve açıklamaları çevrim içi randevuda 👉 {BOOKING_LINK}",
        "prices":   f"Güncel fiyatları buradan görebilirsiniz 👉 {BOOKING_LINK}",
        "reviews":  f"Müşteri yorumları için çevrim içi sayfayı ziyaret edin 👉 {BOOKING_LINK}",
        "address":  f"Adres: {ADDRESS}\nHarita 👉 {MAPS_LINK}",
        "hours":    "Çalışma saatlerimiz: Pazartesi–Cumartesi 10:00–20:00.",
        "thanks":   "Teşekkür ederiz 🤍 Yelena Heal Aura Studio'da tekrar görüşmek üzere.",
        "fallback": f"Randevu ve uygun saatleri görmek için 👉 {BOOKING_LINK}",
    }
    return (TR if lang == "tr" else RU)[key]

# =======================
# Patterns & rules
# =======================
TR_GREETINGS = [
    "merhaba", "selam", "iyi günler", "günaydın", "iyi akşamlar", "slm", "mrb"
]
RU_GREETINGS = [
    "привет", "здравствуйте", "добрый день", "добрый вечер", "доброе утро", "салам"
]

def handle_greetings(text: str, lang: str) -> str | None:
    t = text.lower().strip()
    if lang == "tr":
        if any(g in t for g in TR_GREETINGS) or t in ["👋","✋","🤚"]:
            return T("greet", "tr")
    else:
        if any(g in t for g in RU_GREETINGS) or t in ["👋","✋","🤚"]:
            return T("greet", "ru")
    return None

def route_intent(text: str) -> str | None:
    lang = detect_lang(text)
    t = text.lower()

    # Availability / booking / slots
    if any(w in t for w in [
        "окошк","свободн","есть ли время","время есть","расписание","записаться","запись",
        "slot","müsait","boş","uygun","randevu","randevu almak","saat","takvim"
    ]):
        return T("booking", lang)

    # Services
    if any(w in t for w in ["какие массаж", "виды массажа", "услуг", "массаж", "массаже", "hizmet", "masaj", "çeşit"]):
        return T("services", lang)

    # Prices
    if any(w in t for w in ["цена","стоим","сколько стоит","прайс","fiyat","ücret","ücretler"]):
        return T("prices", lang)

    # Reviews
    if any(w in t for w in ["отзыв","рейтинг","review","yorum","değerlendirme"]):
        return T("reviews", lang)

    # Address / location
    if any(w in t for w in ["адрес","где вы","как пройти","локац","место","adres","konum","nereye","neredesiniz"]):
        return T("address", lang)

    # Working hours
    if any(w in t for w in ["график","режим","часы","во сколько","когда открыты","çalışma saat","kaçta","açık"]):
        return T("hours", lang)

    # Thanks
    if any(w in t for w in ["спасибо","благодар","teşekkür","sağ ol","sagol"]):
        return T("thanks", lang)

    # Generic salon keywords -> helpful fallback
    if any(w in t for w in ["массаж","salon","studio","yelena","heal","aura","dikidi","massage","istanbul","масаж"]):
        return T("fallback", lang)

    return None  # let GPT decide or stay silent

# ----------- GPT rules -----------
def build_system_prompt():
    return f"""
Ты — вежливый и внимательный ассистент салона массажа «Yelena Heal Aura Studio».
Отвечай дружелюбно и по делу, без лишней воды. Используй максимум 2 уместных эмодзи.

📌 ОБЩИЕ ПРАВИЛА:
1) Если вопрос про запись, цены, услуги или отзывы — всегда указывай ссылку:
   «Смотрите актуальные цены, свободные окошки и отзывы по ссылке 👉 {BOOKING_LINK}»
2) Если клиент спрашивает про адрес — давай полный адрес + ссылку на Google Maps:
   «{ADDRESS}
   👉 {MAPS_LINK}»
3) График работы:
   «Мы открыты с понедельника по субботу с 10:00 до 20:00».
4) Язык:
   - Если клиент пишет на турецком — отвечай на турецком.
   - Если на русском — отвечай на русском.
   - Если язык непонятен — ответь сначала по-турецки, ниже по-русски.
5) Если клиент благодарит — отвечай:
   «Спасибо вам 🤍 Ждём снова в Yelena Heal Aura Studio».
6) Если вопрос не связан с салоном, услугами, ценами, адресом, записью или благодарностью — НЕ отвечай вообще.
   В таком случае верни строго строку: NO_REPLY
7) Никогда не придумывай цены и услуги — отправляй только на ссылку с онлайн-записью.
"""

def ask_gpt(user_text: str) -> str:
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content": build_system_prompt()},
                {"role":"user","content": user_text.strip()}
            ],
            temperature=0.2,
            max_tokens=350
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI error:", e)
        return "NO_REPLY"

# ----------- Flask -----------
app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    return "OK", 200

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    # Verify
    if request.method == "GET":
        mode      = request.args.get("hub.mode")
        token     = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Forbidden", 403

    # Receive
    data = request.get_json(silent=True) or {}
    print("INCOMING:", json.dumps(data, ensure_ascii=False))

    for entry in data.get("entry", []):
        for messaging in entry.get("messaging", []):
            # ignore non-message events
            if "message" not in messaging:
                continue

            sender_id = (messaging.get("sender") or {}).get("id")
            msg_obj   = messaging.get("message") or {}

            # Ignore echo/test messages
            if msg_obj.get("is_echo"):
                continue

            text = (msg_obj.get("text") or "").strip()
            if not (sender_id and text):
                continue

            # 1) Language
            lang = detect_lang(text)

            # 2) Greetings first (fixed welcome)
            g = handle_greetings(text, lang)
            if g:
                send_text(sender_id, g)
                continue

            # 3) Rule-based intents (booking, services, etc.)
            rb = route_intent(text)
            if rb:
                send_text(sender_id, rb)
                continue

            # 4) Fallback to GPT (if still relevant)
            reply = ask_gpt(text)
            print("REPLY_FROM_GPT:", reply)
            if reply and reply.strip() != "NO_REPLY":
                send_text(sender_id, reply)

    return "EVENT_RECEIVED", 200

def send_text(psid: str, text: str):
    if not PAGE_ACCESS_TOKEN:
        print("WARN: PAGE_ACCESS_TOKEN is not set")
        return
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    payload = {
        "recipient": {"id": psid},
        "messaging_type": "RESPONSE",
        "message": {"text": text}
    }
    try:
        r = requests.post(url, params=params, json=payload, timeout=15)
        print("SEND STATUS:", r.status_code, r.text)
    except Exception as e:
        print("Send error:", e)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
