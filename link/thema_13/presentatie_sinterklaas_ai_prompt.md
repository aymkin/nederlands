# Промпт для ChatGPT / Gemini — PDF-презентация с картинками

**Как пользоваться:** скопируй всё, что ниже линии, одним куском и вставь в
ChatGPT (нужен режим с генерацией изображений + code interpreter) или в Gemini.
Если модель не умеет отдавать PDF — попроси сначала PNG всех слайдов, потом
«собери их в один PDF».

**Почему промпт запрещает менять нидерландский:** текст уже проверен под уровень
A2 и под лексику курса Link. Если разрешить модели «улучшить» его, она с высокой
вероятностью подставит свои артикли и порядок слов — и ты выйдешь с чужими
ошибками к доценту.

---

Ты — дизайнер презентаций. Сделай мне PDF-презентацию из 8 слайдов, формат 16:9
(горизонтальный, 297 × 167 мм), и сгенерируй для неё иллюстрации.

## Железные правила

1. **НЕ МЕНЯЙ НИДЕРЛАНДСКИЙ ТЕКСТ.** Ни одного слова, ни одной запятой, ни
   одного артикля. Текст уже проверен носителем под уровень A2. Копируй его
   буквально. Если тебе кажется, что там ошибка — всё равно не трогай, просто
   отметь в конце ответа отдельным списком.
2. **Внутри сгенерированных картинок не должно быть никакого текста и никаких
   букв.** Модели искажают нидерландские слова. Все надписи делает вёрстка, не
   картинка.
3. **Zwarte Piet ни в каком виде не изображай.** Он упомянут только словом, на
   слайдах 3 и 4. Иллюстрации к нему не нужны и не должны появляться.
   Украинского чёртика рисовать можно: это фольклорная фигурка с рожками и
   хвостом, к расовым изображениям отношения не имеющая.
4. Текста на слайде мало и он крупный: это опора для устного выступления, а не
   документ для чтения. Ничего не добавляй от себя.

## Оформление

- Фон: тёплый кремовый `#FDF7EE`. Текст: почти чёрный `#2B2118`.
- Акцент «Нидерланды»: красный `#C8102E` + оранжевый `#E86A17`.
- Акцент «Украина»: синий `#0057B7` + золотой `#E8B33A`.
- Шрифт: чистый гротеск (Inter, Helvetica Neue, Arial). Заголовки очень жирные.
- Заголовок слайда ~44 pt, пункты списка ~30 pt. Читаться должно с последнего
  ряда класса.
- Над каждым заголовком — маленькая надпись капсом разрядкой (kicker), она уже
  указана в тексте слайдов.
- Стиль иллюстраций: **плоская векторная иллюстрация, толстые контуры, тёплая
  палитра, слегка «книжная»**. Без фотореализма, без 3D, без градиентных
  блёсток, без стока.

## Слайды

### Слайд 1 — титульный

- Заголовок: **Sinterklaas in Nederland en Oekraïne**
- Подзаголовок: _Hetzelfde feest, twee landen, twee data_
- Нижняя строка мелко: _Presentatie Spreken A2 · Link thema 13 · Alex_
- **Картинка:** три отдельных предмета в ряд над заголовком — старинный пароход
  с красным корпусом; красная епископская митра с золотым крестом; ангел в
  светлом одеянии с золотым нимбом. Плоские иконки, каждая отдельно, на кремовом
  фоне.

### Слайд 2 — Inleiding

Kicker: `INLEIDING` · Заголовок: **Waar ga ik over vertellen?**

Сверху — врезка с красной вертикальной линией слева (`5 december` красным,
`19 december` синим):

> Niet Santa Claus, niet 25 december. Sinterklaas is op **5 december** — en bij
> ons op **19 december**.

Ниже нумерованный список крупными кружками 1–4:

1. Sinterklaas in Nederland — **5 december** _(число красным)_
2. Sint-Mykolaj in Oekraïne — **19 december** _(число синим)_
3. Wat is **hetzelfde**?
4. Wat is **anders**?

- **Картинка:** в правом нижнем углу очень бледный (10–15 % непрозрачности)
  силуэт нидерландской ветряной мельницы.

### Слайд 3 — Nederland

Kicker: `TEN EERSTE` · Заголовок: **Nederland** + красная «пилюля» с текстом
`5 december`

- Een oude man met een witte **baard**, een rode **mantel** en een **mijter**
- Hij is wel **duizend jaar** oud — dat vertellen ze de kinderen
- Hij komt met de **boot** uit **Spanje** — niemand weet waarom
- Hij komt niet alleen: met **Zwarte Piet**
- In de weken ervóór: de kinderen **zetten hun schoen**

Внизу ряд из 4 иконок с подписями: `de boot` · `de schoen zetten` ·
`de kruidnoten` · `de chocoladeletter`

- **Картинка:** четыре плоские иконки в ряд — (1) пароход с красным корпусом и
  белой трубой на синих волнах; (2) коричневый детский башмак, из которого
  торчит оранжевая морковка с зелёной ботвой; (3) горстка мелких круглых
  коричневых пряных печений; (4) большая шоколадная буква «A» тёмно-коричневого
  цвета. **Букву «A» рисуй как объект-шоколад, это единственное исключение из
  запрета на буквы.**

### Слайд 4 — Oekraïne

Kicker: `TEN TWEEDE` · Заголовок: **Oekraïne** + синяя «пилюля» с текстом
`19 december`

- Bij ons heet hij **Sint-Mykolaj**
- Een andere datum, want wij hebben een andere **kalender**
- Niet met Zwarte Piet: de **engel** geeft het cadeau, het **duiveltje** de
  **roe**
- Het cadeau ligt **onder het kussen**
- De kinderen **zeggen een versje op** voor Sint-Mykolaj

Внизу ряд из 4 иконок с подписями: `onder het kussen` · `de engel` ·
`het duiveltje` · `koekjes met honing`

- **Картинка A (орнамент):** узкие горизонтальные полосы вверху и внизу слайда —
  геометрический украинский вышивальный орнамент (вишиванка) красными и чёрными
  крестиками-зигзагами по кремовому фону. Именно крестиковая геометрия, не
  цветочный узор.
- **Картинка B (иконки):** (1) светлая подушка, на ней маленький подарок в
  золотой обёртке с синей лентой; (2) ангел в светлом одеянии с золотым нимбом и
  белыми крыльями; (3) маленький тёмный чёртик с рожками, хвостом и оранжевыми
  глазами — мультяшный и добрый, не страшный; (4) медовое печенье в форме
  звезды, золотисто-коричневое.

### Слайд 5 — Wat is hetzelfde?

Kicker: `TEN DERDE` · Заголовок: **Wat is hetzelfde?** (слово `hetzelfde`
красным)

- Dezelfde man: **Sint-Nicolaas**, een bisschop van lang geleden
- In **december**, in beide landen
- Hij komt **'s nachts**, met cadeaus voor de kinderen
- Dezelfde regel: **zoet** → een cadeau, **stout** → **de roe**

- **Картинка:** справа — диаграмма Венна из двух пересекающихся кругов. Левый
  круг красный полупрозрачный, подписан `NL`. Правый синий полупрозрачный,
  подписан `UA`. В области пересечения — `Sint-Nicolaas`. Подписи делает
  вёрстка.

### Слайд 6 — Wat is anders?

Kicker: `TEN VIERDE` · Заголовок: **Wat is anders?** (слово `anders` синим)

Главный элемент слайда — большая врезка с красной вертикальной линией слева.
Слова `gedichten` и `cadeaus` — красным:

> Het **eten** is niet belangrijk. De **gedichten** zijn belangrijk — en de
> **cadeaus**.

Под цитатой — две колонки, разделённые вертикальной линией `#E2D6C3`:

| Nederland _(подпись красным, капсом)_            | Oekraïne _(подпись синим, капсом)_                       |
| ------------------------------------------------ | -------------------------------------------------------- |
| De **volwassenen** maken gedichten — voor elkaar | De **kinderen** zeggen een versje op — voor Sint-Mykolaj |

Под колонками крупно красным: **Precies andersom!**

Внизу мелко серым:
`Het eten: kruidnoten en een chocoladeletter ↔ koekjes met honing`

- **Картинка:** без иллюстраций. Цитата и есть визуальный центр слайда.

### Слайд 7 — Afsluiting

Kicker: `AFSLUITING`

- Заголовок: **Twee landen vieren dezelfde man — op een andere manier.**
- Врезка: _De Nederlandse gedichten begrijp ik **nog niet helemaal** — maar
  **wel een beetje**._
- Строка ниже: Nu vier ik het **twee keer**: op 5 én op 19 december.
- Крупно внизу: **Bedankt voor het luisteren.** и следующей строкой красным
  **Heeft iemand nog een vraag?**
- Две иконки с подписями: митра → `5 december`, подушка с подарком →
  `19 december`

### Слайд 8 — Epiloog (стихотворение)

Kicker: `EPILOOG` · Заголовок: **Een gedicht voor onze groep**

Текст в две колонки, по две строфы в каждой. Скопируй буквально, сохраняя
разбивку на строки:

```
Lieve mensen van onze groep,
Het Nederlands is nu jullie taal.
Sinterklaas zag jullie elke week,
En hij is trots op jullie allemaal!

Eerst was alles nog heel moeilijk:
"De" of "het"? Dat was niet fijn.
Woorden leren, toetsen maken,
En de grammatica van "zijn".

Maar nu praat je over alles:
Over werk, familie, geld.
Van "hallo" tot een heel verhaal —
Kijk eens wat je nu vertelt!

Nu is deze cursus klaar.
Het afscheid is een beetje raar.
Maar jullie blijven verder leren,
Dus: gefeliciteerd met dit jaar!
```

Под текстом курсивом красным: _Groeten, Sinterklaas_

- **Картинка:** те же узкие полосы вишиванки вверху и внизу, что на слайде 4.

## Что отдать в ответе

1. Готовый **PDF**, 8 страниц, 16:9 горизонтально, шрифты вшиты.
2. Отдельно — PNG каждого слайда, 1920 × 1080, на случай если PDF поедет.
3. В самом конце ответа — короткий список: какие места нидерландского текста
   тебе показались подозрительными (но которые ты, как договорились, не менял).
