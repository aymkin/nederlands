# Мост «учебная программа → Fluent» — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Один CLI-скрипт, который импортирует лексику и грамматику активной
темы курса в spaced-repetition Fluent и сообщает, когда тема освоена и пора
дальше.

**Architecture:** Manifest (`<course>/curriculum.json`) владеет
последовательностью и прогрессом (`done/active/locked`).
`scripts/fluent_import.py` читает активный юнит, превращает woordenlijst и
модули грамматики в карточки и пишет их **напрямую** в
`~/.claude/fluent-data/spaced-repetition.json`, перестраивая очередь так же, как
это делает `update-db.py`. Режим `--check` читает ту же БД и считает освоенность
юнита по префиксу `item_id`; `--advance` двигает указатель и импортирует
следующий юнит. SM-2 внутри Fluent владеет расписанием и рециклингом.

**Tech Stack:** Python 3, только stdlib (`json`, `argparse`, `pathlib`, `re`,
`datetime`, `shutil`, `tempfile`). Тесты — plain `assert`, запускаются
`python3 scripts/test_fluent_import.py` (pytest не требуется).

## Global Constraints

- **Stdlib only** — никаких новых зависимостей.
- **Импортёр пишет ТОЛЬКО `spaced-repetition.json`** — не трогает остальные 5 БД
  Fluent (никаких счётчиков сессий, стриков, accuracy_trend).
- **Перед записью — бэкап** копией в
  `~/.claude/fluent-data/.backups/pre-import-<unit>-<date>/spaced-repetition.json`.
- **Идемпотентность** — добавлять только `item_id`, которых ещё нет в `items`.
- **Унифицированный префикс `item_id`:** `{course}_t{N}_…` для всей темы
  (лексика `{course}_t{N}_voc_{taak}_{slug}`, грамматика
  `{course}_t{N}_gram_{section}_{idx}`).
- **Ровно один юнит `active`** в manifest.
- **Порог перехода:** доля карточек юнита с `mastery_level ≥ 3` **≥ 0.80** И
  число «красных» (`consecutive_incorrect ≥ 2`) **== 0**.
- **Переход вручную** (`--advance`), автоматического нет.
- **Очередь** перестраивается точь-в-точь как в `update-db.py` (см. Task 4) —
  это осознанное отклонение от правила плагина «не редактировать
  spaced-repetition.json руками»: импортёр сохраняет инвариант очереди, потому
  что строит её тем же алгоритмом, и никогда не вмешивается в поток повторений.
- **Даты** в формате `%Y-%m-%d`; сравнение строк = сравнение дат (ISO).
- **Тестируемость:** все функции, пишущие на диск, принимают путь аргументом;
  реальные пути из `~/.claude/fluent-data/` подставляются только в `main()`.
- Markdown-доки обёрнуты на 80 (`pnpm run format`).

---

## File Structure

- `scripts/fluent_import.py` — единственный исполняемый модуль: загрузка
  manifest, парсеры лексики и грамматики, запись в SR, гейт, advance, CLI.
- `scripts/test_fluent_import.py` — self-contained assert-тесты.
- `link/curriculum.json` — manifest курса Link (данные).

---

### Task 1: Scaffold, date-хелперы, manifest-загрузчик

**Files:**

- Create: `scripts/fluent_import.py`
- Create: `link/curriculum.json`
- Test: `scripts/test_fluent_import.py`

**Interfaces:**

- Produces:
  - `today_str() -> str`
  - `tomorrow(s: str) -> str`
  - `date_plus_days(s: str, n: int) -> str`
  - `load_manifest(course_dir: Path) -> dict`
  - `active_unit(manifest: dict) -> dict` — возвращает единственный юнит со
    `status == "active"`; бросает `ValueError`, если их не ровно один.
  - `unit_prefix(course: str, unit_id: str) -> str` — `"link","thema_8"` →
    `"link_t8_"`.

- [ ] **Step 1: Write the failing test**

```python
# scripts/test_fluent_import.py
import json
import tempfile
from pathlib import Path

import fluent_import as fi


def test_unit_prefix():
    assert fi.unit_prefix("link", "thema_8") == "link_t8_"
    assert fi.unit_prefix("de_opmaat", "thema_12") == "de_opmaat_t12_"


def test_date_helpers():
    assert fi.tomorrow("2026-06-26") == "2026-06-27"
    assert fi.date_plus_days("2026-06-26", 7) == "2026-07-03"


def test_active_unit_ok():
    m = {"course": "link", "units": [
        {"id": "thema_8", "status": "active"},
        {"id": "thema_9", "status": "locked"}]}
    assert fi.active_unit(m)["id"] == "thema_8"


def test_active_unit_requires_exactly_one():
    m = {"course": "link", "units": [
        {"id": "thema_8", "status": "done"},
        {"id": "thema_9", "status": "locked"}]}
    try:
        fi.active_unit(m)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_load_manifest():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "curriculum.json"
        p.write_text(json.dumps({"course": "link", "units": []}))
        assert fi.load_manifest(Path(d))["course"] == "link"


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scripts && python3 test_fluent_import.py` Expected: FAIL —
`ModuleNotFoundError: No module named 'fluent_import'` (или `AttributeError` на
первой функции).

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/fluent_import.py
#!/usr/bin/env python3
"""Импорт лексики/грамматики активной темы курса в spaced-repetition Fluent."""
import json
from datetime import datetime, timedelta
from pathlib import Path


def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def date_str(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


def today_str() -> str:
    return date_str(datetime.now())


def tomorrow(s: str) -> str:
    return date_str(parse_date(s) + timedelta(days=1))


def date_plus_days(s: str, n: int) -> str:
    return date_str(parse_date(s) + timedelta(days=n))


def load_manifest(course_dir: Path) -> dict:
    return json.loads((course_dir / "curriculum.json").read_text(encoding="utf-8"))


def active_unit(manifest: dict) -> dict:
    actives = [u for u in manifest["units"] if u.get("status") == "active"]
    if len(actives) != 1:
        raise ValueError(f"expected exactly 1 active unit, got {len(actives)}")
    return actives[0]


def unit_prefix(course: str, unit_id: str) -> str:
    # "thema_8" -> "8"; устойчивый префикс для idempotency + фильтра гейта
    num = unit_id.split("_")[-1]
    return f"{course}_t{num}_"
```

- [ ] **Step 4: Create the Link manifest**

```json
// link/curriculum.json
{
  "course": "link",
  "units": [
    {
      "id": "thema_8",
      "grammar_file": "grammatica_thema08_in_mijn_buurt.md",
      "grammar_modules": "all",
      "status": "active"
    },
    {
      "id": "thema_9",
      "grammar_file": "grammatica_thema09_is_dat_wel_veilig.md",
      "grammar_modules": "all",
      "status": "locked"
    },
    {
      "id": "thema_10",
      "grammar_file": "grammatica_thema10_wat_koop_je.md",
      "grammar_modules": "all",
      "status": "locked"
    },
    {
      "id": "thema_11",
      "grammar_file": "grammatica_thema11_wat_gaan_we_doen.md",
      "grammar_modules": "all",
      "status": "locked"
    },
    {
      "id": "thema_12",
      "grammar_file": "grammatica_thema12_op_de_basisschool.md",
      "grammar_modules": "all",
      "status": "locked"
    }
  ]
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd scripts && python3 test_fluent_import.py` Expected: PASS — `5 passed`

- [ ] **Step 6: Commit**

```bash
git add scripts/fluent_import.py scripts/test_fluent_import.py link/curriculum.json
git commit -m "feat(fluent): scaffold curriculum-bridge importer + Link manifest"
```

---

### Task 2: Парсер лексики → карточки

**Files:**

- Modify: `scripts/fluent_import.py`
- Test: `scripts/test_fluent_import.py`

**Interfaces:**

- Consumes: `unit_prefix`.
- Produces:
  - `slug(text: str) -> str`
  - `parse_woordenlijst(anki_path: Path) -> list[tuple[str, str]]` — список
    `(word, translation)` без header-строк.
  - `vocab_items(course: str, unit: dict, course_dir: Path) -> list[dict]` —
    карточки Fluent
    (`item_id, item_type="vocabulary", content, answer, category, priority`).
    Читает все `*woordenlijst*thema{N}*_anki.txt` темы.

- [ ] **Step 1: Write the failing test**

```python
def test_slug():
    assert fi.slug("de buurt") == "de-buurt"
    assert fi.slug("'s morgens") == "s-morgens"


def test_parse_woordenlijst():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "woordenlijst_thema8_taak1_anki.txt"
        p.write_text(
            "#separator:tab\n#html:true\n#tags column:5\n"
            "de buurt\tIk woon in de buurt.\tрайон\tЯ живу в районе.\tlink::thema8\n"
            "lopen\tIk loop.\tходить\tЯ хожу.\tlink::thema8\n",
            encoding="utf-8")
        rows = fi.parse_woordenlijst(p)
        assert rows == [("de buurt", "район"), ("lopen", "ходить")]


def test_vocab_items():
    with tempfile.TemporaryDirectory() as d:
        unit_dir = Path(d) / "thema_8" / "taak_1"
        unit_dir.mkdir(parents=True)
        (unit_dir / "woordenlijst_thema8_taak1_anki.txt").write_text(
            "#separator:tab\n"
            "de buurt\tIk woon in de buurt.\tрайон\tЯ живу.\tlink::thema8\n",
            encoding="utf-8")
        unit = {"id": "thema_8", "status": "active"}
        items = fi.vocab_items("link", unit, Path(d))
        assert len(items) == 1
        it = items[0]
        assert it["item_id"] == "link_t8_voc_taak1_de-buurt"
        assert it["item_type"] == "vocabulary"
        assert it["content"] == "de buurt"
        assert it["answer"] == "район"
        assert it["category"] == "link_thema8"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scripts && python3 test_fluent_import.py` Expected: FAIL —
`AttributeError: module 'fluent_import' has no attribute 'slug'`

- [ ] **Step 3: Write minimal implementation**

```python
import re

_HEADER = ("#separator", "#html", "#columns", "#tags", "#notetype")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def parse_woordenlijst(anki_path: Path) -> list:
    rows = []
    for line in anki_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        word = cols[0].strip()
        # колонки: Word | Example | Translation | TranslationExample | Tags
        translation = cols[2].strip() if len(cols) > 2 else (
            cols[1].strip() if len(cols) > 1 else "")
        if word:
            rows.append((word, translation))
    return rows


def _taak_from_name(name: str) -> str:
    m = re.search(r"taak(\d+)", name)
    return f"taak{m.group(1)}" if m else "taak0"


def vocab_items(course: str, unit: dict, course_dir: Path) -> list:
    num = unit["id"].split("_")[-1]
    prefix = unit_prefix(course, unit["id"])
    unit_dir = course_dir / unit["id"]
    items = []
    files = sorted(unit_dir.rglob(f"*woordenlijst*thema{num}*_anki.txt"))
    for f in files:
        taak = _taak_from_name(f.name)
        for word, translation in parse_woordenlijst(f):
            items.append({
                "item_id": f"{prefix}voc_{taak}_{slug(word)}",
                "item_type": "vocabulary",
                "content": word,
                "answer": translation,
                "category": f"{course}_thema{num}",
                "priority": "medium",
            })
    return items
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scripts && python3 test_fluent_import.py` Expected: PASS — `8 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/fluent_import.py scripts/test_fluent_import.py
git commit -m "feat(fluent): parse woordenlijst into vocabulary cards"
```

---

### Task 3: Парсер грамматики → cloze-карточки (ядро)

**Files:**

- Modify: `scripts/fluent_import.py`
- Test: `scripts/test_fluent_import.py`

**Interfaces:**

- Consumes: `unit_prefix`.
- Produces:
  - `parse_grammar_clozes(md_text: str, modules, prefix: str) -> tuple[list, list]`
    — `(items, skipped)`. `modules` = `"all"` или список номеров секций (строки
    вида `"2.1"`). `items` — карточки `grammar_rule`; `skipped` — список
    `"{section} {title}"` для модулей без жирных примеров.
  - `grammar_items(course, unit, gramatica_dir) -> tuple[list, list]` — читает
    `unit["grammar_file"]` из каталога грамматики, добавляет `category` и
    устойчивый `item_id`.

Правила парсинга:

- Секция = заголовок `## N.N Title` (regex `^##\s+(\d+\.\d+)\s+(.+)$`).
- Если `modules != "all"` и номер секции не в списке — пропустить (молча).
- Внутри секции искать блок `### Voorbeelden uit oefeningen` (до следующего
  `###`/`##`/конца).
- Каждый буллет `- ...` с `**жирным**`: бланкуется **первый** жирный фрагмент →
  `content = "<строка с ___> (<title>)"`, `answer = <жирный текст>`. Несколько
  жирных в строке — бланкуем только первый (детерминированно, цель грамматики
  обычно одна форма).
- `item_id = f"{prefix}gram_{section}_{idx}"`, `idx` — 1-based внутри секции.
- Секция без жирных примеров → в `skipped` (карточки не выдумываем).

- [ ] **Step 1: Write the failing test**

```python
GRAMMAR_SAMPLE = """# Thema X

## 2.1 Het werkwoord: ik, we + werkwoord

### Regel
| Persoon | Vorm |
|---|---|
| ik | **werk** |

### Voorbeelden uit oefeningen
- Ik **werk** in Rotterdam.
- We **werken** in Rotterdam.

## 3.1 Alleen een tabel

### Regel
| a | b |
|---|---|
"""


def test_parse_grammar_clozes_basic():
    items, skipped = fi.parse_grammar_clozes(GRAMMAR_SAMPLE, "all", "link_t8_")
    assert len(items) == 2
    first = items[0]
    assert first["item_id"] == "link_t8_gram_2.1_1"
    assert first["item_type"] == "grammar_rule"
    assert first["answer"] == "werk"
    assert first["content"] == "Ik ___ in Rotterdam. (Het werkwoord: ik, we + werkwoord)"
    # модуль 3.1 без жирных примеров — пропущен
    assert any("3.1" in s for s in skipped)


def test_parse_grammar_clozes_module_filter():
    items, skipped = fi.parse_grammar_clozes(GRAMMAR_SAMPLE, ["3.1"], "link_t8_")
    assert items == []  # 2.1 отфильтрован, 3.1 без примеров
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scripts && python3 test_fluent_import.py` Expected: FAIL —
`AttributeError: ... 'parse_grammar_clozes'`

- [ ] **Step 3: Write minimal implementation**

```python
_SECTION_RE = re.compile(r"^##\s+(\d+\.\d+)\s+(.+?)\s*$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _split_sections(md_text: str) -> list:
    """[(section_num, title, body_lines), ...] по заголовкам '## N.N Title'."""
    sections, cur = [], None
    for line in md_text.splitlines():
        m = _SECTION_RE.match(line)
        if m:
            cur = {"num": m.group(1), "title": m.group(2), "lines": []}
            sections.append(cur)
        elif cur is not None:
            cur["lines"].append(line)
    return sections


def _voorbeelden_lines(body_lines: list) -> list:
    """Буллеты блока 'Voorbeelden uit oefeningen' секции."""
    out, collecting = [], False
    for line in body_lines:
        s = line.strip()
        if s.startswith("###"):
            collecting = s.lower().startswith("### voorbeelden")
            continue
        if collecting and s.startswith("- "):
            out.append(s[2:].strip())
    return out


def parse_grammar_clozes(md_text: str, modules, prefix: str) -> tuple:
    items, skipped = [], []
    for sec in _split_sections(md_text):
        if modules != "all" and sec["num"] not in modules:
            continue
        examples = _voorbeelden_lines(sec["lines"])
        made = 0
        for ex in examples:
            m = _BOLD_RE.search(ex)
            if not m:
                continue
            answer = m.group(1)
            content = (ex[:m.start()] + "___" + ex[m.end():]).strip()
            made += 1
            items.append({
                "item_id": f"{prefix}gram_{sec['num']}_{made}",
                "item_type": "grammar_rule",
                "content": f"{content} ({sec['title']})",
                "answer": answer,
                "priority": "medium",
            })
        if made == 0:
            skipped.append(f"{sec['num']} {sec['title']}")
    return items, skipped


def grammar_items(course: str, unit: dict, gramatica_dir: Path) -> tuple:
    num = unit["id"].split("_")[-1]
    prefix = unit_prefix(course, unit["id"])
    md = (gramatica_dir / unit["grammar_file"]).read_text(encoding="utf-8")
    items, skipped = parse_grammar_clozes(md, unit.get("grammar_modules", "all"), prefix)
    for it in items:
        it["category"] = f"grammar_thema{num}"
    return items, skipped
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scripts && python3 test_fluent_import.py` Expected: PASS — `10 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/fluent_import.py scripts/test_fluent_import.py
git commit -m "feat(fluent): parse grammar bold examples into cloze cards"
```

---

### Task 4: Запись в spaced-repetition.json + перестройка очереди

**Files:**

- Modify: `scripts/fluent_import.py`
- Test: `scripts/test_fluent_import.py`

**Interfaces:**

- Consumes: `tomorrow`, `date_plus_days`.
- Produces:
  - `new_sr_item(item: dict, today: str) -> dict` — карточка с полями SM-2
    (`due_date=tomorrow(today)`, `interval_days=1`, `repetitions=0`,
    `easiness_factor=2.5`, `consecutive_*=0`, `mastery_level=0`,
    `total_reviews=0`, плюс `content/answer/category/priority/type/id`).
  - `add_items(sr: dict, items: list, today: str) -> int` — добавляет только
    новые `item_id`, возвращает число добавленных (idempotent).
  - `rebuild_queue(sr: dict, today: str) -> None` — зеркалит `update-db.py`.
  - `write_sr(sr: dict, sr_path: Path) -> None` — бэкап + атомарная запись.

- [ ] **Step 1: Write the failing test**

```python
def test_add_items_idempotent():
    sr = {"items": {}, "review_queue": {}, "metadata": {}}
    items = [{"item_id": "link_t8_voc_taak1_de-buurt", "item_type": "vocabulary",
              "content": "de buurt", "answer": "район", "category": "link_thema8",
              "priority": "medium"}]
    assert fi.add_items(sr, items, "2026-06-26") == 1
    assert fi.add_items(sr, items, "2026-06-26") == 0  # второй раз — 0
    it = sr["items"]["link_t8_voc_taak1_de-buurt"]
    assert it["due_date"] == "2026-06-27"
    assert it["easiness_factor"] == 2.5
    assert it["mastery_level"] == 0


def test_rebuild_queue_buckets():
    sr = {"items": {
        "a": {"due_date": "2026-06-25"},   # <= today
        "b": {"due_date": "2026-06-27"},   # tomorrow
        "c": {"due_date": "2026-06-30"},   # this_week
        "d": {"due_date": "2026-08-01"},   # later
    }, "review_queue": {}, "metadata": {}}
    fi.rebuild_queue(sr, "2026-06-26")
    q = sr["review_queue"]
    assert q["today"] == ["a"]
    assert q["tomorrow"] == ["b"]
    assert q["this_week"] == ["c"]
    assert q["later"] == ["d"]
    assert sr["metadata"]["total_items_tracked"] == 4


def test_write_sr_backs_up_and_writes():
    with tempfile.TemporaryDirectory() as d:
        sr_path = Path(d) / "spaced-repetition.json"
        sr_path.write_text(json.dumps({"items": {}, "metadata": {}}))
        fi.write_sr({"items": {"x": {}}, "metadata": {}}, sr_path)
        assert json.loads(sr_path.read_text())["items"] == {"x": {}}
        backups = list((Path(d) / ".backups").rglob("spaced-repetition.json"))
        assert len(backups) == 1  # старая версия сохранена
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scripts && python3 test_fluent_import.py` Expected: FAIL —
`AttributeError: ... 'add_items'`

- [ ] **Step 3: Write minimal implementation**

```python
import shutil


def new_sr_item(item: dict, today: str) -> dict:
    return {
        "id": item["item_id"],
        "type": item.get("item_type", "vocabulary"),
        "content": item.get("content", ""),
        "answer": item.get("answer", ""),
        "category": item.get("category", ""),
        "difficulty": "",
        "created_date": today,
        "due_date": tomorrow(today),
        "interval_days": 1,
        "repetitions": 0,
        "easiness_factor": 2.5,
        "consecutive_correct": 0,
        "consecutive_incorrect": 0,
        "last_reviewed": today,
        "last_quality": 3,
        "mastery_level": 0,
        "total_reviews": 0,
        "priority": item.get("priority", "medium"),
    }


def add_items(sr: dict, items: list, today: str) -> int:
    store = sr.setdefault("items", {})
    added = 0
    for it in items:
        if it["item_id"] not in store:
            store[it["item_id"]] = new_sr_item(it, today)
            added += 1
    return added


def rebuild_queue(sr: dict, today: str) -> None:
    items = sr.setdefault("items", {})
    q = {"today": [], "tomorrow": [], "this_week": [], "later": []}
    tom = tomorrow(today)
    week_end = date_plus_days(today, 7)
    for item_id, item in items.items():
        due = item.get("due_date", today)
        if due <= today:
            q["today"].append(item_id)
        elif due == tom:
            q["tomorrow"].append(item_id)
        elif due <= week_end:
            q["this_week"].append(item_id)
        else:
            q["later"].append(item_id)
    sr["review_queue"] = q
    sr.setdefault("metadata", {})["last_updated"] = today
    sr["metadata"]["total_items_tracked"] = len(items)


def write_sr(sr: dict, sr_path: Path) -> None:
    if sr_path.exists():
        backup_dir = sr_path.parent / ".backups" / f"pre-import-{today_str()}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sr_path, backup_dir / sr_path.name)
    tmp = sr_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(sr, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(sr_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scripts && python3 test_fluent_import.py` Expected: PASS — `13 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/fluent_import.py scripts/test_fluent_import.py
git commit -m "feat(fluent): idempotent SR write + queue rebuild mirroring update-db"
```

---

### Task 5: Сборка импорта + CLI (`import` по умолчанию)

**Files:**

- Modify: `scripts/fluent_import.py`
- Test: `scripts/test_fluent_import.py`

**Interfaces:**

- Consumes: `load_manifest`, `active_unit`, `vocab_items`, `grammar_items`,
  `add_items`, `rebuild_queue`, `write_sr`, `today_str`.
- Produces:
  - `fluent_data_dir() -> Path` — `Path.home()/".claude"/"fluent-data"`.
  - `do_import(course: str, repo_root: Path, sr_path: Path, today: str) -> dict`
    — возвращает summary `{unit, vocab, grammar, added, skipped}`.
    `course_dir = repo_root/course`; грамматика из
    `repo_root/course/"gramatica"` для Link.
  - `main(argv=None)` — argparse: `--course` (required), `--check`, `--advance`.

Замечание: каталог грамматики Link — `link/gramatica` (буква как в репозитории).

- [ ] **Step 1: Write the failing test**

```python
def _make_repo(d):
    root = Path(d)
    (root / "link" / "thema_8" / "taak_1").mkdir(parents=True)
    (root / "link" / "gramatica").mkdir(parents=True)
    (root / "link" / "thema_8" / "taak_1" /
     "woordenlijst_thema8_taak1_anki.txt").write_text(
        "#separator:tab\nde buurt\tIk woon in de buurt.\tрайон\tЯ живу.\tt\n",
        encoding="utf-8")
    (root / "link" / "gramatica" / "grammatica_thema08_in_mijn_buurt.md").write_text(
        "## 1.1 Test\n\n### Voorbeelden uit oefeningen\n- Ik **werk** hier.\n",
        encoding="utf-8")
    (root / "link" / "curriculum.json").write_text(json.dumps({
        "course": "link", "units": [
            {"id": "thema_8", "grammar_file": "grammatica_thema08_in_mijn_buurt.md",
             "grammar_modules": "all", "status": "active"}]}), encoding="utf-8")
    return root


def test_do_import_end_to_end_and_idempotent():
    with tempfile.TemporaryDirectory() as d:
        root = _make_repo(d)
        sr_path = root / "spaced-repetition.json"
        sr_path.write_text(json.dumps({"items": {}, "metadata": {}}))
        s1 = fi.do_import("link", root, sr_path, "2026-06-26")
        assert s1["vocab"] == 1 and s1["grammar"] == 1 and s1["added"] == 2
        sr = json.loads(sr_path.read_text())
        assert "link_t8_voc_taak1_de-buurt" in sr["items"]
        assert "link_t8_gram_1.1_1" in sr["items"]
        assert sr["review_queue"]["tomorrow"]  # due завтра
        s2 = fi.do_import("link", root, sr_path, "2026-06-26")
        assert s2["added"] == 0  # idempotent
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scripts && python3 test_fluent_import.py` Expected: FAIL —
`AttributeError: ... 'do_import'`

- [ ] **Step 3: Write minimal implementation**

```python
import argparse


def fluent_data_dir() -> Path:
    return Path.home() / ".claude" / "fluent-data"


def do_import(course: str, repo_root: Path, sr_path: Path, today: str) -> dict:
    course_dir = repo_root / course
    manifest = load_manifest(course_dir)
    unit = active_unit(manifest)
    vocab = vocab_items(course, unit, course_dir)
    grammar, skipped = grammar_items(course, unit, course_dir / "gramatica")
    sr = json.loads(sr_path.read_text(encoding="utf-8"))
    added = add_items(sr, vocab + grammar, today)
    rebuild_queue(sr, today)
    write_sr(sr, sr_path)
    return {"unit": unit["id"], "vocab": len(vocab), "grammar": len(grammar),
            "added": added, "skipped": skipped}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Curriculum → Fluent bridge")
    ap.add_argument("--course", required=True)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--advance", action="store_true")
    args = ap.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    sr_path = fluent_data_dir() / "spaced-repetition.json"
    today = today_str()

    if args.check:
        print(check(args.course, repo_root, sr_path)["report"])
        return
    if args.advance:
        s = advance(args.course, repo_root, sr_path, today)
        print(f"→ active: {s['unit']} | added {s['added']}")
        return
    s = do_import(args.course, repo_root, sr_path, today)
    print(f"Импорт {s['unit']}: лексика {s['vocab']}, грамматика {s['grammar']}, "
          f"новых {s['added']}")
    if s["skipped"]:
        print("Пропущены модули без жирных примеров: " + "; ".join(s["skipped"]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scripts && python3 test_fluent_import.py` Expected: PASS — `14 passed`

(`main` ещё ссылается на `check`/`advance` из Task 6–7 — это в порядке: они
вызываются только в соответствующих ветках CLI, тест их не трогает. Если запуск
CLI до Task 7 нужен — используй только импорт по умолчанию.)

- [ ] **Step 5: Commit**

```bash
git add scripts/fluent_import.py scripts/test_fluent_import.py
git commit -m "feat(fluent): wire do_import + CLI default import mode"
```

---

### Task 6: Гейт `--check`

**Files:**

- Modify: `scripts/fluent_import.py`
- Test: `scripts/test_fluent_import.py`

**Interfaces:**

- Consumes: `load_manifest`, `active_unit`, `unit_prefix`.
- Produces:
  - `check(course: str, repo_root: Path, sr_path: Path) -> dict` — возвращает
    `{unit, total, mastered, red, ready (bool), report (str)}`. Порог:
    `mastered/total >= 0.80 and red == 0` (при `total == 0` → `ready=False`).

- [ ] **Step 1: Write the failing test**

```python
def _sr_with(items):
    return {"items": items, "review_queue": {}, "metadata": {}}


def test_check_ready():
    with tempfile.TemporaryDirectory() as d:
        root = _make_repo(d)
        sr_path = root / "spaced-repetition.json"
        items = {f"link_t8_voc_x{i}": {"mastery_level": 3,
                 "consecutive_incorrect": 0} for i in range(8)}
        items.update({f"link_t8_voc_y{i}": {"mastery_level": 1,
                      "consecutive_incorrect": 0} for i in range(2)})
        sr_path.write_text(json.dumps(_sr_with(items)))
        v = fi.check("link", root, sr_path)
        assert v["total"] == 10 and v["mastered"] == 8 and v["red"] == 0
        assert v["ready"] is True


def test_check_blocked_by_red():
    with tempfile.TemporaryDirectory() as d:
        root = _make_repo(d)
        sr_path = root / "spaced-repetition.json"
        items = {f"link_t8_voc_x{i}": {"mastery_level": 3,
                 "consecutive_incorrect": 0} for i in range(9)}
        items["link_t8_voc_bad"] = {"mastery_level": 3, "consecutive_incorrect": 2}
        sr_path.write_text(json.dumps(_sr_with(items)))
        v = fi.check("link", root, sr_path)
        assert v["red"] == 1 and v["ready"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scripts && python3 test_fluent_import.py` Expected: FAIL —
`AttributeError: ... 'check'`

- [ ] **Step 3: Write minimal implementation**

```python
MASTERY_THRESHOLD = 0.80


def check(course: str, repo_root: Path, sr_path: Path) -> dict:
    manifest = load_manifest(repo_root / course)
    unit = active_unit(manifest)
    prefix = unit_prefix(course, unit["id"])
    sr = json.loads(sr_path.read_text(encoding="utf-8"))
    unit_items = [it for i, it in sr.get("items", {}).items() if i.startswith(prefix)]
    total = len(unit_items)
    mastered = sum(1 for it in unit_items if it.get("mastery_level", 0) >= 3)
    red = sum(1 for it in unit_items if it.get("consecutive_incorrect", 0) >= 2)
    pct = (mastered / total) if total else 0.0
    ready = total > 0 and pct >= MASTERY_THRESHOLD and red == 0
    mark = "✅ готов дальше — запусти --advance" if ready else "⏳ продолжай"
    report = (f"{unit['id']} — {total} карточек | mastery≥3: {mastered}/{total} "
              f"({pct:.0%}) | красных: {red}\n{mark}")
    return {"unit": unit["id"], "total": total, "mastered": mastered,
            "red": red, "ready": ready, "report": report}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scripts && python3 test_fluent_import.py` Expected: PASS — `16 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/fluent_import.py scripts/test_fluent_import.py
git commit -m "feat(fluent): --check mastery gate by item_id prefix"
```

---

### Task 7: Переход `--advance`

**Files:**

- Modify: `scripts/fluent_import.py`
- Test: `scripts/test_fluent_import.py`

**Interfaces:**

- Consumes: `load_manifest`, `active_unit`, `do_import`.
- Produces:
  - `save_manifest(course_dir: Path, manifest: dict) -> None` — атомарная запись
    `curriculum.json`.
  - `advance(course: str, repo_root: Path, sr_path: Path, today: str) -> dict` —
    активный юнит → `done`, следующий по порядку (`locked`) → `active`,
    сохраняет manifest, импортирует новый юнит. Бросает `ValueError`, если
    активный — последний (`course complete`).

- [ ] **Step 1: Write the failing test**

```python
def test_advance_moves_pointer_and_imports():
    with tempfile.TemporaryDirectory() as d:
        root = _make_repo(d)
        # добавим thema_9, чтобы было куда переходить
        (root / "link" / "thema_9" / "taak_1").mkdir(parents=True)
        (root / "link" / "thema_9" / "taak_1" /
         "woordenlijst_thema9_taak1_anki.txt").write_text(
            "#separator:tab\nde straat\tIk loop.\tулица\tЯ.\tt\n", encoding="utf-8")
        (root / "link" / "gramatica" / "grammatica_thema09_x.md").write_text(
            "## 1.1 T\n\n### Voorbeelden uit oefeningen\n- Ik **ga** weg.\n",
            encoding="utf-8")
        m = json.loads((root / "link" / "curriculum.json").read_text())
        m["units"].append({"id": "thema_9", "grammar_file": "grammatica_thema09_x.md",
                           "grammar_modules": "all", "status": "locked"})
        (root / "link" / "curriculum.json").write_text(json.dumps(m))
        sr_path = root / "spaced-repetition.json"
        sr_path.write_text(json.dumps({"items": {}, "metadata": {}}))

        s = fi.advance("link", root, sr_path, "2026-06-26")
        assert s["unit"] == "thema_9"
        m2 = json.loads((root / "link" / "curriculum.json").read_text())
        st = {u["id"]: u["status"] for u in m2["units"]}
        assert st == {"thema_8": "done", "thema_9": "active"}
        assert "link_t9_voc_taak1_de-straat" in json.loads(sr_path.read_text())["items"]


def test_advance_at_last_unit_raises():
    with tempfile.TemporaryDirectory() as d:
        root = _make_repo(d)  # единственный юнит thema_8 = active
        sr_path = root / "spaced-repetition.json"
        sr_path.write_text(json.dumps({"items": {}, "metadata": {}}))
        try:
            fi.advance("link", root, sr_path, "2026-06-26")
            assert False, "expected ValueError"
        except ValueError:
            pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scripts && python3 test_fluent_import.py` Expected: FAIL —
`AttributeError: ... 'advance'`

- [ ] **Step 3: Write minimal implementation**

```python
def save_manifest(course_dir: Path, manifest: dict) -> None:
    tmp = course_dir / "curriculum.json.tmp"
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(course_dir / "curriculum.json")


def advance(course: str, repo_root: Path, sr_path: Path, today: str) -> dict:
    course_dir = repo_root / course
    manifest = load_manifest(course_dir)
    units = manifest["units"]
    idx = next(i for i, u in enumerate(units) if u.get("status") == "active")
    if idx + 1 >= len(units):
        raise ValueError("course complete — нет следующего юнита")
    units[idx]["status"] = "done"
    units[idx + 1]["status"] = "active"
    save_manifest(course_dir, manifest)
    return do_import(course, repo_root, sr_path, today)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scripts && python3 test_fluent_import.py` Expected: PASS — `18 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/fluent_import.py scripts/test_fluent_import.py
git commit -m "feat(fluent): --advance moves curriculum pointer and imports"
```

---

### Task 8: Документация и реальный прогон

**Files:**

- Modify: `scripts/README.md`
- Modify: `CLAUDE.md` (раздел про Fluent-bridge, кратко)

**Interfaces:** none (docs + ручной прогон).

- [ ] **Step 1: Прогнать тесты целиком**

Run: `cd scripts && python3 test_fluent_import.py` Expected: PASS — `18 passed`

- [ ] **Step 2: Реальный dry-сценарий на Link thema 8**

Run:

```bash
python3 scripts/fluent_import.py --course link        # импорт активной темы
python3 scripts/fluent_import.py --course link --check # должно показать статистику
```

Expected: импорт сообщает число лексики/грамматики; `--check` печатает строку
вида `thema_8 — N карточек | mastery≥3: 0/N (0%) | красных: 0` (свежий импорт →
ещё ничего не освоено).

- [ ] **Step 3: Дописать `scripts/README.md`**

Добавить раздел `fluent_import.py` с тремя командами (`import` / `--check` /
`--advance`), форматом `curriculum.json`, правилом «пишет только
spaced-repetition.json, бэкап в `.backups/`», и порогом перехода 80% / 0
красных.

- [ ] **Step 4: Добавить краткий раздел в `CLAUDE.md`**

В секцию про Anki/Fluent добавить: как Link/De Opmaat питают Fluent-повторение
через `scripts/fluent_import.py`, что прогресс по темам живёт в
`<course>/curriculum.json`, а SM-2 владеет расписанием.

- [ ] **Step 5: Commit**

```bash
git add scripts/README.md CLAUDE.md
git commit -m "docs(fluent): document curriculum-bridge importer + manifest"
```

---

## Self-Review

**1. Spec coverage:**

- Последовательность → manifest + `active_unit` (Task 1) ✅
- Сигнал перехода → `--check` порог 80%/0 красных (Task 6) ✅
- Fluent владеет SR → импортёр только сеет items + очередь, SM-2 не трогаем
  (Task 4) ✅
- `new_vocabulary[]`/индексы → `parse_woordenlijst`/`vocab_items` (Task 2) ✅
  (примечание: пишем формат item напрямую в SR — те же поля, что у
  `new_vocabulary[]`, без побочных эффектов сессии; решение из спеки «известный
  нюанс»)
- Подключаемые модули грамматики → `grammar_modules` + `parse_grammar_clozes`
  (Task 3) ✅
- Рециклинг бесплатно → SM-2 в Fluent, импорт идемпотентен (Task 4) ✅
- Бэкап перед записью → `write_sr` (Task 4) ✅
- Унифицированный префикс → `unit_prefix`, проверен в Task 2/3/6 ✅
- Ручной переход → `--advance` отдельной командой (Task 7) ✅

**2. Placeholder scan:** заглушек нет; весь код и тесты приведены целиком.

**3. Type consistency:** имена сверены между задачами — `add_items`,
`rebuild_queue`, `write_sr`, `do_import`, `check`, `advance`, `vocab_items`,
`grammar_items`, `parse_grammar_clozes(md_text, modules, prefix)`,
`unit_prefix(course, unit_id)`. Префикс `{course}_t{N}_` един для лексики
(`…voc…`) и грамматики (`…gram…`), поэтому фильтр гейта ловит обе группы.

**Известное ограничение (зафиксировано в спеке):** бланкуется только первый
жирный фрагмент в строке-примере; модули без жирных примеров пропускаются и
печатаются в отчёте импорта — карточки на пустом месте не создаём.
