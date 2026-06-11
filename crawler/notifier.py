"""
crawler/notifier.py — отправка уведомлений в Telegram.

Использует только requests (уже установлен), без сторонних библиотек.
"""
import re
import requests
import logging

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class Notifier:
    def __init__(self, token: str, chat_id: str):
        self.token   = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id)

        if not self.enabled:
            logger.info("Telegram не настроен — уведомления отключены")

    def _send(self, text: str):
        """Отправляет сообщение в Telegram. Ошибки не роняют краулер."""
        if not self.enabled:
            return

        try:
            url  = TELEGRAM_API.format(token=self.token)
            resp = requests.post(url, json={
                "chat_id":    self.chat_id,
                "text":       text,
                "parse_mode": "HTML",   # поддержка <b>, <i>, <code>
            }, timeout=10)

            if not resp.ok:
                logger.warning(f"Telegram ошибка: {resp.status_code} {resp.text}")
            else:
                logger.info("  📨 Telegram уведомление отправлено")

        except Exception as e:
            # Никогда не роняем краулер из-за уведомлений
            logger.warning(f"Не удалось отправить уведомление: {e}")

    # ─────────────────────────────────────────────
    # Публичные методы — вызываются из price_checker
    # ─────────────────────────────────────────────

    def price_dropped(self, shop: str, old_price: str, new_price: str, diff: int, url: str):
        """Цена упала — самое важное уведомление."""
        text = (
            f"🔥 <b>Цена упала!</b>\n\n"
            f"Магазин: <b>{shop}</b>\n"
            f"Было:    <code>{old_price}</code>\n"
            f"Стало:   <code>{new_price}</code>\n"
            f"Скидка:  <b>−{diff:,}₽</b>\n\n"
            f"<a href='{url}'>Открыть страницу</a>"
        ).replace(",", " ")
        self._send(text)

    def new_historic_minimum(self, shop: str, price: str, url: str):
        """Новый исторический минимум."""
        text = (
            f"🏆 <b>Новый исторический минимум!</b>\n\n"
            f"Магазин: <b>{shop}</b>\n"
            f"Цена:    <code>{price}</code>\n\n"
            f"<a href='{url}'>Открыть страницу</a>"
        )
        self._send(text)

    def daily_summary(self, product_name: str, results: list[dict], best: dict):
        """
        Итоговая сводка после каждого запуска.
        results — список словарей с ключами: магазин, цена, товар
        best    — словарь с лучшей ценой
        """
        if not results:
            self._send("⚠️ Цены не найдены ни в одном магазине.")
            return

        # Строим таблицу цен
        lines = []
        for r in sorted(results, key=lambda x: _price_to_int(x["цена"])):
            lines.append(f"  • {r['магазин']}: <code>{r['цена']}</code>")

        text = (
            f"📊 <b>{product_name}</b>\n\n"
            + "\n".join(lines)
            + f"\n\n🏆 Лучшая: <b>{best['цена']}</b> в {best['магазин']}"
        )
        self._send(text)


def _price_to_int(price: str) -> int:
    digits = re.sub(r"[^\d]", "", price)
    return int(digits) if digits else 0