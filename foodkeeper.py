# -*- coding: utf-8 -*-
"""Слой данных KeepsUntil: разбор FoodKeeper и то, чего в нём НЕТ.

Что даёт источник. USDA FoodKeeper — 661 продукт, и для каждого до девяти
ячеек с диапазонами вида «3 - 5 Weeks», «1 - 2 Days», «Not Recommended».
Это справочник: он говорит, сколько хранится, и не говорит больше ничего.

Что считаем мы, и чего нет ни у источника, ни у конкурентов:

  · РАЗНИЦА между способами. «Заморозка даёт в 12 раз дольше, чем холодильник» —
    это отношение двух диапазонов, и его в FoodKeeper нет;
  · ЦЕНА ВСКРЫТИЯ. Насколько короче живёт вскрытая упаковка. Тоже отношение;
  · МЕСТО В КАТЕГОРИИ. Этот продукт хранится дольше или меньше соседей по
    полке — сортировка по нижней границе внутри категории;
  · ДАТА, а не срок. Диапазон в днях превращается в две календарные даты.

Ни одна из этих величин не переписана — все четыре вычислены. Это и есть то,
что отделяет справочник от копии справочника: [PLAYBOOK §1], правило трёх
вычисленных фактов.

ЧТО ДЕЛАЕМ С «Not Recommended». Это не ноль и не отсутствие данных, а
отдельный ответ: «так хранить не нужно». Ноль означал бы «портится мгновенно»,
пустота — «мы не знаем». Три разных состояния, и путать их нельзя.
"""
import collections
import io
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "foodkeeper_raw.json")

# Единицы FoodKeeper в днях. Месяц — 30, год — 365: округление объявлено здесь
# один раз, а не пересчитывается в каждом месте по-своему.
UNIT_DAYS = {
    "day": 1, "days": 1,
    "week": 7, "weeks": 7,
    "month": 30, "months": 30,
    "year": 365, "years": 365,
    "hour": 1 / 24.0, "hours": 1 / 24.0,
}

# Девять ячеек источника. Порядок — от самого щадящего хранения к самому
# короткому сроку; он же порядок колонок в таблице на странице.
SLOTS = [
    ("freeze", "freeze_output_display_only", "В морозилке"),
    ("freeze_purchase", "from_date_of_purchase_freeze_output_display_only",
     "В морозилке, от дня покупки"),
    ("pantry", "pantry_output_display_only", "В шкафу"),
    ("pantry_purchase", "from_date_of_purchase_pantry_output_display_only",
     "В шкафу, от дня покупки"),
    ("pantry_open", "pantry_after_opening_output_display_only",
     "В шкафу после вскрытия"),
    ("fridge", "refrigerate_output_display_only", "В холодильнике"),
    ("fridge_purchase", "from_date_of_purchase_refrigerate_output_display_only",
     "В холодильнике, от дня покупки"),
    ("fridge_open", "refrigerate_after_opening_output_display_only",
     "В холодильнике после вскрытия"),
    ("fridge_thaw", "refrigerate_after_thawing_output_display_only",
     "В холодильнике после разморозки"),
]

# ВСЕ ШЕСТЬ полей свободного текста источника, каждое привязано к своей
# ячейке. Читались три из шести, и вместе с остальными тремя пропадала
# единственная настоящая инструкция по безопасности на своей странице:
# «It is not safe to cook and eat a whole lobster if it is dead at the time
# of preparation.» Подсказка — не срок, но она и не украшение.
TIP_FIELDS = (
    ("pantry", "pantry_tips"),
    ("pantry_purchase", "from_date_of_purchase_pantry_tips"),
    ("fridge", "refrigerate_tips"),
    ("fridge_purchase", "from_date_of_purchase_refrigerate_tips"),
    ("freeze", "freeze_tips"),
    ("freeze_purchase", "from_date_of_purchase_freeze_tips"),
)

NOT_RECOMMENDED = "not recommended"

# Ответы источника, которые НЕ ЧИСЛО, но и не пустота. Их было 63 ячейки, и
# парсер возвращал на них None — а страница печатала после этого «no pantry
# figure exists for it». Источник дал ответ; он просто не был числом.
# «Indefinitely» — самый обнадёживающий ответ во всём наборе, и он удалялся.
SAYS = {
    "package use-by date": "label",
    "indefinitely": "indefinite",
    "when ripe": "ripe",
    # Опечатка САМОГО источника. Читать её как «1 Year» значит дописать за
    # USDA то, чего он не написал: печатаем как непрочитанное, с исходной
    # строкой. Безымянное не выбрасывается — оно называется.
    "1 yea": "unreadable",
}


class UnknownCell(ValueError):
    """Пятая нечисловая строка в новом снимке обязана ронять сборку, а не
    исчезать: молча пропавшая ячейка — это страница, которая утверждает, что
    источник промолчал."""


def _parse_range(text):
    """«3 - 5 Weeks» -> (21, 35). «Not Recommended» -> ("no", None).

    Возвращает (низ, верх) в днях, либо ("no", None) для «так не хранят»,
    либо ("says", код) для нечислового ответа источника, либо None, если
    ячейка пуста. Состояния РАЗНЫЕ: ноль означал бы «портится мгновенно»,
    пустота — «мы не знаем», «no» — «так хранить не надо», «says» — «ответ
    есть, но он не число».

    На нераспознанной непустой строке ПАДАЕТ: см. UnknownCell.
    """
    if not text:
        return None
    t = text.strip()
    if not t:
        return None
    if NOT_RECOMMENDED in t.lower():
        return ("no", None)
    code = SAYS.get(t.lower())
    if code:
        return ("says", code)
    m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(?:-|to|–)?\s*"
                 r"([0-9]+(?:\.[0-9]+)?)?\s*([A-Za-z]+)", t)
    unit = UNIT_DAYS.get(m.group(3).lower()) if m else None
    if unit is None:
        raise UnknownCell(
            "источник напечатал %r, и это не срок, не «not recommended» и не "
            "один из объявленных нечисловых ответов" % t)
    lo = float(m.group(1))
    hi = float(m.group(2)) if m.group(2) else lo
    return (lo * unit, hi * unit, m.group(3).lower().rstrip("s") + "s")


def _num(days):
    """Дни человеческими словами. Округление одно и здесь."""
    if days is None:
        return None
    if days < 1:
        return "%d ч" % round(days * 24)
    if days < 14:
        return "%d дн." % round(days)
    if days < 60:
        return "%d нед." % round(days / 7.0)
    if days < 365:
        return "%d мес." % round(days / 30.0)
    y = days / 365.0
    return "%s года" % (("%.1f" % y).replace(".", ",")) if y < 5 else "%d лет" % round(y)


def load():
    """Прочитать источник и посчитать по нему то, чего в нём нет."""
    raw = json.load(io.open(RAW, encoding="utf-8"))
    out = []
    for p in raw["product_data"]:
        item = {
            "id": p["id"],
            "name": (p.get("name") or "").strip(),
            "subtitle": (p.get("name_subtitle") or "").strip(),
            "category": (p.get("category_name_display_only") or "").strip(),
            "subcategory": (p.get("subcategory_name_display_only") or "").strip(),
            "keywords": [k.strip() for k in (p.get("keywords") or "").split(",")
                         if k.strip()],
            "slots": {},
            "units": {},
            "says": {},
            "tips": {},
        }
        for key, field, _label in SLOTS:
            v = _parse_range(p.get(field))
            if v is None:
                continue
            if v[0] == "says":
                # Нечисловой ответ живёт ОТДЕЛЬНО от сроков: он печатается
                # словами и никогда не попадает ни в одно отношение.
                item["says"][key] = (v[1], (p.get(field) or "").strip())
                continue
            item["slots"][key] = v[:2]
            # Единица, В КОТОРОЙ ЕЁ НАПЕЧАТАЛ ИСТОЧНИК. Тридцать дней — это
            # «1 month» или «30 days» в зависимости от того, что там стояло,
            # и угадывать по величине значит однажды показать «4 weeks» рядом
            # с посчитанной по тем же данным кратностью 4,3.
            if len(v) > 2:
                item["units"][key] = v[2]
        for key, field in TIP_FIELDS:
            tip = (p.get(field) or "").strip()
            if tip:
                item["tips"][key] = tip
        out.append(item)
    return out


# ------------------------------------------------------------- вычисления

def best(item, *keys):
    """Лучший (самый длинный) срок среди перечисленных ячеек.

    Берём верхнюю границу: «3-5 недель» сравниваем по пяти. Нижняя нужна для
    осторожного ответа, верхняя — для сравнения способов между собой.
    """
    vals = []
    for k in keys:
        v = item["slots"].get(k)
        if v and v[0] != "no":
            vals.append(v)
    if not vals:
        return None
    return max(vals, key=lambda x: x[1])


def unit_of(item, key):
    """Единица, в которой источник напечатал эту ячейку. Без неё тридцать дней
    печатаются то месяцем, то четырьмя неделями, смотря кто печатает."""
    return item["units"].get(key) if key else None


def best_key(item, *keys):
    """Тот же выбор, что и best, но с названием выигравшей ячейки: без него
    неизвестно, в какой единице источник напечатал найденное число."""
    best_k, best_v = None, None
    for k in keys:
        v = item["slots"].get(k)
        if v and v[0] != "no":
            if best_v is None or v[1] > best_v[1]:
                best_k, best_v = k, v
    return (best_k, best_v) if best_k else None


def shelf_key(item):
    r = best_key(item, "fridge", "fridge_purchase", "fridge_open",
                 "fridge_thaw", "pantry", "pantry_purchase", "pantry_open")
    return r[0] if r else None


# Окна ВНЕ морозилки. Отсчёт после разморозки сюда не входит: он следствие
# заморозки, а не альтернатива ей, и делить морозилку на него значит делить
# величину на её собственное продолжение.
WARM_KEYS = ("fridge", "fridge_purchase", "fridge_open",
             "pantry", "pantry_purchase", "pantry_open")

# Ниже суток источник печатает не срок хранения, а ПРЕДЕЛ ПРЕБЫВАНИЯ В ТЕПЛЕ:
# два часа для пирога, один час для разведённой смеси. Это правило опасной
# зоны, а не окно хранения, и в знаменателе отношения ему делать нечего.
SAFETY_LIMIT_DAYS = 1.0


def safety_limit_cells(item):
    """Ячейки, чей срок короче суток: пределы пребывания в тепле.

    Отдельная функция, потому что это отдельная ВЕЛИЧИНА. Двухчасовой предел,
    попавший в знаменатель, напечатал «720× what the freezer buys you» —
    предел опасной зоны, поданный как выгода. Отношение на них не считается
    вовсе, и страница обязана сказать, почему.
    """
    out = []
    for key in WARM_KEYS:
        v = item["slots"].get(key)
        if v and v[0] != "no" and v[1] is not None and v[1] < SAFETY_LIMIT_DAYS:
            out.append((key, v[0], v[1]))
    return out


# ОДНА форма отношения на всю сборку, с ИМЕНОВАННЫМИ сторонами. Пока стороны
# различались только позицией в кортеже, две функции успели завести
# противоположные соглашения — (кратность, малое, большое) у одной и
# (кратность, большое, малое) у другой, — и позиция «1» значила в двух местах
# разное. Направление отношения теперь спрашивается по имени: r = num / den.
Ratio = collections.namedtuple("Ratio", "r den num den_key num_key")


def _ratio(den, num):
    """Одна точка, где вообще происходит деление. Знаменатель короче суток —
    отказ: см. safety_limit_cells."""
    if not den or not num or not den[1][1] or not num[1][1]:
        return None
    if den[1][1] < SAFETY_LIMIT_DAYS:
        return None
    return Ratio(num[1][1] / den[1][1], den[1][1], num[1][1], den[0], num[0])


def freeze_gain(item):
    """Во сколько раз морозилка держит дольше ЛУЧШЕГО способа вне неё.

    ОДНА величина — ОДНА функция. Знаменатель здесь возвращается ИМЕНЕМ
    ЯЧЕЙКИ, а не подразумевается словом «refrigerator» в шаблоне: пока бирка
    делила на то, что кончится первым, а проза — на холодильник, 24 страницы
    печатали два разных «во сколько раз» под одной и той же подписью.

    Знаменатель — самое длинное окно вне морозилки: выигрыш морозилки
    считается против ЛУЧШЕГО, что можно сделать без неё, иначе «выигрыш»
    набирается выбором худшего способа хранения.

    Возвращает (кратность, дни_знаменателя, дни_числителя, ячейка_зн,
    ячейка_числ) или None, если сравнивать нечего либо знаменатель оказался
    пределом опасной зоны.
    """
    return _ratio(best_key(item, *WARM_KEYS),
                  best_key(item, "freeze", "freeze_purchase"))


def opening_cost(item):
    """Во сколько раз короче живёт ВСКРЫТАЯ упаковка.

    Числитель — запечатанное окно, знаменатель — вскрытое, и обе стороны
    возвращаются именами ячеек: место хранения после вскрытия часто меняется
    (шкаф до, холодильник после), и подпись обязана назвать оба.
    Морозилка сюда не входит НИКОГДА: «90 дней в морозилке ÷ 4 дня после
    вскрытия» — это выигрыш заморозки, напечатанный под словом «вскрытие».
    """
    closed = best_key(item, "fridge", "fridge_purchase", "pantry",
                      "pantry_purchase")
    opened = best_key(item, "fridge_open", "pantry_open")
    r = _ratio(opened, closed)
    if not r or r[0] <= 1.0:
        return None
    return r


def warm_cost(item):
    """Во сколько раз шкаф короче холодильника при ОДНОМ состоянии упаковки.

    Пары берутся только внутри одного состояния вскрытия: «запечатанный шкаф
    против вскрытого холодильника» — это цена вскрытия, а не цена тепла, и
    называть её ценой тепла значит напечатать не ту операцию.
    """
    best = None
    for cold, warm in (("fridge", "pantry"),
                       ("fridge_purchase", "pantry_purchase"),
                       ("fridge_open", "pantry_open")):
        r = _ratio(best_key(item, warm), best_key(item, cold))
        if r and r[0] > 1.0 and (best is None or r[0] > best[0]):
            best = r
    return best


# ------------------------------------------------- КАЧЕСТВО против БЕЗОПАСНОСТИ
#
# Одна оговорка стояла на 221 странице сразу и служила ДВУМ ПРОТИВОПОЛОЖНЫМ
# последствиям: «quality guidance, not a safety test» печаталось и под
# «3 days to 4 days» у остатков с мясом (там это предел безопасности, и
# оговорка недопредупреждала), и под шестью месяцами в морозилке (там она
# верна буквально, и её никто не сказал вслух). Одна рамка — одно последствие;
# у фермы это уже третий раз.
#
# ЧЕМ ЭТО РЕШАЕТСЯ — и почему больше не рубрикой. Рубрика — это ПАПКА
# ИСТОЧНИКА, а не свойство еды. Пока решала она, вскрытая банка рыбы получала
# «посмотри и реши» (USDA держит её в «Shelf Stable Foods»), а вскрытая банка
# курицы при том же самом — «выброси не пробуя» (она в «Poultry»): одна
# ситуация и два противоположных вердикта. Вместе с рыбой вкусовую оговорку
# получали домашний айоли на сыром яйце, домашний бульон, творожный торт,
# эклеры, овощи в масле, варёная киноа, свежая паста, вскрытая подливка,
# мытая зелень в пакете и размороженная полента — 61 страница с холодильным
# окном в неделю и короче.
#
# Теперь решают СВОЙСТВА САМОЙ ЕДЫ, в объявленном порядке, и каждый вердикт
# возвращается ВМЕСТЕ С ПРИЗНАКОМ, по которому получен: страница печатает не
# только последствие, но и то, из чего оно выведено.
#
# Порог опасной зоны у FDA — это влажная малокислотная еда (TCS): животная,
# варёная растительная, разрезанная готовая к еде, овощи под маслом,
# непастеризованный низкокислотный сок. Ей противопоставлено то, что хранит
# себя само: сухое, кислое, сладкое, спиртное, чистый жир и сырые целые
# фрукты и овощи — эти портятся НА ВИДУ, и там окно про вкус.

# Рубрики, которые сами по себе являются утверждением О ЕДЕ: мясо, птица,
# рыба, яйца и молочное, готовая еда, детское питание. Ошибка была не в них,
# а в обратном допущении — будто вне этих папок животной еды не бывает.
PERISHABLE_CATEGORIES = frozenset((
    "Meat", "Poultry", "Seafood", "Dairy Products & Eggs",
    "Deli & Prepared Foods", "Baby Food", "Vegetarian Proteins",
    "Food Purchased Frozen",
))

# Сырое тесто в холодильном отделе живёт по правилам скоропортящегося, а
# рубрика у него общая с мукой и сахаром.
PERISHABLE_SUBCATEGORIES = frozenset(("Refrigerated Dough",))

SAFETY, QUALITY, UNSETTLED = "safety", "quality", "unsettled"

# Дольше этого слово «предел» неверно, и это ТРЕТЬЕ объявленное число
# правила. Предел безопасности — утверждение о РОСТЕ БАКТЕРИЙ: «пройдёт
# этот срок, и еда может навредить». Такие сроки в холодильнике меряются
# днями и неделями. Самое длинное холодильное окно, где чтение «предел»
# никем не оспаривается, — яйцо в скорлупе, 3–5 недель; шесть недель —
# первая круглая граница выше него. Дальше «выброси, не пробуя» не
# поддержан ничем: девять страниц печатали его над окнами от двух месяцев
# до двух лет, и топлёное масло получало «выброси» на 730 днях.
#
# ДЛИНА ОКНА ТОЛЬКО СМЯГЧАЕТ. Объявленная асимметрия, зеркальная к «папка
# только ужесточает»: длина имеет право СНЯТЬ утверждение об опасности и
# не имеет права его сделать. Обратное направление — «окно короткое,
# значит опасно» — и есть круговое рассуждение, за которое сайту
# выставили счёт: вердикт о сроке обосновывался самим сроком.
SAFETY_LIMIT_MAX_DAYS = 42.0

# Порог словами — из САМОГО порога, а не второй копией руками.
_WEEK_WORDS = ("no weeks", "one week", "two weeks", "three weeks",
               "four weeks", "five weeks", "six weeks", "seven weeks")
assert SAFETY_LIMIT_MAX_DAYS % 7 == 0, "порог объявлен не целыми неделями"
CAP_WORDS = _WEEK_WORDS[int(SAFETY_LIMIT_MAX_DAYS // 7)]

# Свойство №1: еда животная, сделана из животного, сварена и осталась
# влажной, разрезана и готова к еде, лежит под маслом или отжата сырой из
# низкокислотного овоща. Такая растит болезнетворные бактерии, ничем себя не
# выдавая, и холодильное окно на ней — ПРЕДЕЛ БЕЗОПАСНОСТИ.
#
# Кортеж значит «все слова сразу»: «salsa» сама по себе бывает и заводской
# кислой в банке, и свежерубленой из помидоров, и разводит их не слово
# «salsa», а пара слов.
ANIMAL_WORDS = (
    "meat", "meats", "beef", "veal", "pork", "lamb", "goat", "bison",
    "venison", "poultry", "chicken", "turkey", "fish", "seafood",
    "shellfish", "tuna", "salmon", "anchovies", "sardines", "herring",
    "crab", "lobster", "shrimp", "crayfish", "clams", "oysters", "mussels",
    "scallops", "egg", "eggs", "milk", "cream", "creamy", "cheese",
    "cheesecake", "custard", "chiffon", "yogurt", "mayonnaise", "aioli",
    "broth", "stock", "consomme", "gravy", "quiche", "eclairs", "liver",
    "ham", "bacon", "sausage",
)

# Слова, которыми еда называет себя РАСТИТЕЛЬНОЙ. Животное слово в таком
# имени — сравнение по вкусу, а не происхождение: «Vegan Cheddar
# Cheese» сыром не является, «Soy milk» и «Coconut cream» — тем более.
# Двенадцать растительных продуктов печатали «is an animal food, or made
# with one» как ПРИЧИНУ выбросить их; объяснение, заведомо ложное про еду
# перед читателем, рушит и тот вердикт, который оно объясняет.
NOT_ANIMAL_WORDS = (
    "vegan", "vegetarian", "nondairy", "plant", "imitation",
    "soy", "soya", "coconut", "almond", "cashew", "oat",
    "hemp", "tofu", "tempeh", "seitan",
)

# ЧТО ИСТОЧНИК СКАЗАЛ ПРО ЭТУ ЯЧЕЙКУ СВОИМИ СЛОВАМИ. Не папка и не наша
# догадка: заметка лежит в самой записи и говорит о том, ЧТО ОКНО ЗНАЧИТ.
# Поэтому она сильнее любого нашего списка слов и стоит выше всех.
#
# ОБЛАСТЬ ЗАМЕТКИ — ЧАСТЬ ЗАМЕТКИ. Источник кладёт эту строку в поле
# `pantry`, а говорит она своими же словами про ХОЛОДИЛЬНИК ПОСЛЕ ВСКРЫТИЯ
# («labels ... suggest that they be refrigerated after opening»): берётся
# она по СОСТОЯНИЮ и применяется к холодильным окнам этого состояния.
# Страница майонеза печатала «выброси, не пробуя» вопреки этой самой
# строке в своей же записи.
NOTE_QUALITY_NOT_SAFETY = "quality, not safety"

# Обратная сторона: окно рассчитано на ПРИГОТОВЛЕННЫЙ продукт — значит,
# еда, о которой идёт речь, сваренная и влажная, а не сухой пакет.
# «Dry gravy mixes» получало «животная еда» по слову «gravy», хотя
# правильный ответ написан в самой записи. Эта заметка привязана к СВОЕЙ
# ячейке и на соседние не распространяется.
NOTE_AFTER_COOKING = ("applies to prepared product",
                      "for storage after cooking")

# Сварено или готово к еде и осталось влажным. Сюда же — овощи под маслом
# (ботулизм не пахнет) и сырой сок, отжатый из низкокислотного овоща.
PREPARED_WORDS = (
    "cooked", "boiled", "refried", "thawed", "leftovers", "hummus", "pesto",
    "dip", "dips", "stew", "soup", "tofu", "tempeh", "polenta",
    ("pasta", "fresh"), ("sprouts", "bean"), ("sprouts", "mung"),
    ("salsa", "fresh"), ("vegetables", "marinated"),
    ("juice", "vegetable"), ("juice", "carrot"),
)

# Разрезано, вымыто и готово к еде: у такой еды есть срез, по которому
# бактерии расходятся внутрь, и её едят, не готовя.
#
# Слово «cut» стоит ОДНО, а не в паре с именем овоща: парой были закрыты
# «squash, cut» и «bagged greens», а «Fruit, cut» — разрезанная готовая к еде
# фруктовая нарезка из холодильного отдела — проваливалась дальше и получала
# вкусовой вердикт по слову «fruit» из списка кислого. Признак здесь — СРЕЗ,
# и он не зависит от того, что именно разрезали.
CUT_WORDS = ("cut", "bagged")

SAFETY_FOOD_WORDS = ANIMAL_WORDS + PREPARED_WORDS + CUT_WORDS

# Свойство №2: еда хранит себя сама — сухая, кислая, сладкая, спиртная или
# это чистый жир. Бактериям в ней не на чем расти, а портится она заметно.
KEEPS_ITSELF_WORDS = (
    # сухое
    "flour", "cornmeal", "meal", "dry", "dried", "powder", "powdered",
    "mix", "mixes", "crackers", "croutons", "yeast", "coffee", "jerky",
    "nut", "nuts", "almonds", "cashews", "macadamias", "peanut", "peanuts",
    "pecans", "pistachios", "walnuts", "seed", "seeds", "flaxseed",
    "shell", "raisins",
    # кислое
    "vinegar", "vinaigrette", "pickles", "pickled", "kimchi", "sauerkraut",
    "cranberry", "cranberries", "lemon", "lime", "citrus", "ketchup",
    "mustard", "relish", "chutney", "horseradish", "applesauce", "tamarind",
    "tomato", "tomatoes", "olives", "capers", "fruit", "fruits",
    # сладкое
    "syrup", "honey", "jam", "jams", "jellies", "preserves", "molasses",
    "sugar", "frosting", "icing", "chocolate",
    # спиртное и газированное
    "wine", "beer", "liquor", "liquors", "spirits", "soda", "carbonated",
    # чистый жир: воды нет, расти не в чем
    "oil", "oils", "fat", "grease", "shortening", "lard",
)

# Еда, у которой слова спорят, а ответ известен. Список короткий НАРОЧНО:
# длинный список руками — это уже не правило, а таблица, и проверить её
# нечем. «Bacon grease» — вытопленный жир, а не бекон.
FOOD_OVERRIDES = {
    "bacon grease": (QUALITY, "rendered fat"),
}

# Холодильное окно в неделю и короче — само по себе свидетельство: USDA не
# печатает двухдневный холодильный срок для того, что стабильно и так.
# Порог объявлен ЗДЕСЬ и нигде больше; тот же порог берёт гейт.
COLD_SHORT_DAYS = 7.0

# ХВОСТ предложения "<еда> is ...": ветки, чьё свидетельство лежит в САМОЙ
# ЕДЕ. Ветки, у которых свидетельство лежит в записи (заметка источника, место
# хранения, длина окна), собирают своё предложение целиком в REASON_CLAUSE и в
# эту таблицу не входят: подставлять их сюда значило бы печатать "<еда> is
# stable where the source rates it" под рамкой "решает еда, а не полка".
REASON_EN = {
    "animal": "an animal food, or made with one",
    "prepared": "cooked or ready to eat and still moist",
    "cut": "cut and ready to eat",
    "keeps": "acid, dry, sweet, alcoholic or pure fat",
    "raw whole": "raw and whole",
    "rendered fat": "rendered fat with no water in it",
}

# ОБЪЯСНЕНИЕ ЖИВЁТ ЗДЕСЬ, РЯДОМ С ВЕРДИКТОМ, а не собирается заново на
# странице. Прежде страница склеивала "<еда> is %s" из REASON_EN сама, и
# рамка была одна на все ветки: над двенадцатью растительными продуктами
# стояло "is an animal food, or made with one", а над морозилкой -- "решает
# еда, а не полка", хотя решала ровно полка. Теперь каждая ветка возвращает
# СВОЁ предложение, называющее ровно то свидетельство, по которому она
# сработала, и другого способа объяснить вердикт на странице нет.
_FOOD_FRAME = ("What decides that is the food and not the shelf the source "
               "files it on: %(who)s is %(is)s.")

REASON_CLAUSE = {
    "warm limit": "Below a day the USDA is not printing a shelf life but a "
                  "limit on standing in a warm kitchen, and that holds "
                  "wherever the figure sits.",
    "source says quality": "What decides that is the record's own note: "
                           "the source says quality, not safety, is why the "
                           "label asks for the refrigerator once open.",
    "after cooking": "What decides that is the record's own note: this "
                     "figure is for the product after cooking, which is "
                     "cooked and still moist.",
    "stable there": "The USDA rating this place at all is the USDA saying "
                    "%(who)s keeps there, so the figure rates how good it "
                    "will be.",
    "perishable folder": "What decides that is the food: the source files "
                         "%(who)s under %(folder)s, a heading it keeps for "
                         "perishable food.",
    "too long for a limit": "%(who)s does spoil, but a bacterial limit "
                            "runs in days and this window runs past "
                            "%(cap)s: the figure rates how good it will be.",
    "not settled": "Nothing here names the food: neither %(who)s nor the "
                   "heading it sits under says whether it spoils dangerously "
                   "or keeps itself.",
    "animal": _FOOD_FRAME,
    "prepared": _FOOD_FRAME,
    "cut": _FOOD_FRAME,
    "keeps": _FOOD_FRAME,
    "raw whole": _FOOD_FRAME,
    "rendered fat": _FOOD_FRAME,
}

# Признаки, которыми еда объявлена опасно портящейся, и признаки, которыми она
# объявлена сохраняющей себя. Списки ПОЛНЫЕ: признак, не попавший ни в один,
# роняет сборку, а не получает молча вердикт по умолчанию.
SPOILS_DANGEROUSLY = ("animal", "prepared", "after cooking", "cut",
                      "perishable folder")
KEEPS_SAFE = ("keeps", "raw whole", "rendered fat", "source says quality")


def _food_text(item, state=None):
    """Слова, которыми названа САМА ЕДА: имя продукта и вид состояния.

    Ключевые слова источника сюда не идут: у половины записей они перечисляют
    соседей по полке, и «meat» из чужого перечисления сделало бы животной едой
    банку с оливками.
    """
    parts = [item.get("name") or ""]
    if state is not None:
        parts.append(state.get("kind") or "")
    else:
        parts.append(item.get("subtitle") or "")
    return re.findall(r"[a-z0-9]+", " ".join(parts).lower())


def _hits(words, rule):
    """Правило сработало: одно слово или ВСЕ слова кортежа."""
    if isinstance(rule, tuple):
        return all(w in words for w in rule)
    return rule in words


def _plant_named(item, state=None):
    """Еда НАЗЫВАЕТ СЕБЯ растительной.

    Метка читается из имени продукта всегда, а из подписи вида — только когда
    подпись называет ОДНУ форму. Подпись через запятую перечисляет варианты, и
    метка внутри перечисления говорит про один из них, а не про еду: «Cream
    pies, banana cream, coconut cream, butterscotch» — заварной пирог, и
    слово «coconut» там не имеет права снять с него животное чтение.
    """
    sub = state.get("kind") if state is not None else item.get("subtitle")
    text = item.get("name") or ""
    if sub and "," not in sub:
        text = "%s %s" % (text, sub)
    words = re.findall(r"[a-z0-9]+", text.lower())
    return any(w in words for w in NOT_ANIMAL_WORDS)


def food_nature(item, key, state=None):
    """ЧТО ЭТО ЗА ЕДА — одним признаком, и признак несёт своё свидетельство.

    Половина правила, которая говорит ТОЛЬКО о еде и о том, что источник о ней
    написал сам. Ни места хранения, ни длины окна здесь нет: они решают, что
    это ЗНАЧИТ, а не что это за еда.

    Порядок объявлен, и каждая ветка возвращает признак, из которого потом
    печатается объяснение. Прежде все три списка слов были склеены в один
    кортеж, а признак ВОССТАНАВЛИВАЛСЯ обратным поиском по спискам — слово,
    попавшее в два списка, объяснялось не тем, чем сработало. Теперь признак
    возвращает та самая ветка, которая сработала, и разойтись им негде.
    """
    tips = (state if state is not None else item).get("tips") or {}
    if key.startswith("fridge") and any(
            NOTE_QUALITY_NOT_SAFETY in (x or "").lower()
            for x in tips.values()):
        return "source says quality"
    if any(n in (tips.get(key) or "").lower() for n in NOTE_AFTER_COOKING):
        return "after cooking"
    words = _food_text(item, state)
    named = " ".join(words)
    for text, verdict in FOOD_OVERRIDES.items():
        if named == re.sub(r"[^a-z0-9]+", " ", text).strip():
            return verdict[1]
    plant = _plant_named(item, state)
    for rule in ANIMAL_WORDS:
        if _hits(words, rule) and not plant:
            return "animal"
    for rule in PREPARED_WORDS:
        if _hits(words, rule):
            return "prepared"
    for rule in CUT_WORDS:
        if _hits(words, rule):
            return "cut"
    # Рубрика-утверждение стоит ВЫШЕ списка самосохраняющегося, и это не
    # возврат к папкам. «Fruit» из рубрики Baby Food — вскрытая баночка
    # детского пюре, три дня в холодильнике, — получала вкусовой вердикт по
    # слову «fruit» из списка кислого, потому что список стоял выше. Слово
    # называет вещество, рубрика называет ЕДУ; там, где они спорят,
    # утверждение о еде сильнее. Признак называется своим именем, а не чужим:
    # раньше эта ветка возвращала «animal», и двенадцать растительных
    # продуктов объявлялись животной едой её словами.
    if (item.get("category") in PERISHABLE_CATEGORIES
            or item.get("subcategory") in PERISHABLE_SUBCATEGORIES):
        return "perishable folder"
    for rule in KEEPS_ITSELF_WORDS:
        if _hits(words, rule):
            return "keeps"
    # Сырые фрукты и овощи целиком портятся НА ВИДУ: плесень, слизь, вялость.
    # Разрезанное и вскрытое — уже другая еда: у неё есть срез, по которому
    # бактерии расходятся внутрь, и её едят, не готовя.
    if item.get("category") == "Produce":
        return "cut" if key.endswith("_open") else "raw whole"
    return None


def food_kind(item, key, hi, state=None):
    """(последствие, признак) — ЧТО ЗНАЧИТ это окно и ПОЧЕМУ.

    Одна величина — одна функция, и величина эта — ПОСЛЕДСТВИЕ, а не число.
    Признак возвращается вместе с ним и никогда не сочиняется рядом: из него
    печатается объяснение, и REASON_CLAUSE — единственное место, где оно есть.

    Ветки объявлены по порядку:

    * короче суток — это не срок хранения, а предел пребывания в тепле (два
      часа для пирога, час для разведённой смеси): БЕЗОПАСНОСТЬ, где бы
      источник это число ни напечатал, включая комнатную температуру;
    * источник сам сказал про эту ячейку, что причина — качество: верим ему;
    * морозилка и шкаф — при 0 °F еда остаётся безопасной, пока заморожена, а
      если USDA вообще оценивает комнатную температуру, еда при ней стабильна;
    * холодильник — по СВОЙСТВУ ЕДЫ, но слово «предел» держится только там,
      где оно вообще что-то значит: дольше шести недель предел безопасности не
      поддержан ничем, и длина окна СНИМАЕТ утверждение об опасности;
    * если ни одна ветка не назвала еду — страница ГОВОРИТ ОБ ЭТОМ, а не
      угадывает по длине окна. Угадывание по длине и было тем круговым
      рассуждением, где вердикт о сроке обосновывался самим сроком.
    """
    if hi is not None and hi < SAFETY_LIMIT_DAYS:
        return (SAFETY, "warm limit")
    nature = food_nature(item, key, state)
    if nature == "source says quality":
        return (QUALITY, nature)
    if key.startswith("freeze") or key.startswith("pantry"):
        return (QUALITY, "stable there")
    if nature in SPOILS_DANGEROUSLY:
        if hi is None or hi <= SAFETY_LIMIT_MAX_DAYS:
            return (SAFETY, nature)
        return (QUALITY, "too long for a limit")
    if nature is None:
        return (UNSETTLED, "not settled")
    assert nature in KEEPS_SAFE, "признак %r не объявлен ни в одном списке" % (
        nature,)
    return (QUALITY, nature)


def reason_clause(reason, item=None, who=None):
    """Объяснение вердикта — теми же словами и из того же признака.

    Единственное место, где предложение о причине собирается. Страница его не
    пишет, а получает: собрать его отдельно значило бы завести вторую копию
    правила, и первая же такая копия напечатала «animal food» над соевым
    молоком, потому что рамка была общая, а признак в неё только подставлялся.
    """
    who = who or (item or {}).get("name") or "this food"
    return REASON_CLAUSE[reason] % {
        "who": who,
        "is": REASON_EN.get(reason, ""),
        "folder": (item or {}).get("category") or "the heading it uses",
        "cap": CAP_WORDS,
    }


def food_verdict(item, key, hi, state=None, who=None):
    """(последствие, признак, ОБЪЯСНЕНИЕ) — один вызов, один источник правды.

    Ради этой функции переписано всё выше: пока страница брала у правила
    только последствие, а объяснение писала рядом сама, они и разошлись.
    """
    kind, reason = food_kind(item, key, hi, state)
    return (kind, reason, reason_clause(reason, item, who))


def window_kind(item, key, hi, state=None):
    """Только последствие, без признака: обёртка над food_kind."""
    return food_kind(item, key, hi, state)[0]


def is_perishable(item):
    """Скоропортящийся ли продукт — свойство ЕДЫ, а не полки.

    Ответ выводится из тех же вердиктов, что печатает страница: продукт
    скоропортящийся, если хоть одно его ХОЛОДИЛЬНОЕ окно означает
    безопасность ИЛИ не решено вовсе. Отдельного второго определения не
    существует — одна величина, одна функция.

    Нерешённое считается скоропортящимся НАРОЧНО: правило двух часов дешевле
    ошибиться в сторону предупреждения, а «не знаем» — не повод его снять.
    """
    states = item.get("states") or [item]
    for st in states:
        for key, v in (st.get("slots") or {}).items():
            if not key.startswith("fridge") or not v or v[0] == "no":
                continue
            if window_kind(item, key, v[1], st) in (SAFETY, UNSETTLED):
                return True
    return False


# Состояние упаковки: сравнивать места между собой можно только внутри него.
# «Запечатанный шкаф против вскрытого холодильника» — это цена вскрытия, а не
# выбор места, и обозвать одно другим мы уже успели.
OPENING_GROUP = {
    "fridge": "plain", "pantry": "plain",
    "fridge_purchase": "bought", "pantry_purchase": "bought",
    "fridge_open": "open", "pantry_open": "open",
    "fridge_thaw": "thaw",
}


def better_place_for(state, key):
    """Ячейка ТОГО ЖЕ состояния и того же вскрытия, но с местом получше.

    Источник печатает и шкаф, и холодильник для одного и того же лука: месяц
    против недели. Это не «что кончится первым» — это ВЫБОР МЕСТА, и худший
    из двух не связывает никого, кроме того, кто уже положил не туда.
    Флуоресцентное поле помечало именно его на 48 страницах.
    """
    grp = OPENING_GROUP.get(key)
    if grp is None:
        return None
    v = state["slots"].get(key)
    if not v or v[0] == "no":
        return None
    best_k, best_v = None, None
    for k2, v2 in state["slots"].items():
        if k2 == key or OPENING_GROUP.get(k2) != grp or not v2 or v2[0] == "no":
            continue
        if v2[0] >= v[0] and v2[1] >= v[1] and v2[0] > v[0]:
            if best_v is None or v2[0] > best_v[0]:
                best_k, best_v = k2, v2
    return best_k


def source_rows():
    """Сколько строк в снимке источника. Ровно то, что читает load(), без
    снятия дублей и без разбиения на состояния: страница «Метод» называет это
    число, и оно обязано совпадать с тем, что печатают страницы продуктов."""
    return len(load())


def shelf_days(item):
    """Срок для сортировки: верхняя граница лучшего НЕморозильного способа.

    Морозилка исключена нарочно: она уравнивает почти всё, и рейтинг по ней
    перестал бы что-либо различать.
    """
    v = best(item, "fridge", "fridge_purchase", "fridge_open", "fridge_thaw",
             "pantry", "pantry_purchase", "pantry_open")
    return v[1] if v else None


def rank_in_category(items):
    """Место продукта среди соседей по категории — по сроку хранения.

    Ранг считается ОДНОЙ функцией на весь сайт. Ранг, посчитанный в двух
    местах независимо, у нас уже расходился публично.
    """
    by_cat = {}
    for it in items:
        d = shelf_days(it)
        if d is not None:
            by_cat.setdefault(it["category"], []).append((d, it["id"]))
    ranks = {}
    for cat, rows in by_cat.items():
        rows.sort(key=lambda x: (-x[0], x[1]))
        # Одинаковый срок — одинаковое место. Нумерация по позиции в списке
        # уже давала нам «#37 из 57» там, где тридцать семь были равны.
        place, prev, seen = 0, None, 0
        for d, pid in rows:
            seen += 1
            if d != prev:
                place = seen
                prev = d
            ranks[pid] = (place, len(rows), d)
    return ranks


def _ascii(text):
    """Латиница без диакритики: «consommé» -> «consomme».

    Слаг собирался прямо из [a-z0-9], и знак с диакритикой не заменялся, а
    ИСЧЕЗАЛ: адрес /chicken-broth-stock-consomm/ обрывался на середине слова,
    и так же обрывались /beef-broth-stock-consomm/ и /marshmallow-crm/.
    Разложение по NFD отбрасывает только КОМБИНИРУЮЩИЙ знак и оставляет
    букву на месте.
    """
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if not unicodedata.combining(c))


def slug_head(item):
    """Простое имя продукта: всё до первой запятой, без подзаголовка.

    Источник печатает уточнение прямо в имени — «Shrimp, crayfish», «Pizza,
    frozen», — и адрес получался /shrimp-crayfish/ при том, что набирают
    слово «shrimp». Хвост после запятой никуда не девается: он стоит в
    заголовке страницы и в подписи поля.
    """
    s = re.sub(r"[^a-z0-9]+", "-",
               _ascii(item["name"].split(",")[0].lower()))
    return re.sub(r"-+", "-", s.strip("-"))


def assign_slugs(items):
    """Адрес — то слово, которым продукт ищут. ОДНА функция на весь сайт.

    Страница живёт по простому имени; хвост имени и подзаголовок дописываются
    только тогда, когда простое имя занял кто-то другой. Слова «shrimp»,
    «pizza» и ещё сто тридцать пять отдавали 404 при живой странице ровно на
    том слове, которым эту еду ищут.

    Столкновение решается порядком источника, а не выбором вида: адрес
    обязан быть устойчив к тому, что таблица PLAIN_MEANS однажды назовёт
    другую строку. Продукт, чьё полное имя И ЕСТЬ простое, забирает адрес
    вне очереди — иначе «Fruit, cut» отняла бы /fruit/ у записи, которая
    называется просто «Fruit».
    """
    claims = {}
    for it in items:
        claims.setdefault(slug_head(it), []).append(it)
    for head, group in claims.items():
        plain = [x for x in group if slug(x) == head]
        win = plain[0] if plain else min(group, key=lambda x: int(x["id"]))
        for it in group:
            it["slug"] = head if it is win else slug(it)
    return items


def slug(item):
    """Адрес страницы. У продукта с несколькими состояниями подзаголовка нет —
    он у состояний, — и адрес получается тем словом, которым продукт ищут:
    /leftovers/, а не /leftovers-without-meat-fish-poultry-or-egg/."""
    parts = [item["name"]]
    if item["subtitle"]:
        parts.append(item["subtitle"])
    s = _ascii("-".join(parts).lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return re.sub(r"-+", "-", s)


# ------------------------------------------------- единица публикации
#
# ПРОДУКТ, А НЕ СТРОКА ИСТОЧНИКА. Замер 05.09.2026: 100 имён из 466 несут
# больше одной строки, и в одноимённых группах сидят 292 строки из 658 — 44%
# источника. Порознь такие строки почти дословные близнецы («Leftovers, with
# meat» против «Leftovers, without meat»), и гейт близнецов честно выбрасывал
# всю голову ниши. Он работал правильно — неверна была ЕДИНИЦА.
#
# Строки с одним ИМЕНЕМ сливаются в один продукт с несколькими СОСТОЯНИЯМИ.
# Слияние по имени, а не по подзаголовку: «Chicken parts» и «Chicken» — разные
# продукты, «Milk / lactose-free» и «Milk / ultra-pasteurized» — один.

def _rated_n(row):
    return len([1 for v in row["slots"].values() if v[0] != "no"])


def state_title(product, st):
    """Имя состояния так, как оно печатается и ищется: «Milk, lactose-free».

    Безымянное состояние печатается с номером записи источника, а не
    выбрасывается: выбрасывание безымянного уже стоило ферме 444 348 домов.
    """
    if st["kind"]:
        return "%s, %s" % (product["name"], st["kind"])
    return "%s (USDA record %s)" % (product["name"], st["id"])


# ------------------------------------------------- ЗА ЧТО ГОВОРИТ СТРАНИЦА
#
# ПРАВИЛО. Страница живёт по ПРОСТОМУ слову — /eggs/, /tuna/, /milk/ — и
# говорить обязана за тот вид, который человек ИМЕЕТ В ВИДУ, набирая это
# слово. Это НЕ «первая строка источника» и НЕ «строка без подзаголовка»:
# у молока первой строкой стоит «plain or flavored», у тунца человек имеет
# в виду консерву, у арахисовой пасты — магазинную, у яиц — те, что в
# скорлупе, а у чеснока — головку, у которой подзаголовка нет вовсе.
#
# Значение простого слова из подзаголовка НЕ ВЫВОДИТСЯ никаким правилом.
# Попытка вывести его словами («подзаголовок не сужает продукт до
# консервированной формы») дала тринадцать страниц, говоривших за чужой вид,
# и при этом печатавших фразу «за страницу отвечает первая строка источника»,
# которая на них была неверна. Правило, которое приходится опровергать
# исключениями, — это таблица исключений, написанная нечестно.
#
# Поэтому значение ОБЪЯВЛЕНО: по строке на имя, и объявлен КЛЮЧ СТРОКИ
# ИСТОЧНИКА, а не число. Сроки по-прежнему приходят из снимка, и подделать
# ими срок нельзя; гейт проверяет, что объявленный ключ есть среди строк
# этого имени и что имя вида на странице совпадает с подзаголовком той самой
# строки. Имя, у которого в снимке больше одной строки и нет объявления,
# РОНЯЕТ сборку: новая строка в новом снимке обязана быть замечена руками,
# а не молча сдвинуть, за что говорит страница.
#
# Второй ответ таблицы — SPLIT: простое слово НЕ ЗНАЧИТ одного вида.
# «Beef» — это и фарш, и стейк, и рёбрышки; «Ham» — двадцать видов от свежей
# до консервированной; «Pies» — три начинки с разными окнами. Такая страница
# не выбирает вид молча: у неё НЕТ ни одного числа крупной строкой, она
# печатает виды списком и даёт выбрать. Продукт со SPLIT не получает
# собственных ячеек вовсе — ни кратности, ни места в рубрике, ни даты: всё
# это утверждения ПРО ВИД, а вида у такой страницы нет.
#
# ЧЕГО ЭТО НЕ ОТМЕНЯЕТ. Более короткое окно другого вида никуда не девается:
# оно стоит на бирке под ответом, в таблице видов и в прозе. Ведущий вид
# решает, О ЧЁМ страница, а не что на ней есть.

SPLIT = "split"          # простое слово не значит одного вида: страница-выбор

# Ключ — имя продукта так, как по нему слиты строки (нижний регистр).
# Значение — идентификатор строки FoodKeeper либо SPLIT. Комментарий рядом
# называет вид словами: сверять глазами надо ВИД, а не число.
PLAIN_MEANS = {
    "almonds": "438",                      # без скорлупы: так их и покупают
    "amaranth": "575",                     # цельное зерно, а не мука
    "applesauce": "370",                   # магазинная банка
    "bacon": "79",                         # строка без подзаголовка
    "bagel": "449",                        # свежий, а не замороженный
    "barbecue sauce": "340",               # бутылка
    "barley": "577",                       # цельное зерно
    "basil": "509",                        # свежий пучок, а не сушёный
    "beef": SPLIT,                         # фарш, стейк и рёбра — разное
    "beets": "274",                        # строка без подзаголовка
    "berries": SPLIT,                      # две разные корзины ягод
    "bison": SPLIT,                        # цельный кусок против фарша
    "black pepper": "469",                 # молотый
    "bratwurst": "638",                    # свежая
    "buckwheat": "579",                    # цельное зерно
    "canadian bacon": "519",               # нарезка в упаковке
    "canned goods": SPLIT,                 # кислые и некислые — разные сроки
    "cereal": "374",                       # готовые хлопья
    "cheese": SPLIT,                       # твёрдый, тёртый и мягкий — разное
    "chicken": "113",                      # сырая тушка
    "chicken parts": "116",                # все три части: окно одно
    "chorizo": "630",                      # свежая
    "cinnamon rolls": "635",               # печёные
    "coconut milk": "429",                 # строка без подзаголовка
    "coffee": "541",                       # молотый магазинный
    "coffee creamer": "8",                 # жидкие сливки из холодильника
    "cookies": "199",                      # мягкое печенье
    "cornmeal": "218",                     # обычная
    "crab meat": "154",                    # свежее
    "cranberry sauce": "565",              # банка
    "cream": SPLIT,                        # пять разных сливок
    "edamame": "641",                      # замороженные стручки
    "egg substitutes": "310",              # строка без подзаголовка
    "eggs": "21",                          # в скорлупе
    "farro": "581",                        # цельное зерно
    "fish": "312",                         # сырая, потрошёная
    "flaxseed": "503",                     # целое семя
    "flour": "222",                        # белая
    "fresh whole lobster": "158",          # живой
    "garlic": "285",                       # строка без подзаголовка: головка
    "gelatin": "225",                      # пакетик с вкусом
    '"genuine" maple syrup': "534",        # пластиковая бутылка
    "goat": SPLIT,                         # цельный кусок против фарша
    "ham": SPLIT,                          # двадцать видов, окна врозь
    "herbs": "288",                        # строка без подзаголовка: свежие
    "hummus": "181",                       # магазинный
    "jerky": "109",                        # магазинные
    "kugel": "667",                        # домашний
    "lamb": SPLIT,                         # цельный кусок против фарша
    "lean fish": "144",                    # обе строки: окно одно
    "leftovers": "173",                    # все три строки: окно одно
    "lemon juice": "448",                  # строка без подзаголовка: бутылка
    "lettuce": "290",                      # кочанный
    "luncheon meat or poultry": "192",     # запечатанная упаковка
    "milk": "27",                          # обычное: числа на него источник
                                           # не даёт вовсе, и страница это
                                           # говорит словами
    "millet": "583",                       # цельное зерно
    "muffin": "452",                       # покупной
    "mung bean": "680",                    # сухой боб, а не ростки
    "mushrooms": "292",                    # строка без подзаголовка
    "mustard": "351",                      # строка без подзаголовка
    "nutrition supplement drinks": "558",  # банка
    "oats": "585",                         # цельное зерно
    "olives": "352",                       # банка
    "onions": "294",                       # репчатый
    "orange juice": "455",                 # пакет из магазина
    "pate": "188",                         # строка без подзаголовка
    "peanut butter": "387",                # магазинная
    "peanuts": "442",                      # без скорлупы
    "pecans": "444",                       # без скорлупы
    "pies": SPLIT,                         # три начинки, окна врозь
    "polenta": "656",                      # готовая в упаковке
    "popcorn": "389",                      # сухие зёрна
    "pork": SPLIT,                         # цельный кусок против фарша
    "potatoes": "297",                     # строка без подзаголовка
    "pumpkin seeds": "604",                # все четыре строки: окно одно
    "quinoa": "425",                       # сырая
    # Три имени, у которых строки-двойники лежат в РАЗНЫХ рубриках
    # источника (мясные шашлычки против птичьих, замороженные овощи
    # против детского питания). Адрес у них один, и корпус берёт
    # первую строку; здесь объявлена она же, чтобы «за что говорит
    # страница» и «что вообще выпущено» не расходились.
    "raw kabobs with vegetables": "106",   # мясные
    "retort pouches or boxes": "112",      # мясные
    "rice": "338",                         # белый
    "rye": "587",                          # цельное зерно
    "salad dressing": "623",               # бутылка
    "salsa": "357",                        # банка
    "sausage": "102",                      # сырая
    "sausages": "322",                     # сырые
    "sorghum": "589",                      # цельное зерно
    "spaghetti squash": "596",             # целая
    "spelt": "591",                        # цельное зерно
    "spice/spices": "238",                 # молотые
    "squash": SPLIT,                       # летняя и зимняя — разные овощи
    "sugar": "240",                        # сахарный песок
    "sunflower seeds": "609",              # жареные, без скорлупы
    "tea": "410",                          # пакетики
    "teff": "593",                         # цельное зерно
    "tomato sauce": "599",                 # банка
    "tortillas": "196",                    # обе строки: окно одно
    "tuna": "618",                         # консерва
    "turkey": "114",                       # сырая тушка
    "turkey parts": "119",                 # все три части: окно одно
    "veal": SPLIT,                         # цельный кусок против фарша
    "vegetables": "331",                   # замороженные
    "vegetable juice": "567",              # бутылка с полки
    "whipped topping": "32",               # ведёрко
    "whole wheat bread": "461",            # покупной нарезанный
}


class UndeclaredName(ValueError):
    """У имени больше одной строки, а значения простого слова нет.

    Молча выбрать за читателя нельзя: ровно это и печатало чужой вид на
    тринадцати страницах. Новая строка в новом снимке обязана уронить
    сборку.
    """


def plain_row(rows):
    """Строка, ЗА КОТОРУЮ говорит страница, или None у страницы-выбора.

    Одна величина — одна функция: этот выбор больше нигде не повторяется,
    прозе он приходит пометкой «lead» на состоянии.
    """
    rows = sorted(rows, key=lambda x: int(x["id"]))
    if len(rows) == 1:
        return rows[0]
    name = rows[0]["name"].strip()
    want = PLAIN_MEANS.get(name.lower(), None)
    if want is None:
        raise UndeclaredName(
            "имя %r несёт в снимке %d строк, и ни одна не объявлена значением "
            "простого слова: допиши строку в PLAIN_MEANS" % (name, len(rows)))
    if want == SPLIT:
        return None
    by_id = dict((r["id"], r) for r in rows)
    if want not in by_id:
        raise UndeclaredName(
            "имя %r объявлено строкой %s, которой в снимке у него нет: %s"
            % (name, want, ", ".join(sorted(by_id))))
    return by_id[want]


def merge_by_name(items):
    """Слить строки одного ИМЕНИ в один продукт со списком состояний.

    За какой вид говорит страница, решает plain_row — см. правило над ней;
    вида может не быть вовсе, и тогда продукт помечается «split». По нему
    считаются ОТНОШЕНИЯ (выигрыш заморозки, цена вскрытия, место в
    категории): смешивать величины разных состояний нельзя, это была бы одна
    величина с двумя обозначениями. Страница объявляет вслух, какое состояние
    сравнивается, и печатает окна КАЖДОГО состояния.
    """
    groups = {}
    for it in items:
        groups.setdefault(it["name"].strip().lower(), []).append(it)
    out = []
    for key in sorted(groups, key=lambda k: min(int(x["id"])
                                                for x in groups[k])):
        rows = sorted(groups[key], key=lambda x: int(x["id"]))
        lead = plain_row(rows)
        states = [{"id": r["id"], "kind": r["subtitle"], "slots": r["slots"],
                   "units": r["units"], "tips": r["tips"],
                   "says": r.get("says") or {},
                   "lead": lead is not None and r["id"] == lead["id"]}
                  for r in rows]
        kw, seen = [], set()
        for r in rows:
            for k in r["keywords"]:
                if k.lower() not in seen:
                    seen.add(k.lower())
                    kw.append(k)
        head = lead or rows[0]
        p = {
            "id": head["id"],
            "name": head["name"],
            # Подзаголовок остаётся ТОЛЬКО у продукта из одной строки: у
            # многосоставного он принадлежит состоянию, а не продукту.
            "subtitle": head["subtitle"] if len(rows) == 1 else "",
            # Рубрика берётся у ПЕРВОЙ строки имени, а не у ведущей: источник
            # держит сгущённое молоко в «Shelf Stable Foods», и продукт «Milk»
            # уезжал в бакалею вместе с ним. Что это за еда, решает первая
            # запись; какими числами она сравнивается — первая, у которой эти
            # числа есть.
            "category": rows[0]["category"],
            "subcategory": rows[0]["subcategory"],
            "keywords": kw,
            # У страницы-выбора СВОИХ ячеек нет: кратность, место в рубрике
            # и дата — утверждения про вид, а вида у неё нет. Пустые ячейки
            # тут не «мы не знаем», а «простое слово не значит одного вида»,
            # и страница говорит это словами.
            "slots": lead["slots"] if lead else {},
            "units": lead["units"] if lead else {},
            "says": (lead.get("says") or {}) if lead else {},
            "tips": lead["tips"] if lead else {},
            "split": lead is None,
            "states": states,
            "n_states": len(states),
            "row_ids": [r["id"] for r in rows],
        }
        p["slug"] = slug(p)
        out.append(p)
    return out


def facts(item, ranks):
    """Вычисленные факты страницы. Именно они проходят гейт уникальности.

    Каждый — результат расчёта, а не строка из источника: отношение, место в
    ряду или разность. Переписанный из источника диапазон фактом не считается.
    """
    out = []
    g = freeze_gain(item)
    if g:
        out.append("freeze:%s:%.2f" % (item["id"], g.r))
    o = opening_cost(item)
    if o:
        out.append("open:%s:%.2f" % (item["id"], o.r))
    r = ranks.get(item["id"])
    if r:
        out.append("rank:%s:%d/%d" % (item["id"], r[0], r[1]))
    d = shelf_days(item)
    if d is not None:
        out.append("shelf:%s:%.1f" % (item["id"], d))
    n = len([k for k in item["slots"] if item["slots"][k][0] != "no"])
    if n:
        out.append("slots:%s:%d" % (item["id"], n))
    return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    items = load()
    ranks = rank_in_category(items)
    with_slots = [i for i in items if i["slots"]]
    print("продуктов в источнике: %d" % len(items))
    print("с хотя бы одной заполненной ячейкой: %d" % len(with_slots))
    print("с рангом в категории: %d" % len(ranks))
    fz = [i for i in items if freeze_gain(i)]
    op = [i for i in items if opening_cost(i)]
    print("можно посчитать выигрыш заморозки: %d" % len(fz))
    print("можно посчитать цену вскрытия: %d" % len(op))
    ok = [i for i in items if len(facts(i, ranks)) >= 3]
    print("проходят порог в 3 вычисленных факта: %d" % len(ok))
    print()
    for it in sorted(fz, key=lambda i: -freeze_gain(i)[0])[:5]:
        g = freeze_gain(it)
        print("  %-42s заморозка даёт в %.0f раз дольше (%s -> %s)"
              % (it["name"] + (", " + it["subtitle"] if it["subtitle"] else ""),
                 g[0], _num(g[1]), _num(g[2])))
