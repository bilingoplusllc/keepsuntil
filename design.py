# -*- coding: utf-8 -*-
"""Облик KeepsUntil — «ДАТА, А НЕ СРОК». Одна сырая строка CSS, ноль сборщиков.

ОТКУДА ЭТО. По правилу D-014 были заказаны четыре ЦЕЛЬНЫХ направления. Сперва
выбрана «Бирка на банке», и сайт был свёрстан ею целиком. 15.09.2026 Дмытро
посмотрел все четыре и выбрал ЭТО, назвав причину: навигация и удобство. Он
прав в том, что решает: на бирке первым крупным числом стоял СРОК, а человек
с банкой в руке спрашивает не «сколько», а «до какого числа».

ГИПОТЕЗА. Страница — не этикетка и не статья, а ПРИБОР с одним вводом.
Наверху поле даты, ниже — ответ, и ответ этот есть ДАТА В КАЛЕНДАРЕ, а не
длительность. Пока дата не названа, прибор честно показывает диапазон
источника.

ГЛАВНЫЙ ПРИЁМ — ТА ЖЕ ЯЧЕЙКА ДО И ПОСЛЕ ВВОДА. Ответ живёт в ОДНОМ месте
(`.out`). До ввода в нём стоит срок словами источника; после ввода на том же
месте, тем же кеглем встаёт дата, набранная сигнальным цветом, а подпись над
ней из «Use by» превращается в обратный отсчёт. Ничего не появляется и не
исчезает: величина МЕНЯЕТ ПРИРОДУ, оставаясь на месте. Поэтому у ответа нет
второй копии: прежняя бирка печатала срок дважды — крупно в `.dur` и ещё раз
в `.out`, — и вторая копия и была тем, что делало страницу списком, а не
прибором.

ПОРЯДОК, КОТОРЫЙ ИЗ ЭТОГО СЛЕДУЕТ: имя → ПОЛЕ ДАТЫ → ответ. Поле стоит ВЫШЕ
ответа, потому что ответ от него зависит; на бирке оно лежало внутри ответа,
третьей строкой снизу, и до него не доходил взгляд.

ЧТО УЖЕ ЗАНЯТО НА ФЕРМЕ, и чего здесь поэтому нет:
  · MileageCurve — почти белый фон и сине-зелёный акцент;
  · FedPay — пергамент, тёмно-синяя полоса, ЗАСЕЧКОВЫЙ текст;
  · BatteryCross — сталь, МОНОШИРИННЫЙ, острые углы;
  · KeepsUntil-1 — тёплая бумага, сливовый, Georgia, данные в таблицах;
  · KeepsUntil-2 («бирка») — средне-тёмная столешница, белый лист на ней,
    узкий гротеск капителью, лаймовая заливка, отрывная перфорация.
Здесь: белая страница без столешницы и без листа, системный гротеск, синяя
краска сигналом, вся иерархия — на трёх весах линейки и двух регистрах кегля.

ПРАВИЛА СИСТЕМЫ, которые нельзя нарушать при правках:
  · ОДИН сигнал `--signal`, и здесь он КРАСКА, а не заливка. Работа у него
    ровно одна: **ВЕЛИЧИНА, РАДИ КОТОРОЙ ПОСТРОЕНА ЭТА СТРАНИЦА, В ЕЁ
    ОКОНЧАТЕЛЬНОМ ВИДЕ.** У товара это ДАТА, и потому сигнал загорается
    только после ввода дня: пока дня нет, в ячейке стоит диапазон источника,
    то есть заготовка ответа, а не ответ. У рейтинга это ведущее значение —
    оно окончательно всегда. Ни заголовок, ни подпись, ни ссылка сигналом не
    набираются; единственное исключение — кольцо фокуса, и оно рисуется
    вокруг того самого поля, куда день и вводят;
  · ДВА РЕГИСТРА КЕГЛЯ И НИ ОДНОГО ПРОМЕЖУТОЧНОГО. Капитель подписи (--f1,
    прописные, трекинг .16em) и крупная величина (--d2/--d1, вес 800, трекинг
    отрицательный). Всё между ними — проза (--f2) и два её усиления (--f3,
    --f4) для имён в реестре. Подпись НАД величиной делает работу заголовка;
  · ТРИ ВЕСА ЛИНЕЙКИ, и каждый значит своё: 7px наверху страницы — это сам
    предмет; 2px отбивает ОТВЕТ и границу «ответ кончился»; 1px разделяет
    строки реестра. Четвёртого веса нет. Цвет тихой линии обязан держать 3:1
    на бумаге: макет направления рисовал её #dfe2ea, то есть 1,30:1, — вся
    структура реестра была бы ниже графического минимума, ровно тот дефект,
    который на этом сайте уже покупали;
  · ДВА ВЕРТИКАЛЬНЫХ КРАЯ НА ВЕСЬ САЙТ. Имя по левому, величина по правому,
    и колонка величины одинакова в таблице продукта, в рейтинге и в находках
    поиска. Третьего края нет нигде;
  · НИ ОДНОЙ РАМКИ ВОКРУГ ДАННЫХ. Рамка в этом направлении ровно одна и
    означает ВВОД: её носит поле даты и поле поиска. Обвести рамкой таблицу
    значило бы сказать, что в неё тоже можно писать;
  · каждый цвет объявлен на голом :root и переопределён в тёмной теме. Цвет,
    объявленный единственный раз внутри media-блока, — дефект;
  · текст не тусклее 4,5:1, графика не тусклее 3:1, В ОБЕИХ ТЕМАХ, и это
    СЧИТАЕТСЯ гейтом с наложением полупрозрачных значений на свой фон.

ДВЕ ВЕЛИЧИНЫ, ИЗ КОТОРЫХ ВЫВЕДЕНО ВСЁ ОСТАЛЬНОЕ:

  · `--u:4px` — ЕДИНСТВЕННАЯ единица отступа. Каждый padding, margin, gap и
    top в этом файле есть `calc(var(--u)*n)` при целом n или ноль. Ритм
    направления — восьмёрка, то есть чётные n; нечётные оставлены тем местам,
    где подпись прижимается к своей величине;
  · ШКАЛА КЕГЛЕЙ — четыре текстовых ступени и две крупные: 12 / 15 / 18 / 22
    и два clamp-а. Ниже 15px живёт ровно один размер — капитель подписей.
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
  /* Бумага и краска. Столешницы в этом направлении НЕТ: страница и есть
     лист, поэтому --surface и --stock объявлены одним значением. Оба имени
     сохранены: их спрашивает гейт контраста, и «фон под листом» остаётся
     самостоятельной ролью, даже когда совпадает с бумагой. */
  --surface:#ffffff;
  --stock:#ffffff;
  --ink:#10131b;
  --ink2:#5f6577;

  /* ТРИ ВЕСА ЛИНЕЙКИ. --tear носит имя прежнего главного приёма и остаётся
     САМОЙ ГРОМКОЙ линией системы: 7px наверху страницы и 2px под ответом.
     --hair и --edge — тихая линия реестра, и она обязана держать 3:1. */
  --hair:#8b92a3;
  --edge:#8b92a3;
  --tear:#10131b;
  --heavy:#10131b;

  /* ОДИН сигнал, и он КРАСКА. Означает ровно одно: дата, посчитанная из
     названного дня. До ввода сигнала на странице нет. */
  --signal:#2b31d8;

  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;

  /* ЕДИНСТВЕННАЯ единица отступа и всё, что из неё выведено */
  --u:4px;
  --pad:calc(var(--u)*4);
  --rad:calc(var(--u)*3);
  --tag:1080px;

  /* ШКАЛА КЕГЛЕЙ. Ниже 15px живёт только капитель подписей. */
  --f1:12px;
  --f2:15px;
  --f3:18px;
  --f4:22px;
  --d1:clamp(34px,9vw,60px);
  --d2:clamp(21px,5.6vw,29px);

  color-scheme:light dark;
}

@media (prefers-color-scheme:dark){
  :root{
    --surface:#0c0e13;
    --stock:#0c0e13;
    --ink:#e9ebf2;
    --ink2:#979db0;
    --hair:#5a6272;
    --edge:#5a6272;
    --tear:#e9ebf2;
    --heavy:#e9ebf2;
    --signal:#98a0ff;
  }
}

*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
/* Полоса 7px — САМ ПРЕДМЕТ: единственное, что рисуется во всю ширину окна.
   Она нарисована кромкой body, а не элементом: узел без текста ломает
   правила «последний теряет линию», как уже случилось с 540 невидимыми
   рекламными местами на соседнем сайте. */
body{
  margin:0;padding:calc(var(--u)*5);min-height:100vh;
  border-top:7px solid var(--tear);
  background:var(--surface);color:var(--ink);
  font-family:var(--sans);font-size:var(--f2);
  font-variant-numeric:tabular-nums;line-height:1.45;
}
h1,h2,h3,p,ul,ol,form,figure{margin:0;padding:0}
ul{list-style:none}
a{color:inherit}
/* Кольцо фокуса — КРАСКОЙ, а не сигналом: 18,6:1 на светлой бумаге и
   16,2:1 на тёмной. Сигналом его красить нельзя, хотя контраста хватает:
   кольцо обходит КАЖДУЮ ссылку страницы, и сигнал получил бы второе
   занятие — «сюда можно нажать» вместо «вот посчитанная величина». Одно
   исключение, которое исключением не является: подчёркивание поля ввода при
   фокусе остаётся сигнальным, потому что поле — это место, ОТКУДА берётся
   та самая дата, то есть та же работа. */
:focus-visible{outline:3px solid var(--heavy);outline-offset:2px}
@media (min-width:600px){body{padding:calc(var(--u)*8)}}

.skip{position:static;display:block;width:1px;height:1px;overflow:hidden;
  white-space:nowrap;background:var(--stock);color:var(--ink)}
.skip:focus-visible{width:auto;height:auto;padding:calc(var(--u)*2) 0}

/* --------------------------------------------------------- полоса набора */
/* Лист не рисуется ничем: ни фона, ни рамки, ни тени. Предмет на этой
   странице один — прибор, и обводить его значило бы завести вторую рамку
   там, где рамка означает ввод. */
.sheet{max-width:var(--tag);margin:0 auto}

/* С 1024px появляется ВТОРОЙ вертикальный край — колонка рельсы. Больше
   колонок не заводится: текст и реестр остаются одной колонкой, потому что
   прибор с двумя колонками ответа перестаёт быть прибором. */
@media (min-width:1024px){
  .sheet{display:grid;align-items:start;
    grid-template-columns:minmax(0,1fr) 300px;
    column-gap:calc(var(--u)*10)}
  .label{grid-column:1;grid-row:1}
  .perf{grid-column:1;grid-row:2}
  .stub{grid-column:1;grid-row:3}
  .sheet > .ad{grid-column:2;grid-row:1/span 3}
}

/* ------------------------------------------------------------ марка */
.strip{display:flex;flex-wrap:wrap;justify-content:space-between;
  align-items:baseline;gap:var(--u) calc(var(--u)*4);
  padding:0 0 calc(var(--u)*3);
  font-size:var(--f1);letter-spacing:.18em;text-transform:uppercase;
  font-weight:600;color:var(--ink2)}
.mark{display:flex;align-items:center;gap:calc(var(--u)*2)}
.mark a{text-decoration:none;border-bottom:1px solid var(--hair)}
.mark a:hover{border-bottom-color:var(--ink)}
.strip svg{display:block}
.src{color:var(--ink2);letter-spacing:.14em;text-align:right}

/* ------------------------------------------------------- поле и подпись */
.field{padding:calc(var(--u)*4) 0;border-bottom:1px solid var(--hair)}
.cap{font-size:var(--f1);letter-spacing:.16em;text-transform:uppercase;
  font-weight:600;color:var(--ink2);margin-bottom:calc(var(--u)*2)}
/* Имя НЕ прописными. Капитель здесь принадлежит подписи, и имя, набранное
   тем же приёмом, читалось бы подписью к самому себе. Ступень кегля
   выбирается расчётом ширины строки, а не числом знаков — см. fit_display. */
.item{margin:var(--u) 0;font-size:var(--d1);font-weight:800;
  letter-spacing:-.04em;line-height:1.02}
.item.long{font-size:var(--d2)}
/* Слова запроса вокруг имени: «How long does / MILK / last in the fridge?».
   Прописные — ПОДПИСЬ ПОЛЯ и ничто другое. Первый прогон одел капителью и
   запрос, и отсчёт, и оговорку: на экране телефона вышло семь строк
   прописных против двух величин, то есть подпись стала основным текстом, а
   два регистра — одним. Здесь и ниже прописными остаются только те строки,
   которые НАЗЫВАЮТ соседнюю величину.

   `letter-spacing:normal` — НЕ УКРАШЕНИЕ, А ПОГАШЕНИЕ НАСЛЕДСТВА. Трекинг
   наследуется ВЫЧИСЛЕННОЙ АБСОЛЮТНОЙ длиной, а не долей кегля: -.04em,
   посчитанные на `.item` при её собственных 60px, приходят сюда как -2.4px,
   и для кегля 15px это -0.16em — пробел между словами схлопывается, и
   посетитель читает «Howlongdoes lastinthefridge». Замерено в браузере:
   ширина строки 68,9px против 100,1px при нормальном трекинге, то есть
   -31%. Дефект стоял на ПЕРВОЙ строке всех 295 карточек товара — на самом
   вопросе, ради ответа на который человек пришёл из поиска, — и завёлся он
   ровно при переверстке, когда вопрос переехал ВНУТРЬ h1 и утащил за собой
   дисплейный трекинг. Соседняя `.sub` того же кегля 15px стоит СЕСТРОЙ h1,
   наследства не получает и набрана верно — она и была контролем.

   Правило, которое из этого следует и которое проверяется гейтом: потомок
   блока с отрицательным трекингом, объявляющий СВОЙ кегль, обязан объявить
   и свой трекинг. */
.ask{display:block;font-size:var(--f2);font-weight:400;color:var(--ink2);
  letter-spacing:normal;line-height:1.4}
/* ВТОРОЕ окно набирается МЕНЬШЕ ответа. Равный кегль делал два числа
   равноправными, и взгляд ловил нижнее — ровно та ошибка, ради которой
   порядок полей на прежней бирке уже однажды переставляли. */
.dur{font-size:var(--d2);font-weight:800;letter-spacing:-.03em;
  line-height:1.05}
.dur.long{font-size:var(--f4)}
.sub{margin-top:calc(var(--u)*2);font-size:var(--f2);font-weight:400;
  color:var(--ink2)}

/* ----------------------------------------------- ВВОД: единственная рамка */
/* Поле даты стоит ВЫШЕ ответа. Рамка означает «сюда пишут», и носят её
   только два элемента на сайте: это поле и поле поиска. */
.dateline{display:flex;flex-wrap:wrap;align-items:baseline;
  gap:var(--u) calc(var(--u)*4);
  margin-top:calc(var(--u)*4);
  padding:calc(var(--u)*3) var(--pad);
  border:2px solid var(--heavy);border-radius:var(--rad)}
.dateline label{width:100%;font-size:var(--f1);letter-spacing:.16em;
  text-transform:uppercase;font-weight:600;color:var(--ink2)}
.dateline input{flex:1 1 130px;min-width:0;background:transparent;border:0;
  border-bottom:2px solid var(--hair);color:var(--ink);
  font-family:var(--sans);font-weight:700;font-size:var(--d2);
  letter-spacing:-.02em;line-height:1.2;padding:0 0 var(--u);border-radius:0}
.dateline input:focus{border-bottom-color:var(--signal)}

/* ------------------------------------------------ ОТВЕТ: та же ячейка */
/* До ввода здесь стоит срок словами источника, после — дата сигнальным
   цветом, и подпись над ней из «Use by» становится обратным отсчётом.
   Класс `on` вешает скрипт: цвет — это утверждение «посчитано из вашего
   дня», и вешать его на разметку, пока дня нет, значило бы соврать. */
.hot{padding:calc(var(--u)*5) 0;border-bottom:1px solid var(--hair)}
.out{font-size:var(--d1);font-weight:800;letter-spacing:-.035em;
  line-height:1.02}
.out.on{color:var(--signal)}
.out small{display:block;font-size:var(--f1);letter-spacing:.16em;
  text-transform:uppercase;font-weight:600;color:var(--ink2);
  margin-bottom:calc(var(--u)*2)}
/* Что окно ЗНАЧИТ — на первом экране, подписью, а не прозой. Одна оговорка
   на 221 странице служила двум противоположным последствиям, и правильное
   слово стояло ниже, куда с телефона не доходят. */
.means{margin-top:calc(var(--u)*4);padding-left:calc(var(--u)*3);
  border-left:2px solid var(--hair);
  font-size:var(--f2);font-weight:400;color:var(--ink2)}

/* ----------------------------------------- во сколько раз дешевле */
.cost{display:flex;align-items:baseline;gap:calc(var(--u)*4);
  padding:calc(var(--u)*5) 0;border-bottom:1px solid var(--hair)}
.x{font-size:var(--d2);font-weight:800;letter-spacing:-.035em;line-height:1}
.t{font-size:var(--f1);letter-spacing:.14em;text-transform:uppercase;
  font-weight:600;color:var(--ink2)}
.calc{display:block;margin-top:var(--u);font-size:var(--f1);
  letter-spacing:.1em;color:var(--ink2)}

/* ------------------------------------------- граница «ответ кончился» */
/* Здесь стоит подпись, называющая то, что ниже: выше границы страница
   ОТВЕЧАЕТ, ниже — показывает, как ответ посчитан.

   ЧЕМ ЭТО ДЕРЖИТСЯ НА САМОМ ДЕЛЕ. Прежний облик писал здесь, что правило
   «над этой линией нет ни одного предложения прозы» проверяется гейтом.
   Такого гейта нет: есть `g_label_fits_one_screen`, и он считает ВЫСОТУ, а
   не наличие прозы. Описанный и несуществующий рычаг хуже отсутствующего —
   на него рассчитывают, — поэтому здесь сказано как есть: выше границы
   абзацев нет по построению (label_fields печатает только поля), а стоит
   на страже бюджет первого экрана. */
.perf{margin-top:calc(var(--u)*6);padding:calc(var(--u)*6) 0 0;
  border-top:2px solid var(--tear);
  font-size:var(--f1);letter-spacing:.2em;text-transform:uppercase;
  font-weight:600;color:var(--ink2)}

/* ---------------------------------------------------------- разбор */
.stub{padding:0 0 calc(var(--u)*4)}
.stub section{padding:calc(var(--u)*6) 0;border-bottom:1px solid var(--hair)}
.stub section:last-of-type{border-bottom:0}
/* Заголовок раздела — единственное усиление между капителью и крупной
   строкой, и он НЕ прописными: капитель занята подписями. */
.stub h2{font-size:var(--f4);font-weight:700;letter-spacing:-.02em;
  margin-bottom:calc(var(--u)*3)}
.stub p{font-size:var(--f2);line-height:1.6;max-width:68ch;
  overflow-wrap:anywhere}
.stub p + p{margin-top:calc(var(--u)*3)}
.quiet{color:var(--ink2)}
.tip{border-left:2px solid var(--hair);padding-left:calc(var(--u)*3)}
.tip b{font-size:var(--f1);letter-spacing:.14em;text-transform:uppercase;
  font-weight:600;color:var(--ink2)}

/* ------------------------------------- второй отсчёт: своё поле даты */
.second{display:flex;flex-wrap:wrap;align-items:baseline;
  gap:var(--u) calc(var(--u)*4);
  margin-top:calc(var(--u)*4);
  padding:calc(var(--u)*3) var(--pad) calc(var(--u)*4);
  border:2px solid var(--heavy);border-radius:var(--rad)}
.second label{width:100%;font-size:var(--f1);letter-spacing:.16em;
  text-transform:uppercase;font-weight:600;color:var(--ink2)}
.second input{flex:1 1 130px;min-width:0;background:transparent;border:0;
  border-bottom:2px solid var(--hair);color:var(--ink);
  font-family:var(--sans);font-weight:700;font-size:var(--d2);
  letter-spacing:-.02em;padding:0 0 var(--u);border-radius:0}
.second input:focus{border-bottom-color:var(--signal)}

/* ------------------------------ РЕЕСТР: ДВА ВЕРТИКАЛЬНЫХ КРАЯ */
/* Единственная сетка направления, и она одна на таблицу продукта, рейтинг и
   находки поиска: имя по левому краю, величина по правому. С 640px колонка
   величины фиксирована (18rem) — иначе «правый край» гулял бы от страницы к
   странице вслед за длиной имени, и краёв стало бы столько же, сколько
   страниц. Ниже 640px колонки складываются в одну, и величина остаётся под
   именем по ЛЕВОМУ краю: правый край на телефоне держать нечем. */
.kind{margin-top:calc(var(--u)*6);font-size:var(--f3);font-weight:700;
  letter-spacing:-.015em;padding-bottom:calc(var(--u)*2);
  border-bottom:2px solid var(--heavy)}
.rows{margin-top:0}
.rows li,.near a,.res a{display:grid;grid-template-columns:1fr;
  gap:var(--u);padding:calc(var(--u)*3) 0;text-decoration:none}
.rows li{border-bottom:1px solid var(--hair)}
.rows li:last-child{border-bottom:0}
.rk{font-size:var(--f1);letter-spacing:.14em;text-transform:uppercase;
  font-weight:600;color:var(--ink2)}
.rv{font-size:var(--f3);font-weight:700;letter-spacing:-.015em}
.rv.on{color:var(--signal)}
.rv small{display:block;font-size:var(--f1);letter-spacing:.16em;
  text-transform:uppercase;font-weight:600;color:var(--ink2);
  margin-bottom:var(--u)}

/* ------------------------------------------ соседи, рейтинги, находки */
.near li,.res li{border-bottom:1px solid var(--hair)}
.near li:last-child,.res li:last-child{border-bottom:0}
.near a:hover .n,.near a:focus .n,.res a:hover .n{text-decoration:underline}
.n{font-size:var(--f3);font-weight:700;letter-spacing:-.015em}
/* ВЕЛИЧИНА — это величина, а не предложение: оговорка уезжает строкой ниже
   обычным начертанием. */
.v{font-size:var(--f2);font-weight:600;letter-spacing:-.005em}
.v small{display:block;font-size:var(--f1);font-weight:400;
  color:var(--ink2);margin-top:var(--u)}
/* ВЕДУЩАЯ СТРОКА РЕЙТИНГА — ответ, который даёт витрина, и помечена она тем
   же сигналом и тем же способом, что ответ на странице товара. */
.near[data-lead] li:first-child .n{font-size:var(--f4)}
.near[data-lead] li:first-child .v{font-size:var(--f3);color:var(--signal)}

/* ---------------------------------------------- поиск: вторая рамка */
.hunt,.stub .find{margin-top:calc(var(--u)*5);
  padding:calc(var(--u)*3) var(--pad) calc(var(--u)*4);
  border:2px solid var(--heavy);border-radius:var(--rad)}
.hunt input,.find input{width:100%;background:transparent;border:0;
  border-bottom:2px solid var(--hair);color:var(--ink);
  font-family:var(--sans);font-weight:700;font-size:var(--d2);
  letter-spacing:-.02em;padding:0 0 var(--u);border-radius:0;
  margin-top:calc(var(--u)*2)}
.hunt input:focus,.find input:focus{border-bottom-color:var(--signal)}
.hunt input::placeholder,.find input::placeholder{color:var(--ink2);
  font-weight:400}
.findp{margin-top:calc(var(--u)*3);font-size:var(--f2);font-weight:400;
  color:var(--ink2)}
.res{margin-top:calc(var(--u)*4);padding-top:calc(var(--u)*3);
  border-top:1px solid var(--hair)}
.none{margin-top:calc(var(--u)*4);font-size:var(--f2);font-weight:400;
  color:var(--ink2)}

/* ---------------------------------------------------------- навигация */
.ways{margin-top:calc(var(--u)*4);padding-top:calc(var(--u)*3);
  border-top:1px solid var(--hair)}
.way{margin-top:calc(var(--u)*3);font-size:var(--f2);font-weight:600}
.way:first-child{margin-top:0}
.wcap{display:block;color:var(--ink2);font-size:var(--f1);
  letter-spacing:.16em;text-transform:uppercase;margin-bottom:var(--u)}

.foot{padding:calc(var(--u)*6) 0 0;border-top:1px solid var(--hair);
  font-size:var(--f2);font-weight:400;color:var(--ink2)}

@media (min-width:640px){
  .rows li,.near a,.res a{grid-template-columns:1fr 18rem;
    gap:calc(var(--u)*2) calc(var(--u)*8);align-items:baseline}
  .rk,.n{grid-column:1}
  .rv,.v{grid-column:2;text-align:right}
}
"""


# Стиль рекламных мест держится ОТДЕЛЬНО и вставляется только при ADS=True.
#
# ТРИ ПРАВИЛА, КАЖДОЕ КУПЛЕНО ОШИБКОЙ:
#
# 1. Место существует, только когда в нём ЧТО-ТО ЕСТЬ. `display:none` не
#    выводит узел из :last-child, и на соседнем сайте пятьсот сорок невидимых
#    мест сломали пять правил отступов на ста пятидесяти семи страницах.
# 2. Размер задан ТОЧНО и обязан ВЛЕЗАТЬ В СВОЙ КОНТЕЙНЕР на каждой ширине.
# 3. Ответ ВЫШЕ первой рекламы на любом типе страницы: рельса стоит ПОСЛЕ
#    границы «ответ кончился», то есть ниже поля даты и ниже самого ответа.
AD_CSS = r"""
.ad{overflow:hidden;display:flex;align-items:stretch;margin:0 auto}
.sheet > .ad{margin:calc(var(--u)*6) auto}
.stub .ad{margin:0 auto calc(var(--u)*6)}
.adband{max-width:var(--tag);margin:0 auto;padding-top:calc(var(--u)*6)}
.house{display:flex;flex-direction:column;justify-content:center;
  gap:var(--u);width:100%;padding:calc(var(--u)*3) calc(var(--u)*4);
  text-decoration:none;color:var(--ink);
  background:var(--stock);border:1px solid var(--hair);
  border-radius:var(--rad)}
.house:hover .hn{text-decoration:underline}
.hcap{font-size:var(--f1);letter-spacing:.2em;text-transform:uppercase;
  font-weight:600;color:var(--ink2)}
.hn{font-size:var(--f3);font-weight:700;letter-spacing:-.015em}
.hsub{font-size:var(--f2);line-height:1.35;color:var(--ink2)}
.ad-rail{width:300px;height:50px}
.ad-flow{width:300px;height:250px}
.ad-lead{width:300px;height:250px}
.ad-rail .house{flex-direction:row;align-items:baseline;gap:calc(var(--u)*2);
  padding:0 calc(var(--u)*2);white-space:nowrap}
.ad-rail .hsub{display:none}
@media (min-width:360px){
  .ad-rail{width:320px;height:50px}
  .ad-flow{width:336px;height:280px}
  .ad-lead{width:336px;height:280px}
}
@media (min-width:776px){
  .ad-lead{width:728px;height:90px}
  .ad-lead .house{flex-direction:row;align-items:baseline;
    gap:calc(var(--u)*4);padding:0 calc(var(--u)*4)}
}
@media (min-width:1024px){
  .ad-rail{width:300px;height:600px}
  .ad-rail .house{flex-direction:column;align-items:flex-start;gap:var(--u);
    padding:calc(var(--u)*4) calc(var(--u)*5);white-space:normal}
  .ad-rail .hsub{display:block}
  .ad-lead{width:970px;height:250px}
  .ad-lead .house{flex-direction:column;align-items:flex-start;
    gap:calc(var(--u)*3);padding:calc(var(--u)*5) calc(var(--u)*6)}
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
    body_pad = px_of("calc(var(--u)*5)" if vw < 600 else "calc(var(--u)*8)",
                     css, vw)
    # Без вычета рамки: листа с кромкой в этом направлении нет — поля стоят
    # прямо в полосе набора, и её ширина и есть место под строку.
    room = min(vw - 2 * body_pad, px_of("var(--tag)", css, vw))
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
    """Ширина колонки, в которой набирается ответ, на экране vw."""
    css = CSS if css is None else css
    body_pad = px_of("calc(var(--u)*5)" if vw < 600 else "calc(var(--u)*8)",
                     css, vw)
    # Боковой отступ поля равен нулю: единственный отступ от края экрана —
    # отступ полосы набора, и он объявлен на body. Вычитать здесь --pad
    # значило бы держать второй левый край, которого в облике нет.
    return min(vw - 2 * body_pad, px_of("var(--tag)", css, vw))


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
