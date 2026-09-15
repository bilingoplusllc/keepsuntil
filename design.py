# -*- coding: utf-8 -*-
"""Облик KeepsUntil — «БИРКА НА БАНКЕ». Одна сырая строка CSS, ноль сборщиков.

ОТКУДА ЭТО. Первая попытка (02.09.2026) была системой токенов и тёмной темой,
и Дмытро посмотрел и сказал: «как предыдущий сайт». Он был прав — токены,
шкала кеглей и тёмная тема это гигиена, а не облик. По правилу D-014 заказаны
четыре ЦЕЛЬНЫХ направления, каждое со своей гипотезой о том, чем является
страница; выбрано глазами это.

ГИПОТЕЗА. Страница — не статья и не справочник, а ЭТИКЕТКА: физический предмет
фиксированного размера, который можно распечатать и наклеить на контейнер.
Читается с вытянутой руки, в плохом кухонном свете, человеком, у которого
заняты руки: телефон в одной, банка в другой.

ГЛАВНЫЙ ПРИЁМ — СГИБ ЭТО ПЕРФОРАЦИЯ. Всё выше пунктира — бирка с полным
ответом, помещающаяся на один экран телефона без прокрутки. Всё ниже —
отрывной корешок: метод, соседи, оговорки. Требование «ответ на одном экране»
превращено в видимую физическую границу, которая сама объясняет, почему ниже
лежит другое по важности.

ПРАВИЛО, КОТОРОЕ ИЗ ЭТОГО СЛЕДУЕТ И КОТОРОЕ ДЕРЖИТ СТРАНИЦУ:
**над перфорацией нет ни одного предложения прозы.** Только подписи полей,
величины и одно поле ввода. Проза начинается ровно после отрыва. Это
проверяется гейтом, а не памятью.

ЧТО УЖЕ ЗАНЯТО НА ФЕРМЕ, и чего здесь поэтому нет:
  · MileageCurve — почти белый фон и сине-зелёный акцент;
  · FedPay — пергамент, тёмно-синяя полоса, ЗАСЕЧКОВЫЙ текст;
  · BatteryCross — сталь, моноширинный, острые углы;
  · KeepsUntil-1 — тёплая бумага, сливовый, Georgia в заголовках, одна
    колонка по мере текста, разделы h2 стопкой, данные в таблицах с рамкой.
Здесь: средне-тёмная столешница, белый прямоугольник бирки на ней, узкий
гротеск капителью, ни одной таблицы, поля бланка вместо разделов.

ПРАВИЛА СИСТЕМЫ, которые нельзя нарушать при правках:
  · ОДИН сигнальный цвет `#d9f000`, и он ВСЕГДА ЗАЛИВКА, никогда не текст по
    светлому. Ровно одно флуоресцентное поле на экран, и означает оно одно:
    **ОТВЕТ, КОТОРЫЙ ДАЁТ ЭТА СТРАНИЦА.** У товара это окно, которое кончится
    первым; у рейтинга — ведущая строка, ради которой рейтинг построен; на
    главной — само поле поиска. Разбор облика нашёл у сигнала два
    противоречащих занятия («кончится первым» на товаре против «набирай
    здесь» на главной) и полное отсутствие на трети поверхности: одна фраза
    выше — это то, что сводит оба занятия в одно и заводит сигнал на витрины;
  · сигнал ОДИНАКОВ в обеих темах, потому что флуоресцентная краска не
    меняется от освещения. Чёрное по нему даёт около 14:1 — самое читаемое
    место на экране, и это физически достоверно;
  · тёмная тема — ТОТ ЖЕ ПРЕДМЕТ, ОТПЕЧАТАННЫЙ НАОБОРОТ: краска светлой темы
    (#15170f) становится бумагой тёмной. Это не инверсия наугад;
  · иерархию несут ЧЕТЫРЕ ВЕСА ЛИНЕЙКИ, а не цвет: волосяная (--hair)
    разделяет поля, жирная 3px (--heavy / --on-signal) отбивает шапку и
    сигнальное поле, кромка листа (--edge) отделяет предмет от столешницы,
    и САМАЯ ГРОМКАЯ — перфорация (--tear). Перфорация делила токен с
    волосяной линией, то есть главный приём облика был нарисован самым тихим
    значением системы; теперь у него свой токен и 10:1;
  · бирка шириной 520px и НЕ РАСТЁТ. У физического предмета есть размер; на
    широком экране лист становится двухколоночным, а не растягивается, и
    колонка бирки КОНЧАЕТСЯ ВМЕСТЕ СО СВОИМ СОДЕРЖИМЫМ: `align-items:start`.
    Прежде сетка растягивала бирку до высоты корешка, и 46% ширины экрана на
    1280px были пустой белой полосой в 1400px высотой;
  · каждый цвет объявлен на голом :root и переопределён в тёмной теме. Цвет,
    объявленный единственный раз внутри media-блока, — дефект: у нас так
    карточка осталась светлой внутри тёмной полосы при контрасте 1,07:1;
  · текст не тусклее 4,5:1, графика не тусклее 3:1, В ОБЕИХ ТЕМАХ, и это
    СЧИТАЕТСЯ гейтом с наложением полупрозрачных значений на свой фон.

ДВЕ ВЕЛИЧИНЫ, ИЗ КОТОРЫХ ВЫВЕДЕНО ВСЁ ОСТАЛЬНОЕ:

  · `--u:4px` — ЕДИНСТВЕННАЯ единица отступа. Каждый padding, margin, gap и
    top в этом файле есть `calc(var(--u)*n)` при целом n или ноль. Разбор
    облика насчитал здесь 13 разных значений отступа и шесть разных
    `margin-top`, не выведенных ни из чего: «шесть ритмов в одной колонке,
    шатающихся на 1–3px от полосы к полосе». Гейт «отступы выведены из базы»
    не пропускает больше ни одного числа руками;
  · ШКАЛА КЕГЛЕЙ — четыре текстовых ступени и две крупные:
    12 / 15 / 18 / 22 и два clamp'а для крупной строки. Было девять размеров
    в полосе 9,5–15px, пять из них с половиной пикселя, и заголовок раздела
    (11px) был МЕНЬШЕ основного текста (13,5px). Основной текст 15px, ниже
    15px живёт ровно один размер — капитель подписей, и она не основной
    текст. Гейт «кегли из шкалы» не пропускает число мимо токена.
"""


def strip_comments(css):
    """Убрать комментарии из CSS ПЕРЕД вставкой в страницу.

    Комментарии здесь по-русски, потому что объясняют решения; сайт —
    английский. На соседнем сайте первая сборка отдала русские слова на все
    167 страниц, и поймал это гейт языка, а не глаз.
    """
    out, i = [], 0
    while True:
        j = css.find("/*", i)
        if j < 0:
            out.append(css[i:])
            break
        out.append(css[i:j])
        k = css.find("*/", j + 2)
        if k < 0:
            break
        i = k + 2
    return "".join(out)


CSS = r"""
:root{
  /* столешница, бумага бирки, две краски */
  --surface:#8e9488;
  --stock:#ffffff;
  --ink:#15170f;
  --ink2:#5d6155;
  /* ЧЕТЫРЕ ВЕСА ЛИНЕЙКИ, и каждый живёт на СВОЁМ фоне. Волосяная — на
     бумаге, кромка листа — на столешнице, перфорация — на бумаге и громче
     всех. Одна альфа не может дать 3:1 на двух фонах: при .24 линия давала
     1,69:1 на бумаге и 1,50:1 на столешнице, то есть вся структура полей
     была нарисована ниже графического минимума в обеих темах. */
  --hair:rgba(21,23,15,.48);
  --edge:rgba(21,23,15,.70);
  --tear:rgba(21,23,15,.82);
  --heavy:#15170f;

  /* ОДИН сигнал. Всегда заливка. Одинаков в обеих темах */
  --signal:#d9f000;
  --on-signal:#15170f;
  --sig-cap:rgba(21,23,15,.62);
  --sig-hair:rgba(21,23,15,.55);

  --cond:"Arial Narrow","Helvetica Neue Condensed","Liberation Sans Narrow","Nimbus Sans Narrow",Arial,system-ui,sans-serif;
  --wide:Arial,"Helvetica Neue",system-ui,sans-serif;

  /* ЕДИНСТВЕННАЯ единица отступа и всё, что из неё выведено */
  --u:4px;
  --pad:calc(var(--u)*3);
  --rad:calc(var(--u)*2);
  --tag:520px;

  /* ШКАЛА КЕГЛЕЙ. Четыре текстовых ступени, шаг не меньше 20%, и две
     крупные строки. Ниже 15px живёт только капитель подписей. */
  --f1:12px;
  --f2:15px;
  --f3:18px;
  --f4:22px;
  --d1:clamp(30px,9.4vw,46px);
  --d2:clamp(21px,6vw,29px);

  /* Родные контролы следуют теме страницы. Прежде :root не объявлял схему
     вовсе, и в тёмной теме календарный значок в корешке рисовался светлым
     контролом по почти чёрной бумаге — как и полоса прокрутки. */
  color-scheme:light dark;
}

@media (prefers-color-scheme:dark){
  :root{
    --surface:#060704;
    --stock:#15170f;
    --ink:#f1f2ea;
    --ink2:#969c88;
    --hair:rgba(241,242,234,.38);
    --edge:rgba(241,242,234,.44);
    --tear:rgba(241,242,234,.78);
    --heavy:#f1f2ea;
  }
}

*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0;padding:calc(var(--u)*2);min-height:100vh;
  background:var(--surface);color:var(--ink);
  font-family:var(--cond);font-stretch:condensed;font-size:var(--f2);
  font-variant-numeric:tabular-nums;line-height:1.25;
}
h1,h2,h3,p,ul,ol,form,figure{margin:0;padding:0}
ul{list-style:none}
a{color:inherit}
/* Кольцо фокуса рисуется КРАСКОЙ, а не сигналом: сигнал не меняется от темы
   и на белой бумаге давал 1,28:1 — то есть на светлой теме клавиатурный
   фокус был невидим на каждой ссылке и каждом поле сайта. Краска флипается
   вместе с темой (18,1:1 и 16,0:1), а сигнал остаётся ореолом. Внутри
   флуоресцентного поля кольцо снова становится тёмным: светлая краска на
   лайме — это 1,13:1. */
:focus-visible{outline:3px solid var(--heavy);outline-offset:2px;
  box-shadow:0 0 0 6px var(--signal)}
.hot :focus-visible{outline-color:var(--on-signal);box-shadow:none}
@media (min-width:600px){body{padding:calc(var(--u)*6)}}

.skip{position:static;display:block;width:1px;height:1px;overflow:hidden;
  white-space:nowrap;background:var(--stock);color:var(--ink)}
.skip:focus-visible{width:auto;height:auto;padding:calc(var(--u)*2) var(--pad)}

/* ------------------------------------------------------------- лист */
.sheet{max-width:var(--tag);margin:0 auto;background:var(--stock);
  border:1px solid var(--edge);border-radius:var(--rad);overflow:hidden}
/* ДВЕ КОЛОНКИ с 1024px, а не с 900. Между 900 и 1024 корешок сжимался до
   332px, и в него не влезала ни одна настоящая рекламная единица.

   Три вещи, которые здесь чинятся разом:
   · `align-items:start` — колонка бирки кончается вместе с содержимым.
     Прежде сетка тянула её до высоты корешка: 520px белого на 1400px вниз;
   · бирка и корешок становятся ДВУМЯ предметами на столешнице, каждый со
     своей кромкой. Пустоты под биркой больше нет — под ней стол;
   · перфорация НЕ ИСЧЕЗАЕТ. Прежде выше 900px весь приём сводился к
     `border-right:2px dashed` при 1,69:1, то есть на экране, с которого
     приходит десктопный посетитель, отрывного корешка просто не было.
     Теперь это настоящая насечка: столбик штрихов --tear (10:1) высотой в
     бирку, нарисованный фоном, а не подложенным вручную элементом. */
@media (min-width:1024px){
  .sheet{max-width:1120px;display:grid;align-items:start;
    grid-template-columns:var(--tag) minmax(320px,1fr);
    grid-template-rows:auto 1fr;
    background:none;border:0;border-radius:0;overflow:visible}
  .label{grid-column:1;grid-row:1;
    background-color:var(--stock);border:1px solid var(--edge);
    border-right:0;border-radius:var(--rad) 0 0 var(--rad);
    background-image:repeating-linear-gradient(to bottom,
      var(--tear) 0 calc(var(--u)*2),transparent calc(var(--u)*2) calc(var(--u)*4));
    background-repeat:no-repeat;background-position:100% 0;
    background-size:3px 100%}
  .sheet > .ad{grid-column:1;grid-row:2}
  .stub{grid-column:2;grid-row:1/span 2;
    background-color:var(--stock);border:1px solid var(--edge);
    border-radius:0 var(--rad) var(--rad) 0}
}

/* --------------------------------------------------------- кромка */
.strip{display:flex;flex-wrap:wrap;justify-content:space-between;
  align-items:center;
  gap:calc(var(--u)*2);padding:calc(var(--u)*2) var(--pad);
  border-bottom:3px solid var(--heavy);
  font-size:var(--f1);letter-spacing:.16em;text-transform:uppercase;
  font-weight:700}
.mark{display:flex;align-items:center;gap:calc(var(--u)*2)}
.mark a{text-decoration:none}
.strip svg{display:block}
.src{color:var(--ink2);letter-spacing:.06em;text-align:right}

/* --------------------------------------------------- поля бланка */
.field{padding:calc(var(--u)*2) var(--pad);border-bottom:1px solid var(--hair)}
.cap{font-size:var(--f1);letter-spacing:.16em;text-transform:uppercase;
  font-weight:700;color:var(--ink2);margin-bottom:var(--u)}
/* КРУПНАЯ СТРОКА и её же уменьшенная ступень. Ступень выбирается НЕ по числу
   знаков, а расчётом ширины строки в Arial (узкого шрифта на телефоне нет) —
   см. fit_display ниже. Прежний сторож `len(name) > 48` пропускал вторую по
   высоте страницу сайта и ужимал те, которым это было не нужно. */
.item{font-size:var(--d1);font-weight:700;text-transform:uppercase;
  letter-spacing:.005em;line-height:1.02}
.item.long{font-size:var(--d2)}
/* Слова запроса вокруг имени: «HOW LONG DOES / MILK / LAST IN THE FRIDGE?».
   Крупной строкой остаётся имя — вопрос, набранный тем же кеглем, добавил бы
   к первому экрану ещё три строки заглавных. */
.ask{display:block;font-size:var(--f1);letter-spacing:.16em;font-weight:700;
  color:var(--ink2);line-height:1.25}
.dur{font-size:var(--d1);font-weight:700;text-transform:uppercase;
  letter-spacing:.005em;line-height:1.02}
.dur.long{font-size:var(--d2)}
.sub{margin-top:var(--u);font-size:var(--f1);letter-spacing:.14em;
  text-transform:uppercase;font-weight:700;color:var(--ink2)}

/* ------------- единственное флуоресцентное поле: ОТВЕТ ЭТОЙ СТРАНИЦЫ */
/* Линия под сигнальным полем — краской ПО СИГНАЛУ, а не темой: `--heavy`
   в тёмной теме становится светлым и давал 1,13:1 по лайму, то есть самая
   жирная линия системы исчезала ровно там, где она закрывает ответ. */
.hot{background:var(--signal);color:var(--on-signal);
  padding:calc(var(--u)*3) var(--pad);border-bottom:3px solid var(--on-signal)}
.hot .cap,.hot .sub{color:var(--sig-cap)}
/* Что окно ЗНАЧИТ — на первом экране, строкой бланка, а не прозой. Одна
   оговорка на 221 странице служила двум противоположным последствиям, и
   правильное слово стояло за перфорацией, куда с телефона не доходят. */
.means{margin-top:calc(var(--u)*2);padding-top:calc(var(--u)*2);
  border-top:1px solid var(--sig-hair);
  font-size:var(--f1);letter-spacing:.14em;text-transform:uppercase;
  font-weight:700;color:var(--on-signal)}
.dateline{display:flex;flex-wrap:wrap;align-items:center;
  gap:var(--u) calc(var(--u)*2);
  margin-top:calc(var(--u)*2);padding-top:calc(var(--u)*2);
  border-top:1px solid var(--sig-hair)}
.dateline label{font-size:var(--f1);letter-spacing:.16em;
  text-transform:uppercase;font-weight:700;color:var(--sig-cap)}
.dateline input{flex:1 1 130px;min-width:0;background:transparent;border:0;
  border-bottom:3px solid var(--on-signal);color:var(--on-signal);
  color-scheme:light;font-family:var(--cond);font-stretch:condensed;
  font-weight:700;font-size:var(--f4);line-height:1.2;
  padding:0 0 var(--u);border-radius:0}
/* Кольцо фокуса НЕ гасится: `outline:none` оставлял полю единственным
   признаком фокуса утолщение подчёркивания на два пикселя. Утолщение
   остаётся, кольцо возвращается. */
.dateline input:focus{border-bottom-width:5px}
.out{margin-top:calc(var(--u)*2);font-size:var(--f3);font-weight:700;
  text-transform:uppercase;letter-spacing:.01em}
.out small{display:block;font-size:var(--f1);letter-spacing:.14em;
  font-weight:700;color:var(--sig-cap);margin-bottom:var(--u)}

/* ----------------------------------------- во сколько раз дешевле */
/* Кратность стоит НИЖЕ перфорации. Она не ответ, а сравнение: на бирке она
   съедала 72–150px первого экрана телефона на каждой странице товара. */
.cost{display:flex;align-items:baseline;gap:calc(var(--u)*3);
  padding:var(--pad);border-bottom:1px solid var(--hair)}
.x{font-size:var(--d2);font-weight:700;line-height:1.02}
.t{font-size:var(--f1);letter-spacing:.13em;text-transform:uppercase;
  font-weight:700}
/* Без nowrap: строка расчёта уезжала за обрезанный край листа на пяти
   страницах при 320px, и ни один гейт этого не видел — переполнения
   документа не возникало. */
.calc{display:block;margin-top:var(--u);font-size:var(--f1);
  letter-spacing:.1em;color:var(--ink2)}

/* ------------------------------------------------------ перфорация */
/* САМЫЙ ГРОМКИЙ приём облика набирался САМЫМ ТИХИМ в системе: 9,5px по
   --ink2 на пунктире --hair. Теперь это ступень капители по краске и линии
   --tear в 10:1 — то, чем сайт назван, видно с вытянутой руки. */
.perf{display:flex;align-items:center;justify-content:center;
  gap:calc(var(--u)*2);padding:calc(var(--u)*3) var(--pad);
  border-top:2px dashed var(--tear);border-bottom:2px dashed var(--tear);
  font-size:var(--f1);letter-spacing:.24em;text-transform:uppercase;
  font-weight:700;color:var(--ink)}
@media (min-width:1024px){.perf{display:none}}

/* --------------------------------------------------------- корешок */
.stub{padding:0 0 calc(var(--u)*2)}
.stub section{padding:var(--pad);border-bottom:1px solid var(--hair)}
.stub section:last-of-type{border-bottom:0}
/* Заголовок раздела БОЛЬШЕ основного текста. Прежде 11px против 13,5px:
   раздел читался как подпись под тем, что он возглавляет. */
.stub h2{font-size:var(--f3);letter-spacing:.06em;text-transform:uppercase;
  font-weight:700;margin-bottom:calc(var(--u)*2)}
.stub p{font-family:var(--wide);font-stretch:normal;font-size:var(--f2);
  line-height:1.6;max-width:64ch;overflow-wrap:anywhere}
.stub p + p{margin-top:calc(var(--u)*2)}
.quiet{color:var(--ink2)}
/* Слова источника. НЕ величина: 34 подсказки длиной до 321 знака стояли в
   колонке значений и набирались капсом по правому краю. Здесь они проза —
   по левому краю, обычным регистром, с отбивкой от соседней. */
.tip{border-left:2px solid var(--hair);padding-left:calc(var(--u)*2)}
.tip b{font-family:var(--cond);font-stretch:condensed;letter-spacing:.06em;
  text-transform:uppercase;font-size:var(--f1);color:var(--ink2)}

/* ---------------------------------------- второй отсчёт в корешке */
.second{display:flex;flex-wrap:wrap;align-items:center;
  gap:var(--u) calc(var(--u)*2);
  margin-top:calc(var(--u)*2);padding-top:calc(var(--u)*2);
  border-top:1px solid var(--hair)}
.second label{font-size:var(--f1);letter-spacing:.16em;
  text-transform:uppercase;font-weight:700;color:var(--ink2)}
.second input{flex:1 1 130px;min-width:0;background:transparent;border:0;
  border-bottom:2px solid var(--ink);color:var(--ink);
  font-family:var(--cond);font-stretch:condensed;font-weight:700;
  font-size:var(--f4);padding:0 0 var(--u);border-radius:0}
.second input:focus{border-bottom-width:4px}
.rv small{display:block;font-size:var(--f1);letter-spacing:.14em;
  font-weight:700;color:var(--ink2);margin-bottom:var(--u)}

/* ------------------------------ строки бланка вместо таблиц */
/* Заголовок группы: у продукта под одним именем источник держит несколько
   состояний с РАЗНЫМИ сроками, и каждое обязано быть названо. Без имени
   страница врёт: три окна подряд без подписи читаются как одно. */
.kind{margin-top:calc(var(--u)*3);font-size:var(--f2);letter-spacing:.06em;
  text-transform:uppercase;font-weight:700;padding-bottom:var(--u);
  border-bottom:1px solid var(--heavy)}
.rows{margin-top:var(--u)}
/* `align-items:start`, а не baseline: справа стоит величина, которая
   переносится, и по первой базовой линии выравнивались только ПЕРВЫЕ строки
   колонок — правая свисала ниже, и пунктир переставал читаться строкой. */
.rows li{display:flex;align-items:start;justify-content:space-between;
  gap:calc(var(--u)*3);padding:calc(var(--u)*2) 0;
  border-bottom:1px dotted var(--hair)}
.rows li:last-child{border-bottom:0}
.rk{font-size:var(--f1);letter-spacing:.14em;text-transform:uppercase;
  font-weight:700;color:var(--ink2)}
.rv{font-size:var(--f2);font-weight:700;text-transform:uppercase;
  letter-spacing:.02em;text-align:right}

/* ------------------------------------------------- соседи и поиск */
.near li{border-bottom:1px dotted var(--hair)}
.near li:last-child{border-bottom:0}
.near a{display:flex;align-items:start;justify-content:space-between;
  gap:calc(var(--u)*3);padding:calc(var(--u)*2) 0;text-decoration:none}
.near a:hover .n,.near a:focus .n{text-decoration:underline}
.n{font-size:var(--f2);font-weight:700;text-transform:uppercase;
  letter-spacing:.02em}
/* ВЕЛИЧИНА — это величина, а не предложение. «60 times longer frozen than
   the sealed fridge (6 days to 12 months)» в колонке значений — 44 знака,
   которые ломали строку бланка пополам. Число стоит величиной, оговорка
   уезжает строкой ниже. */
.v{font-size:var(--f1);letter-spacing:.12em;text-transform:uppercase;
  font-weight:700;color:var(--ink2);text-align:right;flex:0 1 auto;
  max-width:52%}
.v small{display:block;font-size:var(--f1);letter-spacing:.06em;
  font-weight:400;text-transform:none;margin-top:var(--u)}
/* ВЕДУЩАЯ СТРОКА РЕЙТИНГА — это ответ, который даёт витрина, и она помечена
   тем же сигналом, что и связывающее окно на бирке. Прежде на шестнадцати
   витринах не было ни одного лаймового пятна: страницы выглядели другим,
   более простым продуктом. */
.near[data-lead] li:first-child a{background:var(--signal);
  color:var(--on-signal);padding-left:var(--u);padding-right:var(--u)}
.near[data-lead] li:first-child .v{color:var(--sig-cap)}

.hunt input{width:100%;background:transparent;border:0;
  border-bottom:3px solid var(--on-signal);color:var(--on-signal);
  color-scheme:light;font-family:var(--cond);font-stretch:condensed;
  font-weight:700;font-size:var(--d2);text-transform:uppercase;
  padding:0 0 var(--u);border-radius:0;margin-top:var(--u)}
.hunt input:focus{border-bottom-width:5px}
.hunt input::placeholder{color:var(--sig-cap)}
/* Список находок и «ничего не нашлось» живут на ДВУХ фонах: на лайме
   главной и на бумаге корешка любой другой страницы. Краска, годная на
   лайме, на бумаге тёмной темы даёт 1,1:1 — поэтому по умолчанию цвета
   бумажные, а лаймовые надеваются только внутри .hunt. */
.res{margin-top:calc(var(--u)*2);padding-top:calc(var(--u)*2);
  border-top:1px solid var(--hair)}
.res li{border-bottom:1px solid var(--hair)}
.res li:last-child{border-bottom:0}
.res a{display:flex;align-items:start;justify-content:space-between;
  gap:calc(var(--u)*2);padding:calc(var(--u)*2) 0;text-decoration:none}
.res a:hover .n{text-decoration:underline}
.res .v{color:var(--ink2)}
.none{margin-top:calc(var(--u)*2);font-size:var(--f1);letter-spacing:.14em;
  text-transform:uppercase;font-weight:700;color:var(--ink2)}
.hunt .res,.hunt .res li{border-color:var(--sig-hair)}
.hunt .res .v,.hunt .none{color:var(--sig-cap)}

/* ------------------------------- поиск и навигация на КАЖДОЙ странице */
/* Поле поиска вне главной НЕ лаймовое: сигнал означает ответ ЭТОЙ страницы,
   а на странице товара ответ — окно, а не лукап. Второе лаймовое пятно
   стёрло бы первое на 277 страницах. */
.stub .find{padding:var(--pad);border-bottom:1px solid var(--hair)}
.find input{width:100%;background:transparent;border:0;
  border-bottom:3px solid var(--heavy);color:var(--ink);
  font-family:var(--cond);font-stretch:condensed;font-weight:700;
  font-size:var(--d2);text-transform:uppercase;
  padding:0 0 var(--u);border-radius:0;margin-top:var(--u)}
.find input:focus{border-bottom-width:5px}
.find input::placeholder{color:var(--ink2)}
.findp{margin-top:calc(var(--u)*2);font-family:var(--cond);
  font-stretch:condensed;font-size:var(--f1);letter-spacing:.14em;
  text-transform:uppercase;font-weight:700;color:var(--ink2)}
.ways{margin-top:calc(var(--u)*2);padding-top:calc(var(--u)*2);
  border-top:1px solid var(--hair)}
.way{margin-top:calc(var(--u)*2);font-size:var(--f2);letter-spacing:.02em;
  text-transform:uppercase;font-weight:700}
.way:first-child{margin-top:0}
.wcap{display:block;color:var(--ink2);font-size:var(--f1);
  letter-spacing:.16em;margin-bottom:var(--u)}

.foot{padding:var(--pad);font-size:var(--f1);letter-spacing:.16em;
  text-transform:uppercase;font-weight:700;color:var(--ink2)}
"""


# Стиль рекламных мест держится ОТДЕЛЬНО и вставляется только при ADS=True.
#
# ТРИ ПРАВИЛА, КАЖДОЕ КУПЛЕНО ОШИБКОЙ:
#
# 1. Место существует, только когда в нём ЧТО-ТО ЕСТЬ. `display:none` не
#    выводит узел из :last-child, и на соседнем сайте пятьсот сорок невидимых
#    мест сломали пять правил отступов на ста пятидесяти семи страницах.
#    Поэтому ни одно место здесь не прячется по ширине: на узком экране
#    МЕНЯЕТСЯ ФОРМАТ, а прежний не сплющивается и не исчезает.
# 2. Размер задан ТОЧНО, и он обязан ВЛЕЗАТЬ В СВОЙ КОНТЕЙНЕР на каждой
#    ширине. Прежний `.ad-flow{width:728px}` жил в колонке корешка шириной
#    439–598px и обрезался на 18–42% при `overflow:hidden` — ни один гейт
#    этого не видел, потому что переполнения документа не возникало.
# 3. Ответ ВЫШЕ первой рекламы на любом типе страницы. На бирке рекламы нет
#    до последнего поля: `.ad-rail` стоит ПОСЛЕ всех полей бланка, то есть
#    после ответа и поля даты.
#
# ТРИ МЕСТА:
#   ad-rail  300x600 в боковой колонке на десктопе (та самая пустая колонка
#            на 1400px, которую нашёл разбор облика), 320x50 на телефоне;
#   ad-flow  336x280 в потоке корешка, ниже перфорации и ниже четырёх
#            разделов текста;
#   ad-lead  970x250 / 728x90 полосой во всю ширину под листом — единственное
#            место, где колонка ДЕЙСТВИТЕЛЬНО широкая.
AD_CSS = r"""
/* Рамка НЕ на месте, а на своей врезке: `width:728px` с рамкой при
   border-box даёт креатив 726px, то есть объявленную единицу, отрисованную
   на два пикселя меньше. Место — ровно объявленный прямоугольник. */
.ad{overflow:hidden;display:flex;align-items:stretch;margin:0 auto}
.sheet > .ad{margin:calc(var(--u)*3) auto}
.stub .ad{margin:0 auto calc(var(--u)*3)}
.adband{max-width:1120px;margin:0 auto;padding-top:calc(var(--u)*3)}
.house{display:flex;flex-direction:column;justify-content:center;
  gap:var(--u);width:100%;padding:calc(var(--u)*2) calc(var(--u)*3);
  text-decoration:none;color:var(--ink);
  background:var(--stock);border:1px solid var(--hair)}
.house:hover .hn{text-decoration:underline}
.hcap{font-size:var(--f1);letter-spacing:.2em;text-transform:uppercase;
  font-weight:700;color:var(--ink2)}
.hn{font-size:var(--f3);font-weight:700;text-transform:uppercase;
  letter-spacing:.01em}
.hsub{font-family:var(--wide);font-stretch:normal;font-size:var(--f2);
  line-height:1.35;color:var(--ink2)}
/* Рельса на телефоне — полоса в 50px: она стоит В БИРКЕ, а бирка обязана
   помещаться на один экран. Прямоугольник 280px уводил отрывную линию с 648
   на 928 пикселей, то есть отменял главное правило облика. */
.ad-rail{width:300px;height:50px}
.ad-flow{width:300px;height:250px}
.ad-lead{width:300px;height:250px}
.ad-rail .house{flex-direction:row;align-items:baseline;gap:calc(var(--u)*2);
  padding:0 calc(var(--u)*2);white-space:nowrap}
.ad-rail .hsub{overflow:hidden;text-overflow:ellipsis;min-width:0}
@media (min-width:360px){
  .ad-rail{width:320px;height:50px}
  .ad-flow{width:336px;height:280px}
  .ad-lead{width:336px;height:280px}
}
@media (min-width:776px){
  .ad-lead{width:728px;height:90px}
  .ad-lead .house{flex-direction:row;align-items:baseline;
    gap:calc(var(--u)*3);padding:0 calc(var(--u)*3)}
}
@media (min-width:1024px){
  .ad-rail{width:300px;height:600px}
  .ad-rail .house{flex-direction:column;align-items:flex-start;gap:var(--u);
    padding:calc(var(--u)*3) calc(var(--u)*4);white-space:normal}
  .ad-lead{width:970px;height:250px}
  .ad-lead .house{flex-direction:column;align-items:flex-start;
    gap:calc(var(--u)*2);padding:calc(var(--u)*4) calc(var(--u)*5)}
}
"""


# --------------------------------------------------------------------------
# ЛИНЕЙКА: сколько места занимает набранная строка
#
# Обмер Arial Bold, единиц на em (снят в браузере через canvas measureText,
# 1000px, округление до тысячных). Считаем ПО ARIAL, а не по узкому шрифту
# стека: ни на Android, ни на iOS ни одного из четырёх узких начертаний нет,
# и `font-stretch:condensed` невариативному шрифту не делает ничего. Телефон
# — это худший случай, а бирка обязана поместиться именно на нём.
ADVANCE = {
    " ": .278, "!": .333, '"': .474, "&": .722, "'": .238, "(": .333,
    ")": .333, "*": .389, "+": .584, ",": .278, "-": .333, ".": .278,
    "/": .278, "0": .556, "1": .556, "2": .556, "3": .556, "4": .556,
    "5": .556, "6": .556, "7": .556, "8": .556, "9": .556, ":": .333,
    ";": .333, "?": .611, "A": .722, "B": .722, "C": .722, "D": .722,
    "E": .667, "F": .611, "G": .778, "H": .722, "I": .278, "J": .556,
    "K": .722, "L": .611, "M": .833, "N": .722, "O": .778, "P": .667,
    "Q": .778, "R": .722, "S": .667, "T": .611, "U": .722, "V": .667,
    "W": .944, "X": .667, "Y": .667, "Z": .611, "%": .889, "°": .4,
    "·": .333, "–": .556, "—": 1.0, "×": .584, "÷": .549,
}
ADV_DEFAULT = .611       # неизвестный знак считается широким, а не узким


def text_width(s, px, track=0.0):
    """Ширина строки ЗАГЛАВНЫМИ в Arial Bold при кегле px и трекинге track em.

    CSS добавляет трекинг ПОСЛЕ каждого знака, включая последний, — так это
    и считается.
    """
    s = s.upper()
    return px * (sum(ADVANCE.get(ch, ADV_DEFAULT) for ch in s)
                 + track * len(s))


def line_count(s, px, track, room):
    """Сколько строк займёт s в колонке шириной room. Перенос по словам,
    жадный, как в браузере; слово шире колонки занимает свою строку."""
    words = s.upper().split()
    if not words or room <= 0:
        return 1
    lines, cur = 1, 0.0
    space = text_width(" ", px, track)
    for w in words:
        ww = text_width(w, px, track)
        if cur and cur + space + ww > room:
            lines += 1
            cur = ww
        else:
            cur = (cur + space + ww) if cur else ww
    return lines


# --------------------------------------------------------------------------
# БЮДЖЕТ ВЫСОТЫ БИРКИ
#
# Правило облика — «всё выше перфорации помещается на один экран телефона».
# Сторожил его `len(name) > 48`, то есть ЧИСЛО ЗНАКОВ вместо высоты: он
# пропускал вторую по высоте страницу сайта («Beef broth, stock, consommé
# (commercially produced)» — ровно 48 знаков) и ужимал те, которым это было
# не нужно. Считается теперь высота, и считается она по ТОМУ ЖЕ CSS, который
# отдаётся браузеру: числа берутся из CSS разбором, а не переписываются сюда
# руками — переписанное расходится с отданным молча.

BUDGET_VW = 375          # iPhone SE / базовая ширина замера
BUDGET_PX = 553          # видимая часть экрана в Safari на этой ширине


_CLEAN = {}
_ROOTS = {}


def clean(css):
    """CSS без комментариев. Комментарии здесь по-русски и мешают разбору:
    чанк «/* ... */ --hair:rgba(...)» не начинается с «--», и половина
    токенов терялась МОЛЧА — линейка считала по нулям и говорила, что всё
    помещается."""
    if css not in _CLEAN:
        _CLEAN[css] = strip_comments(css)
    return _CLEAN[css]


def _root_vars(css):
    """Токены с голого :root. Тёмная тема тут не нужна: она меняет только
    цвета, а высоту дают отступы и кегли."""
    if css in _ROOTS:
        return _ROOTS[css]
    c = clean(css)
    i = c.find(":root{")
    j = c.find("}", i)
    out = {}
    for decl in c[i + 6:j].split(";"):
        if ":" in decl and decl.strip().startswith("--"):
            k, v = decl.split(":", 1)
            out[k.strip()] = v.strip()
    _ROOTS[css] = out
    return out


def px_of(value, css, vw=BUDGET_VW):
    """Значение CSS в пикселях: число, var(), calc(var(--u)*n), clamp()."""
    v = str(value).strip()
    root = _root_vars(css)
    for _ in range(6):
        if v.startswith("var(") and v.endswith(")"):
            v = root.get(v[4:-1].strip(), "0").strip()
        else:
            break
    if v.startswith("clamp(") and v.endswith(")"):
        lo, mid, hi = [x.strip() for x in v[6:-1].split(",")]
        lo, hi = px_of(lo, css, vw), px_of(hi, css, vw)
        if mid.endswith("vw"):
            mid = float(mid[:-2]) * vw / 100.0
        else:
            mid = px_of(mid, css, vw)
        return min(max(lo, mid), hi)
    if v.startswith("calc(") and v.endswith(")"):
        body = v[5:-1]
        if "*" in body:
            a, b = body.split("*", 1)
            return px_of(a, css, vw) * float(b.strip())
        return px_of(body, css, vw)
    if v.endswith("px"):
        return float(v[:-2])
    if v.endswith("em"):
        return float(v[:-2])
    try:
        return float(v)
    except ValueError:
        return 0.0


def decls(css, selector):
    """Объявления одного селектора, взятые ИЗ CSS. Медиа-блоки не читаются:
    бюджет считается на 375px, а все медиа-условия здесь начинаются с 600."""
    out = {}
    css = clean(css)
    i = 0
    while True:
        i = css.find(selector + "{", i)
        if i < 0:
            return out
        # селектор должен стоять началом правила, а не хвостом другого
        head = css.rfind("}", 0, i)
        head2 = css.rfind("{", 0, i)
        if head2 > head:            # мы внутри media-блока — пропускаем
            i += 1
            continue
        j = css.find("}", i)
        for d in css[i + len(selector) + 1:j].split(";"):
            if ":" in d:
                k, v = d.split(":", 1)
                out[k.strip()] = v.strip()
        i = j + 1


def track_of(d):
    v = d.get("letter-spacing", "0")
    return float(v[:-2]) if v.endswith("em") else 0.0


# --------------------------------------------------------------------------
# ЛИНЕЙКА ХОДИТ ПО ОТДАННОМУ. Модель разбирает ту разметку, которая ушла в
# браузер, и тот CSS, который ушёл вместе с ней. Гейт, спросивший бы у
# генератора, чего тот хотел, согласился бы сам с собой — такой у нас уже был.

import re as _re

_TAG = _re.compile(r"<(/?)([a-z0-9]+)([^>]*)>", _re.I)
_CLS = _re.compile(r'class="([^"]*)"')
_VOID = ("br", "img", "input", "hr", "meta", "link", "source")
_ENT = (("&middot;", "·"), ("&mdash;", "—"), ("&ndash;", "–"),
        ("&divide;", "÷"), ("&times;", "×"), ("&hellip;", "…"),
        ("&nbsp;", " "), ("&quot;", '"'), ("&#39;", "'"), ("&deg;", "°"),
        ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"))


_SVG = _re.compile(r"<svg\b.*?</svg>", _re.S | _re.I)


def blocks(html):
    """Непосредственные дети фрагмента: [(тег, классы, атрибуты, нутро)].

    Рисунок вырезается целиком ДО разбора: внутри него самозакрывающиеся
    <path/>, которые сканер тегов считал открывающими, и глубина вложенности
    не возвращалась к нулю — разбор бирки молча давал пустой список.
    """
    html = _SVG.sub(" ", html)
    out, depth, start, cur = [], 0, 0, None
    for m in _TAG.finditer(html):
        close, tag, at = m.group(1), m.group(2).lower(), m.group(3)
        if (tag in _VOID or at.rstrip().endswith("/")) and not close:
            if depth == 0:
                c = _CLS.search(at)
                out.append((tag, c.group(1) if c else "", at, ""))
            continue
        if not close:
            if depth == 0:
                c = _CLS.search(at)
                cur, start = (tag, c.group(1) if c else "", at), m.end()
            depth += 1
        else:
            depth -= 1
            if depth == 0 and cur:
                out.append(cur + (html[start:m.start()],))
                cur = None
    return out


def _plain(s):
    s = _re.sub(r"<svg\b.*?</svg>", " ", s, flags=_re.S | _re.I)
    s = _re.sub(r"<[^>]+>", " ", s)
    for a, b in _ENT:
        s = s.replace(a, b)
    return " ".join(s.split())


def own_text(html):
    """Текст САМОГО элемента: без текста вложенных элементов."""
    s = _re.sub(r"<svg\b.*?</svg>", " ", html, flags=_re.S | _re.I)
    s = _re.sub(r"<([a-z0-9]+)\b[^>]*>.*?</\1>", " ", s,
                flags=_re.S | _re.I)
    return _plain(s)


def media_decls(css, selector, vw):
    """Объявления селектора с учётом медиа-блоков, применимых на ширине vw."""
    out, i = {}, 0
    css = clean(css)
    while True:
        m = _re.search(r"@media\s*\(min-width:(\d+)px\)\s*\{", css[i:])
        stop = i + m.start() if m else len(css)
        out.update(decls(css[i:stop], selector))
        if not m:
            return out
        j, depth = i + m.end(), 1
        k = j
        while depth and k < len(css):
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1
        if vw >= int(m.group(1)):
            out.update(decls(css[j:k - 1], selector))
        i = k


def _side(d, prop, side, css, vw):
    """padding/margin с учётом сокращения: одно значение — все стороны, два —
    вертикаль и горизонталь."""
    exact = d.get("%s-%s" % (prop, side))
    if exact is not None:
        return px_of(exact, css, vw)
    v = d.get(prop)
    if not v:
        return 0.0
    parts = _split_values(v)
    if len(parts) == 1:
        return px_of(parts[0], css, vw)
    vert, horz = parts[0], parts[1]
    if len(parts) >= 3 and side == "bottom":
        vert = parts[2]
    if len(parts) >= 4 and side == "left":
        horz = parts[3]
    return px_of(vert if side in ("top", "bottom") else horz, css, vw)


def _split_values(v):
    """Разбить «calc(var(--u)*2) var(--pad)» по пробелам ВНЕ скобок."""
    out, depth, cur = [], 0, ""
    for ch in v:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == " " and depth == 0:
            if cur:
                out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def _bord(d, side):
    v = d.get("border-%s" % side, d.get("border", ""))
    m = _re.match(r"\s*(\d+(?:\.\d+)?)px", v)
    w = float(m.group(1)) if m else 0.0
    if d.get("border-%s-width" % side, "").endswith("px"):
        w = float(d["border-%s-width" % side][:-2])
    return w


def _sel_for(tag, cls, parent_sel):
    names = cls.split()
    if names:
        base = "." + names[0]
        return base, (base + "." + names[1]) if len(names) > 1 else None
    if parent_sel:
        return "%s %s" % (parent_sel, tag), None
    return tag, None


def _style(css, tag, cls, parent_sel, vw):
    base, mod = _sel_for(tag, cls, parent_sel)
    d = dict(decls(css, base))
    if not d and parent_sel:
        d = dict(decls(css, "%s %s" % (parent_sel, tag)))
    if mod:
        d.update(decls(css, mod))
    return base, d


def _text_h(text, d, css, room, vw, inherit):
    if not text:
        return 0.0
    size = px_of(d.get("font-size", inherit[0]), css, vw)
    lh = d.get("line-height", inherit[1])
    lh = float(lh) if not str(lh).endswith("px") else px_of(lh, css, vw) / size
    return line_count(text, size, track_of(d), room) * size * lh


def elem_height(tag, cls, attrs, inner, css, ad_css, room, vw,
                parent_sel="", inherit=("var(--f2)", "1.25")):
    """Высота одного элемента вместе с отступами и рамками."""
    names = cls.split()
    if tag == "svg":
        return 0.0
    if "ad" in names:
        slot = [x for x in names if x.startswith("ad-")]
        if not slot:
            return 0.0
        h = px_of(media_decls(ad_css, "." + slot[0], vw).get("height", "0"),
                  css, vw)
        m = media_decls(ad_css, ".sheet > .ad", vw)
        return h + 2 * _side(m, "margin", "top", css, vw)
    sel, d = _style(css, tag, cls, parent_sel, vw)
    box = (_side(d, "margin", "top", css, vw)
           + _side(d, "margin", "bottom", css, vw)
           + _side(d, "padding", "top", css, vw)
           + _side(d, "padding", "bottom", css, vw)
           + _bord(d, "top") + _bord(d, "bottom"))
    room2 = room - _side(d, "padding", "left", css, vw) \
        - _side(d, "padding", "right", css, vw)
    inh = (d.get("font-size", inherit[0]), d.get("line-height", inherit[1]))
    if tag == "input":
        size = px_of(d.get("font-size", inh[0]), css, vw)
        return box + size * 1.2
    box_flex = d.get("display", "") in ("flex", "grid")
    flex = box_flex and d.get("flex-direction", "row") != "column"
    wrap = d.get("flex-wrap", "nowrap") == "wrap"
    kids = [k for k in blocks(inner)
            if k[0] != "svg" and (box_flex or _is_block(k, css, sel, vw))]
    if not kids and "data-clock=" in attrs:
        # Коробка отсчёта пуста в разметке: поле рисует скрипт. Считаем
        # строку, которую он рисует, — подпись и поле ввода в один ряд.
        di = decls(css, sel + " input")
        return box + (px_of(di.get("font-size", "var(--f4)"), css, vw) * 1.2
                      + _side(di, "padding", "bottom", css, vw)
                      + _bord(di, "bottom"))
    if kids:
        row = flex and not (wrap and _overflows(kids, css, room2, vw, sel,
                                               inh))
        if row:
            shares = _flex_shares(kids, css, room2, vw, sel, inh)
        else:
            shares = [room2] * len(kids)
        hs = [elem_height(t2, c2, a2, i2, css, ad_css, sh, vw, sel, inh)
              for (t2, c2, a2, i2), sh in zip(kids, shares)]
        if row:
            h = max(hs)
        else:
            h = sum(hs)
            if flex:
                h += px_of(_split_values(d.get("gap", "0"))[0], css, vw) \
                    * (len(hs) - 1)
        return box + h + _text_h(_inline_text(inner, css, sel, vw, box_flex),
                                 d, css, room2, vw, inherit)
    return box + _text_h(_plain(inner), d, css, room2, vw, inherit)


def label_height(label_html, css, ad_css="", vw=BUDGET_VW):
    """Высота бирки на экране vw. Модель обязана быть НЕ МЕНЬШЕ настоящей:
    бюджет, который занижает, пропускает страницу, не влезающую в телефон."""
    body_pad = px_of("calc(var(--u)*2)" if vw < 600 else "calc(var(--u)*6)",
                     css, vw)
    sheet = min(vw - 2 * body_pad, px_of("var(--tag)", css, vw))
    room = sheet - 2
    return sum(elem_height(t, c, a, i, css, ad_css, room, vw, ".label")
               for t, c, a, i in blocks(label_html))


def label_of(page_html):
    """Разметка бирки со страницы: от начала бирки ДО ПЕРФОРАЦИИ.

    Всё, что выше отрывной линии, — бирка; ниже её начинается корешок, и
    реклама с перфорацией в бюджет первого экрана не входят, потому что они
    и есть его нижняя граница.
    """
    i = page_html.find('<div class="label">')
    if i < 0:
        return ""
    j = page_html.find('<div class="perf">', i)
    if j < 0:
        j = page_html.find('<div class="stub"', i)
    return page_html[i + 19:j].rsplit("</div>", 1)[0]


def label_room(css=None, vw=BUDGET_VW):
    """Ширина колонки внутри поля бирки на экране vw."""
    css = CSS if css is None else css
    body_pad = px_of("calc(var(--u)*2)" if vw < 600 else "calc(var(--u)*6)",
                     css, vw)
    sheet = min(vw - 2 * body_pad, px_of("var(--tag)", css, vw))
    return sheet - 2 - 2 * px_of("var(--pad)", css, vw)


def fit_display(text, css=None, vw=BUDGET_VW):
    """Класс крупной строки: «» или « long». Решает ШИРИНА, не длина имени.

    Прежний сторож был `len(name) > 48`, то есть ЧИСЛО ЗНАКОВ: «Beef broth,
    stock, consomme (commercially produced)» — ровно 48 знаков — уходил в
    четыре строки по 46px и делал вторую по высоте бирку сайта, а короткие
    имена ужимались зря. Ширина строки в Arial считается, а не угадывается.
    """
    css = CSS if css is None else css
    room = label_room(css, vw)
    size = px_of("var(--d1)", css, vw)
    tr = track_of(decls(css, ".item"))
    return "" if line_count(text, size, tr, room) <= 1 else " long"


def _flex_shares(kids, css, room, vw, parent_sel, inherit):
    """Сколько места достаётся каждому ребёнку строки-флекса.

    Место делится по ЕСТЕСТВЕННОЙ ширине: две колонки кромки — марка и
    происхождение — никогда не были равны, а деление поровну давало
    происхождению лишнюю строку в каждой бирке сайта.
    """
    nat = []
    for tag, cls, _at, inner in kids:  # noqa: E501
        _sel, d = _style(css, tag, cls, parent_sel, vw)
        size = px_of(d.get("font-size", inherit[0]), css, vw)
        nat.append(max(1.0, text_width(_plain(inner), size, track_of(d))))
    total = sum(nat)
    if total <= room:
        return [w for w in nat]
    return [max(room * 0.2, room * w / total) for w in nat]


def _overflows(kids, css, room, vw, parent_sel, inherit):
    """Не влезают ли дети строки-флекса в одну строку целиком."""
    tot = 0.0
    for tag, cls, _at, inner in kids:
        _sel, d = _style(css, tag, cls, parent_sel, vw)
        size = px_of(d.get("font-size", inherit[0]), css, vw)
        tot += text_width(_plain(inner), size, track_of(d))
    return tot > room


_BLOCK_TAGS = ("div", "h1", "h2", "h3", "p", "ul", "ol", "li", "section",
               "label", "input", "form")


def _is_block(kid, css, parent_sel, vw):
    """Блочный ли ребёнок. Строчные (<a>, <b>) набираются в строку родителя."""
    tag, cls, _at, _inner = kid
    if tag in _BLOCK_TAGS:
        return True
    _sel, d = _style(css, tag, cls, parent_sel, vw)
    return d.get("display", "inline") in ("block", "flex", "grid",
                                          "list-item")


def _inline_text(inner, css, parent_sel, vw, box_flex=False):
    """Текст элемента вместе со строчными детьми и без блочных."""
    s = _SVG.sub(" ", inner)
    for kid in blocks(s):
        if (box_flex or _is_block(kid, css, parent_sel, vw)) and kid[3]:
            s = s.replace(kid[3], " ", 1)
    return _plain(s)
