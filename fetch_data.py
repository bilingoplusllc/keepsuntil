# -*- coding: utf-8 -*-
"""Скачать USDA FoodKeeper и записать, ОТКУДА и КОГДА он взят.

ПОЧЕМУ ЭТОТ ФАЙЛ ЕСТЬ. Файл данных однажды уже лежал у нас в репозитории,
положенный туда руками, и ни один скрипт его не скачивал: локально всё
работало, а CI упал бы на первом же прогоне. Здесь скачивание — отдельный
явный шаг, и он оставляет след: адрес, дата, размер, отпечаток.

ПОЧЕМУ ДАННЫЕ ВСЁ РАВНО ЛЕЖАТ В РЕПОЗИТОРИИ. Сборка обязана быть
воспроизводимой и не зависеть от чужого сервера в момент выкладки. Поэтому
снимок закреплён в data/, обновляется НАМЕРЕННО этим скриптом, и на каждой
странице сайта стоит дата снимка. Автоматически обновляющийся источник тихо
переписал бы 226 страниц под чужие цифры.

ИСТОЧНИК НЕ ОТДАЁТСЯ СКРИПТУ. Проверено 01.09.2026: запрос из Python получает
403 и с браузерными заголовками тоже — защита смотрит не только на них. Файл
берётся браузером, по адресу, найденному в сетевых запросах самой страницы
FoodKeeper. Поэтому:

  · обновление данных — РУЧНОЙ шаг, `python fetch_data.py --manual` печатает
    процедуру и записывает провенанс по лежащему файлу;
  · CI НИЧЕГО НЕ КАЧАЕТ и запускает только `--verify`;
  · автоматическая попытка всё же есть: если однажды источник откроется, она
    сработает, а пока честно падает с объяснением.

Притворяться, что загрузка автоматизирована, было бы хуже, чем её отсутствие:
на несуществующий рычаг рассчитывают.
"""
import hashlib
import io
import json
import os
import sys
import urllib.request
from datetime import date, timezone, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RAW = os.path.join(DATA, "foodkeeper_raw.json")
META = os.path.join(DATA, "foodkeeper_meta.json")

URL = "https://www.foodsafety.gov/sites/default/files/foodkeeper_data_url_en.json"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/128.0.0.0 Safari/537.36"),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.foodsafety.gov/keep-food-safe/foodkeeper-app",
}

PROCEDURE = """Обновление данных FoodKeeper — руками:
  1. открыть https://www.foodsafety.gov/keep-food-safe/foodkeeper-app
  2. в сетевых запросах страницы найти foodkeeper_data_url_en.json
  3. сохранить ответ как data/foodkeeper_raw.json
  4. python fetch_data.py --manual   (запишет провенанс)
  5. сдвинуть DATA_VINTAGE и CONTENT_DATE в render.py
  6. python render.py && python gates.py
"""

MIN_PRODUCTS = 400          # источник даёт 661; резкое падение — не обновление


def fetch():
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def check_payload(raw):
    """Данные обязаны быть похожи на данные. Пустой или урезанный ответ,
    записанный поверх рабочего снимка, — худший вид обновления."""
    data = json.loads(raw.decode("utf-8"))
    if "product_data" not in data:
        raise SystemExit("в ответе нет product_data — это не FoodKeeper")
    n = len(data["product_data"])
    if n < MIN_PRODUCTS:
        raise SystemExit("продуктов %d, ожидалось не меньше %d — ответ урезан"
                         % (n, MIN_PRODUCTS))
    sample = data["product_data"][0]
    for field in ("id", "name", "category_name_display_only"):
        if field not in sample:
            raise SystemExit("в записи нет поля %s — формат изменился" % field)
    return n


def save(raw, n):
    if not os.path.isdir(DATA):
        os.makedirs(DATA)
    io.open(RAW, "wb").write(raw)
    today = datetime.now(timezone.utc).date()
    meta = {
        "url": URL,
        "retrieved": today.isoformat(),
        "bytes": len(raw),
        "products": n,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    io.open(META, "w", encoding="utf-8", newline="\n").write(
        json.dumps(meta, indent=1) + "\n")
    return meta


def verify():
    """Файл на диске — тот самый, что скачан, и дата на сайте — его дата.

    Эталон здесь не выведен из проверяемого: отпечаток записан в момент
    скачивания, а строка DATA_VINTAGE набирается руками в render.py. Проверка,
    сверяющая результат со своим же вводом, у нас уже была зелёной на
    прошлогодних данных.
    """
    if not os.path.isfile(META):
        raise SystemExit("нет foodkeeper_meta.json — запустите fetch_data.py")
    meta = json.load(io.open(META, encoding="utf-8"))
    raw = io.open(RAW, "rb").read()
    got = hashlib.sha256(raw).hexdigest()
    if got != meta["sha256"]:
        raise SystemExit("файл данных отличается от скачанного: %s против %s"
                         % (got[:12], meta["sha256"][:12]))
    sys.path.insert(0, HERE)
    import render as rd
    d = date.fromisoformat(meta["retrieved"])
    want = d.strftime("%-d %B %Y") if os.name != "nt" else \
        "%d %s %d" % (d.day, d.strftime("%B"), d.year)
    if want not in rd.DATA_VINTAGE:
        raise SystemExit("на сайте написано «%s», а снимок от %s"
                         % (rd.DATA_VINTAGE, want))
    print("данные: %d продуктов, %d байт, снимок от %s, отпечаток %s"
          % (meta["products"], meta["bytes"], meta["retrieved"],
             meta["sha256"][:12]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--verify" in sys.argv:
        verify()
    elif "--manual" in sys.argv:
        raw = io.open(RAW, "rb").read()
        n = check_payload(raw)
        meta = save(raw, n)
        print("провенанс записан по лежащему файлу:")
        print("  %d продуктов, %d байт, отпечаток %s, снимок от %s"
              % (n, meta["bytes"], meta["sha256"][:12], meta["retrieved"]))
        print("сдвиньте DATA_VINTAGE и CONTENT_DATE в render.py под эту дату")
    else:
        print(PROCEDURE)
        try:
            raw = fetch()
        except Exception as e:
            raise SystemExit("автоматическая загрузка не прошла (%s). "
                             "Обновляйте вручную по процедуре выше." % e)
        n = check_payload(raw)
        meta = save(raw, n)
        print("скачано: %d продуктов, %d байт, отпечаток %s"
              % (n, meta["bytes"], meta["sha256"][:12]))
        print("сдвиньте DATA_VINTAGE и CONTENT_DATE в render.py")
