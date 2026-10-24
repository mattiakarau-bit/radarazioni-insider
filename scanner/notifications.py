"""Optional free Telegram notification. GitHub Secrets never go to the public site."""
import json
import os
import urllib.parse
import urllib.request


def send_telegram(item: dict) -> bool:
    token, chat_id = os.getenv('TELEGRAM_BOT_TOKEN'), os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        return False
    if item.get('analysis', {}).get('buy_signal'):
        raise ValueError('Questo scanner non invia raccomandazioni automatiche di acquisto')
    msg = (f"🔎 RadarAzioni · DA APPROFONDIRE (non BUY)\n"
           f"{item['symbol']} — {item['company']}\n"
           f"Insider: {item['insider']} | codice P: ${item['amount']:,.0f}\n"
           f"Punteggio di screening: {item['analysis']['score']}/100\n"
           f"SEC: {item['form_url']}\n"
           f"Prezzo/valutazione e modello ML ancora non verificati.")
    body = urllib.parse.urlencode({'chat_id': chat_id, 'text': msg,
                                    'disable_web_page_preview': 'true'}).encode()
    req = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage', data=body, method='POST')
    with urllib.request.urlopen(req, timeout=20) as response:
        result = json.load(response)
    if not result.get('ok'):
        raise RuntimeError('Telegram non ha confermato la consegna')
    return True
