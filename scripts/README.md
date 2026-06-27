# Scripts

Утилиты для автоматизации создания учебных материалов.

---

## audio_to_anki.py

Автоматическая нарезка аудио диалогов на отдельные предложения и генерация Anki
карточек с аутентичной озвучкой.

### Назначение

Превращает учебный аудиофайл (диалог, упражнение) в набор Anki карточек, где
каждое предложение = 1 карточка с оригинальным аудио из учебника.

---

## Быстрый старт

### Рекомендуемый режим: Forced Alignment (с транскрипцией)

```bash
# Точные границы предложений + чистый текст из MD файла
python3 scripts/audio_to_anki.py thema_7/2/h07_oefening_02.mp3 \
    --transcript thema_7/2/h07_oefening_02.md \
    --theme gezondheid \
    --copy-to-anki
```

### Простой режим: Whisper-only (без транскрипции)

```bash
# Сегментация по паузам (может давать неточные границы)
python3 scripts/audio_to_anki.py thema_7/2/h07_oefening_02.mp3 \
    --theme gezondheid \
    --copy-to-anki
```

После выполнения:

1. Заполни переводы в `sententiae_gezondheid_anki.txt`
2. Импортируй в Anki: File → Import

---

## Зависимости

### Установка (один раз)

```bash
# FFmpeg — нарезка аудио
brew install ffmpeg

# OpenAI Whisper — распознавание речи
pip install openai-whisper
```

### Проверка установки

```bash
ffmpeg -version    # Должна показать версию
whisper --help     # Должна показать справку
```

---

## Как это работает

### Два режима работы

| Режим                                   | Когда использовать   | Результат                                   |
| --------------------------------------- | -------------------- | ------------------------------------------- |
| **Forced Alignment** (с `--transcript`) | Есть MD транскрипция | Точные границы предложений, чистый текст    |
| **Whisper-only** (без `--transcript`)   | Нет транскрипции     | Границы по паузам, возможны ошибки в тексте |

### Архитектура: Forced Alignment (рекомендуется)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FORCED ALIGNMENT PIPELINE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐ │
│  │  MP3 +   │   │   WHISPER    │   │   ALIGNMENT  │   │     OUTPUT       │ │
│  │  MD file │──▶│  word-level  │──▶│   (difflib)  │──▶│  Точные границы  │ │
│  │          │   │  timestamps  │   │              │   │  предложений     │ │
│  └──────────┘   └──────────────┘   └──────────────┘   └──────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Архитектура: Whisper-only (простой режим)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           WHISPER-ONLY PIPELINE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐    ┌───────────┐    ┌──────────┐    ┌──────────────────┐ │
│  │  INPUT   │    │  WHISPER  │    │  FFMPEG  │    │     OUTPUT       │ │
│  │  MP3     │───▶│  (ASR)    │───▶│  (split) │───▶│  Anki cards +    │ │
│  │  file    │    │           │    │          │    │  audio segments  │ │
│  └──────────┘    └───────────┘    └──────────┘    └──────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Пошаговый процесс

| Шаг | Компонент       | Что делает                  | Результат                      |
| --- | --------------- | --------------------------- | ------------------------------ |
| 1   | **Whisper**     | Распознаёт голландскую речь | JSON с текстом + таймстемпы    |
| 2   | **FFmpeg**      | Нарезает MP3 по таймстемпам | Отдельные MP3 для каждой фразы |
| 3   | **Генератор**   | Создаёт Anki import файл    | TSV файл с карточками          |
| 4   | **Копирование** | Переносит в Anki media      | Аудио готово к использованию   |

### Детали реализации

**Whisper:**

- Модель: `base` (оптимально для учебного аудио)
- Язык: Dutch (нидерландский)
- Выход: JSON с сегментами `{start, end, text}`

**FFmpeg:**

- Кодек: libmp3lame (качество 2)
- Padding: -0.1s до начала, +0.2s после конца
- Формат имени: `{prefix}_sentence_{NNN}.mp3`

**Anki файл:**

- Формат: TSV (tab-separated values)
- Поля: Dutch | Russian | Audio | Tags
- Теги: `sententiae::{theme}::{level}::audio`

---

## Параметры командной строки

```bash
python3 scripts/audio_to_anki.py [audio] [options]
```

### Обязательные

| Параметр | Описание         | Пример                          |
| -------- | ---------------- | ------------------------------- |
| `audio`  | Путь к MP3 файлу | `thema_7/2/h07_oefening_02.mp3` |

### Опциональные

| Параметр         | Описание                | По умолчанию | Пример       |
| ---------------- | ----------------------- | ------------ | ------------ |
| `--transcript`   | MD файл с транскрипцией | -            | `trans.md`   |
| `--theme`        | Тема для тегов Anki     | `general`    | `gezondheid` |
| `--level`        | Уровень CEFR            | `A2`         | `A1`, `B1`   |
| `--copy-to-anki` | Копировать аудио в Anki | выключено    | флаг         |

### Справка

```bash
python3 scripts/audio_to_anki.py --help
```

---

## Формат MD транскрипции

Для режима Forced Alignment нужен MD файл в формате `Speaker: текст`.

### Требования

- Каждая реплика на **одной строке**
- Формат: `Speaker: полный текст реплики`
- Пустые строки между репликами (для читаемости)
- Заголовки `#` игнорируются

### Пример

```markdown
# 2 Luisteren

Mila: Hoi schat, lekker getennist?

Willem: Niet echt. Het eerste half uur heb ik heerlijk gespeeld, maar toen
maakte ik een verkeerde beweging.

Willem: Nu heb ik zo'n pijn aan mijn linkerenkel. Volgens mij is hij dikker.

Mila: Doe je sokken eens even uit. Ja inderdaad, deze enkel is dikker dan de
andere.
```

### Важно

- Если реплика длинная — всё равно **одна строка**
- Текст из MD используется в карточках (без ошибок Whisper)
- Whisper нужен только для **таймстампов**, не для текста

---

## Выходные файлы

### Структура после выполнения

```
thema_7/2/
├── h07_oefening_02.mp3                    # Исходный файл (не изменяется)
├── h07_oefening_02.json                   # Whisper output
│                                          # (таймстемпы для отладки)
├── h07_oefening_02_sentences/             # Нарезанные аудио
│   ├── h07_oefening_02_sentence_001.mp3   # "Hoi schat, lekker getennist?"
│   ├── h07_oefening_02_sentence_002.mp3   # "Niet echt."
│   ├── h07_oefening_02_sentence_003.mp3   # "Het eerste half uur..."
│   └── ... (по количеству сегментов)
│
└── sententiae_gezondheid_anki.txt         # Anki import файл
```

### Формат Anki файла

```
#separator:tab
#html:true
#tags column:4

Hoi schat, lekker getennist?	[TODO: перевод]	[sound:h07_oefening_02_sentence_001.mp3]	sententiae::gezondheid::A2::audio
Niet echt.	[TODO: перевод]	[sound:h07_oefening_02_sentence_002.mp3]	sententiae::gezondheid::A2::audio
```

### Anki media folder

При использовании `--copy-to-anki` файлы копируются в:

```
~/Library/Application Support/Anki2/{profile}/collection.media/
```

Скрипт автоматически находит профиль:

- Если профиль один — использует его
- Если несколько — использует первый + предупреждение

---

## Примеры использования

### Базовый (без автокопирования)

```bash
python3 scripts/audio_to_anki.py thema_7/2/h07_oefening_02.mp3 --theme gezondheid
```

Затем вручную:

```bash
cp thema_7/2/h07_oefening_02_sentences/*.mp3 \
   ~/Library/Application\ Support/Anki2/alex/collection.media/
```

### Рекомендуемый (с автокопированием)

```bash
python3 scripts/audio_to_anki.py thema_7/2/h07_oefening_02.mp3 \
    --theme gezondheid \
    --copy-to-anki
```

### Разные темы

```bash
# Thema 7: Gezondheid (здоровье)
python3 scripts/audio_to_anki.py thema_7/2/h07_oefening_02.mp3 --theme gezondheid --copy-to-anki

# Thema 6: Wonen (жильё)
python3 scripts/audio_to_anki.py thema_6/audio.mp3 --theme wonen --copy-to-anki

# Thema 5: Werk (работа), уровень B1
python3 scripts/audio_to_anki.py thema_5/dialog.mp3 --theme werk --level B1 --copy-to-anki
```

---

## Постобработка

### 1. Корректировка текста (опционально)

Whisper модель `base` может ошибаться в:

- Медицинских терминах (`fysiotherapeut` → `visu-terap`)
- Именах собственных (`Notenbomenlaan` → `noot een wonenlaan`)
- Разговорных формах (`schat` → `schap`)

**Решение:** Сравни с оригинальной транскрипцией и исправь в txt файле.

### 2. Добавление переводов

Открой `sententiae_{theme}_anki.txt` и замени `[TODO: перевод]`:

```
Hoi schat, lekker getennist?	Привет, дорогой, хорошо поиграл в теннис?	[sound:...]	...
```

### 3. Импорт в Anki

1. File → Import
2. Выбери `sententiae_{theme}_anki.txt`
3. Настрой поля:
   - Field 1 → Front
   - Field 2 → Back
   - Field 3 → Audio
   - Field 4 → Tags

### 4. Настройка карточки (один раз)

**Tools → Manage Note Types → [твой тип] → Cards**

Front Template:

```html
{{Front}} {{Audio}}
```

Back Template:

```html
{{FrontSide}}
<hr id="answer" />
{{Back}}
```

---

## Troubleshooting

| Проблема                     | Причина                   | Решение                                         |
| ---------------------------- | ------------------------- | ----------------------------------------------- |
| `whisper: command not found` | Whisper не установлен     | `pip install openai-whisper`                    |
| `ffmpeg: command not found`  | FFmpeg не установлен      | `brew install ffmpeg`                           |
| Аудио не играет в Anki       | Файлы не в media folder   | Используй `--copy-to-anki` или скопируй вручную |
| Anki media folder не найден  | Anki не запускался        | Запусти Anki хотя бы раз                        |
| Границы сегментов неточные   | Whisper режет по паузам   | **Используй `--transcript` с MD файлом**        |
| Ошибки в тексте карточек     | Whisper неточно распознал | **Используй `--transcript` с MD файлом**        |
| `Не удалось найти: '...'`    | Alignment не нашёл текст  | Проверь что текст в MD соответствует аудио      |

### Проверка Anki media

В Anki: **Tools → Check Media**

Покажет:

- Отсутствующие файлы (referenced but missing)
- Лишние файлы (in media but unused)

---

## Технические детали

### Поддерживаемые платформы

| ОС      | Путь к Anki                            |
| ------- | -------------------------------------- |
| macOS   | `~/Library/Application Support/Anki2/` |
| Linux   | `~/.local/share/Anki2/`                |
| Windows | `%APPDATA%\Anki2\`                     |

### Whisper модели

| Модель   | Размер  | Скорость       | Качество | Рекомендация             |
| -------- | ------- | -------------- | -------- | ------------------------ |
| `tiny`   | 39 MB   | Очень быстро   | Низкое   | Для тестов               |
| `base`   | 74 MB   | Быстро         | Хорошее  | **По умолчанию**         |
| `small`  | 244 MB  | Средне         | Лучше    | Если base не справляется |
| `medium` | 769 MB  | Медленно       | Отличное | Для сложного аудио       |
| `large`  | 1550 MB | Очень медленно | Лучшее   | Для критичных задач      |

### Изменение модели

В файле `audio_to_anki.py`, строка ~104:

```python
"--model",
"base",  # Изменить на: small, medium, large
```

---

## Альтернативы

Если Whisper не подходит:

| Инструмент                | Плюсы                        | Минусы                    |
| ------------------------- | ---------------------------- | ------------------------- |
| **Aeneas**                | Использует ТВОЮ транскрипцию | Требует подготовки текста |
| **Audacity**              | Точный контроль              | Долго, ручная работа      |
| **Google Speech-to-Text** | Хорошее качество             | Платный API               |

---

## fluent_import.py

Мост между учебными материалами (Link/De Opmaat) и базой интервального повторения
Fluent. Читает активную тему курса, извлекает лексику и грамматику, записывает
карточки в `~/.claude/fluent-data/spaced-repetition.json`. SM-2-расписание
ведёт сам Fluent — импортёр только сеет новые items и пересчитывает очередь.

### Зависимости

Только стандартная библиотека Python 3 — сторонних пакетов не нужно.

### Три режима

```bash
# Импорт активной темы (лексика + грамматика) в Fluent
python3 scripts/fluent_import.py --course link

# Проверка готовности к переходу (mastery gate)
python3 scripts/fluent_import.py --course link --check

# Перевести курс на следующую тему и сразу импортировать её
python3 scripts/fluent_import.py --course link --advance

# Фокус на конкретной теме БЕЗ сдвига указателя прогресса
python3 scripts/fluent_import.py --course link --thema 5
python3 scripts/fluent_import.py --course link --thema 5 --taak 2  # только taak 2
python3 scripts/fluent_import.py --course link --check --thema 5   # её mastery
```

### Параметры

| Параметр    | Описание                                          |
| ----------- | ------------------------------------------------- |
| `--course`  | Имя курса — папка в корне репо (`link` и др.)     |
| `--check`   | Показать статистику mastery без изменений         |
| `--advance` | Пометить активную тему `done`, активировать       |
|             | следующую, импортировать её                       |
| `--thema N` | Импорт/проверка темы N **без** сдвига указателя   |
| `--taak N`  | Сузить лексику до одной taak (грамматика — вся)    |

### Формат curriculum.json

Файл `<course>/curriculum.json` описывает последовательность тем и текущую
позицию в курсе:

```json
{
  "units": [
    {
      "id": "thema_8",
      "status": "active",
      "grammar_file": "grammatica_thema08_in_mijn_buurt.md",
      "grammar_modules": ["2.1", "2.11"]
    },
    {
      "id": "thema_9",
      "status": "locked",
      "grammar_file": "grammatica_thema09_is_dat_wel_veilig.md",
      "grammar_modules": "all"
    }
  ]
}
```

| Поле              | Значения                        | Описание                                  |
| ----------------- | ------------------------------- | ----------------------------------------- |
| `status`          | `done` / `active` / `locked`    | Ровно одна тема — `active` в любой момент |
| `grammar_modules` | `"all"` или список `["8.1", …]` | Какие разделы грамматики включить         |
| `grammar_file`    | имя файла грамматики             | Markdown с разделами `## N.N Заголовок`   |

### Что и откуда берётся

**Лексика** — из файлов `*woordenlijst*thema{N}*_anki.txt` в папке темы
(5-колоночный TSV: Word | Example | Translation | TranslationExample | Tags).
Берётся колонка 1 (слово) и колонка 3 (перевод).

**Грамматика** — cloze-карточки из Markdown-файла `grammar_file` (голое имя
файла). Скрипт ищет его сначала в папке темы `link/thema_N/<grammar_file>`, а
если там нет — в общей папке `link/gramatica/<grammar_file>` (поддерживает обе
раскладки). Внутри файла берутся разделы
`## N.N Заголовок → ### Voorbeelden uit oefeningen → буллеты`. Первый **жирный**
фрагмент в буллете становится пробелом (`___`), остальной текст — вопросом.
Разделы без жирных примеров пропускаются и сообщаются в stdout.

### Идентификаторы карточек

Формат `item_id` устойчив и уникален — импорт идемпотентен:

```
link_t8_voc_taak2_het-stokbrood      # лексика
link_t8_gram_8.1_1                    # грамматика (раздел 8.1, пример 1)
```

Фильтр гейта и `--advance` используют префикс `{course}_t{N}_` чтобы
изолировать карточки одной темы.

> **Внимание (грамматика):** `item_id` грамматики позиционный
> (`gram_{раздел}_{номер}`). Если после импорта вставить новый **жирный** пример
> в середину раздела, последующие примеры перенумеруются — старые карточки
> «осиротеют» (останутся в повторении), а сдвинутые добавятся заново. Правь
> грамматику до импорта темы. Лексика этому не подвержена (id по слову).

### Запись в Fluent и бэкап

Скрипт пишет **только** `~/.claude/fluent-data/spaced-repetition.json`.
Перед каждой записью создаётся бэкап:

```
~/.claude/fluent-data/.backups/pre-import-YYYY-MM-DD-HHMMSS/spaced-repetition.json
```

Запись атомарна: сначала `spaced-repetition.json.<pid>.tmp`, затем rename.

### Mastery gate (--check / --advance)

Тема считается освоенной и готовой к переходу при одновременном выполнении двух
условий:

| Условие                   | Порог                                     |
| ------------------------- | ----------------------------------------- |
| Карточки с `mastery_level ≥ 3` | ≥ 80% от всех карточек темы          |
| «Красные» карточки        | 0 (`consecutive_incorrect ≥ 2` → красная) |

`--check` печатает строку вида:

```
thema_8 — 42 карточки | mastery≥3: 38/42 (90.5%) | красных: 0
✅ готов дальше — запусти --advance
```

Если порог не достигнут — `⏳ продолжай`.

### Тесты

```bash
cd scripts && python3 test_fluent_import.py
# Ожидается: 21 passed
```
