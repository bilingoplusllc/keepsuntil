# -*- coding: utf-8 -*-
"""Проза KeepsUntil. Ветвится по ФОРМЕ данных, а не подставляет числа в скелет.

ПОЧЕМУ ЭТОТ ФАЙЛ ВООБЩЕ ЕСТЬ. Первая сборка дала 593 страницы, и гейт близнецов
оставил от них 5: медиана сходства прозы 0,82, девятый дециль — 1,00, то есть
побайтово одинаковый текст. Причина была одна: ОДИН шаблон абзаца, в который
подставлялись разные числа. Это дословно то, что Google называет scaled content
abuse, и вычисленные факты в заголовке от этого не спасают.

ЧТО ИЗМЕНИЛОСЬ. Сначала считается ФОРМА данных продукта — не значения, а
признаки: есть ли выигрыш заморозки и меняется ли при этом ЕДИНИЦА измерения
(дни превращаются в месяцы), запрещена ли заморозка вовсе, какие из девяти
ячеек источника заполнены, где продукт стоит в своей категории и кто стоит
рядом, насколько широк собственный разброс источника, где продукт в
распределении всего корпуса. Форма выбирает, ЧТО сказать первым и какие
утверждения его поддержат; единица измерения выбирает, КАК это сказать.

«Freezing turns days into months» и «here both the refrigerator and the freezer
are measured in weeks» — это разные утверждения о разных данных, а не одно
утверждение с разными числами.

ПРАВИЛО ФАЙЛА: ни одна фраза не должна годиться любому продукту. Если
предложение можно поставить на любую страницу, не соврав, — оно не несёт факта
и здесь ему не место. Исключений ровно два — границы применимости и метод, и
они объявлены общими вслух и вынесены из сравнения на близнецов.

ЯЗЫК САЙТА АНГЛИЙСКИЙ.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foodkeeper as fk  # noqa: E402
import design  # noqa: E402

# Два окна, а не одно. Блоки, которые ОТВЕЧАЮТ на запрос, обязаны быть
# самодостаточными пассажами: единица извлечения в поиске — абзац, а не
# страница. Блоки, которые лишь ВВОДЯТ таблицу или список, стоящие тут же
# ниже, столько слов не несут, и раздутые до сорока они наполняются водой —
# то есть ровно тем, из-за чего страницы становятся близнецами.
ANSWER_MIN, ANSWER_MAX = 35, 72
INTRO_MIN, INTRO_MAX = 18, 56

# Сколько вычисленных величин нужно, чтобы печатать блок СРАВНЕНИЙ. Это порог
# ПРОРЕЖИВАНИЯ, а не допуска: страница заводится на продукт, у которого есть
# что сказать, а не на тот, у которого много чего можно поделить. Прежде тот
# же порог стоял на входе и снимал страницу целиком — вместе с головой ниши.
MIN_FACTS = 3

FAMILY = {"pantry": "the pantry", "fridge": "the refrigerator",
          "freeze": "the freezer"}

SLOT_EN = {
    "freeze": "freezer",
    "freeze_purchase": "freezer from the day of purchase",
    "pantry": "pantry",
    "pantry_purchase": "pantry from the day of purchase",
    "pantry_open": "pantry after opening",
    "fridge": "refrigerator",
    "fridge_purchase": "refrigerator from the day of purchase",
    "fridge_open": "refrigerator after opening",
    "fridge_thaw": "refrigerator after thawing",
}

# У каждой строки таблицы своё СОБЫТИЕ отсчёта. Одно поле на все строки
# считало срок «от дня покупки» от дня хранения, а срок «после вскрытия» — от
# дня, когда упаковка ещё была закрыта: ошибка в обе стороны сразу.
CLOCK_OF = {
    "freeze": "stored", "freeze_purchase": "bought",
    "pantry": "stored", "pantry_purchase": "bought", "pantry_open": "opened",
    "fridge": "stored", "fridge_purchase": "bought", "fridge_open": "opened",
    "fridge_thaw": "thawed",
}

CLOCK_LABEL = {
    "stored": "Stored on",
    "bought": "Bought on",
    "opened": "Opened on",
    "thawed": "Thawed on",
}

CLOCK_TAIL = {
    "stored": "after the day you stored it",
    "bought": "after the day you bought it",
    "opened": "after the day you opened it",
    "thawed": "after the day it finished thawing",
}

SLOT_TH = {
    "freeze": "Freezer",
    "freeze_purchase": "Freezer, from purchase",
    "pantry": "Pantry",
    "pantry_purchase": "Pantry, from purchase",
    "pantry_open": "Pantry, after opening",
    "fridge": "Refrigerator",
    "fridge_purchase": "Refrigerator, from purchase",
    "fridge_open": "Refrigerator, after opening",
    "fridge_thaw": "Refrigerator, after thawing",
}

QUOTE = chr(34)


def esc(s):
    s = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s.replace(QUOTE, "&quot;")


def title_of(it):
    return it["name"] + (", " + it["subtitle"] if it["subtitle"] else "")


def short_of(it):
    """Имя для крупной строки. Полное имя источника печатается тут же, ниже.

    Ставится в render.assign_short по всему корпусу, потому что различимость —
    свойство НАБОРА, а не одной записи. Здесь только чтение.
    """
    return it.get("short") or it["name"]


# Множественное число ищется у ГЛАВНОГО слова имени, а не у всей строки:
# «Ketchup, cocktail, or chili sauce» — про кетчуп, и глагол при нём
# единственный. Хвосты «-ss», «-us», «-is» на множественное не указывают
# («Hummus», «Asparagus», «Molasses»).
_SING_TAIL = ("ss", "us", "is", "os")


def is_plural(name):
    head = re.split(r"[,(]", name)[0].strip()
    w = re.findall(r"[A-Za-z]+", head)
    if not w:
        return False
    w = w[-1].lower()
    return len(w) > 2 and w.endswith("s") and not w.endswith(_SING_TAIL)


def does_do(name):
    """Глагол при имени: «How long DO apples last» / «How long DOES milk last».

    66 описаний в выдаче читались «How long Apples keeps in the fridge» — то
    самое согласование, которое гейт уже ловит у чисел и не ловил у имён.
    """
    return "do" if is_plural(name) else "does"


def keeps_word(name):
    return "keep" if is_plural(name) else "keeps"


def human(days, unit=None):
    """Дни словами. ОДНА функция на сайт: величина, названная в двух местах
    по-разному, однажды разойдётся публично.

    Единица выбирается ТА, в которой величина выражается целым числом, — то
    есть та, в которой её напечатал источник. Раньше порог стоял по величине,
    и месяц источника выходил «4 weeks»: в таблице стояло 4 недели, а рядом
    посчитанная по тем же данным кратность говорила 4,3 раза. Читатель видел
    два числа об одном и том же, и они не сходились.
    """
    if days is None:
        return "unknown"
    sizes = {"hours": 1 / 24.0, "days": 1.0, "weeks": 7.0, "months": 30.0,
             "years": 365.0}
    if unit in sizes:
        q = days / sizes[unit]
        if abs(q - round(q)) < 0.01 and round(q) >= 1:
            k, name = int(round(q)), unit.rstrip("s")
            return "1 %s" % name if k == 1 else "%d %ss" % (k, name)
    if days < 1:
        k = int(round(days * 24))
        return "1 hour" if k == 1 else "%d hours" % k
    for size, name in ((365.0, "year"), (30.0, "month"), (7.0, "week")):
        q = days / size
        if days >= size and abs(q - round(q)) < 0.01:
            k = int(round(q))
            return "1 %s" % name if k == 1 else "%d %ss" % (k, name)
    k = int(round(days))
    return "1 day" if k == 1 else "%d days" % k


def scale_of(days, unit=None):
    """Единица, в которой ЧИТАЕТСЯ срок, — ровно та, которую выберет human.

    Раньше это были две независимые лестницы порогов, и они разошлись: на
    странице стояло «1 week becomes 1 month» и тут же «days turning into
    weeks». Одна величина — одна функция; здесь просто спрашиваем ту же.
    """
    if days is None:
        return None
    word = human(days, unit).split()[-1]
    return word if word.endswith("s") else word + "s"


def band(v, unit=None):
    if v is None:
        return None
    if v[0] == "no":
        return "not recommended"
    lo, hi = v
    if abs(hi - lo) < 0.01:
        return human(hi, unit)
    return "%s to %s" % (human(lo, unit), human(hi, unit))


SHELF_SHORT = {
    "fridge": "in the fridge", "fridge_purchase": "in the fridge",
    "fridge_open": "in the fridge once opened",
    "fridge_thaw": "in the fridge once thawed",
    "pantry": "in the pantry", "pantry_purchase": "in the pantry",
    "pantry_open": "in the pantry once opened",
}




def shelf_h(it):
    """Срок вне морозилки словами, в единице источника. Единственная точка
    входа: величина, названная в двух местах по-разному, однажды разойдётся
    публично, и у нас это уже случалось с рангом."""
    return human(fk.shelf_days(it), fk.unit_of(it, fk.shelf_key(it)))


def u(it, key):
    """Единица, в которой источник напечатал эту ячейку."""
    return it["units"].get(key)


def slot_text(it, key):
    """Значение ячейки словами, в единице источника. ОДНА точка входа: таблица
    и проза обязаны называть одно и то же число одинаково."""
    return band(it["slots"].get(key), u(it, key))


WORD_N = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
          7: "seven", 8: "eight", 9: "nine"}


# Границы, за которыми отношение перестаёт быть «тем же самым». Ниже 1,15
# фраза «N times longer» либо ложна, либо бессмысленна: «1 times longer» —
# это «не длиннее вовсе».
GAIN_UP, GAIN_DOWN = 1.15, 0.87


def gain_way(r):
    """Куда смотрит отношение: «up» — морозилка даёт больше, «flat» — не
    меняет ничего, «down» — морозилка держит МЕНЬШЕ.

    Одна функция на всю сборку. Пока направление подразумевалось словом
    «longer» в каждом шаблоне, девять страниц обещали выигрыш там, где
    морозилка держит вшестеро меньше.
    """
    if r >= GAIN_UP:
        return "up"
    return "flat" if r > GAIN_DOWN else "down"


def mult(x):
    """Кратность словами, в форме, которая складывается с «longer».

    Слово «twice» — наречие: «twice longer» и «a factor of twice» это не
    английский. Кратность всегда «N times», а «во столько-то раз» для оборота
    «a factor of» берётся из factor().
    """
    if x >= 9.5:
        return "%d times" % int(round(x))
    if abs(x - round(x)) < 0.08:
        return "%d times" % int(round(x))
    return "%s times" % ("%.1f" % x).rstrip("0").rstrip(".")


def factor(x):
    """Число для оборота «a factor of»: там стоит ЧИСЛО, а не кратность."""
    if abs(x - round(x)) < 0.08:
        n = int(round(x))
        return WORD_N.get(n, "%d" % n)
    return ("%.1f" % x).rstrip("0").rstrip(".")


def listing(names):
    """Перечисление по-английски, с and перед последним."""
    names = list(names)
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return "%s and %s" % (names[0], names[1])
    return "%s and %s" % (", ".join(names[:-1]), names[-1])


def plural_en(n, one, many=None):
    """Согласование числа: «1 rated figures» читается как машина."""
    return "%d %s" % (n, one if n == 1 else (many or one + "s"))


def best_slot(it, *keys):
    """Как fk.best, но возвращает ещё и КАКАЯ ячейка выиграла: название способа
    прозе нужно не меньше, чем число."""
    best = None
    for k in keys:
        v = it["slots"].get(k)
        if v and v[0] != "no":
            if best is None or v[1] > best[1][1]:
                best = (k, v)
    return best


def widest_span(it):
    """Самый широкий диапазон ВНУТРИ одной ячейки: во сколько раз оптимистичный
    конец больше осторожного. Это про неуверенность источника."""
    best_r, best_v = 0.0, None
    for key, v in it["slots"].items():
        if v[0] == "no" or not v[0]:
            continue
        lo, hi = v
        if lo > 0 and hi / lo > best_r:
            best_r, best_v = hi / lo, (key, lo, hi)
    if best_v and best_r > 1.01:
        return (best_r, best_v)
    return None


def method_spread(it):
    """Во сколько раз лучший способ хранения обгоняет худший. Это НЕ разброс
    внутри диапазона: тот про неуверенность, а этот про то, насколько вообще
    важен выбор способа."""
    tops = [(v[1], k) for k, v in it["slots"].items()
            if v[0] != "no" and v[1]]
    if len(tops) < 2:
        return None
    lo, hi = min(tops), max(tops)
    if lo[0] > 0 and hi[0] / lo[0] > 1.05:
        return (hi[0] / lo[0], lo[0], hi[0], lo[1], hi[1])
    return None


def pct_below(sorted_vals, v):
    """Доля корпуса ниже значения, в процентах. Нужна, чтобы «больше, чем почти
    у всего остального» было проверенным утверждением, а не фигурой речи."""
    if not sorted_vals:
        return None
    lo, hi = 0, len(sorted_vals)
    while lo < hi:
        mid = (lo + hi) // 2
        if sorted_vals[mid] < v:
            lo = mid + 1
        else:
            hi = mid
    return int(round(100.0 * lo / len(sorted_vals)))


# ------------------------------------------------------------------ контекст

def context(items, ranks):
    """Всё, что нужно знать о КОРПУСЕ, чтобы утверждение о продукте было
    проверяемым: распределения и порядок внутри категории."""
    gains = sorted(fk.freeze_gain(i).r for i in items if fk.freeze_gain(i))
    opens = sorted(fk.opening_cost(i).r for i in items if fk.opening_cost(i))
    shelf = sorted(fk.shelf_days(i) for i in items
                   if fk.shelf_days(i) is not None)
    by_cat = {}
    for it in items:
        d = fk.shelf_days(it)
        if d is not None:
            by_cat.setdefault(it["category"], []).append(it)
    for cat in by_cat:
        by_cat[cat].sort(key=lambda x: (-fk.shelf_days(x), x["id"]))
    # Сколько ещё продуктов записаны тем же НАБОРОМ мест хранения. Величина
    # вычисленная по всему корпусу: источник её нигде не называет, а она сразу
    # говорит, обычна эта запись или редкая.
    pat = {}
    for it in items:
        key = tuple(sorted(families(it)))
        pat[key] = pat.get(key, 0) + 1
    # Распределение по МЕСТУ ХРАНЕНИЯ. Доля «дольше, чем 29% всего списка»
    # считалась против корпуса, где рядом стоят пищевая сода, мёд и консервы:
    # она отвечала на вопрос, которого у человека с открытым холодильником
    # нет. Сравнивать надо с тем, что USDA кладёт В ТО ЖЕ МЕСТО.
    by_place = {}
    for fam in PLACE_KEYS:
        by_place[fam] = sorted(v for v in (place_best(it, fam) for it in items)
                               if v is not None)
    # Счёт по ПРЕДИКАТУ, который произносит предложение, а не по набору мест.
    # «no pantry figure exists for it, as for 132 of the 466 foods» стояло на
    # 66 страницах, и 132 — это число продуктов с набором РОВНО {холодильник,
    # морозилка}, тогда как без кладовой их вдвое больше. Число было верное,
    # но отвечало на более узкий вопрос, чем задан фразой.
    no_place = {}
    for fam in PLACE_KEYS:
        no_place[fam] = sum(1 for it in items if fam not in families(it))
    # Когорты: кто ещё записан ТЕМ ЖЕ набором ячеек и кто лежит на той же
    # полке источника. Имена оттуда — самые непохожие слова страницы.
    by_slots, by_sub = {}, {}
    for it in items:
        by_slots.setdefault(tuple(all_keys(it)), []).append(it)
        by_sub.setdefault((it["category"], it["subcategory"]), []).append(it)
    for row in list(by_slots.values()) + list(by_sub.values()):
        row.sort(key=lambda x: int(x["id"]))
    # РОДНЯ ПО СЛОВУ: другие записи источника, чьё имя содержит имя этого
    # продукта целиком. «Turkey» и рядом «Turkey parts», «Ground turkey or
    # chicken», «Turkey bacon» — три отдельные записи с тремя разными
    # морозильными сроками, о которых страница индейки не говорила ни слова.
    kin = {}
    for it in items:
        own = set(re.findall(r"[a-z0-9]+", it["name"].lower()))
        kin[it["id"]] = [x for x in items
                         if x["id"] != it["id"]
                         and own < set(re.findall(r"[a-z0-9]+",
                                                  x["name"].lower()))]
    for row in kin.values():
        row.sort(key=lambda x: int(x["id"]))
    return {"gains": gains, "opens": opens, "shelf": shelf, "cat": by_cat,
            "ranks": ranks, "patterns": pat, "total": len(items),
            # СТРОК В СНИМКЕ — столько, сколько их в файле источника, а не
            # столько, сколько состояний осталось после снятия дублей. Здесь
            # стояло второе, а печаталось первым именем: страницы говорили
            # «record 682, one of the 658 rows in the snapshot», и число
            # записи оказывалось больше числа строк. Дублей при этом ноль —
            # проверено по всем полям, — а совпадают по имени три пары,
            # различаясь рубрикой и ячейками.
            "rows": fk.source_rows(),
            "states": sum(len(states_of(it)) for it in items),
            "place": by_place, "no_place": no_place,
            "slotset": by_slots, "shelfmates": by_sub, "kin": kin}


# Семейства мест: ячейка -> место. Одна таблица на всю сборку.
PLACE_KEYS = {
    "fridge": ("fridge", "fridge_purchase", "fridge_open", "fridge_thaw"),
    "pantry": ("pantry", "pantry_purchase", "pantry_open"),
    "freeze": ("freeze", "freeze_purchase"),
}

PLACE_WORD = {"fridge": "refrigerator", "pantry": "pantry",
              "freeze": "freezer"}

# То же место С АРТИКЛЕМ, для позиции подлежащего/дополнения.
PLACE_NOUN = {"fridge": "the refrigerator", "pantry": "the pantry",
              "freeze": "the freezer"}


def place_best(it, place):
    """Самое длинное окно продукта в ЭТОМ месте, по всем его состояниям.

    ОДНА функция на обе стороны сравнения: и распределение по корпусу, и
    величина одного продукта считаются ею. Пока сторон было две, корпус
    считался по ведущему состоянию, а страница — по сигнальному, и это ровно
    та пара, которая у нас однажды разошлась публично.
    """
    vals = [r[3] for r in rated_all(it) if r[1].split("_")[0] == place]
    return max(vals) if vals else None


def neighbours_in_rank(it, ctx):
    """Кто стоит непосредственно выше и ниже в своей категории. Имена соседей —
    самые непохожие слова, какие вообще может дать страница."""
    row = ctx["cat"].get(it["category"]) or []
    for i, x in enumerate(row):
        if x["id"] == it["id"]:
            above = row[i - 1] if i > 0 else None
            below = row[i + 1] if i + 1 < len(row) else None
            return above, below
    return None, None


# -------------------------------------------------------------------- форма

def shape(it, ctx):
    """Форма данных продукта: признаки, а не значения. По ней выбирается, ЧТО
    сказать; значения подставляются уже внутри выбранной ветки."""
    g, o = fk.freeze_gain(it), fk.opening_cost(it)
    sp, d = widest_span(it), fk.shelf_days(it)
    r = ctx["ranks"].get(it["id"])
    sts = states_of(it)
    # Ячейки, заполненные ХОТЬ У ОДНОГО состояния. Абзац вводит бланк, а в
    # бланке стоят все состояния: посчитанное по ведущему число спорило бы с
    # тем, что видно строкой ниже.
    filled = {k for st in sts for k in st["slots"]}
    s = {
        "gain": g, "open": o, "span": sp, "days": d, "rank": r,
        "spread": method_spread(it),
        "filled": len(filled),
        "n_states": len(sts),
        "kinds": [kind_title(it, x) for x in sts],
        "lead_kind": (kind_title(it, lead_state(it))
                      if len(sts) > 1 and not split(it) else None),
        "subject": (kind_title(it, lead_state(it))
                    if len(sts) > 1 and not split(it) else title_of(it)),
        "split": split(it),
        "facts": len(fk.facts(it, ctx["ranks"])),
        "no_slots": no_only_keys(it),
        "mixed": mixed_keys(it),
        "thaw": thaw_state(it) is not None,
        "tips": len(tips_all(it)),
        "days_u": fk.unit_of(it, fk.shelf_key(it)),
        "cat_size": len(ctx["cat"].get(it["category"]) or []),
        "n_gain": len(ctx["gains"]),
        "n_open": len(ctx["opens"]),
        "fam": families(it),
    }
    s["fam_count"] = ctx["patterns"].get(tuple(sorted(s["fam"])), 0)
    s["fam_total"] = ctx["total"]
    # Счёт для КАЖДОГО предиката, который умеет произнести абзац. Берётся тот,
    # который назван словами, а не тот, что удобнее посчитать.
    s["no_place_n"] = dict(ctx["no_place"])
    s["scale"] = scale_of(d, s["days_u"])
    # «Морозилки нет» — утверждение о СПОСОБЕ: ни одно состояние не даёт
    # морозильного срока, и хотя бы одно говорит «не надо».
    s["no_freeze"] = ("freeze" not in s["fam"]
                      and any(k.startswith("freeze") for k in s["no_slots"]))
    # Стороны отношения спрашиваются ПО ИМЕНИ. Позиция в кортеже уже
    # значила у двух функций разное, и «closed» одной была «opened»
    # другой.
    s["gain_shift"] = bool(g) and scale_of(g.den) != scale_of(g.num)
    s["open_shift"] = bool(o) and scale_of(o.num) != scale_of(o.den)
    s["gain_pct"] = pct_below(ctx["gains"], g.r) if g else None
    s["open_pct"] = pct_below(ctx["opens"], o.r) if o else None
    s["shelf_pct"] = pct_below(ctx["shelf"], d) if d is not None else None
    s["above"], s["below"] = neighbours_in_rank(it, ctx)
    row = ctx["cat"].get(it["category"]) or []
    s["tied"] = sum(1 for x in row
                    if d is not None and abs(fk.shelf_days(x) - d) < 0.01)
    # Сколько записей корпуса держат РОВНО тот же срок. Без этого числа
    # доля «ниже нас» в 0% печаталась как утверждение и не значила ничего:
    # 13 страниц несли «keeps longer than 0% of everything listed».
    s["shelf_ties"] = sum(1 for x in ctx["shelf"]
                          if d is not None and abs(x - d) < 0.01)
    s["shelf_n"] = len(ctx["shelf"])
    # Место связывающего окна и положение продукта СРЕДИ ТОГО ЖЕ МЕСТА.
    h = hot_slot(it)
    s["place"] = h[1].split("_")[0] if h else None
    pv = ctx["place"].get(s["place"]) or []
    hv = place_best(it, s["place"]) if (h and pv) else None
    s["place_n"] = len(pv)
    s["place_pct"] = pct_below(pv, hv) if hv is not None else None
    s["place_ties"] = sum(1 for x in pv
                          if hv is not None and abs(x - hv) < 0.01)
    s["lead"] = _lead(s)
    return s


def _lead(s):
    """Что на этой странице главное. Порядок — по силе сигнала, и он же порядок
    интереса читателя: запрет важнее кратности, смена единицы важнее величины,
    край списка важнее середины."""
    if s["no_freeze"]:
        return "no_freeze"
    if s["gain_shift"] and gain_way(s["gain"].r) == "up":
        return "gain_jump"
    if s["open_shift"]:
        return "open_jump"
    # Край списка — только когда край ОДИН. При ничьей «самое недолговечное»
    # печаталось рядом с соседом, держащим ровно столько же.
    if (s["rank"] and s["cat_size"] >= 6 and s["tied"] <= 1
            and s["rank"][0] in (1, s["cat_size"])):
        return "rank_edge"
    if (s["gain_pct"] is not None and s["gain_pct"] >= 85
            and gain_way(s["gain"].r) == "up"):
        return "gain_top"
    if s["open_pct"] is not None and s["open_pct"] >= 85:
        return "open_top"
    if s["span"] and s["span"][0] >= 2.5:
        return "span_wide"
    if s["gain"]:
        return {"up": "gain_flat", "flat": "gain_none",
                "down": "gain_worse"}[gain_way(s["gain"].r)]
    if s["open"]:
        return "open_flat"
    if s["scale"] in ("hours", "days"):
        return "short_life"
    if s["scale"] == "years":
        return "long_life"
    if s["filled"] >= 5:
        return "many_methods"
    return "few_methods"


# ------------------------------------------------------------ ведущий абзац
#
# Один заголовок и одна рамка на КАЖДУЮ форму данных. Заголовок называет то,
# что интересно на ЭТОЙ странице, а не то, что мы пишем на всех.

def subj(s):
    """Кто именно ранжируется. У продукта из нескольких состояний ранг считают
    по ВЕДУЩЕМУ, и называть его «this item» значит приписать всему продукту
    окно одного его состояния — на странице, где рядом напечатаны другие."""
    return s["subject"] if s["n_states"] > 1 else "This item"


def subj_l(s):
    return s["subject"] if s["n_states"] > 1 else "this item"


HEADS = {
    "no_freeze": "Why the freezer is not an option here",
    "gain_jump": "Freezing changes the unit, not just the number",
    "open_jump": "What opening the package actually costs",
    "rank_edge": "The edge of its own category",
    "gain_top": "One of the largest freezer gains in the data",
    "open_top": "One of the steepest drops after opening",
    "span_wide": "How vague the source is about this one",
    "gain_flat": "The freezer helps less here than you would expect",
    "gain_none": "The freezer changes nothing here",
    "gain_worse": "The freezer is the shorter option here",
    "open_flat": "Sealed against opened",
    "short_life": "A short window, and what shortens it further",
    "long_life": "Built to sit on a shelf",
    "many_methods": "Nine ways to store it, and how many are rated",
    "few_methods": "The methods the USDA actually rates for this item",
}


# Ячейки вне морозилки. Список объявлен ОДИН раз: пока он стоял россыпью в
# вызове, «все места, кроме морозилки» и «то, чем страница отвечает» были
# двумя разными наборами, и одно молча подменяло другое.
NON_FREEZE_KEYS = ("fridge", "fridge_purchase", "fridge_open",
                   "pantry", "pantry_purchase", "pantry_open")


def _l_no_freeze(it, s):
    # ОДНА ВЕЛИЧИНА — ОДИН КОНЕЦ ДИАПАЗОНА, И ОДИН НОСИТЕЛЬ. Здесь стоял
    # `best_slot`, то есть САМОЕ ДЛИННОЕ окно вне морозилки, — а шапка
    # страницы отвечает СВЯЗЫВАЮЩИМ, тем, что кончится первым. На /caviar/
    # это давало «весь ответ — 1–4 недели» над собственным ответом «2 дня ·
    # Safety limit · past it, throw it out»: ошибка в четырнадцать раз, в
    # сторону съеденной испорченной еды, на странице про икру.
    #
    # И вторая ложь в той же фразе: «a single field» печаталось на 11
    # страницах из 22, где заполнено больше одного не-морозильного поля, а
    # таблица прямо ниже печатала их все.
    filled = [k for k in NON_FREEZE_KEYS
              if (it["slots"].get(k) or ("no",))[0] != "no"]
    hot = hot_slot(it)
    bs = None
    if hot and hot[1] in filled:
        bs = (hot[1], it["slots"][hot[1]])
    elif filled:
        bs = best_slot(it, *NON_FREEZE_KEYS)
    if not bs:
        return ("The USDA marks freezing as not recommended for this item and "
                "publishes no usable figure for any other method either, which "
                "leaves the handling notes below as the only guidance the "
                "source is prepared to give on it.")
    key, _v = bs
    v = slot_text(it, key)
    # «There is no colder option to fall back on» стояло на 21 странице и не
    # говорило НИ ПОЧЕМУ, НИ ЧТО ДЕЛАТЬ ВМЕСТО. «Not recommended» — это
    # приговор без основания: источник его не объясняет, и дописывать за него
    # причину значит печатать своё утверждение под его именем. Зато можно
    # сказать, чем этот приговор ТОЧНО не является.
    if s["n_states"] > 1:
        return fit_para(
            "The USDA marks the freezer as not recommended for every one of "
            "the %d kinds under this name, and for %s the whole answer is %s "
            "in the %s." % (s["n_states"], s["subject"], v, SLOT_EN[key]),
            "The source prints the verdict without a reason and this page "
            "will not invent one.",
            std(NOT_RECOMMENDED_WHY))
    if len(filled) > 1:
        return fit_para(
            "The USDA marks the freezer as not recommended for this item, so "
            "the answer comes from the %s figure: %s. The source fills %d of "
            "its fields outside the freezer here, and every one of them is "
            "printed below." % (SLOT_EN[key], v, len(filled)),
            "The source prints that verdict without a reason, and a reason we "
            "made up would be ours rather than theirs.",
            std(NOT_RECOMMENDED_WHY))
    return fit_para(
        "The USDA marks the freezer as not recommended for this item, so the "
        "whole answer is a single field: %s in the %s." % (v, SLOT_EN[key]),
        "The source prints that verdict without a reason, and a reason we "
        "made up would be ours rather than theirs.",
        std(NOT_RECOMMENDED_WHY))


def den_in(s):
    """Знаменатель выигрыша заморозки СЛОВАМИ, взятый у самого отношения.

    Слово «refrigerator» стояло вписанным в каждый шаблон, а делить могло на
    шкаф: на 24 страницах бирка и проза называли одним словом два разных
    знаменателя. Сторона деления спрашивается у fk.Ratio, а не подразумевается
    шаблоном — ровно то же правило, что и для направления.
    """
    return "in %s" % DEN_PHRASE[s["gain"].den_key]


def _l_gain_jump(it, s):
    g = s["gain"]
    r, fr, fz = g.r, g.den, g.num
    uf, uz = u(it, g.den_key), u(it, g.num_key)
    fr_h, fz_h = human(fr, uf), human(fz, uz)
    u1, u2 = scale_of(fr, uf), scale_of(fz, uz)
    d = den_in(s)
    if u2 == "years":
        return ("Freezing moves this item onto a different calendar. %s %s "
                "becomes %s in the freezer, %s longer, and the "
                "point at which you stop counting in %s and start counting in "
                "years." % (human(fr), d, human(fz), mult(r), u1))
    if u1 in ("hours", "days"):
        return ("Here the freezer does not so much extend the answer as replace "
                "it. %s %s becomes %s in the freezer: %s "
                "longer, and %s turning into %s."
                % (fr_h, d, fz_h, mult(r), u1, u2))
    return ("Freezing does not just add time to this item, it changes the unit "
            "the answer is written in: %s %s against %s in "
            "the freezer, %s longer, %s in place of %s."
            % (fr_h, d, fz_h, mult(r), u2, u1))


def _l_open_jump(it, s):
    o = s["open"]
    uc, uo = u(it, o.num_key), u(it, o.den_key)
    c_h, o_h = human(o.num, uc), human(o.den, uo)
    u1, u2 = scale_of(o.num, uc), scale_of(o.den, uo)
    return ("Opening the package is the decision that settles this page. "
            "Sealed, the item holds %s %s; once open it holds %s %s, the same "
            "food measured in %s instead of %s, a drop of %s."
            % (c_h, SHORT_WHERE[o.num_key], o_h, SHORT_WHERE[o.den_key],
               u2, u1, mult(o.r)))


def _l_rank_edge(it, s):
    place, total, days = s["rank"]
    if place == 1 and s["below"] is not None:
        return ("Nothing else the USDA lists under %s keeps longer outside the "
                "freezer. %s holds %s, while the next one down, %s, "
                "manages %s. That is the gap at the top of a list of %d."
                % (it["category"], subj(s), shelf_h(it), title_of(s["below"]),
                   shelf_h(s["below"]), total))
    if s["above"] is not None:
        return ("%s is the shortest-lived entry in the %s list: %s outside "
                "the freezer, against %s for %s, the item immediately above "
                "it. All %d of the others keep longer."
                % (subj(s), it["category"], shelf_h(it),
                   shelf_h(s["above"]), title_of(s["above"]), total - 1))
    return ("Among the %d items the USDA lists under %s, %s sits at "
            "position %d by shelf life outside the freezer, holding %s."
            % (total, it["category"], subj_l(s), place, shelf_h(it)))


def _l_gain_top(it, s):
    g = s["gain"]
    return ("Freezing pays off here more than it does for %d%% of the %d foods "
            "where the USDA publishes both figures. The freezer gives %s what "
            "%s gives: %s against %s."
            % (s["gain_pct"], s["n_gain"], mult(g.r),
               DEN_PHRASE[g.den_key],
               human(g.den, u(it, g.den_key)),
               human(g.num, u(it, g.num_key))))


def _l_open_top(it, s):
    o = s["open"]
    return ("Few items on this site lose as much to a broken seal. The drop "
            "after opening is steeper here than for %d%% of the %d entries "
            "where both figures exist: %s %s down to %s %s, a factor of %s."
            % (s["open_pct"], s["n_open"],
               human(o.num, u(it, o.num_key)), SHORT_WHERE[o.num_key],
               human(o.den, u(it, o.den_key)), SHORT_WHERE[o.den_key],
               factor(o.r)))


def _l_span_wide(it, s):
    ratio, (key, lo, hi) = s["span"]
    uk = u(it, key)
    return ("The source is unusually unsure about this one. Its widest range, "
            "the %s, runs from %s to %s, a factor of %s between the cautious "
            "end and the optimistic one, on a figure most people read as a "
            "single number."
            % (SLOT_EN[key], human(lo, uk), human(hi, uk), factor(ratio)))


def _l_gain_flat(it, s):
    g = s["gain"]
    uf, uz = u(it, g.den_key), u(it, g.num_key)
    return ("The freezer buys less here than its reputation suggests: %s what "
            "%s gives, %s against %s, both still measured in %s. For "
            "this item freezing is an extension rather than a different way of "
            "keeping it." % (mult(g.r), DEN_PHRASE[g.den_key],
                             human(g.den, uf), human(g.num, uz),
                             scale_of(g.num, uz)))


def _l_gain_none(it, s):
    """Морозилка не меняет ничего: источник даёт ОДИН И ТОТ ЖЕ срок.

    Прежде это печаталось как «1 times longer than the refrigerator» — то
    есть «длиннее ровно во столько раз, во сколько не длиннее».
    """
    g = s["gain"]
    uf, uz = u(it, g.den_key), u(it, g.num_key)
    return ("The USDA gives this item the same window either way: %s %s "
            "and %s in the freezer. Freezing is not a mistake "
            "here, it simply buys nothing, and %s is the "
            "cheaper place to keep it."
            % (human(g.den, uf), den_in(s), human(g.num, uz),
               DEN_PHRASE[g.den_key]))


def _l_gain_worse(it, s):
    """Морозилка держит МЕНЬШЕ. Это тоже сведение, и оно полезнее выигрыша:
    именно его читатель бы не угадал."""
    g = s["gain"]
    uf, uz = u(it, g.den_key), u(it, g.num_key)
    return ("Here the freezer is the shorter option, not the longer one: %s "
            "%s against %s frozen, %s less. That is the "
            "reverse of what the freezer usually does, and it is the one "
            "thing about this item worth remembering."
            % (human(g.den, uf), den_in(s), human(g.num, uz),
               mult(1.0 / g.r) if g.r else "far"))


def _l_open_flat(it, s):
    o = s["open"]
    return ("Opening the package costs %s here: %s %s against %s %s. "
            "That is a real difference and worth dating the container "
            "for, but not the collapse it becomes for the more perishable "
            "items in the same list."
            % (mult(o.r), human(o.num, u(it, o.num_key)),
               SHORT_WHERE[o.num_key], human(o.den, u(it, o.den_key)),
               SHORT_WHERE[o.den_key]))


def _l_short_life(it, s):
    place = s["rank"][0] if s["rank"] else 0
    return ("%s is one of the short-lived entries in the data: %s outside "
            "the freezer, position %d of %d in the %s list. At that scale a "
            "day of delay is a large share of the whole window, which is why "
            "the figure is printed as a range rather than an average."
            % (subj(s), shelf_h(it), place, s["cat_size"], it["category"]))


def _l_long_life(it, s):
    # Доля берётся у corpus_place: край она называет именем, а не нулём или
    # сотней. «longer than 100% of everything listed» — это «дольше всех»,
    # сказанное числом, которое ничего не значит.
    return ("%s is built to sit. It keeps %s outside the freezer. %s It is "
            "long enough that the date it went into storage matters more "
            "than anything you can judge by looking at it."
            % (subj(s), shelf_h(it), corpus_place(s)))


def _l_many_methods(it, s):
    names = [SLOT_EN[k] for k in all_keys(it)]
    sp = s["spread"]
    if s["n_states"] > 1:
        return ("Across the %d kinds the USDA lists under this name it rates "
                "%d of its nine storage methods somewhere, among them the %s. "
                "No kind carries all of them, which is why the windows below "
                "are kept apart instead of averaged."
                % (s["n_states"], len(names), listing(names[:3])))
    if sp:
        return ("The USDA rates %d of its nine storage methods for this item, "
                "among them the %s, and the longest of them beats the shortest "
                "by %s. The method matters more here than the food does."
                % (len(names), listing(names[:3]), mult(sp[0])))
    return ("The USDA rates %d of its nine storage methods for this item: the "
            "%s. That is more than it manages for most entries, and all of "
            "them are printed below rather than reduced to one number."
            % (len(names), listing(names)))


def _l_few_methods(it, s):
    names = [SLOT_EN[k] for k in all_keys(it)]
    verb = " is" if len(names) == 1 else " are"
    if s["n_states"] > 1:
        return ("The USDA rates only %d of its nine storage methods anywhere "
                "in the %d kinds it lists under this name, and the %s%s what "
                "it rates. The other %d slots are blank in every kind, and a "
                "blank is not a zero."
                % (len(names), s["n_states"], listing(names), verb,
                   9 - len(names)))
    return ("The USDA rates only %d of its nine storage methods for this item, "
            "and the %s%s what it rates. The other %d slots are blank, and a "
            "blank is not a zero: it means no published figure, not that the "
            "method fails."
            % (len(names), listing(names), verb, 9 - len(names)))


LEAD_WRITERS = {
    "no_freeze": _l_no_freeze, "gain_jump": _l_gain_jump,
    "open_jump": _l_open_jump, "rank_edge": _l_rank_edge,
    "gain_top": _l_gain_top, "open_top": _l_open_top,
    "span_wide": _l_span_wide, "gain_flat": _l_gain_flat,
    "gain_none": _l_gain_none, "gain_worse": _l_gain_worse,
    "open_flat": _l_open_flat, "short_life": _l_short_life,
    "long_life": _l_long_life, "many_methods": _l_many_methods,
    "few_methods": _l_few_methods,
}


# ---------------------------------------------------------- поддерживающие
#
# Ведущий сигнал уже потрачен на рамку. Остальные идут добавками в порядке
# силы, и каждая тоже ветвится: короткая добавка, повторяющаяся дословно на
# половине корпуса, вернула бы нас ровно туда, откуда мы ушли.

def _s_gain(it, s):
    g = s["gain"]
    r = g.r
    fr, fz = human(g.den, u(it, g.den_key)), human(g.num, u(it, g.num_key))
    way = gain_way(r)
    if way == "flat":
        return ("The two figures are the same: %s either way, so the choice "
                "between them is about space, not time." % fr)
    if way == "down":
        return ("Frozen it holds %s against %s %s, so the "
                "freezer costs time here instead of buying it."
                % (fz, fr, den_in(s)))
    if r >= 20:
        return ("The freezer stretches it by %s over %s, from %s to %s, which "
                "is the kind of gap that makes the freezer a different "
                "decision rather than a longer one."
                % (mult(r), DEN_PHRASE[g.den_key], fr, fz))
    return ("Freezing extends it by %s over %s, from %s to %s."
            % (mult(r), DEN_PHRASE[g.den_key], fr, fz))


def _s_open(it, s):
    o = s["open"]
    return ("Opening the package costs %s: %s %s, %s %s."
            % (mult(o.r), human(o.num, u(it, o.num_key)),
               SHORT_WHERE[o.num_key],
               human(o.den, u(it, o.den_key)), SHORT_WHERE[o.den_key]))


def _s_rank(it, s):
    place, total, _d = s["rank"]
    if s["above"] is not None and s["below"] is not None:
        return ("In the %s list %s ranks %d of %d, between %s and %s."
                % (it["category"], subj_l(s), place, total,
                   title_of(s["above"]), title_of(s["below"])))
    if s["below"] is not None:
        return ("It heads the %s list of %d, ahead of %s."
                % (it["category"], total, title_of(s["below"])))
    if s["above"] is not None:
        return ("It closes the %s list of %d, behind %s."
                % (it["category"], total, title_of(s["above"])))
    return "It is the only item the USDA ranks under %s." % it["category"]


def _s_span(it, s):
    ratio, (key, lo, hi) = s["span"]
    return ("The %s figure alone spans %s to %s, a factor of %s."
            % (SLOT_EN[key], human(lo, u(it, key)), human(hi, u(it, key)),
               factor(ratio)))


def _s_spread(it, s):
    ratio, lo, hi, klo, khi = s["spread"]
    return ("Across the methods rated, the longest beats the shortest by %s, "
            "%s against %s." % (mult(ratio), human(hi, u(it, khi)),
                                human(lo, u(it, klo))))


def _s_slots(it, s):
    if s["n_states"] > 1:
        return ("Counting every kind, %d of the nine slots carry a figure "
                "somewhere and %d are blank throughout."
                % (s["filled"], 9 - s["filled"]))
    return ("The USDA fills %d of its nine slots here and leaves %d blank."
            % (s["filled"], 9 - s["filled"]))


def _s_thaw(it, s):
    st = thaw_state(it)
    if s["n_states"] > 1:
        return ("%s also carries a separate figure for the refrigerator after "
                "thawing, %s, which most entries leave empty."
                % (kind_title(it, st), st_text(st, "fridge_thaw")))
    return ("It also carries a separate figure for the refrigerator after "
            "thawing, %s, which most items do not."
            % st_text(st, "fridge_thaw"))


def _s_mixed(it, s):
    """Состояния разошлись по одной и той же ячейке. Величина, которой нет ни
    у источника, ни у конкурентов: она видна только после слияния."""
    names = [SLOT_EN[k] for k in s["mixed"]]
    return ("The kinds do not agree about the %s: rated for at least one of "
            "them and marked not recommended for another."
            % listing(names[:2]))


def _s_tips(it, s):
    return ("The source attaches handling notes to %d of the storage "
            "methods, set out in its own words further down." % s["tips"])


def _s_no(it, s):
    names = [SLOT_EN[k] for k in s["no_slots"]]
    return ("The %s carries a not recommended, which is an answer rather than "
            "a gap." % listing(names))


# «rank» здесь нет нарочно: место в категории — предмет отдельного блока
# ниже, и сказанное дважды на одной странице читается как заедание.
SUPPORT_WRITERS = [
    ("gain", _s_gain), ("open", _s_open), ("mixed", _s_mixed),
    ("no_slots", _s_no), ("span", _s_span), ("spread", _s_spread),
    ("thaw", _s_thaw), ("tips", _s_tips), ("filled", _s_slots),
]

# Какой сигнал уже израсходован ведущей рамкой — добавкой он идти не должен,
# иначе абзац дважды скажет одно и то же разными словами.
LEAD_USES = {
    "no_freeze": ("no_slots",), "gain_jump": ("gain",),
    "open_jump": ("open",), "rank_edge": ("rank",), "gain_top": ("gain",),
    "open_top": ("open",), "span_wide": ("span",), "gain_flat": ("gain",),
    "open_flat": ("open",), "short_life": ("rank",), "long_life": (),
    "many_methods": ("filled", "spread"), "few_methods": ("filled",),
}


def wc(text):
    import re as _re
    return len(_re.findall(r"[A-Za-z][A-Za-z'-]*",
                           _re.sub(r"<[^>]+>", " ", text)))


INTRO_HEADS = (
    "Every storage figure the USDA publishes for this item",
    "Turning the range into a date",
    "Items that behave the same way")


def window_for(h2, attrs=""):
    """Окно абзаца — ОДНА функция на сборку и на гейты.

    Таблица окон стояла в render.py, а её копия под именем INTRO_HINT — в
    gates.py: две лестницы для одной величины. Третье окно понадобилось
    блокам глубины, и разойтись они успели бы на первом же прогоне.

    Перечисляющий абзац помечен В РАЗМЕТКЕ, а не именем заголовка:
    заголовок полки называет саму полку и у каждой рубрики свой.
    """
    if 'data-win="detail"' in attrs:
        return DETAIL_MIN, DETAIL_MAX
    if h2 in INTRO_HEADS:
        return INTRO_MIN, INTRO_MAX
    return ANSWER_MIN, ANSWER_MAX


def difference_block(it, s):
    """Блок ОТЛИЧИЯ: рамка по форме данных плюс добавки, пока абзац не дорастёт
    до нижней границы окна. Добавка кладётся только если она в окно влезает.

    Порог вычисленных величин ПРОРЕЖИВАЕТ этот блок и не трогает страницу:
    у ходовой еды источник печатает одну-две ячейки, делить там нечего, а
    вопрос «сколько это лежит» у неё как раз и спрашивают.
    """
    if s["facts"] < MIN_FACTS:
        return ""
    body = LEAD_WRITERS[s["lead"]](it, s)
    used = set(LEAD_USES.get(s["lead"], ()))
    for key, writer in SUPPORT_WRITERS:
        if wc(body) >= ANSWER_MIN:
            break
        if key in used or not s.get(key):
            continue
        piece = writer(it, s)
        if wc(body + " " + piece) > ANSWER_MAX:
            continue
        body += " " + piece
        used.add(key)
    return "<h2>%s</h2><p>%s</p>" % (esc(HEADS[s["lead"]]), body)


def compose(lead, extras, lo=None, hi=None):
    """Собрать абзац: рамка плюс добавки, пока не дорастёт до нижней границы.
    Добавка, которая выбивает абзац за верхнюю, пропускается, а не обрезается."""
    lo = ANSWER_MIN if lo is None else lo
    hi = ANSWER_MAX if hi is None else hi
    body = lead
    for piece in extras:
        if wc(body) >= lo:
            break
        if not piece or wc(body + " " + piece) > hi:
            continue
        body += " " + piece
    return body


def alt_names(it):
    """Имена, под которыми источник индексирует продукт и которых НЕТ в его
    заголовке. Повторить название другими словами — не факт; назвать то, под
    чем его ищут, — факт, и он у каждого свой."""
    have = set(re.findall(r"[a-z]+", title_of(it).lower()))
    out = []
    for k in it["keywords"]:
        w = k.strip()
        if not w or w.lower() in out:
            continue
        parts = set(re.findall(r"[a-z]+", w.lower()))
        if not parts or parts.issubset(have):
            continue
        # «egg» при заголовке «Eggs, in shell» — то же слово, а не другое имя.
        # Отбрасываем ФОРМУ ТОГО ЖЕ слова, а не всё похожее: «egg» при
        # заголовке «Eggs, in shell» — то же слово, а «craisins» при
        # «Cranberries» — другое имя, под которым продукт ищут. Признак формы
        # одного слова: одно начало и разница длины не больше двух букв.
        if any((a.startswith(b) or b.startswith(a)) and abs(len(a) - len(b)) <= 2
               for a in parts for b in have):
            continue
        out.append(w.lower())
    return out[:4]


def families(it):
    """Какие из трёх мест хранения источник вообще рассматривает для продукта.
    Это форма записи, а не её значения, и по ней продукты делятся куда резче,
    чем по числам.

    Считается по ВСЕМ состояниям: абзац вводит бланк, а в бланке стоят все
    состояния. Посчитанный по одному, он отрицал бы морозилку на странице, где
    морозильная строка напечатана строкой ниже.
    """
    f = set()
    for st in states_of(it):
        for k, v in st["slots"].items():
            if v[0] != "no":
                f.add(k.split("_")[0])
    return f


def all_keys(it):
    """Ячейки, которым источник дал срок хоть у одного состояния."""
    have = {k for st in states_of(it) for k, v in st["slots"].items()
            if v[0] != "no"}
    return [k for k, _f, _l in fk.SLOTS if k in have]


def _said_no(it):
    return {k for st in states_of(it) for k, v in st["slots"].items()
            if v[0] == "no"}


def no_only_keys(it):
    """Ячейки, где сказано «не надо» и СПОСОБ не рассматривается больше нигде.

    Сравнение идёт по СПОСОБУ, а не по ячейке: у молока ячейка «в морозилке»
    сказала «не надо» у одного состояния, а ячейка «в морозилке от дня
    покупки» дала три месяца у другого — и страница печатала «морозилка тут не
    вариант» над строкой с морозилкой. «Не надо» — ответ, а не пробел, но
    ответ ЭТОГО состояния.
    """
    have = families(it)
    said_no = _said_no(it)
    return [k for k, _f, _l in fk.SLOTS
            if k in said_no and k.split("_")[0] not in have]


def mixed_keys(it):
    """Способы, о которых состояния расходятся: одному срок, другому «не надо».
    Величина, которой нет ни у источника, ни у конкурентов: она видна только
    после слияния строк в продукт."""
    have = families(it)
    said_no = _said_no(it)
    return [k for k, _f, _l in fk.SLOTS
            if k in said_no and k.split("_")[0] in have]


def thaw_state(it):
    for st in states_of(it):
        v = st["slots"].get("fridge_thaw")
        if v and v[0] != "no":
            return st
    return None


def tips_all(it):
    """Подсказки источника по всем состояниям: (состояние, ячейка, текст).

    Пробелы схлопываются: в источнике внутри предложений встречаются двойные,
    и на странице они видны как разрыв набора. Слова при этом те же — сайт
    заявляет, что печатает подсказку дословно, и печатает.
    """
    return [(st, k, re.sub(r"\s+", " ", t).strip())
            for st in states_of(it)
            for k, t in sorted((st.get("tips") or {}).items())]


# --------------------------------------------------------- остальные блоки

WARM_KEYS = ("fridge", "fridge_purchase", "fridge_open", "fridge_thaw",
             "pantry", "pantry_purchase", "pantry_open")


def rated_warm(it):
    """Все НЕморозильные ячейки, которым источник дал срок."""
    return [(k, v) for k in WARM_KEYS
            for v in [it["slots"].get(k)] if v and v[0] != "no"]




# Подпись поля бирки: место и состояние, как на складской наклейке.
SLOT_LABEL = {
    "freeze": "In the freezer",
    "freeze_purchase": "In the freezer",
    "pantry": "In the pantry",
    "pantry_purchase": "Unopened &middot; in the pantry",
    "pantry_open": "Once opened &middot; in the pantry",
    "fridge": "In the fridge",
    "fridge_purchase": "Unopened &middot; in the fridge",
    "fridge_open": "Once opened &middot; in the fridge",
    "fridge_thaw": "Once thawed &middot; in the fridge",
}

# Условие под величиной: с какого дня идёт счёт. Одно предложение — но это
# подпись поля, а не проза: над перфорацией прозы нет.
CLOCK_CAP = {
    "stored": "Counted from the day you stored it",
    "bought": "Counted from the day you bought it",
    "opened": "Counted from the day you opened it",
    "thawed": "Counted from the day it finished thawing",
}


def rated_slots(it):
    """Все ячейки ВЕДУЩЕГО состояния, которым источник дал срок."""
    out = []
    for key, _f, _l in fk.SLOTS:
        v = it["slots"].get(key)
        if v and v[0] != "no":
            out.append((key, v[0], v[1], CLOCK_OF[key]))
    return out


# ------------------------------------------------ состояния одного продукта
#
# Страница заводится на ПРОДУКТ, а состояний у него может быть несколько:
# «Leftovers» — с мясом, без мяса, пицца. Сроки у состояний РАЗНЫЕ, поэтому
# каждое обязано печатать свой подзаголовок: одна рамка — одно последствие.

def states_of(it):
    """Состояния продукта. У однострочного оно одно, и код везде один."""
    st = it.get("states")
    if st:
        return st
    return [{"id": it.get("id"), "kind": it.get("subtitle", ""),
             "slots": it["slots"], "units": it["units"],
             "tips": it.get("tips", {}), "lead": True}]


def multi(it):
    return len(states_of(it)) > 1


def split(it):
    """Простое слово этой страницы НЕ ЗНАЧИТ одного вида: см. fk.PLAIN_MEANS.

    У такой страницы нет ведущего вида, а значит нет ни одного числа крупной
    строкой: «Beef» — это и фарш, и стейк, и рёбрышки, и любое из этих окон,
    поставленное ответом, отвечает не на тот вопрос.
    """
    return bool(it.get("split"))


def lead_state(it):
    """Вид, ЗА КОТОРЫЙ говорит страница, или None у страницы-выбора."""
    for st in states_of(it):
        if st.get("lead"):
            return st
    return None if split(it) else states_of(it)[0]


def kind_cap(st):
    """Имя состояния для подписи поля. Безымянное печатается номером записи
    источника, а не выбрасывается."""
    k = (st.get("kind") or "").strip()
    if k:
        return k[0].upper() + k[1:]
    return "USDA record %s" % st.get("id")


def nameless_states(it):
    """Сколько состояний продукта источник оставил БЕЗ подзаголовка."""
    return len([1 for x in states_of(it)
                if not (x.get("kind") or "").strip()])


def kind_title(it, st):
    """Имя состояния так, как его ищут: «Milk, lactose-free».

    Состояние без подзаголовка — это строка, чьё имя И ЕСТЬ имя продукта, и
    печатается она именем продукта. Номер записи дописывается ТОЛЬКО когда
    безымянных под одним именем несколько: там он единственное, что их
    различает, и выбросить его нельзя. Пока он дописывался всегда,
    «Potatoes (USDA record 297) · Unopened · in the pantry» стояло подписью
    сигнального поля на одиннадцати страницах — внутренний ключ, вылезший
    в ответ.
    """
    if st.get("kind"):
        return "%s, %s" % (it["name"], st["kind"])
    if nameless_states(it) > 1:
        return "%s (USDA record %s)" % (it["name"], st.get("id"))
    return it["name"]


def st_text(st, key):
    """Величина ячейки СОСТОЯНИЯ словами, в единице источника."""
    return band(st["slots"].get(key), (st.get("units") or {}).get(key))


def field_label(it, st, key):
    """Подпись поля: состояние и место. ОДНА функция на бирку и на бланк —
    поле, названное в двух местах по-разному, гейт ловит как разные величины.

    Имя состояния режется по границе слова: у консервов оно длиной в
    предложение и давало пять строк капители над величиной, дважды на одной
    бирке. Целиком оно стоит заголовком группы в бланке.
    """
    if multi(it):
        return "%s &middot; %s" % (esc(short_kind(kind_title(it, st))),
                                   SLOT_LABEL[key])
    return SLOT_LABEL[key]


def short_kind(k):
    """Имя состояния для ПОДПИСИ поля. Тот же порог, что в строке списка."""
    k = k.strip()
    if len(k) <= KIND_IN_LIST:
        return k
    return k[:KIND_IN_LIST].rsplit(" ", 1)[0].rstrip(" ,;(") + chr(8230)


def rated_all(it):
    """Все сроки ВСЕХ состояний: (состояние, ячейка, низ, верх, отсчёт)."""
    out = []
    for i, st in enumerate(states_of(it)):
        for key, _f, _l in fk.SLOTS:
            v = st["slots"].get(key)
            if v and v[0] != "no":
                out.append((st, key, v[0], v[1], CLOCK_OF[key], i))
    return out


def rated_lead(it):
    """Сроки ВЕДУЩЕГО состояния — того, о котором страница.

    Ответ страницы берётся отсюда, а не со всех состояний сразу. У продукта с
    несколькими видами состояния — это РАЗНАЯ ЕДА, и правило «кончится
    первым», пущенное через все виды, выбирало не то окно, а не тот продукт:
    страница «Eggs» отвечала сроком сырых белков, пока источник держит яйца в
    скорлупе в десять раз дольше.

    Внутри ведущего состояния правило «кончится первым» остаётся: там оно про
    ОДНУ еду и связывает по-настоящему.
    """
    lead = lead_state(it)
    if lead is None:
        return []
    rows = [r for r in rated_all(it) if r[0].get("id") == lead.get("id")]
    return rows or rated_all(it)


def shortest_other_state(it):
    """Состояние с самым коротким окном вне морозилки СРЕДИ ОСТАЛЬНЫХ.

    Печатается прямо под именем: выбор ведущего состояния решает, о чём
    страница, и не имеет права спрятать вид, который кончается раньше.
    """
    lead = lead_state(it)
    lid = lead.get("id") if lead else None
    rows = [r for r in rated_all(it)
            if r[0].get("id") != lid
            and not r[1].startswith("freeze")]
    return min(rows, key=lambda r: (r[2], r[3], r[5], r[1])) if rows else None


def warm_span(it):
    """Самое короткое и самое длинное окно ВНЕ морозилки среди состояний.

    Заголовок страницы — это ответ, а ответ схлопывается в сторону
    осторожности: печатается нижний конец диапазона. Верхний конец живёт
    только внутри объявленных сравнений.
    """
    rows = [r for r in rated_all(it) if not r[1].startswith("freeze")]
    if not rows:
        return None
    return (min(rows, key=lambda r: (r[3], r[5], r[1])),
            max(rows, key=lambda r: (r[3], -r[5], r[1])))


TITLE_MAX = 60


def head_title(it, s, fit=None):
    """Заголовок страницы. ОДНА функция на все виды продуктов.

    Первое, что в нём стоит после имени, — answer_value(): ровно та строка,
    которую печатает указатель, витрина и список соседей. Пока заголовок
    собирался отдельно от списков, 127 строк указателя несли число, которого
    в заголовке цели не было вовсе — «6 weeks» в списке против «4 weeks» в
    заголовке, у одной и той же еды.

    Варианты сокращаются в объявленном порядке, и ответ уходит ПОСЛЕДНИМ:
    длинное имя вытесняет из заголовка что угодно, кроме ответа.
    """
    fit = fit or (lambda x: x)
    t = title_of(it)
    a = answer_value(it)
    if not a:
        if multi(it):
            # Не «no window published»: окна есть, их несколько, и заголовок
            # обязан сказать именно это.
            for head in ("%s: %s rated separately"
                         % (t, NO_ONE_ANSWER % s["n_states"]),
                         "%s: %s" % (t, NO_ONE_ANSWER % s["n_states"]), t):
                if len(esc(head)) <= TITLE_MAX:
                    return head
            return fit(t)
        return fit("%s: %s" % (t, NO_WINDOW))
    tries = []
    if multi(it):
        tries.append("%s: %s, %d kinds" % (t, a, s["n_states"]))
        tries.append("%s: %s" % (t, a))
    else:
        b = hot_slot(it)
        rest = [r for r in rated_all(it) if (r[1], r[5]) != (b[1], b[5])]
        if rest:
            l = max(rest, key=lambda r: (r[3], r[1]))
            second = "%s %s" % (human(l[2], (l[0].get("units") or {}).get(l[1])),
                                LISTING_WHERE[l[1]])
            tries.append("%s: %s, %s" % (t, a, second))
        tries.append("%s: %s" % (t, a))
    tries.append(t)
    for head in tries:
        if len(esc(head)) <= TITLE_MAX:
            return head
    return fit(tries[-2] if len(tries) > 1 else tries[-1])


# Фраза о том, ЗА ЧТО говорит страница. ОДНА на весь сайт, и выводится из
# той же пометки «lead», по которой считается сам ответ, — разойтись с ним
# она не может. Прежде таких фраз было три, разными словами, и все три
# утверждали «за страницу отвечает первая строка источника»: на тринадцати
# страницах это было ПРОСТО НЕВЕРНО — источник ставит первым сушёный базилик,
# консервированную ветчину и молоко без единого числа.

SPEAKS_MARK = "the kind the plain name means"


def speaks_for(it):
    """Чем эта страница отвечает и почему именно этим."""
    n = len(states_of(it))
    if split(it):
        return ("No one of the %d is %s, so this page prints no single "
                "figure: the kinds are listed with their own windows and you "
                "pick yours." % (n, SPEAKS_MARK))
    lead = lead_state(it)
    if lead is None or n < 2:
        return ""
    return ("Comparisons and the place in the category are computed for %s, "
            "which is %s here, chosen kind by kind rather than by the order "
            "the source happens to list them in."
            % (kind_title(it, lead), SPEAKS_MARK))


def multi_desc(it, s):
    """Описание в выдаче: сколько видов и от чего до чего."""
    t = title_of(it)
    span = warm_span(it)
    if not span:
        return ("How long %s %s: the USDA rates %d kinds of it separately "
                "and gives none of them a window outside the freezer."
                % (t, keeps_word(t), s["n_states"]))
    (s1, k1, lo1, _h1, _c1, _i1), (s2, k2, lo2, _h2, _c2, _i2) = span
    a = human(lo1, (s1.get("units") or {}).get(k1))
    b = human(lo2, (s2.get("units") or {}).get(k2))
    if a == b:
        return ("How long %s %s: the USDA rates %d kinds of it separately "
                "and gives them all %s, each with its own rows here."
                % (t, keeps_word(t), s["n_states"], a))
    return ("How long %s %s: the USDA rates %d kinds of it separately, from "
            "%s to %s, and each kind keeps its own windows here."
            % (t, keeps_word(t), s["n_states"], a, b))


# Место хранения так, как оно печатается В СПИСКЕ и В ЗАГОЛОВКЕ. Слова здесь
# те же, что и в SHELF_SHORT, плюс морозилка: список обязан печатать ту же
# строку, что и заголовок страницы, к которой ведёт, — иначе указатель и цель
# называют одну величину двумя способами.
LISTING_WHERE = {
    "freeze": "in the freezer", "freeze_purchase": "in the freezer",
    "fridge": "in the fridge", "fridge_purchase": "sealed in the fridge",
    "fridge_open": "in the fridge once opened",
    "fridge_thaw": "in the fridge once thawed",
    "pantry": "in the pantry", "pantry_purchase": "sealed in the pantry",
    "pantry_open": "in the pantry once opened",
}


def hot_slot(it):
    """СВЯЗЫВАЮЩЕЕ окно продукта: то, что кончится первым.

    ОДИН носитель этого решения на всю сборку — бирка, витрины, указатель,
    соседи и заголовок печатают ЭТО. Пока витрины печатали самое длинное
    окно, 401 строка обещала «Pies — 4 days outside the freezer» там, где
    источник даёт двухчасовой предел при комнатной температуре.

    Два правила внутри, и оба про безопасность, а не про красоту:

    * морозилка в кандидаты не идёт, пока есть хоть одно окно вне её:
      замороженная еда при 0 °F безопасна сколько угодно, а портится то, что
      лежит в тепле и в холодильнике;
    * сравниваются ОСТОРОЖНЫЕ концы диапазонов: связывает читателя нижняя
      граница, и «3–4 дня» кончаются раньше, чем «3,5–3,5».
    """
    rated = rated_lead(it)
    if not rated:
        return None
    warm = [r for r in rated if not r[1].startswith("freeze")]
    # ЧЕТВЁРТОЕ правило: вид, за который говорит страница, может не отвечать
    # на вопрос, ради которого простое слово и набрано. У обычного молока
    # источник вместо холодильного срока печатает «Package use-by date», а
    # три месяца в морозилке — ответ на другой вопрос; напечатанные крупной
    # строкой, они читаются как срок молока. Страница тогда не отвечает
    # числом вовсе: она говорит это словами и печатает виды, которым срок
    # ДАН. Правило работает только там, где есть с чем сравнить, — у
    # продукта из одной строки одна морозилка по-прежнему отвечает.
    if not warm and multi(it) and any(not r[1].startswith("freeze")
                                      for r in rated_all(it)):
        return None
    pool = warm or rated
    # ПЯТОЕ правило, и оно про то же, что и третье. Ячейка короче суток —
    # это предел пребывания в тепле (fk.safety_limit_cells), а не окно
    # хранения: «2 Hours» у пирога значит «не оставляй на столе». Пока такая
    # ячейка связывала, /pies/ и /quiche/ отвечали двумя часами при
    # семидневном и пятидневном холодильном окне того же вида — ровно то,
    # что домашний читатель прочтёт как «пирог живёт два часа». Правило
    # снимается, когда деться некуда: если другого окна вне морозилки у вида
    # нет, предел остаётся ответом, потому что он единственное, что дано.
    keep = [r for r in pool if r[3] >= fk.SAFETY_LIMIT_DAYS]
    pool = keep or pool
    # ТРЕТЬЕ правило, и оно про совет, а не про число. Ячейка, у которой в том
    # же состоянии есть место ПОЛУЧШЕ, не связывает никого: источник печатает
    # и шкаф, и холодильник для одного и того же лука — месяц против недели, —
    # и «кончится первым» тут значит всего лишь «положили не туда». Сигналом
    # это помечалось на 48 страницах, включая картошку, которой сам же
    # источник советует холодильника избегать.
    choice = [r for r in pool if not fk.better_place_for(r[0], r[1])]
    pool = choice or pool
    return min(pool, key=lambda r: (r[2], r[3], r[5], r[1])) if pool else None


# Подсказка, СУЖАЮЩАЯ ячейку до другой готовности продукта: «Freezer timeline
# applies to cooked and mashed potatoes» при холодильном сроке сырой картошки.
# Отношение тогда сравнивает ДВА РАЗНЫХ БЛЮДА, и источник об этом сказал, а
# сайт молчал: 26× у картошки, 11× у яблок.
SCOPE_RE = re.compile(r"\bapplies\b", re.I)

SCOPE_HEAD = "The two sides of that multiplier are not the same dish"


def scope_notes(it):
    """Подсказки источника, сужающие ячейку до другой готовности."""
    out = []
    for st in states_of(it):
        for k, v in sorted((st.get("tips") or {}).items()):
            if SCOPE_RE.search(v):
                out.append((st, k, v))
    return out


def ratio_scope(it):
    """Из них — те, что попали в СТОРОНУ напечатанного отношения."""
    hr = headline_ratio(it)
    if not hr:
        return []
    r = hr[1]
    fams = {r.den_key.split("_")[0], r.num_key.split("_")[0]}
    return [x for x in scope_notes(it) if x[1].split("_")[0] in fams]


def scope_block(it):
    """Отношение, чьи стороны — разная готовность одного продукта."""
    rows = ratio_scope(it)
    if not rows:
        return ""
    hr = headline_ratio(it)
    _kind, r = hr
    st, key, text = rows[0]
    lead = fit_para(
        "The %s multiplier on this page is drawn across a change of "
        "preparation: the source's note on the %s figure reads %s%s%s"
        % (ratio_x(r) + chr(215), PLACE_WORD[key.split("_")[0]],
           QUOTE, esc(text.rstrip(".")), QUOTE + "."),
        "It divides %s %s by %s %s, and those two are not the same dish."
        % (human(r.num, u(it, r.num_key)),
           SHORT_WHERE.get(r.num_key, LISTING_WHERE[r.num_key]),
           human(r.den, u(it, r.den_key)),
           SHORT_WHERE.get(r.den_key, LISTING_WHERE[r.den_key])),
        std(RATIO_CROSSES))
    return "<h2>%s</h2><p>%s</p>" % (SCOPE_HEAD, lead)


def wrong_place_block(it, s):
    """Где источник даёт ДВА места на одно состояние: какое из них лучше.

    Флуоресцентное поле помечало худшее из двух на 48 страницах — картошку в
    холодильнике против шкафа, лук в холодильнике против шкафа, — потому что
    «кончится первым» и «что тебе делать» это разные вопросы, и облик их
    смешал. Теперь сигнал берёт лучшее место, а проигравшее НАЗВАНО здесь:
    молча выбросить строку значило бы спрятать половину того, что напечатал
    источник.
    """
    rows = wrong_place_rows(it)
    if not rows:
        return ""
    st, key, better = rows[0]
    who = brief_who(it, st)
    # СЛОВО ПЕРЕЖИЛО РАЗМЕТКУ. Здесь стояло «The signal above marks the
    # pantry» — фраза из облика «бирка», где лаймовая ЗАЛИВКА действительно
    # помечала выигравшее место. В облике «Дата, а не срок» сигнал это
    # синяя КРАСКА, и до ввода даты его на странице НЕТ ВОВСЕ: посетитель
    # 49 страниц искал глазами пометку, которой не существует. Хуже того,
    # на трёх страницах названное место противоречило тому, чем страница
    # отвечает в шапке, а на странице-выборе ответа наверху нет вообще.
    #
    # Теперь фраза говорит о САМОМ МЕСТЕ, а утверждение «этим страница и
    # отвечает» печатается, только если это правда — то есть если ведущая
    # ячейка и есть то самое место получше.
    hot = hot_slot(it)
    answers_with = bool(hot) and (hot[0] is st) and hot[1] == better
    place = PLACE_NOUN[better.split("_")[0]]
    # Длина хвоста — тоже часть правки: первая формулировка была на шесть
    # слов длиннее прежней и вытолкнула семь страниц за верхнюю границу окна
    # абзаца (75 слов при потолке 72), то есть молча выбросила их из корпуса.
    # PLACE_NOUN несёт артикль САМ («the pantry»): шаблон со своим «the»
    # давал «answers with the the pantry» на каждой такой странице.
    tail = ("This page answers with %s, the longer of the two." % place
            if answers_with else
            "Of the two, %s is the longer." % place)
    lead = ("The USDA rates two places for %s in one state and they "
            "disagree: %s %s against %s %s. %s"
            % (who, st_text(st, better), SHELF_SHORT.get(better,
                                                         LISTING_WHERE[better]),
               st_text(st, key), SHELF_SHORT.get(key, LISTING_WHERE[key]),
               tail))
    tip = (st.get("tips") or {}).get(key.split("_")[0])
    why = ("The source attaches a note to the shorter one, printed below in "
           "its own words." if tip else
           "%d of the windows here are the shorter of two places the source "
           "rates for one state." % len(rows) if len(rows) > 1 else
           "The shorter one stays on the page because dropping it would hide "
           "half of what the source printed.")
    return ("<h2>Two places, and one of them is the wrong one</h2><p>%s</p>"
            % fit_para(lead, why, std(WHOSE_FIGURES)))


def wrong_place_rows(it):
    """Ячейки, у которых в том же состоянии есть место получше: (состояние,
    ячейка, ячейка получше). То, чего читатель бы не угадал, и то, что до сих
    пор печаталось у него ответом."""
    out = []
    for st, key, _lo, _hi, _clock, _i in rated_all(it):
        if key.startswith("freeze"):
            continue
        b = fk.better_place_for(st, key)
        if b:
            out.append((st, key, b))
    return out


def longest_slot(it):
    """Самое длинное окно ВЕДУЩЕГО состояния. Бирка целиком говорит об одной
    еде: «яйца в скорлупе» в сигнальном поле и «12 месяцев» замороженных
    белков во втором — это одна бирка про два разных продукта."""
    rated = rated_lead(it)
    return max(rated, key=lambda r: (r[3], -r[5], r[1])) if rated else None


def answer_value(it):
    """Ответ продукта словами: осторожный конец СВЯЗЫВАЮЩЕГО окна и место.

    Одна строка, один вид, одна функция — её печатают витрины, указатель,
    соседи и заголовок. Верхний конец диапазона здесь не появляется никогда:
    там, где число стоит ОТВЕТОМ, печатается осторожный край, и «6 weeks» в
    указателе против «4 weeks» в заголовке цели стоили нам 127 строк.
    """
    b = hot_slot(it)
    if not b:
        return None
    st, key, lo, _hi, _clock, _i = b
    return "%s %s" % (human(lo, (st.get("units") or {}).get(key)),
                      LISTING_WHERE[key])


LONG_GAP = 1.5           # ниже этого две величины в строке — одна и та же
KIND_IN_LIST = 44       # длина имени вида в строке списка, по слову


def long_value(it):
    """Самое длинное окно вне морозилки — ВТОРАЯ величина строки списка, и
    только когда она ощутимо длиннее связывающей. Она есть то, по чему
    построен рейтинг «дольше всех вне морозилки», и без неё этот рейтинг
    печатал бы не свои числа."""
    b = hot_slot(it)
    if not b:
        return None
    # ВЕДУЩЕЕ СОСТОЯНИЕ, а не все. Правило записано у rated_lead: у продукта
    # с несколькими видами состояния это РАЗНАЯ ЕДА, и строка, где первая
    # величина взята у ведущего вида, а вторая у любого, говорит о двух
    # предметах сразу. Видно было на рейтинге: «Spice — up to 4 years» стояло
    # НИЖЕ «Tuna — 3 years», потому что сортировка идёт по ведущему состоянию
    # (fk.shelf_days), а печаталось по всем.
    rows = [r for r in rated_lead(it) if not r[1].startswith("freeze")]
    if not rows:
        return None
    # «UP TO N» — ЭТО ВЕРХНИЙ КРАЙ, и печатался нижний. Из 107 продуктов с
    # этой оговоркой у 40 стояло меньшее число: /baking-powder/ обещал «up to
    # 6 months» там, где источник даёт 6-18, а /caviar/ — «up to 1 week» при
    # 1-4 неделях. Справочник, цитирующий USDA, занижал USDA втрое.
    #   Ключ отбора двигается вместе с печатью: выбирать по нижнему краю, а
    # печатать верхний значило бы выбрать не ту строку и напечатать не то
    # число — ровно так расходились peanut butter и honeydew.
    l = max(rows, key=lambda r: (r[3], r[2], r[1]))
    if (l[1], l[5]) == (b[1], b[5]) or l[2] < b[2] * LONG_GAP:
        return None
    return "%s %s" % (human(l[3], (l[0].get("units") or {}).get(l[1])),
                      LISTING_WHERE[l[1]])


def listing_value(it):
    """Строка продукта В СПИСКЕ: сперва СВЯЗЫВАЮЩЕЕ окно, потом самое длинное.

    Связывающее стоит первым, потому что оно и есть ответ: 401 строка витрин
    печатала только длинный конец, и «Pies — 4 days outside the freezer»
    стояло там, где источник даёт двухчасовой предел при комнатной
    температуре. Длинное окно печатается рядом, когда оно ощутимо длиннее:
    без него рейтинг «дольше всех вне морозилки» показывал бы не то число,
    по которому построен.

    У продукта с несколькими состояниями рядом стоит имя состояния: без него
    список обещает окно одного вида, а страница помечает сигналом другое.
    """
    v, note = listing_parts(it)
    return ("%s %s %s" % (v, chr(183), note)) if note else v


# Строка «числа нет» объявлена ЗДЕСЬ и нигде больше: её печатают заголовок,
# бирка, витрины и указатель, а гейты по ней узнают форму страницы.
NO_WINDOW = "no window published"
NO_WINDOW_CAP = "No window published"
NO_WINDOW_DUR = "Not rated"
# Строка страницы, у которой ответа нет не от незнания, а оттого что простое
# слово не значит одного вида. Объявлена ЗДЕСЬ и нигде больше.
NO_ONE_ANSWER = "%d kinds"
PICK_DUR = "Which kind?"


def answer_line(it):
    """Строка ответа для заголовка, витрин, указателя и соседей. ОДНА на сайт.

    Ответа может не быть по трём разным причинам, и все три — не «мы не
    знаем»: страница-выбор (простое слово не значит одного вида), вид без
    окна вне морозилки и запись, которой источник не дал срока вовсе.
    Первые две несут виды, и строка называет их число, а не пустоту.
    """
    v = answer_value(it)
    if v:
        return v
    return (NO_ONE_ANSWER % len(states_of(it))) if multi(it) else NO_WINDOW


def listing_days(it):
    """Наибольшая величина, КОТОРУЮ СТРОКА НАПЕЧАТАЕТ, в днях.

    Рейтинг «дольше всех вне морозилки» сортировался по fk.shelf_days —
    лучшему сроку по ВСЕМ состояниям, — а печатал строку ведущего состояния.
    Две величины расходились, и порядок на странице ломался у всех на виду:
    «Spice — up to 4 years» стояло ниже «Tuna — 3 years», «Baking soda — up
    to 3 years» ниже «Quinoa — 2 years». Восемь таких пар из 59 строк.
    Сортировка обязана идти по тому числу, которое читатель видит.
    """
    rows = [r for r in rated_lead(it) if not r[1].startswith("freeze")]
    if not rows:
        return fk.shelf_days(it) or 0.0
    b = hot_slot(it)
    best_hi = max(r[3] for r in rows)
    # Длинная величина печатается не всегда: без неё строка показывает только
    # связывающее окно — и показывает его ОСТОРОЖНЫМ краем, как answer_value.
    # Сортировка по верхнему краю там, где напечатан нижний, дала бы ту же
    # рассогласованность в третий раз: «Quinoa 2 years» выше «Baking soda up
    # to 3 years».
    return best_hi if long_value(it) else ((b[2] if b else None) or best_hi)


def listing_top_text(it):
    """Словами — ТА ЖЕ величина, по которой строка стоит в рейтинге.

    Абзац витрины цитировал осторожный край («leads at 8 months»), а размах
    считал по ранжирующей величине («a spread of 365 times»): два числа об
    одном предмете в одном предложении. Цитата берётся отсюда, размах — из
    listing_days, и обе стороны смотрят на одно.
    """
    lv = long_value(it)
    return lv if lv else listing_parts(it)[0]


def listing_parts(it):
    """Та же строка ДВУМЯ частями: величина и оговорка к ней.

    Колонка значений — это поле бланка, а не абзац: 44 знака в ней ломали
    строку пополам. Величина стоит величиной, оговорка уезжает строкой ниже.
    """
    v = answer_value(it)
    if not v:
        # Страница-выбор и вид без окна несут ВИДЫ, а не пустоту: строка
        # списка называет их число и размах, и обе величины стоят на самой
        # странице.
        if multi(it):
            span = warm_span(it)
            note = ""
            if span:
                (s1, k1, lo1, _h1, _c1, _i1), (s2, k2, lo2, _h2, _c2, _i2) = span
                a = human(lo1, (s1.get("units") or {}).get(k1))
                b = human(lo2, (s2.get("units") or {}).get(k2))
                note = a if a == b else "%s to %s" % (a, b)
            return (answer_line(it), note)
        return (NO_WINDOW, "")
    note = []
    if multi(it):
        k = (hot_slot(it)[0].get("kind") or "").strip()
        if k:
            # Подзаголовки источника бывают длиной в предложение («low acid,
            # such as meat, poultry, fish, gravy, stew, soups, beans…»).
            # В строке списка он режется по границе слова: узнать вид по
            # началу можно, а полностью он стоит на самой странице.
            if len(k) > KIND_IN_LIST:
                k = k[:KIND_IN_LIST].rsplit(" ", 1)[0].rstrip(" ,;(") + chr(8230)
            note.append(k)
    long = long_value(it)
    if long:
        note.append("up to %s" % long)
    return (v, (" %s " % chr(183)).join(note))


def out_field(st, key, lo, hi, clock):
    """ЯЧЕЙКА ОТВЕТА — ГЛАВНЫЙ ПРИЁМ ОБЛИКА. Она ОДНА и та же до и после
    ввода даты: до — срок словами источника, после — дата в календаре, на том
    же месте и тем же кеглем, сигнальным цветом. Подпись над величиной из
    «Use by» превращается в обратный отсчёт, и оба текста ставит скрипт.

    Отсчёт («after the day you opened it») в ячейку НЕ ВХОДИТ: он стоит
    подписью под ней. Внутри он добавлял к величине сорок знаков, а величина
    здесь набрана крупной строкой — четыре строки заглавных вместо одной.

    Срок короче суток сюда не попадает вовсе: двухчасовой предел при
    комнатной температуре, ставший датой, читается как разрешение на день.
    Вызывающий обязан это проверить; см. label_fields.
    """
    lead = "Use by"
    # Без скрипта здесь стояло «PICK THE DAY ABOVE» рядом с полем даты,
    # которое без скрипта ничего не считает: указание, которое никогда не
    # сбудется, хуже отсутствующего. Теперь в разметке стоит САМ ДИАПАЗОН —
    # ровно то, что печатает скрипт, пока день не выбран.
    plain = esc(st_text(st, key))
    return ('<div class="out" data-lo="%d" data-hi="%d" data-clock="%s" '
            'data-lead="%s" data-plain="%s"><small>%s</small>%s</div>'
            % (int(round(lo)), int(round(hi)),
               clock, lead, plain, lead, plain))


def date_input(clock, hot):
    """Поле даты. У каждого отсчёта своё: срок «от покупки» нельзя считать от
    дня вскрытия, и одно поле на все строки уже стоило нам 323 строк, которые
    считались не от того дня.

    Само поле СТРОИТ СКРИПТ. Отрисованный `<input type="date">` без скрипта —
    мёртвый контрол: человек выбирает день, и не происходит ничего. До того
    коробка спрятана атрибутом `hidden`, а подпись лежит в РАЗМЕТКЕ, чтобы в
    скрипте не заводилось ни одной строки текста.
    """
    return ('<div class="%s" data-clock="%s" data-label="%s" hidden></div>'
            % ("dateline" if hot else "second", clock,
               esc(CLOCK_LABEL[clock])))


ASK_WHERE = {
    "fridge": "in the fridge", "fridge_purchase": "in the fridge",
    "fridge_open": "in the fridge once opened",
    "fridge_thaw": "in the fridge after thawing",
    "pantry": "in the pantry", "pantry_purchase": "in the pantry",
    "pantry_open": "in the pantry once opened",
    "freeze": "in the freezer", "freeze_purchase": "in the freezer",
}


def ask_tail(hot):
    """Хвост вопроса называет ТО САМОЕ место, к которому относится число под
    ним. Общий «last?» на 277 страницах был бы ключевым словом, а не
    вопросом."""
    return "last %s?" % ASK_WHERE[hot[1]] if hot else "last?"


def ask_head(it, hot):
    """Заголовок теми словами, которыми это спрашивают.

    Замерено по собранному: «last» стояло во всём корпусе ОДИН раз, «how
    long» — ноль раз в заголовках. Головной запрос ниши — «how long does X
    last in the fridge», и до этой правки страница не несла его нигде.

    Крупной строкой при этом остаётся имя, а не вопрос: слова вопроса стоят
    мелкими строками над и под ним, поэтому запрос на странице появился, а
    первый экран не вырос на семь строк заглавных.
    """
    short = short_of(it)
    return ('<span class="ask">How long %s</span>%s<span class="ask">%s</span>'
            % (does_do(short), esc(short), esc(ask_tail(hot))))


def item_field(it, hot):
    """Поле «что это». Полное имя источника печатается ЦЕЛИКОМ, строкой ниже:
    выброшенный хвост имени — это выброшенное различие между продуктами."""
    short, full = short_of(it), title_of(it)
    subs = []
    if full != short:
        subs.append(esc("USDA FoodKeeper: %s" % full))
    if multi(it):
        # ЗДЕСЬ ЧИСЛА НЕТ, и это правка, а не упущение. Ремень безопасности —
        # вид, который кончается раньше ведущего, — стоял ИМЕННО ЗДЕСЬ, с
        # именем и числом, и первым числом страницы /eggs/ оказывались два
        # дня сырого белка: подпись под именем читают РАНЬШЕ ответа. Ремень
        # никуда не делась — она переехала под ответ (belt_sentence),
        # первой фразой первого раздела корешка, где она и есть
        # то, чем был задуман: оговорка к ответу, а не ответ.
        # На странице-выборе счёт видов стоит подписью САМОГО поля выбора
        # («10 kinds under one name»), и вторая такая же строка над ним была
        # бы одной величиной, названной дважды.
        if not split(it):
            subs.append("%d kinds &middot; each with its own window"
                        % len(states_of(it)))
    sub = ('<div class="sub">%s</div>' % "<br>".join(subs)) if subs else ""
    # Ступень кегля выбирает ШИРИНА строки в Arial, а не число знаков:
    # узкого начертания на телефоне нет ни одного, и «len(name) > 24»
    # ужимало «Cooked rice» и пропускало имена, которые в строку не встают.
    return ('<div class="field"><h1 class="item%s">%s</h1>%s</div>'
            % (design.fit_display(short), ask_head(it, hot), sub))


BELT_TAIL = "which is shorter than the window this page answers with"


# Чем оборачивается кратчайшее окно на странице-выборе. Три
# признака — три разных последствия, и ни одно не пересказывает
# другое: смешение их одной формулировкой уже стоило нам страниц.
SHORTEST_IS = {
    "safety": "a safety limit, and past it the food goes out untasted",
    "quality": "a quality window, and past it the food is judged by look and smell",
    "unsettled": "a figure the record does not settle, so the shorter answer is the one to take",
}


def belt_sentence(it):
    """Оговорка к ответу: вид под тем же именем, кончающийся РАНЬШЕ.

    Выбор вида решает, о чём страница, и не имеет права спрятать окно
    короче. Но и вставать ПЕРЕД ответом он не имеет права: пока эта фраза
    стояла подписью под именем продукта, первым числом страницы /eggs/ были
    два дня сырого белка — ровно то число, от которого оговорка и должна
    была уберечь. Порядок и есть смысл.

    И не в бирке: над перфорацией на этом сайте нет ни одного предложения
    прозы, только поля бланка, — а поставленная туда, оговорка стоила от 27
    до 34px первого экрана и вывела восемь бирок за бюджет. Её место —
    ПЕРВАЯ фраза ПЕРВОГО раздела корешка, сразу под ответом.
    """
    hot = hot_slot(it)
    if hot is None or not multi(it):
        return ""
    other = shortest_other_state(it)
    if not other or other[2] >= hot[2]:
        return ""
    return ("%s keeps %s, %s."
            % (kind_title(it, other[0]),
               human(other[2], (other[0].get("units") or {}).get(other[1])),
               BELT_TAIL))


# Что печатается в строке вида, которому источник не дал числа вне
# морозилки. Объявлено здесь и читается вводной фразой: пока строка была
# литералом внутри генератора, вводная обещала «виды, которым источник дал
# число», и последней строкой перечня стоял вид без числа.
NO_BAND_TEXT = "outside the freezer, nothing published"


def pick_rows(it):
    """Виды страницы-выбора, сгруппированные ПО ОКНУ, короткое сверху.

    Ровно один ряд на КАЖДОЕ РАЗЛИЧАЮЩЕЕСЯ окно вне морозилки: у ветчины
    двадцать видов и пять разных окон, а двадцать строк над перфорацией не
    поместились бы на экран телефона (design.BUDGET_PX). Группировка — не
    сокращение списка: полный список стоит строкой ниже, в бланке, и каждая
    группа названа своим первым видом, а не числом.
    """
    groups = {}
    for st in states_of(it):
        band = shelf_band(st)
        key = band or ""
        groups.setdefault(key, []).append(st)
    rows = []
    for band, sts in groups.items():
        # Порядок — по ОСТОРОЖНОМУ концу, как везде на сайте, где число
        # стоит ответом: сортировка по верхней границе поставила бы «3 days
        # to 5 days» впереди «3 days to 4 days».
        k = fk.shelf_key(sts[0])
        v = sts[0]["slots"][k] if k else None
        name = short_kind(kind_cap(sts[0]))
        if len(sts) > 1:
            name = "%s and %d more" % (name, len(sts) - 1)
        rows.append(((v[0], v[1]) if v else (1e9, 1e9), name,
                     band or NO_BAND_TEXT))
    return [(n, b) for _d, n, b in sorted(rows)]


def pick_field(it, silent):
    """Поле выбора ВМЕСТО ответа: ни одного числа крупной строкой.

    Две причины попасть сюда, и обе не «мы не знаем». Первая — простое слово
    не значит одного вида (fk.PLAIN_MEANS = SPLIT): «Pies» отвечали
    двухчасовым пределом мясной начинки, «Beef» — рёберным отрубом при
    запросе про фарш. Вторая — вид, который простое слово ЗНАЧИТ, источник
    оставил без срока вне морозилки: у обычного молока вместо числа стоит
    «Package use-by date». В обоих случаях страница печатает ВИДЫ и их окна
    и говорит словами, почему одного числа тут нет.
    """
    sts = states_of(it)
    picked = pick_rows(it)
    # ВВОДНАЯ ОБЯЗАНА ОПИСЫВАТЬ ТОТ ПЕРЕЧЕНЬ, КОТОРЫЙ ПОД НЕЙ. На /milk/
    # фраза обещала «виды, которым источник дал число», а последней строкой
    # шёл «Plain or flavored — outside the freezer, nothing published»,
    # то есть ровно тот вид, у которого числа нет и о котором подпись самого
    # ответа двумя строками выше говорит «Package use-by date».
    all_numbered = all(b != NO_BAND_TEXT for _n, b in picked)
    rows = "".join('<li><span class="rk">%s</span>'
                   '<span class="rv">%s</span></li>' % (esc(n), esc(b))
                   for n, b in picked)
    lead = lead_state(it)
    said = None
    if silent and lead is not None:
        for k in fk.WARM_KEYS:
            if k in (lead.get("says") or {}):
                said = (k, (lead.get("says") or {})[k][0])
                break
    if said:
        # ВЕДУЩИЙ ВИД УЖЕ НАЗВАН ПОДПИСЬЮ ЭТОГО ЖЕ БЛОКА, двумя строками
        # выше («Milk, plain or flavored · In the fridge — Package use-by
        # date»). Его же строка в перечне говорила «outside the freezer,
        # nothing published»: одна запись источника, два разных ответа на
        # одном экране. Перечень отвечает на вопрос «а каким видам число
        # ДАНО», и виду без числа в нём не место.
        drop = short_kind(kind_cap(lead)) if lead is not None else None
        if drop:
            picked = [(nm, b) for nm, b in picked
                      if not (b == NO_BAND_TEXT and nm.startswith(drop))]
        all_numbered = all(b != NO_BAND_TEXT for _n, b in picked)
        rows = "".join('<li><span class="rk">%s</span>'
                       '<span class="rv">%s</span></li>' % (esc(n), esc(b))
                       for n, b in picked)
        cap = field_label(it, lead, said[0])
        dur = SAYS_VALUE[said[1]]
        why = ("The USDA answers this one in words rather than in days, so "
               "there is no figure here to count from. "
               + ("These are the kinds it does put a number on:"
                  if all_numbered else
                  "Here is every kind under this name, with whatever the "
                  "source gives each:"))
    elif silent:
        cap = esc(short_kind(kind_title(it, lead))) if lead else esc(
            title_of(it))
        dur = NO_WINDOW_DUR
        why = ("The USDA gives this kind no window outside the freezer at "
               "all. "
               + ("These are the kinds it does rate:" if all_numbered else
                  "Here is every kind under this name, with whatever the "
                  "source gives each:"))
    else:
        cap = esc("%d kinds under one name" % len(sts))
        dur = PICK_DUR
        why = "None of them is what the plain word means. Pick yours:"
    return ('<div class="hot" data-pick><div class="cap">%s</div>'
            '<div class="dur%s">%s</div><div class="sub">%s</div>'
            '<ul class="rows" role="list">%s</ul></div>'
            % (cap, design.fit_display(dur), esc(dur), esc(why), rows))


def label_fields(it, s):
    """Бирка: ЧТО, флуоресцентным — что кончится первым, потом самое длинное.

    Ни одного предложения прозы: только подписи полей, величины и одно поле
    ввода. Это правило держит ответ на одном экране телефона и проверяется
    гейтом.

    Кратность стоит НИЖЕ перфорации (prose.cost_box печатает её первым
    блоком корешка): она сравнение, а не ответ, и на телефоне съедала
    74–134px первого экрана.

    Порядок полей изменён: связывающее окно стоит ПЕРВЫМ. Замерено на
    телефоне — на банке консервов первое крупное число было «2 years to 5
    years» (запечатанная банка в шкафу), а «3 days to 4 days» вскрытой стояло
    ниже. Взгляд ловит первое крупное число, и оно обязано быть тем, которое
    кончится первым.
    """
    rated = rated_all(it)
    hot = hot_slot(it) if rated else None
    out = item_field(it, hot)
    if split(it):
        return out + pick_field(it, False)
    if rated and hot is None:
        # Виды есть, а вид, за который говорит страница, окна вне морозилки
        # не имеет: печатать морозильное число ответом значило бы ответить
        # на другой вопрос.
        return out + pick_field(it, True)
    if not rated:
        return out + ('<div class="hot"><div class="cap">%s'
                      '</div><div class="dur">%s</div>'
                      '<div class="sub">The USDA lists this food without a '
                      'storage time</div></div>' % (NO_WINDOW_CAP,
                                                    NO_WINDOW_DUR))
    h_st, h_key, h_lo, h_hi, h_clock, h_i = hot
    # Строка «что это значит» стоит В ответе, выше границы: она и есть
    # последствие, ради которого человек смотрит на число. Одна величина —
    # один носитель: слово выбирает та же fk.window_kind, что и раздел «Is
    # this window about safety or about taste?» ниже.
    h_text = st_text(h_st, h_key)
    dated = h_hi >= 1
    # ПОЛЕ ДАТЫ СТОИТ ВЫШЕ ОТВЕТА И ВНЕ ЕГО. На прежней бирке оно лежало
    # внутри ответа, третьей строкой снизу, и до него не доходил взгляд:
    # человек читал срок и уходил, а вся суть сайта — в дате. Порядок теперь
    # такой же, как у прибора: имя, ввод, показание.
    if dated:
        out += date_input(h_clock, True)
    # Величина ОДНА. Если день назван, её несёт .out (та же ячейка до и
    # после ввода); если окно короче суток, даты не будет никогда, и её
    # несёт .dur. Двух копий одного числа в ответе больше нет.
    if dated:
        value = out_field(h_st, h_key, h_lo, h_hi, h_clock)
    else:
        value = ('<div class="dur%s">%s</div>'
                 % (design.fit_display(h_text), esc(h_text)))
    out += ('<div class="hot"><div class="cap">%s</div>%s'
            '<div class="sub">%s</div><div class="means">%s</div></div>'
            % (field_label(it, h_st, h_key), value,
               clock_cap(h_clock, h_hi),
               MEANS_CHIP[row_kind(it, h_st, h_key)]))
    return out


def longest_box(it, s):
    """Самое длинное окно — ПЕРВЫМ блоком разбора, а не на первом экране.

    На прежней бирке оно стояло под ответом и стоило 113px первого экрана
    телефона. Это не ответ: ответ — то, что кончится РАНЬШЕ всего, и ради
    него человек и открыл страницу. Самое длинное окно — СРАВНЕНИЕ, ровно
    как кратность, и стоит теперь рядом с ней, сразу под границей.

    Вычислительно ничего не изменилось: те же hot_slot и longest_slot, то же
    условие «это не одна и та же ячейка». Переехала только точка печати.
    """
    rated = rated_all(it)
    if not rated or split(it):
        return ""
    hot = hot_slot(it)
    if hot is None:
        return ""
    longest = longest_slot(it)
    h_key, h_i = hot[1], hot[5]
    l_st, l_key, _l_lo, l_hi, l_clock, l_i = longest
    if (h_i, h_key) == (l_i, l_key):
        return ""
    l_text = st_text(l_st, l_key)
    return ('<div class="field"><div class="cap">%s</div>'
            '<div class="dur%s">%s</div><div class="sub">%s</div></div>'
            % (field_label(it, l_st, l_key), design.fit_display(l_text),
               esc(l_text), clock_cap(l_clock, l_hi)))


# --------------------------------------------------- кратность: одна на страницу
#
# ОДНА величина — ОДНА функция. Пока бирка делила «самое длинное на то, что
# кончится первым», а проза — «морозилку на холодильник», обе печатали под
# одной подписью два разных числа: 24 страницы с расхождением до 240× против
# 34×. Теперь и бирка, и проза, и описание в выдаче, и главная берут число
# ИЗ ОДНОЙ ФУНКЦИИ, а подпись называет ОБЕ стороны деления.

# Знаменатель словами — для подписи. Направление отношения не подразумевается
# словом в шаблоне: оно спрашивается у самого отношения (fk.Ratio.den_key).
DEN_PHRASE = {
    "fridge": "the refrigerator", "fridge_purchase": "the sealed fridge",
    "fridge_open": "the opened fridge", "fridge_thaw": "thawing",
    "pantry": "the pantry", "pantry_purchase": "the sealed pantry",
    "pantry_open": "the opened pantry",
}

# Порядок объявлен здесь и нигде больше. Не «самое большое из посчитанного»:
# выбор наибольшего — это и есть выбор самого лестного числа, ровно то, за
# что этот сайт и попал в аудит.
RATIO_ORDER = ("freeze", "open", "warm")

RATIO_MIN = 1.15         # ниже этого «N times longer» либо ложь, либо шум


def ratios_of(it):
    """Все кратности продукта, каждая от своей функции. Ключ — ЧТО именно
    измерено, и он же выбирает подпись."""
    return {"freeze": fk.freeze_gain(it),
            "open": fk.opening_cost(it),
            "warm": fk.warm_cost(it)}


def headline_ratio(it):
    """Кратность, которую печатает бирка. Возвращает (вид, fk.Ratio) или None.

    Считается по ВЕДУЩЕМУ состоянию: делить двенадцать месяцев сгущённого
    молока на пять дней вскрытого лактозного — это одна величина с двумя
    обозначениями, а не сравнение.
    """
    rs = ratios_of(it)
    for kind in RATIO_ORDER:
        r = rs[kind]
        if r and r.r >= RATIO_MIN:
            return (kind, r)
    return None


def ratio_caption(kind, r):
    """Подпись кратности НАЗЫВАЕТ ОБЕ СТОРОНЫ.

    «What opening the package costs» стояло над «30 days frozen ÷ 7 days
    open» на девяти страницах: подпись говорила про вскрытие, арифметика — про
    морозилку. Подпись выводится из тех же двух ячеек, что и число.
    """
    if kind == "freeze":
        return "What the freezer buys you over %s" % DEN_PHRASE[r.den_key]
    if kind == "open":
        return "What opening the package costs"
    # НАПРАВЛЕНИЕ: делится длинное на короткое, значит стоит времени
    # КОРОТКОЕ — знаменатель. «What the refrigerator costs against the
    # pantry» стояло над отношением, которое говорит ровно обратное.
    return "What %s costs against %s" % (DEN_PHRASE[r.den_key],
                                         DEN_PHRASE[r.num_key])


def ratio_calc(r):
    """Строка расчёта: те же две ячейки, что и в числе, каждая своим именем."""
    return ("%s %s &divide; %s %s"
            % (days_word(r.num), SHORT_WHERE[r.num_key],
               days_word(r.den), SHORT_WHERE[r.den_key]))


def ratio_x(r):
    """Само число на бирке. Округление берётся у mult(): бирка печатала «2.0»
    там, где проза печатала «2 times», и одна величина расходилась с собой на
    четырёх страницах в последнем знаке."""
    return mult(r.r).split(" ", 1)[0]


def cost_box(it):
    """Блок кратности на бирке — или ничего, если считать нечего.

    Отказ от расчёта тут не молчаливый: страница, у которой источник даёт
    предел пребывания в тепле, печатает об этом отдельный раздел в корешке
    (см. safety_block), а не роняет число без объяснения.
    """
    hr = headline_ratio(it)
    if not hr:
        return ""
    kind, r = hr
    cap = ratio_caption(kind, r)
    if multi(it):
        cap = "%s &middot; %s" % (esc(short_kind(kind_title(it,
                                                            lead_state(it)))),
                                  cap)
    else:
        cap = esc(cap)
    return ('<div class="cost"><div class="x">%s&times;</div>'
            '<div class="t">%s<span class="calc">%s</span></div></div>'
            % (ratio_x(r), cap, ratio_calc(r)))


# Слово стороны расчёта РАЗЛИЧАЕТ ячейки. Пока «sealed» означало и шкаф, и
# холодильник, шесть страниц печатали «150 days sealed &divide; 90 days
# sealed» — деление величины на саму себя на вид. Гейт «две стороны расчёта
# различны» держит это правило.
SHORT_WHERE = {
    "freeze": "frozen", "freeze_purchase": "frozen",
    "pantry": "in the pantry", "pantry_purchase": "sealed in the pantry",
    "pantry_open": "open in the pantry",
    "fridge": "in the fridge", "fridge_purchase": "sealed in the fridge",
    "fridge_open": "open in the fridge", "fridge_thaw": "thawed",
}


def days_word(n):
    """«1 day», а не «1 days». Строка расчёта печаталась как «240 days frozen
    ÷ 1 days sealed» на четырёх страницах: число и слово рядом с ним — одна
    величина, и разбирать её на две части значит однажды их рассогласовать."""
    k = int(round(n))
    return "1 day" if k == 1 else "%d days" % k


def clock_cap(clock, hi):
    """С какого дня идёт счёт — и НЕ печатать про день там, где срока в днях
    нет вовсе. «2 HOURS / COUNTED FROM THE DAY YOU STORED IT» разрешало
    двухчасовой предел читать как суточный."""
    if hi is not None and hi < fk.SAFETY_LIMIT_DAYS:
        return "Counted from the moment it came out of the oven or the fridge"
    return CLOCK_CAP[clock]



def kind_head(it, st):
    """Заголовок группы бланка. Печатается у КАЖДОГО состояния: без него
    страница соврёт, потому что окна у состояний разные."""
    return '<h3 class="kind">%s</h3>' % esc(kind_title(it, st))


def state_rows(it, st):
    """Строки бланка одного состояния. Пустое состояние печатается прочерком,
    а не выбрасывается: выброшенное безымянное уже стоило ферме 444 348 домов.
    """
    rows = ""
    says = st.get("says") or {}
    for key, _field, _ru in fk.SLOTS:
        v = st["slots"].get(key)
        if v is None:
            # Нечисловой ответ источника печатается СВОИМ значением, а не
            # выпадает из бланка: 63 такие ячейки исчезали, и страница после
            # этого объявляла, что источник промолчал.
            if key in says:
                rows += ('<li><span class="rk">%s</span>'
                         '<span class="rv">%s</span></li>'
                         % (SLOT_LABEL.get(key, esc(SLOT_TH[key])),
                            esc(SAYS_VALUE[says[key][0]])))
            continue
        rows += ('<li><span class="rk">%s</span>'
                 '<span class="rv">%s</span></li>'
                 % (SLOT_LABEL.get(key, esc(SLOT_TH[key])),
                    esc(st_text(st, key))))
    # Состояние без срока вне морозилки: прочерк ставится ЗДЕСЬ, в его
    # собственной группе. Без него строка источника просто исчезает из
    # бланка, а вопрос «сколько это стоит в холодильнике» остаётся без
    # ответа там, где ответ есть — «источник не публикует».
    if fk.shelf_key(st) is None and not any(
            k in says for k in fk.WARM_KEYS):
        rows += ('<li><span class="rk">Outside the freezer</span>'
                 '<span class="rv">&mdash;</span></li>')
    # Подсказки источника здесь БОЛЬШЕ НЕТ: предложение длиной до 321 знака,
    # поставленное в колонку величин, набиралось капсом по правому краю.
    # Слова источника печатаются прозой в своём разделе — см. tips_block.
    if not rows:
        rows = ('<li><span class="rk">Nothing published</span>'
                '<span class="rv">&mdash;</span></li>')
    return rows


def form_rows(it, per_state):
    """Бланк: один список у продукта из одной строки источника, по списку с
    заголовком — у продукта из нескольких."""
    if not multi(it):
        body = per_state(it, states_of(it)[0])
        return ('<ul class="rows" role="list">%s</ul>' % body) if body else ""
    out = ""
    for st in states_of(it):
        body = per_state(it, st)
        if body:
            out += kind_head(it, st) + ('<ul class="rows" role="list">%s</ul>'
                                        % body)
    return out


def table_block(it, s):
    """Полный бланк и абзац, который называет, ЧТО именно заполнено. Набор
    способов — самая непохожая часть страницы после имён соседей."""
    rows = form_rows(it, state_rows)

    # Рамка выбирается по НАБОРУ мест хранения, а число «сколько ещё продуктов
    # записаны так же» — вычисленное по всему корпусу, и оно у каждого набора
    # своё. Перечисление ячеек было одинаковым у всех с одинаковым набором.
    fam = s["fam"]
    tip_keys = {k for _st, k, _t in tips_all(it)}
    # Нечисловой ответ — тоже ответ. Пока он терялся в парсере, страница
    # писала «no pantry figure exists for it» ровно там, где источник
    # отвечает «Package use-by date».
    says_fam = {k.split("_")[0] for _st, k, _c, _r in says_all(it)}
    n_tips = len(tips_all(it))
    n_same, n_all = s["fam_count"], s["fam_total"]
    numeric = True
    if fam == {"pantry", "fridge", "freeze"}:
        lead = ("All three places the USDA recognizes are rated here — pantry, "
                "refrigerator and freezer — which only %d of the %d foods in "
                "the data manage." % (n_same, n_all))
    elif fam == {"fridge", "freeze"}:
        # Отрицать кладовую, когда источник тут же даёт совет про комнатную
        # температуру, — противоречие внутри одной страницы. Совет не срок, но
        # и «никогда» тут неправда.
        if "pantry" in says_fam:
            # «never at room temperature» — прямая ложь на странице, где
            # источник отвечает про кладовую словами. Ветка отдельная, а не
            # приписка к отрицанию.
            lead = ("The USDA gives this item no pantry time in days: the %d "
                    "figures that carry numbers are all cold ones, and the "
                    "pantry slot is answered in words instead."
                    % s["filled"])
        elif "pantry" in tip_keys:
            lead = ("The USDA publishes no pantry storage time for this "
                    "item, only a note about how long it may stand out, so "
                    "the %d figures that exist are all cold ones."
                    % s["filled"])
        else:
            # Число отвечает НА ПРОИЗНЕСЁННЫЙ предикат: фраза говорит «нет
            # срока в кладовой», а считалось «набор ровно {холодильник,
            # морозилка}» — вдвое более узкий вопрос, на 66 страницах.
            lead = ("The USDA rates this item cold or frozen and never at room "
                    "temperature: no pantry figure exists for it, as for %d of "
                    "the %d foods in the data that get no pantry time at all."
                    % (s["no_place_n"]["pantry"], n_all))
    elif fam == {"pantry", "freeze"}:
        # То же правило: «пропускает холодильник» — это предикат «нет
        # холодильного срока», а не «набор ровно {кладовая, морозилка}».
        lead = ("An unusual pairing: the USDA rates the pantry and the freezer "
                "for this item but skips the refrigerator entirely, one of "
                "%d foods of the %d that get no refrigerator time."
                % (s["no_place_n"]["fridge"], n_all))
    elif fam == {"pantry", "fridge"}:
        if "freeze" in tip_keys:
            lead = ("The USDA gives this item %d storage times across the "
                    "pantry and the refrigerator and none for the freezer, "
                    "though it does attach a freezing note: a note is not a "
                    "published figure." % s["filled"])
        else:
            lead = ("The USDA gives this item a pantry and a refrigerator "
                    "figure and no freezer figure at all, the pattern behind "
                    "%d of the %d foods in the data." % (n_same, n_all))
    elif fam == {"fridge"}:
        extra = (" It adds notes for other methods without giving them a time."
                 if n_tips > 1 else "")
        lead = ("The refrigerator is the only place the USDA gives this item a "
                "storage time, as it does for %d of the %d foods the "
                "USDA lists.%s"
                % (n_same, n_all, extra))
    elif fam == {"pantry"}:
        lead = ("The USDA rates this item in the pantry and nowhere else, one "
                "of %d foods of the %d it files that way." % (n_same, n_all))
    elif fam == {"freeze"}:
        lead = ("The freezer is the only method the USDA gives this item a "
                "time for, which it does for %d of %d foods."
                % (n_same, n_all))
    else:
        # Ветка без единого пригодного срока: числа в ней взять неоткуда,
        # кроме счёта самих ячеек, а абзац без числа гейт снимает — и снимал
        # девятнадцать страниц по причине, которая чинится одной фразой.
        numeric = False
        lead = ("The USDA fills %d of its nine slots for this item, and every "
                "one of them says not recommended rather than giving a time."
                % s["filled"])
    # Оговорка про нечисловой ответ стоит В РАМКЕ, а не в добавках: добавка
    # не доходит до абзаца, который уже добрал слов, и 36 страниц продолжали
    # бы объявлять источник молчащим там, где он ответил словами.
    excl = says_fam - fam
    if excl and "answered in words instead" not in lead:
        where = listing(sorted(FAMILY[k].replace("the ", "") for k in excl))
        # Оговорка длинная, если в абзац влезает, и короткая, если нет:
        # абзац, выбившийся за верхнюю границу окна, снимает всю страницу, а
        # без оговорки страница объявляет источник молчащим там, где он
        # ответил словами.
        # «Те, что с числом» — правда ТОЛЬКО там, где выше речь шла о
        # числовых ячейках. В ветке без единого срока фраза становилась
        # прямой ложью: на /sour-cream/ страница объявляла ячейки «не
        # рекомендовано» ячейками с числом, в одном предложении с самой
        # собой.
        long_c = ((" Those are the slots with a number in them." if numeric
                   else "")
                  + " The %s slot is not blank either: the source answers it "
                  "in words rather than in days, and that answer is set out "
                  "below." % where)
        short_c = (" The %s slot is not blank either: the source answers it "
                   "in words, below." % where)
        lead += long_c if wc(lead + long_c) <= INTRO_MAX else short_c
    # Чужие имена продукта — то, под чем его ищут, и то, чего нет ни на одной
    # другой странице. Кладём их В РАМКУ, а не в необязательные добавки:
    # добавка до них не доходит, если рамка уже добрала до нижней границы.
    alt = alt_names(it)
    tail = ""
    if alt:
        tail = " The source also indexes it as %s." % listing(alt)
    elif it["subcategory"]:
        tail = " Within %s it is filed under %s." % (it["category"],
                                                     it["subcategory"])
    if tail and wc(lead + tail) <= INTRO_MAX:
        lead += tail
    extras = []
    if s["n_states"] > 1:
        extras.append("The rows are grouped by kind, %d in all, because the "
                      "windows differ between them."
                      % s["n_states"])
    if s["open"]:
        extras.append("Both the sealed and the opened rows are filled, which "
                      "is what makes the comparison above possible.")
    ths = thaw_state(it)
    if ths is not None:
        extras.append("It also carries the after-thawing row at %s, which most "
                      "entries leave empty." % st_text(ths, "fridge_thaw"))
    if s["no_slots"]:
        n_no = len(s["no_slots"])
        extras.append("%s not recommended, which is an answer, not a gap."
                      % ("One row says" if n_no == 1 else "%d rows say" % n_no))
    if s["mixed"]:
        extras.append("On %s the kinds disagree: rated for one, marked not "
                      "recommended for another."
                      % listing([SLOT_EN[k] for k in s["mixed"][:2]]))
    if s["spread"]:
        extras.append("Shortest to longest, the rows differ by %s."
                      % mult(s["spread"][0]))
    extras.append("%d of the nine slots carry a value; %d are blank, and a "
                  "blank is not a zero." % (s["filled"], 9 - s["filled"]))
    return ("<h2>Every storage figure the USDA publishes for this item</h2>"
            "<p>%s</p>%s"
            % (compose(lead, extras, INTRO_MIN, INTRO_MAX), rows))


def kind_names(it, budget=40):
    """Имена состояний, пока они укладываются в бюджет слов абзаца.

    Подзаголовки источника бывают длиной в предложение («low acid, such as
    meat, poultry, fish, gravy, stew, soups, beans, carrots, corn, pasta,
    peas, potatoes, spinach»), а у ветчины их двадцать. Перечисляем, пока
    помещается, остальные считаем числом — и число тоже факт.
    """
    names, used, rest = [], 0, 0
    for st in states_of(it):
        k = (st.get("kind") or "").strip() or ("USDA record %s" % st.get("id"))
        n = len(k.split())
        if used + n > budget:
            rest += 1
            continue
        names.append(k)
        used += n
    return names, rest


def shelf_band(st):
    """Полный размах срока вне морозилки у состояния: «2 days to 4 days».

    Заголовок страницы схлопывает ту же величину в осторожную сторону («2
    days»), а `shelf_h` берёт верхний конец («4 days»). Печатать в блоке
    состояний один из концов значило бы дать читателю два числа об одном и
    том же, расходящихся в разные стороны, — а полный размах верен обоим.
    """
    k = fk.shelf_key(st)
    return st_text(st, k) if k else None


def _kinds_lead(it, s, budget, with_ends):
    """Рамка блока состояний при заданном бюджете на имена."""
    sts = states_of(it)
    n = len(sts)
    names, rest = kind_names(it, budget)
    if names and rest:
        said = " — %s, and %d more listed below — " % (listing(names), rest)
    elif names:
        said = " — %s — " % listing(names)
    else:
        said = ", each listed below with its own windows, "
    with_w = [st for st in sts if fk.shelf_days(st) is not None]
    vals = sorted(with_w, key=fk.shelf_days)
    if not with_w:
        return ("The USDA files %d separate entries under this name%sand gives "
                "none of them a window outside the freezer at all, which is why "
                "every row below that is not a freezer row carries a dash."
                % (n, said))
    if abs(fk.shelf_days(vals[0]) - fk.shelf_days(vals[-1])) < 0.01:
        return ("The USDA files %d separate entries under this name%sand gives "
                "every one of them the same window outside the freezer, %s. "
                "They are separate rows in the source rather than separate "
                "answers to the question." % (n, said, shelf_band(vals[0])))
    if with_ends:
        return ("The USDA files %d separate entries under this name%sand they "
                "do not keep for the same time: %s holds %s outside the "
                "freezer, %s holds %s."
                % (n, said, kind_title(it, vals[0]), shelf_band(vals[0]),
                   kind_title(it, vals[-1]), shelf_band(vals[-1])))
    # «САМОЕ КОРОТКОЕ ОКНО» ЗДЕСЬ ЗНАЧИЛО НЕ ТО. Величина считается через
    # fk.shelf_days, то есть это ЛУЧШЕЕ неморозильное окно каждого вида, а
    # фраза называла его «самым коротким окном вне морозилки» — и на
    # /canned-goods/ обещала 12–18 месяцев там, где двумя предложениями ниже
    # тот же абзац печатает «The shortest of these … 3 days to 4 days» по
    # вскрытой банке. Один абзац, два разных смысла слова «shortest», и
    # расхождение в девяносто раз.
    #   Числа верны оба; ложной была рамка. Теперь сказано, ЧТО измерено:
    # вид, который держится меньше всех, и его собственное лучшее окно.
    return ("The USDA files %d separate entries under this name%sand they do "
            "not keep for the same time: at its best the shortest-keeping of "
            "them holds %s outside the freezer, the longest %s."
            % (n, said, shelf_band(vals[0]), shelf_band(vals[-1])))


def kinds_block(it, s):
    """Состояния одного продукта, названные поимённо и со своими окнами.

    ЕДИНИЦА ПУБЛИКАЦИИ — продукт, а не строка источника: у ходовой еды
    FoodKeeper держит несколько строк под одним именем, и порознь они были
    почти дословными близнецами, из-за чего гейт выбрасывал всю голову ниши.
    Вместе они дают самый непохожий абзац страницы: имена состояний не
    повторяются больше нигде.
    """
    sts = states_of(it)
    if len(sts) < 2:
        return ""
    n = len(sts)
    # Бюджет на имена подбирается под окно абзаца, а не назначается на глаз:
    # у ветчины двадцать состояний, и рамка с именами вышла в 83 слова при
    # потолке 72 — страница снималась гейтом окна.
    belt = belt_sentence(it)
    lead = ""
    for budget, ends in ((40, True), (28, True), (18, False), (8, False),
                         (0, False)):
        lead = _kinds_lead(it, s, budget, ends)
        if wc(belt + " " + lead) <= ANSWER_MAX - 8:
            break
    if belt:
        lead = belt + " " + lead
    none_w = [st for st in sts if fk.shelf_days(st) is None]
    n_freeze = len([1 for st in sts
                    for k in ("freeze", "freeze_purchase")
                    if (st["slots"].get(k) or ["no"])[0] not in ("no",)])
    extras = []
    if none_w:
        extras.append("%s carries no figure outside the freezer at all: the "
                      "row below stands at a dash rather than being left out."
                      % listing([kind_title(it, x) for x in none_w[:2]]))
    extras.append(speaks_for(it))
    if s["mixed"]:
        extras.append("They also disagree about the %s."
                      % listing([SLOT_EN[k] for k in s["mixed"][:2]]))
    extras.append("%d of the %d carry a freezer figure." % (n_freeze, n))
    # Страница-выбор не печатает одного вердикта — и всё же обязана сказать,
    # чем обернётся САМОЕ КОРОТКОЕ из перечисленных окон: оно стоит в списке
    # первым, и число без последствия — это половина ответа. Фраза несёт имя
    # вида и его окно, поэтому она СВОЯ у каждой страницы: общая дословная
    # стоила бы корпусу 58 страниц, снятых гейтом близнецов. И она НЕ добавка:
    # `compose` бросает очередь, как только абзац дорос, и до неё не доходило.
    short = ""
    w_short = worst_cell(it) if multi(it) else None
    if w_short and hot_slot(it) is None:
        k_short, _r = fk.food_kind(it, w_short[1], w_short[3], w_short[0])
        short = ("<p>%s</p>"
                 % esc("The shortest of these, %s at %s, is %s."
                       % (kind_title(it, w_short[0]),
                          human(w_short[3],
                                (w_short[0].get("units") or {}).get(
                                    w_short[1])),
                          SHORTEST_IS[k_short])))
    return ("<h2>The USDA rates %d kinds of this separately</h2><p>%s</p>%s"
            % (n, compose(lead, extras), short))


def corpus_place(s):
    """Место среди того, что USDA кладёт В ТО ЖЕ МЕСТО.

    Прежде доля считалась против ВСЕГО корпуса, где рядом лежат пищевая сода,
    мёд и консервы, и отвечала на вопрос, которого у человека с открытым
    холодильником нет: «дольше, чем 29% всего перечисленного» — это не ответ
    на «а это много?». Множество сравнения сузилось до тех продуктов, которым
    источник даёт срок в ТОМ ЖЕ месте.

    Край по-прежнему называется именем, а не долей: доля, округлившаяся в 0%
    или 100%, — это край, и «keeps longer than 0%» стояло на 13 страницах.
    """
    p, place = s.get("place_pct"), s.get("place")
    if p is None or not place:
        return ""
    word = PLACE_WORD[place]
    n, ties = s["place_n"], s.get("place_ties") or 1
    if p == 0:
        if ties > 1:
            return ("Nothing the USDA puts in the %s keeps a shorter time, "
                    "and %d of those entries share this same figure."
                    % (word, ties))
        return ("Of the %d foods the USDA gives a %s figure, none keeps a "
                "shorter time than this one." % (n, word))
    if p >= 100:
        if ties > 1:
            return ("Nothing in the %s keeps longer, though %d entries match "
                    "it exactly." % (word, ties))
        return ("Of the %d foods the USDA gives a %s figure, none keeps "
                "longer than this one." % (n, word))
    return ("Among the %d foods the USDA also gives a %s figure, it keeps "
            "longer than %d%% of them." % (n, word, p))


def rank_block(it, s, ctx):
    """«А это много?». Одинокое число ничего не значит, и место среди соседей
    называется через ИМЕНА, а не через долю."""
    if not s["rank"]:
        return ""
    place, total, days = s["rank"]
    row = ctx["cat"].get(it["category"]) or []
    med = shelf_h(row[len(row) // 2]) if row else "unknown"
    # Ничья проверяется ПЕРВОЙ. «Это самое недолговечное, что USDA относит к
    # выпечке: 2 дня, а стоящий выше держит 2 дня» — превосходная степень над
    # равным числом, на трёх страницах.
    if s["tied"] > 1:
        lead = ("%d items in the %s list keep exactly as long as %s, %s, "
                "so they all share place %d of %d rather than being put in an "
                "order the data does not support."
                % (s["tied"], esc(it["category"]), subj_l(s), shelf_h(it),
                   place, total))
    elif place == 1 and s["below"] is not None:
        lead = ("Nothing the USDA files under %s keeps longer outside the "
                "freezer than %s: %s. Next is %s at %s, and the middle of "
                "the %d-item list sits at %s."
                % (esc(it["category"]), subj_l(s), shelf_h(it),
                   esc(title_of(s["below"])), shelf_h(s["below"]), total, med))
    elif s["below"] is None and s["above"] is not None:
        lead = ("%s is the shortest-lived thing the USDA files under %s: %s, "
                "where the item above it, %s, holds %s and the middle of the "
                "%d-item list sits at %s."
                % (subj(s), esc(it["category"]), shelf_h(it),
                   esc(title_of(s["above"])), shelf_h(s["above"]), total, med))
    else:
        lead = ("Among the %d items the USDA files under %s, %s ranks %d "
                "by how long it keeps outside the freezer. %s holds %s, %s "
                "holds %s."
                % (total, esc(it["category"]), subj_l(s), place,
                   esc(title_of(s["above"])), shelf_h(s["above"]),
                   esc(title_of(s["below"])), shelf_h(s["below"])))
    # Методологическая оговорка про верхнюю границу и общие места живёт в блоке
    # метода — одном из двух объявленно общих. Здесь она стояла на каждой
    # странице и своей длиной делала близнецами треть корпуса.
    extras = []
    extras.append(corpus_place(s))
    if s["spread"]:
        extras.append("Its own methods differ by %s, so where you put it "
                      "matters as much as what it is." % mult(s["spread"][0]))
    if s["gain"]:
        extras.append("Freezing lifts it to %s, which the ranking deliberately "
                      "ignores." % human(s["gain"].num))
    return "<h2>Is that a long time?</h2><p>%s</p>" % compose(lead, extras)


DATE_TOOL_JS = (
    # `document` и `getAttribute` названы ОДИН раз: класс «посчитано из
    # вашего дня» стоил 46 байт сверх потолка кода, а поднимать потолок ради
    # цвета значило бы платить весом отданной страницы за облик.
    "(function(){var D=document;function A(e,n){return e.getAttribute('data-'+n)}"
    "var ds=D.querySelectorAll('[data-clock][data-label]');"
    "for(var z=0;z<ds.length;z++){var b=ds[z],c0=A(b,'clock');"
    "var lb=D.createElement('label');lb.htmlFor='kd-'+c0;"
    "lb.textContent=A(b,'label');"
    "var ip=D.createElement('input');ip.type='date';ip.id='kd-'+c0;"
    "b.appendChild(lb);b.appendChild(ip);b.hidden=false}"
    "var outs=D.querySelectorAll('[data-lo]');if(!outs.length)return;"
    "var WD=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];var MO=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];"
    'var now=new Date();var today=new Date(now.getFullYear(),now.getMonth(),now.getDate());'
    "function fmt(d,y){var s=WD[d.getDay()]+' '+d.getDate()+' '+MO[d.getMonth()];"
    "return y?s+' '+d.getFullYear():s}function add(v,n){var p=v.split('-');"
    'return new Date(+p[0],+p[1]-1,+p[2]+n)}function days(a,b){return Math.round((b-a)/86400000)}'
    "function say(n){return n===1?'1 day':n+' days'}function run(){for(var k=0;"
    "k<outs.length;k++){var e=outs[k];var c=A(e,'clock');"
    "var i=D.getElementById('kd-'+c);var head=e.firstChild;if(!i||!i.value){e.classList.remove('on');e.lastChild.nodeValue=A(e,'plain');"
    "head.textContent=A(e,'lead');continue}var lo=add(i.value,+A(e,'lo'));"
    "var hi=add(i.value,+A(e,'hi'));var y=lo.getFullYear()!==today.getFullYear()||hi.getFullYear()!==today.getFullYear();"
    "var text=fmt(lo,y);if(hi-lo>0){text=text+' - '+fmt(hi,y)}e.lastChild.nodeValue=text;e.classList.add('on');"
    # «ПРОСРОЧЕНО» РЕШАЕТСЯ КОНЦОМ ОКНА, А ОТСЧЁТ — НАЧАЛОМ. Обе величины
    # брались от lo, и на 226 страницах из 296 календарь объявлял еду
    # просроченной внутри её собственного окна: у йогурта с окном 1-2 недели
    # строка «Past it by 7 days» стояла над датой, которая ещё не наступила.
    # Ошибка была в сторону выброшенной еды — самая дорогая из двух.
    #   Обратный отсчёт остаётся на lo сознательно: «действовать к» — это
    # РАННИЙ край, и перенос его на hi увёл бы икру с 7 суток на 28, то есть
    # ошибся бы в сторону съеденной испорченной.
    "var a=days(today,lo),b=days(today,hi);"
    "head.textContent=(b<0?('Past it by '+say(-b)):(a>0?(say(a)+' from today')"
    ":(b===0?'Today is the last day':('In the window now, '+say(b)+' left'))))"
    "+' · '+A(e,'plain');"
    "}}var ins=D.querySelectorAll('input[type=date]');for(var j=0;"
    "j<ins.length;j++){ins[j].addEventListener('change',run);ins[j].addEventListener('input',run)}"
    'run()})();'
)


def _date_rows(it, st, used_clocks):
    rows = ""
    for key, _f, _l in fk.SLOTS:
        v = st["slots"].get(key)
        if v is None or v[0] == "no":
            continue
        lo, hi = v
        clock = CLOCK_OF[key]
        # Срок короче суток датой не показывается: двухчасовой предел при
        # комнатной температуре, превращённый в дату, читается как разрешение
        # на весь день.
        if hi < 1:
            rows += ('<li><span class="rk">%s</span><span class="rv">%s, and '
                     'no date will help: it is shorter than a day</span></li>'
                     % (SLOT_LABEL.get(key, esc(SLOT_TH[key])),
                        esc(st_text(st, key))))
            continue
        if clock not in used_clocks:
            used_clocks.append(clock)
        plain = "%s %s" % (st_text(st, key), CLOCK_TAIL[clock])
        rows += ('<li><span class="rk">%s</span>'
                 '<span class="rv" data-lo="%d" data-hi="%d" '
                 'data-clock="%s" data-lead="%s" data-plain="%s">'
                 '<small>%s</small>%s</span></li>'
                 % (SLOT_LABEL.get(key, esc(SLOT_TH[key])),
                    int(round(lo)), int(round(hi)), clock,
                    "Use by", esc(plain), "Use by", esc(plain)))
    return rows


def date_block(it, s):
    """Блок 9 — посчитать на своих числах. Скрипт встроенный и ничего не грузит;
    без него в ячейках остаётся тот же диапазон словами."""
    used_clocks = []
    rows = form_rows(it, lambda p, st: _date_rows(p, st, used_clocks))
    if not rows:
        return ""
    d = s["days"]
    days = int(round(d)) if d is not None else 0
    # Датируемые способы называются поимённо: их набор у каждого продукта свой,
    # и это единственная часть блока, которая не может совпасть у всех.
    dat = [SLOT_EN[k] for k in all_keys(it)]
    opens = [k for k in all_keys(it) if k.endswith("_open")]
    n_rows = rows.count("data-lo=")
    if s["n_states"] > 1:
        lead = ("Each kind gets its own dated rows here, %s across the %d the "
                "USDA lists under this name, because a date is only worth "
                "printing against the window it belongs to."
                % (plural_en(n_rows, "row"), s["n_states"]))
    elif opens:
        lead = ("Two clocks run on this item: one from the day it went "
                "into storage and one from the day the seal broke. Both are "
                "listed below, %s in all." % plural_en(n_rows, "row"))
    elif len(dat) >= 4:
        lead = ("%d of the rows below take a date, and each has its own range, "
                "so this item ends up with %d deadlines rather than one."
                % (n_rows, n_rows))
    elif s["scale"] in ("months", "years"):
        lead = ("Counting %s forward from a date is not arithmetic anyone "
                "does reliably in their head. Give the field the day it went "
                "into storage." % shelf_h(it))
    elif len(dat) == 1:
        lead = ("One row, one deadline: %s in the %s, counted from the day it "
                "went in rather than the day it was made."
                % (human(d, s["days_u"]), dat[0]))
    else:
        lead = ("The window here is %s, short enough that the day it went in "
                "is worth writing down." % human(d, s["days_u"]))
    hot = hot_slot(it)
    # Поле бирки печатается только для окна длиннее суток — то же условие,
    # что и в label_fields; повторить его здесь дешевле, чем разойтись с ним.
    on_label = {hot[4]} if (hot and hot[3] >= 1) else set()
    # Поле строит скрипт — ОДНОЙ функцией с полем на бирке: два места, где
    # печатается один и тот же контрол, однажды разойдутся.
    fields = "".join(date_input(c, False)
                     for c in used_clocks if c not in on_label)
    extras = ["Each clock has its own field: a figure counted from the day "
              "of purchase cannot be counted from the day you opened it."
              if fields else
              "The field for this one is at the top of the page, above "
              "the answer it changes.",
              "Nothing is sent anywhere: the arithmetic runs in your browser."]
    return ("<h2>Turning the range into a date</h2><p>%s</p>%s%s"
            % (compose(lead, extras, INTRO_MIN, INTRO_MAX), fields, rows))


def neighbours_block(it, s, nbs):
    """Соседи ПО ДАННЫМ. Форма пучка — все дольше, все короче или вокруг —
    это разные утверждения, и говорить их надо по-разному."""
    if not nbs:
        return ""
    li = "".join('<li><a href="/%s/"><span class="n">%s</span>'
                 '<span class="v">%s%s</span></a></li>'
                 % (n["slug"], esc(n["title"]), esc(n["why"]),
                    ('<small>%s</small>' % esc(n["note"]))
                    if n.get("note") else "")
                 for n in nbs)
    d = s["days"]
    order = sorted(nbs, key=lambda x: x["days"])
    lo_n, hi_n = order[0], order[-1]
    lo, hi = lo_n["days"], hi_n["days"]
    lo_h, hi_h, d_h = lo_n["h"], hi_n["h"], shelf_h(it)
    ties = sum(1 for x in nbs if d is not None and abs(x["days"] - d) < 0.01)
    tight = lo > 0 and hi / lo < 1.35
    if d is None:
        # РАЗНАЯ ФОРМА ДАННЫХ - РАЗНЫЕ СЛОВА. Числа у этого продукта нет
        # вовсе, сравнивать не по чему, и список стоит здесь затем, чтобы
        # вывести на еду, которой источник срок ДАЛ.
        # «Окна нет вовсе» и «одного окна нет» — РАЗНЫЕ утверждения, и
        # второе стоит на странице, где ниже напечатано десять окон.
        if multi(it):
            lead = ("%s carries no single window to compare — its %d kinds "
                    "each keep their own — so these %d are simply what the "
                    "USDA rates on the same shelf, shortest first: %s at %s "
                    "through %s at %s."
                    % (subj_l(s), len(states_of(it)), len(nbs),
                       lo_n["title"], lo_h, hi_n["title"], hi_h))
        else:
            lead = ("The USDA gives %s no window of its own to compare, so "
                    "these %d are simply what it does rate on the same shelf, "
                    "shortest first: %s at %s through %s at %s."
                    % (subj_l(s), len(nbs), lo_n["title"], lo_h,
                       hi_n["title"], hi_h))
    elif ties >= 3:
        lead = ("All %d of the %d items nearest %s keep exactly as long as it "
                "does, %s, so the ranking around it is a tie rather than an "
                "order." % (ties, len(nbs), subj_l(s), d_h))
    elif tight:
        lead = ("The %d items nearest it sit inside a band of %s to %s — a "
                "tight cluster, and %s at %s is inside it."
                % (len(nbs), lo_h, hi_h, subj_l(s), d_h))
    elif lo >= d:
        lead = ("All %d of the nearest items keep at least as long as %s, "
                "%s to %s against its %s: it is the bottom of its own "
                "cluster." % (len(nbs), subj_l(s), lo_h, hi_h, d_h))
    elif hi <= d:
        lead = ("Every one of the %d nearest items keeps the same or less, %s "
                "to %s against the %s of %s, which makes it the durable end of "
                "the cluster." % (len(nbs), lo_h, hi_h, d_h, subj_l(s)))
    else:
        lead = ("The %d items below are the closest match to %s by storage "
                "behavior, running %s to %s and bracketing its %s."
                % (len(nbs), subj_l(s), lo_h, hi_h, d_h))
    extras = []
    if s["rank"]:
        extras.append("They are the %d entries nearest it among the %d the "
                      "USDA files under %s."
                      % (len(nbs), s["rank"][1], it["category"]))
    if s["gain"]:
        extras.append("Freezing would put this one at %s, a comparison the "
                      "list below deliberately leaves out."
                      % human(s["gain"].num))
    if s["spread"]:
        extras.append("Its own best and worst methods are %s apart."
                      % mult(s["spread"][0]))
    return ("<h2>Items that behave the same way</h2><p>%s</p>"
            '<ul class="near" role="list">%s</ul>'
            % (compose(lead, extras, INTRO_MIN, INTRO_MAX), li))


# ----------------------------------------------------------- блоки глубины
#
# Третье окно абзаца. Первые два — ОТВЕЧАЮЩИЙ (35–72 слова) и ВВОДЯЩИЙ
# стоящую ниже таблицу (18–56). Это — ПЕРЕЧИСЛЯЮЩИЙ: он называет другие
# продукты поимённо, и требовать от него краткости значило бы выбросить
# имена, то есть ровно те слова, которых нет ни на одной другой странице.
#
# Ловушка волны записана прямо здесь: страницы удлиняются НЕ водой. Каждый
# абзац ниже ветвится по ФОРМЕ (размер когорты, край полки, есть ли куда
# шагнуть вверх, сколько записей под именем) и обязан нести имена соседей и
# посчитанное число. Дописывание слов — ровно то, чем ферма получила 593
# страницы с медианой сходства 0,82.
DETAIL_MIN, DETAIL_MAX = 80, 140

# Сколько имён показывает список глубины. Порядок — по БЛИЗОСТИ срока к
# нашему, поэтому у двух продуктов одной когорты списки всё-таки разные.
COHORT_SHOWN = 8


def verb_n(n, one, many):
    """Глагол при СЧЁТЕ. «1 entry in the category keep half as long» — та же
    рассогласовка, что «How long Apples keeps», только по другому подлежащему,
    и ловит её тот же гейт."""
    return one if n == 1 else many


def _dist(it, x):
    a, b = fk.shelf_days(it), fk.shelf_days(x)
    if a is None or b is None:
        return 1e9
    return abs(a - b)


def _by_closeness(it, rows):
    return sorted(rows, key=lambda x: (_dist(it, x), int(x["id"])))


def _mate_rows(rows, by_shelf=False):
    """Строки имён: имя слева, ОТВЕТ этого продукта справа.

    Ссылок здесь нет намеренно: плотность внутренних ссылок на странице и так
    вдвое выше нормы ветки, а работает в этом блоке ИМЯ, а не переход.
    Величина берётся той же функцией answer_value, что печатают витрины,
    указатель и заголовок цели: вторая лестница для одной величины однажды
    разойдётся с первой.
    """
    # СТРОКА ОБЯЗАНА ПОКАЗАТЬ ТО, ЗА ЧТО ОНА В СПИСКЕ. Печатался только
    # связывающий ответ, а отбор в этот блок идёт по ДЛИННОМУ окну: на
    # /relish/ под фразой «3 products that hold at least twice as long than
    # 30 months» стояло «Gravy — 1 day», «Anchovies — 3 days». 184 страницы
    # из 297, и блок читался как сломанная выгрузка, хотя отбор был верен.
    #   Длинная величина ставится ВТОРОЙ, а не вместо: подменять связывающее
    # окно самым длинным здесь уже пробовали, и получилось «Pies — 4 days»
    # там, где источник даёт два часа при комнатной температуре.
    #   Когда блок СРАВНИВАЕТ по сроку вне морозилки (`by_shelf`), первой
    # стоит ровно та величина, по которой шёл отбор, — иначе подпись говорит
    # «вдвое дольше двух лет», а строка показывает три года осторожного края
    # при четырёх годах верхнего, и читателю видно противоречие, которого в
    # данных нет. Осторожный ответ остаётся второй строкой и никуда не
    # девается.
    def _two(x):
        if by_shelf:
            val, note = shelf_h(x), answer_line(x)
            if note == val:
                note = ""
        else:
            val, note = listing_parts(x)
        return ('%s%s' % (esc(val),
                          ('<small>%s</small>' % esc(note)) if note else ""))
    li = "".join(
        '<li><span class="rk">%s</span><span class="rv">%s</span></li>'
        % (esc(short_of(x)), _two(x))
        for x in rows)
    # Пометка `data-names` — ОБЪЯВЛЕНИЕ списка имён, по которому гейт находит
    # эти строки и сверяет их с источником. Строка со ссылкой проверяется
    # своим гейтом; строка без ссылки была бы величиной чужого продукта,
    # напечатанной и не проверенной ничем.
    return ('<ul class="rows" data-names="1">%s</ul>' % li) if li else ""


def _named(rows, n=3):
    """Первые имена прозой. Имена — самые непохожие слова, какие может дать
    страница, и стоять они обязаны В АБЗАЦЕ, а не только в списке."""
    return listing([esc(short_of(x)) for x in rows[:n]])


def _detail(head, lead, extras, rows=""):
    """Раздел глубины: заголовок, абзац перечисляющего окна, список имён."""
    return ('<h2>%s</h2><p data-win="detail">%s</p>%s'
            % (esc(head), compose(lead, extras, DETAIL_MIN, DETAIL_MAX), rows))


def _shape_near(it, ctx, want):
    """Ближайшие ПО ФОРМЕ ЗАПИСИ: точная когорта (тот же набор ячеек) и —
    ОТДЕЛЬНО — добивка из тех, у кого набор пересекается сильнее всего.

    Возвращает (точные, добивка, размер точной когорты). Раньше два набора
    возвращались склеенными, и абзац говорил «Only 1 other product carries
    the same set of places», а список под ним показывал восемь строк: на 66
    страницах строк было больше, чем объявлено, а на 38 абзац противоречил
    сам себе в трёх предложениях подряд. Склеенный список нельзя просто
    обрезать до когорты — на 24 страницах в нём осталось бы ноль строк, и
    гейт, читающий `data-names`, молча позеленел бы над пустотой.
    """
    keys = tuple(all_keys(it))
    exact = [x for x in ctx["slotset"].get(keys, []) if x["id"] != it["id"]]
    out = _by_closeness(it, exact)[:want]
    if len(out) < want:
        have = {x["id"] for x in out} | {it["id"]}
        kset = set(keys)
        rest = [x for x in ctx["cat"].get(it["category"], [])
                if x["id"] not in have]
        rest.sort(key=lambda x: (-len(kset & set(all_keys(x))),
                                 _dist(it, x), int(x["id"])))
        return out, rest[:want - len(out)], len(exact)
    return out, [], len(exact)


def cohort_block(it, s, ctx):
    """Кто ещё записан ТЕМ ЖЕ набором ячеек.

    Набор ячеек — признак, который у источника есть, а на странице не был
    напечатан ни разу: две записи с одинаковыми числами, но разным набором
    мест — разные записи, и человеку это говорит больше, чем сами числа.
    """
    keys = all_keys(it)
    if not keys:
        return ""
    exact, filler, n = _shape_near(it, ctx, COHORT_SHOWN)
    near = exact + filler
    if not near:
        return ""
    where = listing([SLOT_EN[k] for k in keys])
    total, blank = ctx["total"], 9 - len(keys)
    if n == 0:
        lead = ("No other product in the file is rated in exactly this set of "
                "places: %s, and nothing else. That makes the shape of this "
                "record unique among the %d products here, so the closest "
                "comparisons available are the entries that share most of it "
                "— %s. Their windows are printed beside them below, and none "
                "of them is rated in quite the same way."
                % (where, total, _named(near)))
    elif n <= 3:
        lead = ("Only %s in the whole file %s the same set of rated "
                "places as this one, %s: %s. That is %s out of %d, "
                "which makes this a rare shape of record rather than a "
                "common one, and it is worth knowing that the comparison "
                "below is drawn from a very small group."
                % (plural_en(n, "other product"), verb_n(n, "carries",
                                                            "carry"),
                   where, _named(exact, n),
                   plural_en(n, "product"), total))
    elif n <= 15:
        lead = ("%d other products are rated in exactly these places — %s — "
                "out of the %d in the file, so this is an uncommon shape of "
                "record. The nearest of them by keeping time are %s. They are "
                "listed below with their own answers, closest first, which is "
                "why this list differs from the one on their pages."
                % (n, where, total, _named(near)))
    else:
        lead = ("This is a common shape of record: %d of the %d products are "
                "rated in the same places, %s, and %d of the nine slots are "
                "left blank on all of them. Sorted by how close their windows "
                "are to this one, the nearest are %s, and the rest of that "
                "group is what the list below draws on."
                % (n, total, where, blank, _named(near)))
    extras = []
    d = fk.shelf_days(it)
    # СЧИТАЕМ ТЕХ, О КОМ ГОВОРИМ. Здесь считались все восемь показанных, а
    # рамка абзаца выбрана по точной когорте: «Only 1 other product… Of the
    # 8 shown, 2 keep longer» стояло на 38 страницах.
    counted = exact if exact else near
    ranked = [x for x in counted if fk.shelf_days(x) is not None]
    if ranked and d is not None:
        over = sum(1 for x in ranked if fk.shelf_days(x) > d)
        if over == 0:
            extras.append("Of the ones shown, none keeps longer than this "
                          "one does.")
        else:
            extras.append("Of the %d shown, %d %s longer than this one."
                          % (len(ranked), over,
                             verb_n(over, "keeps", "keep")))
    if ranked:
        top = max(ranked, key=lambda x: fk.shelf_days(x))
        extras.append("The longest-keeping of them is %s at %s."
                      % (esc(short_of(top)), shelf_h(top)))
    if s["fam_count"]:
        extras.append("Counted more loosely, by which of the three places "
                      "are rated at all, %d products match this one."
                      % s["fam_count"])
    extras.append("A blank is not a zero: %d of the nine slots carry no "
                  "published figure here." % blank)
    if s["tips"]:
        extras.append("The source also attaches %s to this record."
                      % plural_en(s["tips"], "handling note"))
    extras.append("Shape is counted from the slots that carry a time, so a "
                  "row marked not recommended does not join the set.")
    extras.append("The %d products in the file were merged from the rows the "
                  "USDA publishes, one page for each name." % total)
    # ДВЕ ГРУППЫ, КАЖДАЯ ПОДПИСАНА. Восемь строк под фразой «только один
    # такой» читались как обещание, которого список не держит; обрезать
    # список нельзя — на 24 страницах он стал бы пустым.
    body = _mate_rows(exact) if exact else ""
    if filler:
        body += ('<p data-win="note">%s</p>%s'
                 % ("Closest by shape, but not an exact match — they share "
                    "most of these places, not all of them."
                    if exact else
                    "Nothing carries this exact set of places, so these share "
                    "most of it.", _mate_rows(filler)))
    return _detail("Products the USDA rates in the same places",
                   lead, extras, body)


def shelfmates_block(it, s, ctx):
    """Полка источника — подрубрика, а не рубрика.

    Рубрика («Produce») отвечает на вопрос отдела, подрубрика («Fresh
    Vegetables») — на вопрос полки, и до этой волны она была названа одним
    придаточным на всю страницу.
    """
    shelf = it["subcategory"] or it["category"]
    mates = [x for x in ctx["shelfmates"].get((it["category"],
                                               it["subcategory"]), [])
             if x["id"] != it["id"]]
    rated = [x for x in mates if fk.shelf_days(x) is not None]
    rated.sort(key=lambda x: (-fk.shelf_days(x), int(x["id"])))
    d = fk.shelf_days(it)
    if not rated or d is None:
        return ""
    above = sum(1 for x in rated if fk.shelf_days(x) > d)
    n = len(rated)
    top, bottom = rated[0], rated[-1]
    show = _by_closeness(it, rated)[:COHORT_SHOWN]
    if n == 1:
        lead = ("The USDA files this product on a shelf of two. Its only "
                "shelfmate under %s is %s, which keeps %s against this one's "
                "%s, so every comparison on this page that reaches wider than "
                "the shelf has to climb to the whole of %s to find enough "
                "entries to say anything with."
                % (esc(shelf), esc(short_of(top)), shelf_h(top), shelf_h(it),
                   esc(it["category"])))
    elif n <= 4:
        lead = ("%s is a short shelf: %s besides this one. They run from %s "
                "at %s down to %s at %s, and this product sits with %s above "
                "it. A shelf this small is worth reading whole, which is why "
                "every one of them is printed below rather than a sample."
                % (esc(shelf), plural_en(n, "product"), esc(short_of(top)),
                   shelf_h(top), esc(short_of(bottom)), shelf_h(bottom),
                   plural_en(above, "product")))
    elif above == 0:
        lead = ("Nothing else on the %s shelf keeps longer outside the "
                "freezer than this one. The other %d products there run down "
                "from %s at %s to %s at %s, and the ones nearest this product "
                "by window are %s. That makes this page the top of its own "
                "shelf rather than a middle entry."
                % (esc(shelf), n, esc(short_of(rated[0])), shelf_h(rated[0]),
                   esc(short_of(bottom)), shelf_h(bottom), _named(show)))
    elif above == n:
        lead = ("Every one of the other %d products on the %s shelf keeps "
                "longer outside the freezer than this one, from %s at %s down "
                "to %s at %s. The closest of them by window are %s, and the "
                "gap between this product and the rest of its shelf is the "
                "thing worth noticing here."
                % (n, esc(shelf), esc(short_of(top)), shelf_h(top),
                   esc(short_of(bottom)), shelf_h(bottom), _named(show)))
    else:
        lead = ("The USDA puts this product on the %s shelf together with %d "
                "others, and %d of them %s longer outside the freezer. The "
                "shelf runs from %s at %s down to %s at %s. Nearest this "
                "product by window are %s, which is the order the list below "
                "is printed in."
                % (esc(shelf), n, above, verb_n(above, "keeps", "keep"),
                   esc(short_of(top)), shelf_h(top), esc(short_of(bottom)),
                   shelf_h(bottom), _named(show)))
    # ПОЯСНЕНИЕ ОБЯЗАНО БЫТЬ СВОИМ У КАЖДОЙ СТРАНИЦЫ. Первая попытка была
    # одной и той же фразой на всех: сходство прозы выросло, и гейт
    # близнецов снял СЕМЬ страниц — ровно то, за что этот сайт уже попадал
    # в аудит. Теперь оговорка называет ЭТУ еду и ЕЁ ЖЕ два числа, а если
    # они совпадают, не печатается вовсе: говорить о расхождении там, где
    # его нет, — это второе утверждение, которое неправда.
    # СРАВНИВАЮТСЯ ВЕЛИЧИНЫ, А НЕ СТРОКИ. Первая проверка сличала «1 week»
    # с «1 week in the fridge once opened» — строки разные, число одно, — и
    # оговорка выходила «sits here at 1 week rather than at the 1 week …
    # its own answer prints», то есть противопоставляла величину самой себе.
    own_shelf, own_ans = shelf_h(it), answer_line(it)
    shelf_d, ans_d = fk.shelf_days(it), listing_days(it)
    differs = (shelf_d is not None and ans_d is not None
               and abs(shelf_d - ans_d) > 0.01)
    extras = []
    if differs and own_shelf and own_ans:
        extras.append("The order counts the longest window outside the "
                      "freezer, so %s sits here at %s rather than at the %s "
                      "its own answer prints."
                      % (subj_l(s), own_shelf, own_ans))
    if s["rank"]:
        extras.append("Across the whole of %s the same product ranks %d of "
                      "%d." % (esc(it["category"]), s["rank"][0],
                               s["rank"][1]))
    mid = rated[len(rated) // 2]
    extras.append("The middle of the shelf is %s, at %s."
                  % (esc(short_of(mid)), shelf_h(mid)))
    if it["subcategory"]:
        extras.append("The shelf is the source's own subcategory, %s inside "
                      "%s." % (esc(shelf), esc(it["category"])))
    blank_mates = len(mates) - n
    if blank_mates:
        extras.append("%s on this shelf %s no window outside the "
                      "freezer and %s out of the order."
                      % (plural_en(blank_mates, "product"),
                         verb_n(blank_mates, "publishes", "publish"),
                         verb_n(blank_mates, "stays", "stay")))
    extras.append("The freezer is left out of the order on purpose: it "
                  "flattens almost everything it touches.")
    extras.append("A shelfmate with no published window of its own is left "
                  "out of the order rather than counted as zero.")
    # СТРОКА ПЕЧАТАЕТ ТО ЧИСЛО, ПО КОТОРОМУ ОНА ЗДЕСЬ СТОИТ. Абзац называет
    # полку сроком вне морозилки (`shelf_h`, верхний край лучшего
    # неморозильного окна) — по нему же идёт и порядок, — а строки печатали
    # связывающий ответ, то есть ДРУГОЙ конец и часто другую ячейку: «The
    # shelf runs from Prosciutto at 3 months» стояло прямо над строкой
    # «PROSCIUTTO — 2 months in the fridge». Сверка нашла 65 таких
    # расхождений на 57 страницах.
    #   Лечится не переписыванием абзаца, а тем же ключом, что уже заведён
    # для соседнего блока: `by_shelf` ставит первой ровно ту величину, по
    # которой шёл отбор, оставляя связывающий ответ второй строкой.
    return _detail("The rest of the %s shelf" % shelf, lead, extras,
                   _mate_rows(show, by_shelf=True))


# Во сколько раз продукт должен держаться дольше, чтобы считаться ШАГОМ
# ВВЕРХ, а не тем же самым. Полтора раза — та же граница, по которой строка
# списка решает, печатать ли вторую величину.
STEP_UP = 2.0


def swap_block(it, s, ctx):
    """Сравнение, которое человек у холодильника действительно делает: не
    «дольше, чем 29% всего перечисленного», а «что в этом же отделе лежит
    дольше и насколько». Аудит просил ровно это.
    """
    d = fk.shelf_days(it)
    row = ctx["cat"].get(it["category"]) or []
    if d is None or d <= 0 or not row:
        return ""
    longer = [x for x in row
              if x["id"] != it["id"] and fk.shelf_days(x) >= d * STEP_UP]
    longer.sort(key=lambda x: (fk.shelf_days(x), int(x["id"])))
    shorter = [x for x in row
               if x["id"] != it["id"] and fk.shelf_days(x) * STEP_UP <= d]
    shorter.sort(key=lambda x: (-fk.shelf_days(x), int(x["id"])))
    cat, d_h = esc(it["category"]), shelf_h(it)
    if not longer and not shorter:
        return ""
    if not longer:
        show = shorter[:COHORT_SHOWN]
        lead = ("Nothing the USDA files under %s keeps at least twice as long "
                "as this one outside the freezer. It runs the other way: "
                "%s in the category %s half as long or less, among "
                "them %s. So the question this page answers is not what to "
                "buy instead, but what this product outlasts on the same "
                "shelf, and by how much."
                % (cat, plural_en(len(shorter), "entry", "entries"),
                   verb_n(len(shorter), "keeps", "keep"), _named(show)))
    else:
        show = longer[:COHORT_SHOWN]
        first = show[0]
        if len(longer) <= 4:
            lead = ("If it has to keep longer than %s, %s offers %s that %s "
                    "at least twice as long outside the freezer. The nearest "
                    "step up is %s at %s against this one's %s, and the "
                    "rest are %s. A short list like this one is itself the "
                    "finding: the category has few longer options."
                    % (d_h, cat, plural_en(len(longer), "product"),
                       verb_n(len(longer), "holds", "hold"),
                       esc(short_of(first)), shelf_h(first), d_h,
                       _named(show[1:], 3) or "none beyond it"))
        else:
            lead = ("If it has to keep longer than %s, the %s aisle gives %d "
                    "products that hold at least twice as long outside the "
                    "freezer. The smallest step up is %s at %s against "
                    "this one's %s; after it come %s. They are printed below "
                    "in the order the step gets bigger, not alphabetically."
                    % (d_h, cat, len(longer), esc(short_of(first)),
                       shelf_h(first), d_h, _named(show[1:], 3)))
    extras = []
    if longer and shorter:
        extras.append("In the other direction, %s in the category "
                      "%s half as long or less, %s among them."
                      % (plural_en(len(shorter), "entry", "entries"),
                         verb_n(len(shorter), "keeps", "keep"),
                         _named(shorter, 2)))
    if longer:
        far = longer[-1]
        extras.append("The largest step the category offers is %s at %s."
                      % (esc(short_of(far)), shelf_h(far)))
    if s["gain"]:
        extras.append("Freezing this one instead would reach %s, which the "
                      "comparison above leaves out on purpose."
                      % human(s["gain"].num))
    extras.append("Twice as long is the cutoff used here, so a product a "
                  "few days apart from this one is not treated as a step.")
    extras.append("Every figure compared here is the USDA's own, taken "
                  "outside the freezer: the list leads with the figure the "
                  "comparison is made on, and prints the cautious answer "
                  "under it where the two differ.")
    return _detail("If it has to keep longer than this", lead, extras,
                   _mate_rows(show, by_shelf=True))


def record_block(it, s, ctx, vintage):
    """Запись источника, из которой собрана страница: номера строк, сколько
    ячеек заполнено, сколько ответов не числом, в каких единицах напечатан
    источник. Аудит просил печатать номер записи — до этой волны он был у
    парсера и не был на странице ни разу.
    """
    ids = it.get("row_ids") or [it["id"]]
    n_rows, rows_total = len(ids), ctx["rows"]
    filled = len(all_keys(it))
    n_no = len(_said_no(it))
    n_says = len(says_all(it))
    n_tips = len(tips_all(it))
    unit = fk.unit_of(it, fk.shelf_key(it)) or "days"
    idlist = listing(["%s" % x for x in ids[:4]])
    if n_rows == 1:
        # Оговорка про единицу печатается ТОЛЬКО когда единица источника не
        # день: «printed by the source in days rather than in days» стояло
        # на 69 страницах.
        # ТРЕТЬЯ ВЕТКА: СРОКА НЕТ ВОВСЕ. Раньше их было две — «день» и «не
        # день», — и строка «источник печатает свою величину в днях» уходила
        # на страницу, где величины нет ни одной: /sour-cream/ объявляла
        # ненапечатанное число нетронутым.
        if fk.shelf_key(it) is None:
            how = ("and it gives this item no storage time at all: what the "
                   "source answers here it answers in words, above")
        elif unit != "days":
            how = ("and the binding figure on it is printed by the source in "
                   "%s, which is the unit this page keeps rather than "
                   "converting it to days" % unit)
        else:
            how = ("and the source prints its binding figure in days, so the "
                   "window at the top of this page is the source's own "
                   "number untouched")
        # «Заполнено N из девяти» СКАЗАНО ДВАЖДЫ НА СТРАНИЦЕ, и считались
        # две РАЗНЫЕ вещи: выше — ячейки с любым ответом, здесь — ячейки со
        # сроком. На /sour-cream/ выходило «1 из девяти» и «0 из девяти» в
        # одном документе. Считаемое теперь названо.
        # НОМЕР ЗАПИСИ — ЭТО ИМЯ, А НЕ ПОЗИЦИЯ. Источник нумерует строки с
        # пропусками: номера доходят до 684 при 661 строке, и «record 682,
        # one of the 658 rows» читалось как арифметически невозможное на
        # одиннадцати страницах. Названо словом, а не подогнано числом.
        lead = ("This page is built from a single FoodKeeper row, record %s "
                "&mdash; the source&rsquo;s own number for it, not a position "
                "&mdash; one of the %d rows in the snapshot. That row fills "
                "%d of the nine storage slots with a time, %s."
                % (ids[0], rows_total, filled, how))
    elif n_rows <= 4:
        lead = ("The USDA publishes %d separate rows under this name — "
                "records %s — and this page carries all of them rather than "
                "picking one, because their windows differ. Between them they "
                "fill %d of the nine storage slots with a time. %s"
                % (n_rows, idlist, filled, speaks_for(it)))
    else:
        lead = ("This name is one of the crowded ones in the file: %d rows "
                "carry it, starting at record %s, out of %d rows in the "
                "snapshot altogether. All %d are printed on this page as "
                "separate kinds, because a page that merged their windows "
                "into one figure would be publishing a number the USDA never "
                "did. %s" % (n_rows, ids[0], rows_total, n_rows,
                             speaks_for(it)))
    extras = []
    if n_no:
        extras.append("%s marked not recommended, which is an answer rather "
                      "than a gap." % plural_en(n_no, "slot is", "slots are"))
    if n_says:
        extras.append("%s answered in words instead of days, and printed as "
                      "the source wrote it."
                      % plural_en(n_says, "slot is", "slots are"))
    if n_tips:
        extras.append("The record carries %s, quoted on this page word for "
                      "word." % plural_en(n_tips, "handling note"))
    terms = alt_names(it)
    if terms:
        extras.append("The same record answers to %s in the source's own "
                      "index." % listing([esc(x) for x in terms]))
    if it["subcategory"]:
        extras.append("It is filed under %s inside %s, which is where every "
                      "shelf comparison on this page comes from."
                      % (esc(it["subcategory"]), esc(it["category"])))
    extras.append("Every figure here comes from one fixed snapshot, %s, "
                  "and is not refreshed page by page." % vintage)
    # «Ничего не написано руками» перестало быть правдой в тот день, когда
    # значение простого слова стало объявленным: руками написан ВЫБОР ВИДА,
    # и фраза называет ровно его. Утверждение о полноте печатается из того,
    # что есть, а не из того, что было верно вчера.
    extras.append("No figure on this page is written by hand: the numbers "
                  "are read from that record and the comparisons computed "
                  "from the whole file of %d products." % ctx["total"])
    return _detail("The record this page is built from", lead, extras)


# Ровно два блока на сайте одинаковы у всех страниц, и оба — служебные:
# границы применимости и метод. Они объявлены общими здесь и исключены из
# сравнения на близнецов там. Всё остальное обязано различаться.

def safety_block(it):
    """Почему на этой странице НЕ напечатана кратность против одной из ячеек.

    У пирога источник даёт «2 Hours» в шкафу — это не окно хранения, а предел
    пребывания в тепле. Разделив на него, страница напечатала «720× what the
    freezer buys you»: правило опасной зоны, поданное как выгода. Отказ от
    расчёта объявляется ВСЛУХ: молчаливый отказ читатель принимает за то, что
    считать было нечего.
    """
    cells = []
    for i, st in enumerate(states_of(it)):
        for key, lo, hi in fk.safety_limit_cells(st):
            cells.append((st, key, lo, hi, i))
    if not cells:
        return ""
    st, key, _lo, _hi, _i = cells[0]
    val = st_text(st, key)
    where = SHELF_SHORT.get(key, LISTING_WHERE[key])
    who = (" for %s" % kind_title(it, st)) if multi(it) else ""
    same = all(st_text(c[0], c[1]) == val for c in cells)
    if len(cells) > 1 and same:
        who = " for all %d kinds listed here" % len(cells)
    lead = ("The USDA's figure %s%s is %s, and %s is a limit on standing at "
            "room temperature rather than a window for storing it."
            % (where, who, val, val))
    hr = headline_ratio(it)
    if hr:
        extras = ["No multiplier on this page divides by it. A ratio whose "
                  "denominator is a safety limit turns a danger-zone rule "
                  "into a benefit, which is why the %s multiplier above is "
                  "drawn against %s instead."
                  % (ratio_x(hr[1]) + chr(215), DEN_PHRASE[hr[1].den_key])]
    else:
        extras = ["No multiplier is printed on this page at all. A ratio "
                  "whose denominator is a safety limit turns a danger-zone "
                  "rule into a benefit, and there is no second window here "
                  "to divide by instead."]
    extras.append("Nor is it turned into a date. A date implies a day, and "
                  "this figure is counted from the moment the food came out "
                  "of the oven or the refrigerator, not from the day you put "
                  "it away.")
    if len(cells) > 1 and not same:
        extras.append("Each of the %d kinds carries its own limit, and the "
                      "rows below print them separately rather than reducing "
                      "them to one." % len(cells))
    return ("<h2>Why this page prints no multiplier against the room-"
            "temperature figure</h2><p>%s</p>" % compose(lead, extras))


# Нечисловые ответы источника словами. Их было 63 ячейки, и парсер молча
# возвращал на них None — после чего страница печатала «no pantry figure
# exists for it». Источник ОТВЕТИЛ; ответ просто не был числом, и «read the
# package date» — это указание, а не пробел.
SAYS_VALUE = {
    "label": "Package use-by date",
    "indefinite": "Indefinitely",
    "ripe": "Until ripe",
    "unreadable": "Unreadable in the source",
}

SAYS_PROSE = {
    "label": ("%s it answers with the package date rather than a number, and "
              "the use-by date printed on that particular package is the "
              "figure to go by"),
    "indefinite": ("%s it answers Indefinitely, so kept that way the food "
                   "does not run out of time, though it can still lose "
                   "quality"),
    "ripe": ("%s it answers Until ripe, so the clock is the fruit's own "
             "ripening rather than a count of days"),
    "unreadable": ("%s it prints a value we will not read, because the cell "
                   "is mistyped in the USDA file and guessing at what was "
                   "meant would be our number rather than theirs"),
}


def says_all(it):
    """Нечисловые ответы всех состояний: (состояние, ячейка, код, исходная
    строка)."""
    out = []
    for st in states_of(it):
        for k, v in sorted((st.get("says") or {}).items()):
            out.append((st, k, v[0], v[1]))
    return out


def says_block(it):
    """Названное отсутствие. Пустая ячейка и ячейка с нечисловым ответом —
    РАЗНЫЕ вещи, и страница, объявляющая источник молчащим там, где он
    ответил, врёт ровно на то, что он сказал."""
    rows = says_all(it)
    if not rows:
        return ""
    seen, lead_parts = set(), []
    for st, key, code, _raw in rows:
        where = SHELF_SHORT.get(key, LISTING_WHERE[key])
        if (key, code) in seen:
            continue
        seen.add((key, code))
        lead_parts.append(SAYS_PROSE[code] % where)
    # Число стоит В РАМКЕ, а не в добавке: добавка не доходит до абзаца,
    # который уже добрал слов, и абзац без числа гейт снимает.
    n_slots = len({r[1] for r in rows})
    head = ("%d of the nine slots the USDA keeps for this item %s an answer "
            "that is not a number, and an answer in words is still an "
            "answer: " % (n_slots, "holds" if n_slots == 1 else "hold"))
    # Перечисление режется по границе окна абзаца: три длинных пояснения
    # подряд давали 84 слова при потолке в 72, и страница снималась целиком.
    while len(lead_parts) > 1 and wc(head + listing(lead_parts)) > ANSWER_MAX:
        lead_parts.pop()
    lead = head + listing(lead_parts) + "."
    extras = []
    unread = [r for r in rows if r[2] == "unreadable"]
    if unread:
        extras.append("The source cell reads %s%s%s, character for character."
                      % (QUOTE, unread[0][3], QUOTE))
    extras.append("Cells like these were dropped as unreadable until the "
                  "parser learned to name them, and a page that drops an "
                  "answer then goes on to say the source was silent about it.")
    extras.append("They are printed in the rows above with the words the "
                  "source used, never converted into days.")
    return ("<h2>Where the USDA answers in words instead of days</h2>"
            "<p>%s</p>" % compose(lead, extras))


# Как называется ячейка в подписи подсказки источника. Подсказка — не срок:
# 34 из них, длиной до 321 знака, печатались КАПСОМ по правому краю в колонке
# величин, потому что стояли в том же `.rv`, что и «2 WEEKS».
TIP_WHERE = {
    "pantry": "in the pantry", "pantry_purchase": "in the pantry, from the "
    "day you bought it", "fridge": "in the refrigerator",
    "fridge_purchase": "in the refrigerator, from the day you bought it",
    "freeze": "in the freezer",
    "freeze_purchase": "in the freezer, from the day you bought it",
}

# Слова, по которым подсказка источника — про безопасность, а не про вкус.
SAFE_WORDS = ("safe", "not safe", "unsafe", "bacteria", "illness", "discard")


def tips_block(it):
    """Свободный текст источника — ПРОЗОЙ, в своём разделе.

    Это самое полезное поле FoodKeeper: там лежит и единственная настоящая
    инструкция по безопасности («не варить омара, который умер до варки»), и
    ровно то различение качества и безопасности, которое сайт сам путает.
    В колонке величин оно набиралось капсом по правому краю и читалось как
    ошибка вёрстки.
    """
    rows = tips_all(it)
    if not rows:
        return ""
    safe = [r for r in rows
            if any(w in r[2].lower() for w in SAFE_WORDS)]
    rest = [r for r in rows if r not in safe]
    body = ""
    for st, key, text in safe + rest:
        who = ("%s, %s" % (kind_title(it, st), TIP_WHERE[key])) if multi(it) \
            else TIP_WHERE[key][0].upper() + TIP_WHERE[key][1:]
        body += ('<p class="tip"><b>%s.</b> %s</p>'
                 % (esc(who), esc(text)))
    n_safe, n_all = len(safe), len(rows)
    if not n_safe and n_all == 1:
        tail = ("It is not a storage time: it qualifies the figure above "
                "rather than replacing it.")
    elif not n_safe:
        tail = ("None of them is a storage time: they qualify the figures "
                "above rather than replacing them.")
    elif n_safe == n_all == 1:
        tail = ("It is about safety rather than quality, which is the "
                "distinction this data is easiest to get wrong.")
    elif n_safe == n_all:
        tail = ("All %d are about safety rather than quality, which is the "
                "distinction this data is easiest to get wrong." % n_safe)
    else:
        tail = ("%d of the %d are about safety rather than quality, and %s "
                "printed first." % (n_safe, n_all, "it is" if n_safe == 1
                                    else "they are"))
    lead = ("The USDA attaches %s to this item, reproduced below word for "
            "word. %s" % (plural_en(n_all, "handling note"), tail))
    extras = [
        ("These are the source's own sentences, not ours, and they are the "
         "part of the FoodKeeper record that a table of durations cannot "
         "carry."),
        ("They were set as values in the duration column until this build, "
         "which put a sentence of up to %d characters in capitals along the "
         "right-hand edge." % max(len(r[2]) for r in rows)),
        ("Where a note scopes a figure to one preparation or one kind, the "
         "figure above it means what the note says, not what the row heading "
         "alone suggests."),
    ]
    return ("<h2>What the USDA adds in words</h2><p>%s</p>%s"
            % (compose(lead, extras), body))


# ------------------------------------------------ ДВЕ ОГОВОРКИ, А НЕ ОДНА
#
# «They are quality guidance, not a safety test» стояло на 221 странице
# сразу — и под «3 days to 4 days» у остатков с мясом, где это предел
# безопасности и оговорка НЕДОпредупреждала, и под шестью месяцами в
# морозилке, где она верна буквально и никто её вслух не сказал. Одна рамка —
# одно последствие; ферма шлёпнулась об это уже трижды.
#
# Теперь предложений ДВА, они несовместимы по смыслу, и выбирает между ними
# fk.window_kind — по ячейке, а не по странице. На странице с обоими видами
# окон печатаются ОБА, каждое при своих строках.

SAFETY_SENTENCE = ("Past it, throw it out rather than taste it: a perishable "
                   "food can carry enough bacteria to make you ill while it "
                   "still looks and smells fine.")

QUALITY_SENTENCE = ("Past it, judge it by look and smell: this window rates "
                    "how good the food will be, not the day it becomes a "
                    "hazard.")

# ТРЕТЬЕ предложение, и оно появилось не для красоты. Раньше вердиктов было
# два, и там, где правило не могло назвать еду, страница всё равно выбирала
# один из них — по ДЛИНЕ ОКНА: короткое объявлялось опасным, длинное вкусовым.
# Это круговое рассуждение (вердикт о сроке, обоснованный самим сроком) и
# ровно то, за что сайту выставили счёт. Теперь у «не решено» есть своё слово.
UNSETTLED_SENTENCE = ("Past it, take the shorter of the two answers: we "
                      "would rather print that the record does not settle it "
                      "than pick one for you.")

# Указание для нерешённого случая. Опасная сторона названа ПЕРВОЙ и словами,
# по которым читатель узнаёт еду у себя в руках: он видит её, а мы нет.
UNSETTLED_NOW_WHAT = ("If the food is moist, low in acid and ready to eat "
                      "&mdash; a sauce, a drink, a filling &mdash; treat the "
                      "date as a limit and throw it out untasted; otherwise "
                      "look and smell, and out it goes if either is off.")

# --------------------------------------------------- ОБЪЯВЛЕННАЯ ОБЩАЯ ФРАЗА
#
# Указание по безопасности у всех скоропортящихся продуктов ОДНО И ТО ЖЕ, и
# это правильно: разными словами про одно последствие — ровно тот дефект, за
# который ферма уже платила. Но гейт близнецов считает пятёрки слов, и сто
# общих слов на каждой странице обрушили корпус с 270 страниц до 71.
#
# Поэтому общая фраза ОБЪЯВЛЯЕТСЯ: она печатается внутри `<span data-std>`,
# исключается из сравнения на близнецов — и охраняется своим гейтом в ОБЕ
# стороны, чтобы под этой пометкой нельзя было пронести произвольный текст:
# внутри пометки может стоять только фраза из банка, а фраза из банка не может
# стоять вне пометки. Плюс потолок доли: страница, набранная общей фразой
# больше чем на четверть, — это и есть та самая страница-шаблон.

FREEZER_FACT = ("Held at 0&nbsp;°F food stays safe for as long as it stays "
                "frozen, which is why a freezer figure counts as quality on "
                "this site whatever the food is.")

ASSUMPTIONS = ("Every figure assumes the food was sound when you stored it, "
               "that your refrigerator holds 40&nbsp;°F or below and your "
               "freezer 0&nbsp;°F or below, and that the package was handled "
               "normally.")

TWO_HOUR = ("The USDA's limit for perishable food standing at room "
            "temperature is 2 hours, or 1 hour when the kitchen is above "
            "90&nbsp;°F, and that clock runs whatever the storage figure "
            "says.")

NO_RESCUE = ("Freezing stops the clock but does not turn it back: food "
             "already past its window is not rescued by putting it in the "
             "freezer.")

# Признак порчи зависит от того, ЧТО портится. Одна фраза на всех печатала
# «банка вздулась, помята или проржавела» на 133 страницах, где банки нет
# вовсе: 58 из них — свежие овощи и фрукты, 40 — выпечка и мука, 21 — напитки.
# Число было честное, слова — чужие: ровно тот дефект «одна рамка на разные
# последствия», за который ферма уже платила («покажет не то, а не откажет»
# для 7% и для 700%). Ветвление идёт по РУБРИКЕ источника — это форма записи,
# а не её значение, — и таблица ПОЛНАЯ: запасного варианта нет, новая рубрика
# в снимке обязана уронить сборку, а не тихо получить чужие слова.
LOOK_FRESH = ("Mold, a slimy or sticky surface, soft or darkened spots, or a "
              "sour smell mean it goes out whatever the date says.")

LOOK_BAKED = ("Mold takes the whole package out rather than the slice it grew "
              "on, and so does a musty or old-oil smell in a flour or a mix.")

LOOK_CANNED = ("A jar or can that is bulging, leaking or rusted goes out "
               "unopened, and so does an opened one with mold at the rim or "
               "a sour, fizzing smell.")

LOOK_PANTRY = ("A rancid, paint-like smell in a nut, an oil or a seed, mold "
               "around the neck of a bottle, or a swollen can mean it goes "
               "out whatever the date says.")

LOOK_DRY = ("Insects or webbing in the package, a musty or rancid smell, or "
            "clumping that says damp got in mean it goes out whatever the "
            "date says.")

LOOK_DRINK = ("Fizzing that should not be there, cloudiness, floating strands "
              "or a sour smell mean it goes out whatever the date says.")

LOOK_BY_CAT = {
    "Baby Food": LOOK_FRESH,
    "Baked Goods": LOOK_BAKED,
    "Beverages": LOOK_DRINK,
    "Condiments, Sauces & Canned Goods": LOOK_CANNED,
    "Dairy Products & Eggs": LOOK_FRESH,
    "Deli & Prepared Foods": LOOK_FRESH,
    "Food Purchased Frozen": LOOK_FRESH,
    "Grains, Beans & Pasta": LOOK_DRY,
    "Meat": LOOK_FRESH,
    "Poultry": LOOK_FRESH,
    "Produce": LOOK_FRESH,
    "Seafood": LOOK_FRESH,
    "Shelf Stable Foods": LOOK_PANTRY,
    "Vegetarian Proteins": LOOK_FRESH,
}

LOOK_ALL = (LOOK_FRESH, LOOK_BAKED, LOOK_CANNED, LOOK_PANTRY, LOOK_DRY,
            LOOK_DRINK)


def look_test_for(it):
    """По чему судить, когда окно качества вышло, — словами ЭТОЙ рубрики.

    Ни одна из шести фраз не говорит «понюхай и реши»: они называют признаки,
    при которых еда уходит В МУСОР независимо от даты. Обратной стороны —
    «пахнет нормально, значит можно» — здесь нет и быть не должно, и под
    пределом безопасности не печатается ни одна из шести.
    """
    s = LOOK_BY_CAT.get(it["category"])
    assert s is not None, "нет признака порчи для рубрики %r" % it["category"]
    return s

SOURCE_SILENT = ("The FoodKeeper entry this page is built from prints storage "
                 "times and nothing else, so anything past them here is USDA "
                 "and FSIS guidance rather than a figure from the source.")

PAST_POINTER = ('The whole rule, including the cases the source does not '
                'cover, is set out under <a href="/past-the-date/">what to '
                'do when the date has passed</a>.')

WHOSE_FIGURES = ("Both figures are the USDA's own, so this is a choice of "
                 "where to put the food rather than a disagreement about how "
                 "long it keeps.")

WARM_LIMIT_WHY = ("That is the clock running while food stands in a warm "
                  "kitchen, not a shelf life.")

DISCARD_NOW = ("Throw the container out without tasting it, and count any "
               "hours it already spent out of the refrigerator as part of "
               "that window rather than on top of it.")

NOT_RECOMMENDED_WHY = ("It is not a warning: food held at 0&nbsp;°F stays "
                       "safe, so a not-recommended is a verdict on what "
                       "would come out of the freezer.")

RATIO_CROSSES = ("A multiplier whose sides are different preparations is "
                 "worth printing only with the source's own scope note "
                 "beside it.")

OTHER_KIND_HERE = ("The same page carries windows of more than one kind, "
                   "so which sentence applies depends on which row you "
                   "are reading, not on the food.")

# Банк объявлен здесь и нигде больше. Гейт сверяет с ним обе стороны.
STD_BANK = (SAFETY_SENTENCE, QUALITY_SENTENCE, UNSETTLED_SENTENCE,
            UNSETTLED_NOW_WHAT, FREEZER_FACT, ASSUMPTIONS,
            TWO_HOUR, NO_RESCUE, SOURCE_SILENT, PAST_POINTER,
            WHOSE_FIGURES, WARM_LIMIT_WHY, RATIO_CROSSES,
            DISCARD_NOW, NOT_RECOMMENDED_WHY, OTHER_KIND_HERE) + LOOK_ALL


def std(sentence):
    """Пометить объявленную общую фразу. Ничего, кроме банка, сюда не идёт:
    проверяется гейтом, а не дисциплиной."""
    assert sentence in STD_BANK, "фраза не объявлена в STD_BANK"
    return '<span data-std>%s</span>' % sentence


def plain_text(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


STD_PLAIN = tuple(plain_text(x) for x in STD_BANK)

# Короткая версия того же выбора — для поля бирки. Одна величина, один
# носитель: обе строки выводятся из ТОЙ ЖЕ fk.window_kind.
MEANS_CHIP = {
    fk.SAFETY: "Safety limit &middot; past it, throw it out",
    fk.QUALITY: "Quality window &middot; past it, judge it yourself",
    fk.UNSETTLED: "Not settled here &middot; take the shorter answer",
}

MEANS_WORD = {fk.SAFETY: "a safety limit", fk.QUALITY: "a quality window",
              fk.UNSETTLED: "not settled by this record"}

# Предложение о последствии — по последствию, и таблица ПОЛНАЯ: новый вердикт
# без своего предложения обязан уронить сборку, а не получить чужое.
MEANS_SAYS = {fk.SAFETY: SAFETY_SENTENCE, fk.QUALITY: QUALITY_SENTENCE,
              fk.UNSETTLED: UNSETTLED_SENTENCE}
assert set(MEANS_SAYS) == set(MEANS_CHIP) == set(MEANS_WORD)


def brief_who(it, st):
    """Имя продукта там, где абзац ограничен по словам.

    Имена источника доходят до 126 знаков («Commercial bread products,
    including pan breads, flat breads, rolls and buns»), и одно такое имя
    выбивало блок безопасности за потолок абзаца — то есть снимало страницу
    целиком. Длинное имя заменяется местоимением: блок с указанием, что
    делать, обязан стоять на КАЖДОЙ странице, а не только на короткоимённых.
    """
    name = kind_title(it, st) if multi(it) else title_of(it)
    return name if wc(name) <= 6 else "it"


def fit_para(own, why, sentence, cap=None):
    """Абзац, который ОБЯЗАН влезть в окно: сперва полностью, потом без
    пояснения. Указание по безопасности («выброси, не пробуя») выкидывается
    последним и не выкидывается никогда."""
    cap = ANSWER_MAX if cap is None else cap
    full = "%s %s %s" % (own, why, sentence)
    if wc(full) <= cap:
        return full
    return "%s %s" % (own, sentence)


def row_kind(it, st, key):
    """Что значит ЭТА строка бланка. Один вход на всю сборку."""
    return row_verdict(it, st, key)[0]


def row_verdict(it, st, key):
    """(последствие, признак, ОБЪЯСНЕНИЕ) для строки.

    СОСТОЯНИЕ передаётся внутрь: у продукта с несколькими видами еду называет
    вид, а не одно имя продукта, и без него «Fruit, cut» и «Fruit» — одно и то
    же слово. Объяснение приходит ОТТУДА ЖЕ, откуда вердикт: страница его не
    сочиняет, и второй копии правила у неё нет.
    """
    v = st["slots"].get(key)
    hi = v[1] if (v and v[0] != "no") else None
    return fk.food_verdict(it, key, hi, st, who=brief_who(it, st))


def kinds_present(it):
    """Какие последствия вообще есть на странице: {'safety', 'quality'}."""
    return {row_kind(it, st, key) for st, key, _lo, _hi, _c, _i
            in rated_all(it)}


def hot_kind(it):
    """Последствие СИГНАЛЬНОГО окна — того, по которому страница отвечает."""
    h = hot_slot(it)
    return row_kind(it, h[0], h[1]) if h else None


def where_kind(it, kind):
    """Места, чьи окна на этой странице означают `kind`: (словами, сколько).

    Число возвращается вместе со словами нарочно: «The figure in the freezer
    and in the pantry IS the other kind» — рассогласование, которое гейт
    согласования не ловит, потому что числа в предложении нет вовсе.
    """
    seen, out = set(), []
    for st, key, _lo, _hi, _c, _i in rated_all(it):
        if row_kind(it, st, key) != kind or key in seen:
            continue
        seen.add(key)
        out.append(SHELF_SHORT.get(key, LISTING_WHERE[key]))
    out = out[:3]
    return (listing(out), len(out)) if out else ("", 0)


MEANS_HEAD = "Is this window about safety or about taste?"
NOW_WHAT_HEAD = "It is past the date. Now what?"

# Блоки, ИСКЛЮЧЁННЫЕ из сравнения на близнецов, и причина у каждого своя.
#
# «Where these numbers come from» одинаков у всех по построению.
#
# Два новых — не одинаковы, но их РАЗЛИЧИЯ намеренно бедны: указание «выброси,
# не пробуя» обязано звучать одними и теми же словами у всех скоропортящихся
# продуктов. Одно последствие — одна рамка; писать его каждый раз по-новому
# значит воспроизвести ровно тот дефект, за который ферма уже платила дважды.
# Сто общих слов на страницу уронили корпус с 270 до 143, и торговаться тут
# не с чем: сайту про безопасность еды нужны обе вещи сразу.
#
# Исключение — не лазейка, потому что у него ДВА гейта:
#   · «оговорка соответствует своему окну» пересчитывает вид окна по данным и
#     требует, чтобы напечатанное последствие было именно тем;
#   · «доля общего текста под потолком» не даёт спрятать за исключением
#     сколько угодно текста: больше трети видимых слов — провал.
SHARED_HEADS = ("Where these numbers come from", MEANS_HEAD, NOW_WHAT_HEAD)

# Прежнее имя оставлено рабочим: на него смотрит render.own_prose.
CONSTANT_HEADS = SHARED_HEADS


def means_block(it, s):
    """Что значит окно: предел безопасности или срок годного вкуса.

    Блок, ради которого написан fk.window_kind.
    """
    h = hot_slot(it)
    if not h:
        return ""
    st, key, _lo, _hi, _clock, _i = h
    # ОБЪЯСНЕНИЕ ПРИХОДИТ ВМЕСТЕ С ВЕРДИКТОМ. Прежде страница склеивала его
    # здесь сама, одной рамкой на все ветки, и подставляла в неё признак: над
    # двенадцатью растительными продуктами стояло «is an animal food, or made
    # with one», а над морозильным окном — «решает еда, а не полка», хотя
    # решала ровно полка. Рамку выбирает теперь та же функция, что и вердикт.
    kind, reason, why = row_verdict(it, st, key)
    where = SHELF_SHORT.get(key, LISTING_WHERE[key])
    own = ("The answer at the top of this page reads %s %s."
           % (st_text(st, key), where))
    says = std(MEANS_SAYS[kind])
    # ОБОСНОВАНИЕ НЕ ВЫПАДАЕТ ПО СЧЁТУ СЛОВ там, где оно и есть исключение:
    # вкусовой вердикт на холодном окне в неделю и короче, и всякое «не
    # решено». fit_para выкидывает пояснение первым, и на пяти таких
    # страницах оно уже выпадало.
    lead = "%s %s %s" % (own, why, says)
    tail = []
    # Вид называется ИМЕНЕМ, а не «другой»: вердиктов три, и «the other kind»
    # на странице с тремя видами окон — утверждение о двоичности, которого
    # больше нет. Общая оговорка печатается ОДИН раз, а не по разу на вид.
    others = sorted(kinds_present(it) - {kind})
    named = False
    for other in others:
        words, n = where_kind(it, other)
        if not words:
            continue
        named = True
        tail.append("The %s %s here %s %s."
                    % ("figure" if n == 1 else "figures", words,
                       "is" if n == 1 else "are", MEANS_WORD[other]))
    if named:
        tail.append(std(OTHER_KIND_HERE))
    if "freeze" in families(it):
        tail.append(std(FREEZER_FACT))
    tail.append(std(ASSUMPTIONS))
    return ("<h2>%s</h2><p>%s</p><p>%s</p>"
            % (MEANS_HEAD, lead, " ".join(tail)))


def _hi_short(st, key):
    v = st["slots"].get(key)
    return bool(v and v[0] != "no" and v[1] is not None
                and v[1] < fk.SAFETY_LIMIT_DAYS)


# ------------------------------------------------------------- «а теперь что?»
#
# Запрос с самыми высокими ставками во всей нише — «срок вышел» и «простояло
# ночь на столе», — и сайт на него не отвечал НИЧЕМ: «Past it by 6 days», и
# дальше пустота. Ни «выбросить», ни «когда сомневаешься», ни правила двух
# часов, ни слова «разогреть». Блок ниже отвечает на странице каждого
# продукта и ведёт на /past-the-date/, где то же правило разобрано целиком.

def worst_cell(it):
    """Самое короткое окно вне морозилки СРЕДИ ВСЕХ видов, названное видом.

    У страницы-выбора сигнального окна нет, но вопрос «срок вышел — что
    делать» от этого не исчезает: он и есть самый дорогой запрос ниши.
    Отвечает на него самое короткое из окон под этим именем — то, которое
    кончится первым у кого угодно из читателей, — и вид при нём НАЗВАН.
    """
    rows = [r for r in rated_all(it) if not r[1].startswith("freeze")]
    return min(rows, key=lambda r: (r[2], r[3], r[5], r[1])) if rows else None


def now_what_block(it, s):
    """Срок вышел — что делать. Ветвление по ПОСЛЕДСТВИЮ, а не по продукту."""
    # Сигнального окна может не быть — страница-выбор, вид без окна, — а
    # вопрос «срок вышел, что делать» от этого не исчезает: он и есть самый
    # дорогой запрос ниши. Отвечает тогда самое короткое окно под этим
    # именем, и вид при нём НАЗВАН.
    h = hot_slot(it) or (worst_cell(it) if multi(it) else None)
    if not h:
        return ""
    st, key, _lo, _hi, _clock, _i = h
    # ВЕРДИКТ БЕЗ СВОЕГО ОБЪЯСНЕНИЯ НЕ ПЕЧАТАЕТСЯ НИГДЕ. У страницы-выбора
    # блока «что значит окно» нет вовсе — сигнального окна у неё нет, — и
    # указание «выброси, не пробуя» стояло на ней голым: последствие есть,
    # причина не названа. Причина берётся у того же правила и встаёт сюда.
    kind, _reason, clause = row_verdict(it, st, key)
    lone = hot_slot(it) is None
    who = kind_title(it, st) if multi(it) else title_of(it)
    val = st_text(st, key)
    where = SHELF_SHORT.get(key, LISTING_WHERE[key])
    brief = brief_who(it, st)
    if _hi_short(st, key):
        lead = fit_para(
            "Say the %s the USDA allows %s has run out, or the dish sat on "
            "the counter overnight." % (val, where),
            std(WARM_LIMIT_WHY), std(DISCARD_NOW))
    else:
        # Калькулятор стоит НАД ответом, а у страницы-выбора ответа нет:
        # обещать «the calculator above» там, где его нет, — это указание,
        # которое не сбудется, и оно хуже отсутствующего.
        dash = chr(8212)
        says = ("Say the shortest window under this name %s %s at %s %s %s "
                "has run out" % (dash, brief, val, where, dash)
                ) if hot_slot(it) is None else (
                    "Say the calculator above puts %s past its %s %s window"
                    % (brief, val, where))
        if kind == fk.SAFETY:
            lead = fit_para(
                "%s, or the container sat out on the counter overnight."
                % says, "", std(DISCARD_NOW))
        elif kind == fk.UNSETTLED:
            # Ни «выброси», ни «посмотри и реши»: и то и другое было бы
            # выбором, который правило не сделало. Страница говорит, ЧТО
            # именно не решено, и отдаёт читателю тот признак, которого не
            # хватило нам — еду он видит, а мы нет.
            lead = fit_para(
                "%s." % says,
                "Nothing here settles whether that date is a limit or a "
                "matter of taste.", std(UNSETTLED_NOW_WHAT))
        else:
            lead = fit_para(
                "%s." % says,
                "Past that the calendar stops deciding and the food itself "
                "does.", std(look_test_for(it)))
    tail = []
    # ВЕРДИКТ БЕЗ СВОЕГО ОБЪЯСНЕНИЯ НЕ ПЕЧАТАЕТСЯ НИГДЕ. У страницы-выбора
    # блока «что значит окно» нет вовсе — сигнального окна у неё нет, — и
    # указание «выброси, не пробуя» стояло на ней голым: последствие есть,
    # причина не названа. Причина берётся у того же правила, а стои́т во
    # втором абзаце: в первый, где уже сидят указание и само окно, она не
    # влезает по счёту слов, а выкидывать её ради счёта — это ровно тот
    # дефект, за который правило и переписано.
    if lone:
        tail.append(clause)
    if kind in (fk.SAFETY, fk.UNSETTLED) or fk.is_perishable(it):
        tail.append(std(TWO_HOUR))
    if "freeze" in families(it) and kind in (fk.SAFETY, fk.UNSETTLED):
        tail.append(std(NO_RESCUE))
    # Признак порчи под предел безопасности НЕ идёт: «посмотри и реши» рядом с
    # «выброси не пробуя» — это две рамки на одно последствие, и читатель
    # выберет ту, которая разрешает.
    # ПРЕДЕЛ В ТЕПЛЕ НЕ ТЕРЯЕТСЯ. Пока двухчасовая ячейка стояла ответом,
    # правило комнатной температуры печаталось само собой; теперь ответом
    # стоит холодильное окно (см. пятое правило hot_slot), и предел обязан
    # быть назван здесь — иначе страница пирога перестала бы говорить о
    # самом опасном, что с пирогом делают.
    caps = [(x, k) for x in states_of(it)
            for k, _lo3, _hi3 in fk.safety_limit_cells(x)]
    if caps and not _hi_short(st, key):
        x, k = caps[0]
        who_cap = (" for %s" % plural_en(len(caps), "kind")) if len(caps) > 1 \
            else ((" for %s" % kind_title(it, x)) if multi(it) else "")
        tail.append("The USDA also caps this at %s standing at room "
                    "temperature%s. %s"
                    % (st_text(x, k), who_cap, std(WARM_LIMIT_WHY)))
    tail.append(std(SOURCE_SILENT))
    tail.append(std(PAST_POINTER))
    return ("<h2>%s</h2><p>%s</p><p>%s</p>"
            % (NOW_WHAT_HEAD, lead, " ".join(tail)))


def method_block(vintage):
    """Сюда снесены ВСЕ методологические оговорки. Каждая из них верна для всех
    страниц сразу — значит, повторённая на каждой, она делает страницы
    близнецами и при этом ничего не добавляет ни одной из них."""
    return ("<h2>Where these numbers come from</h2><p>Every range on this page "
            "is published by the USDA FoodKeeper and reproduced unchanged. The "
            "multipliers, the rankings, the percentages and the dates are "
            "ours, computed from those ranges. Where the source gives a span "
            "such as 3 to 5 weeks, comparisons use the upper figure, and "
            "the full span is always printed.</p>"
            "<p>Rankings cover only the items the USDA gives a usable figure "
            "for, and identical ranges share a place rather than being ordered "
            "arbitrarily. Neighbors are chosen by nearest storage time within "
            "the same category, never alphabetically: two foods filed next to "
            "each other by name usually have nothing to do with each other. "
            "The freezer is excluded from ranking because it flattens almost "
            "everything.</p>"
            "<p>Where the USDA lists several kinds under one name, they share "
            "one page here and every kind keeps its own windows: the source "
            "prints them as separate rows, and a page that merged them would "
            "be inventing a figure the source never published. Comparisons "
            "and the place in the category are computed for the kind the "
            "plain name means &mdash; the shell egg for eggs, the can for "
            "tuna &mdash; which is settled name by name rather than by the "
            "order the source lists its rows in, and the page names it. "
            "Where the plain name means no single kind, the page prints no "
            "single figure at all and lists the kinds instead.</p>"
            # ИМЯ ЮРЛИЦА НЕ СТОИТ НА 300 СТРАНИЦАХ. Правило владельца — по
            # минимуму упоминать компанию на видных местах: имя странное для
            # справочника о еде и вызывает лишний вопрос. Ответственность
            # берёт на себя САЙТ, названный своим именем; юрлицо остаётся в
            # /terms/, /privacy/ и в структурных данных как legalName, где
            # без него документ не работает.
            '<p class="quiet">Source: %s. This site computes every '
            'comparison on this page and takes '
            'responsibility for it. Found a figure that does not match the '
            'source? Tell us on the <a href="/contact/">contact page</a>, '
            'with the page and the row &mdash; the parsing is mechanical, so '
            'a mismatch is our bug and we want it. How the whole site is '
            'built, which figures are ours and where the source can be '
            'checked is on the <a href="/methodology/">method page</a>.</p>'
            % esc(vintage))
