"""Каждый блок `run:` воркфлоу разбирается оболочкой ДО первого запуска.

В шаге «Sanity check» лежало одинокое `done` — остаток удалённого цикла.
YAML про содержимое блока не знает ничего, до запуска его не читает никто, а
оболочка разбирает и исполняет покомандно: `set -e` строкой выше отрабатывал,
следующая строка роняла шаг, job `build` краснел ВСЕГДА, и job `deploy`
(`needs: build`) не стартовал никогда. Файл пролежал так две недели.

Проверка стоит секунды. Пустая выборка — провал: «ноль битых блоков» и «ноль
осмотренных блоков» печатаются одинаково, и различать их обязан код, а не
читатель.
"""
import glob
import os
import re
import subprocess
import sys
import tempfile

WHERE = ".github/workflows/*.yml"


def blocks(path):
    """(номер первой строки, текст) для каждого блока `run: |`."""
    lines = open(path, encoding="utf-8").read().split("\n")
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s+)run: \|", lines[i])
        if not m:
            i += 1
            continue
        pad = len(m.group(1)) + 2
        body, j = [], i + 1
        while j < len(lines) and (not lines[j].strip()
                                  or lines[j].startswith(" " * pad)):
            body.append(lines[j][pad:] if lines[j].strip() else "")
            j += 1
        yield i + 1, "\n".join(body)
        i = j


def main():
    files = sorted(glob.glob(WHERE))
    if not files:
        print("::error::воркфлоу не найдены по %s — проверка смотрела не "
              "туда, и это провал, а не пропуск" % WHERE)
        return 1
    seen = bad = 0
    for path in files:
        for line, body in blocks(path):
            seen += 1
            fd, tmp = tempfile.mkstemp(suffix=".sh")
            os.close(fd)
            with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(body)
            res = subprocess.run(["bash", "-n", tmp], capture_output=True,
                                 text=True)
            os.unlink(tmp)
            if res.returncode:
                bad += 1
                print("::error::%s, блок со строки %d: %s"
                      % (path, line, res.stderr.strip()[:200]))
    if not seen:
        print("::error::ни одного блока run: не найдено в %d воркфлоу — "
              "разбор смотрит не на то" % len(files))
        return 1
    print("воркфлоу %d, блоков run: %d, битых %d" % (len(files), seen, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
