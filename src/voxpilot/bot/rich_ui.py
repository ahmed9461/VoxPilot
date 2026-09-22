from __future__ import annotations

from aiogram.types import InputRichMessage


def home_card() -> InputRichMessage:
    return InputRichMessage(
        is_rtl=True,
        html=(
            "<h2>🎙 VoxPilot</h2>"
            "<p>تحويل النص إلى صوت واستنساخ الأصوات باستخدام Fish Audio S2 Pro.</p>"
            "<p>احفظ صوتًا مرجعيًا، جهّز سيرفرًا، ثم أرسل النص مباشرة.</p>"
            "<details><summary>التحكم الصوتي</summary>"
            "<ul><li>مشاعر ونبرات Fish الأصلية</li><li>إعدادات التوليد</li><li>أكثر من صوت محفوظ</li></ul>"
            "</details>"
            "<footer>السيرفر المؤقت يُدار بالكامل من الأزرار.</footer>"
        ),
    )
