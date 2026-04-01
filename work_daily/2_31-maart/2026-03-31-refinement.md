# Refinement — 31 maart 2026

**Deelnemers:** Erik, Rafaël, Alex, Cindy
**Onderwerp:** Component library — nieuwe componenten voor deelvervoer-app

---

## Introductie

**Erik:** Ja, het is nu gewoon een uitzonderlijke situatie. Ik wilde het
voorbereiden, ik wilde het écht goed voorbereiden, maar ik ben er gewoon niet aan
toegekomen. We moeten even schipperen, want Bal is er nu niet bij. Er is een hele
waslijst aan componenten die naar de component library moet, en dat is allemaal
niet voorbereid. Dus we doen wat we kunnen deze sessie.

**Rafaël:** Zeker, dat was ook de reden waarom ik zit — maar we kunnen wisselen
als je wilt.

**Erik:** Zullen we proberen het gesprek in het Nederlands te houden? Niet per se
verplicht, maar laten we het proberen.

---

## 1. Switch Component

**Erik:** We hebben een switch component nodig. Heel mooi. Volgens mij hebben we
er al een in reisbalans. Hebben we er ook een in reisrewards?

**Rafaël:** Ja, ik denk het. Die zit in de instellingenpagina — het
instellingenscherm.

**Erik:** Het idee is eigenlijk om die uiteindelijk te tweaken als een toggle
switch. Moeten we daar een label bij hebben of niet? Of zou dat te groot zijn?

**Rafaël:** Stel, je wilt alleen een switch hebben zonder label...

**Erik:** Ik zou zeggen dat dat een ander component zou moeten zijn. We nemen de
button en de switch als gecombineerd component. Of eigenlijk: het zijn twee losse
componenten, maar je zou de toggle een higher-order component kunnen maken,
waarbij je zegt: als die een label heeft, rendert hij het label erbij.

**Rafaël:** Ja, dat klopt. Want je kunt het zo maken dat je een toggle los hebt,
maar meestal staat er wel iets bij.

**Erik:** Ja, ik zit ook te denken: op alle plekken waar ik een toggle kan
bedenken, zit er zo'n label bij.

**Rafaël:** Alle switches die ik kan bedenken zijn met een label. Dus bij default
is het "met label", toch?

**Erik:** Ja. Maar staat het label altijd links? Naast dat is dan nog de vraag:
heb je al een label-component?

**Rafaël:** Ja, in de controller. Dat is eigenlijk gewoon een tekst-component,
denk ik.

**Erik:** Oké, en daar beginnen we. Dat was eigenlijk de eerstvolgende voor het
design system. Ik heb weinig inzicht in jullie hele designs, maar ik kan me
voorstellen dat je wilt kunnen zeggen: ik wil er een label bij, en dat dat
meteen automatisch goed staat. Want wanneer ga je hem zonder label gebruiken?

**Rafaël:** Het kan wel optioneel zijn.

**Erik:** Ja, dat is toch dat je het optioneel maakt? En in reisrewards — dat
component heet daar "switch", maar is functioneel een checkbox.

### Schatting

**Erik:** Is dit genoeg informatie om te schatten?

**Rafaël:** Ja, denk ik. Het is een component die al bestaat. De tickets gaan
over de switch component, in delen voor de app. Dus je hebt al drie dingen: drie
versies van componenten toegevoegd. Ik wil gewoon even ondersteuning.

**Erik:** In principe zou je nog moeten zeggen: we kopiëren hem uit één van de
andere projecten. Maar we hebben eigenlijk gezegd: we kijken naar beide
implementaties en maken het zo simplistisch en goed mogelijk. Er moet mogelijk
nog iets aan gebeuren, ook al kopieer je hem van één van de projecten.

**Rafaël:** Dat is misschien handig om erbij te vermelden. Misschien in de
technische details — dat we de implementatie uit reisbalans of reisrewards pakken
als basis, maar dat er nog aanpassingen nodig zijn. Het is niet zomaar
copy-paste. We moeten nadenken of het goed genoeg is als component, met de
design tokens en alles erop en eraan.

### Stemming: 3 punten

---

## 2. Icon Button (Pill Button)

**Erik:** Icon button. Heb je al een design voor de component library?

**Rafaël:** Eigenlijk nog niet als los pakket. Dit is de pill button.

**Erik:** Die groene? Nee, deze — de ronde knop. In ons project is het mogelijk
dat we zo'n kleine ronde button al hebben in React Native. Maar in reisbalans
waarschijnlijk niet.

**Rafaël:** We willen een goede button voor het deelplatform toevoegen. Met de
juiste eisen. En wanneer je hem downstream merget naar andere projecten, breid je
hem uit met wat daar nodig is.

**Erik:** Dat is de doorflow — en het mooie is dat als je een nieuwe versie
toevoegt... Ik zie alleen de types: primary, secondary, tertiary, warning, ghost
warning, en inline.

**Rafaël:** Bij ons heten ze anders. Volgens het design hebben we zo'n 12
verschillende types button.

**Erik:** Ze zijn waarschijnlijk hetzelfde, maar anders benoemd in de
webversie — dat is oké. Het gaat erom dat je een nieuwe button maakt en zorgt dat
die alle benodigde stijlen krijgt.

### Stemming: 2 punten

---

## 3. Button Component (met leading/trailing icons)

**Erik:** Dan de button zelf. Er staat "icoon optioneel" — maar dan heb je een
leading icon en een trailing icon die je kunt hebben.

**Rafaël:** Dat vond ik een heel mooi punt. In onze vorige button had ik een
icon-property en een icon-position. Dus je kon altijd maar één icon hebben: of
before, of after. Maar met deze opzet heb je twee properties en kun je kiezen: ik
wil er een voor en een achter, of alleen eentje.

**Erik:** Je verliest geen extra properties, maar je kunt wel kiezen. Leading
icon en trailing icon — dat is echt chill. In plaats van icon met icon-position.

**Rafaël:** Ik zou bij de criteria "icoon optioneel" willen weghalen en er
"leading icon" en "trailing icon" van maken.

### Stemming: 3 punten

---

## 4. Status Label

**Erik:** Statuslabel — ook een mooie. Wie kan vertellen wat die doet?

**Rafaël:** In de browser: oranje, rood, groen. Volgens mij kan die ook grijs,
blauw en paars zijn. We kunnen heel veel verschillende kleuren hebben.

**Erik:** Hebben we het ook in reisrewards?

**Rafaël:** Ja. Het verschil is: wij hebben hem gebouwd op basis van kleur, niet
op semantische betekenis. Dus er is geen mapping van type "warning" of "info"
naar een kleur. Gewoon: je geeft een kleur mee.

**Erik:** Waarom is kleur beter dan een semantisch type?

**Rafaël:** Volgens Marcus hangt er geen vaste betekenis aan. Rood betekent niet
altijd "error" — het kan ook "ended" betekenen. Dat is de reden dat we het op
kleur hebben gebouwd.

**Erik:** Oké. En dark mode?

**Rafaël:** Ik weet niet of deze verandert op basis van dark mode. We maken het
zo dat het goed werkt voor de deelvervoer-app, en daarna moeten de downstream
projecten kijken hoe we dat rechttrekken.

### Stemming: 2 punten

---

## 5. Tussendoor: Alex' examen

**Alex:** Ik ben gisteren naar een intakegesprek geweest voor een nieuwe
Nederlandse cursus. En ik heb een examen gedaan — ik heb 76% gehaald. 79% was
nodig voor B1-niveau, dus 3% te weinig.

**Erik:** 76%? Dus 3% minder dan genoeg. Daarom helpt het af en toe om in het
Nederlands te spreken voor ons, denk ik.

---

## 6. DateTimePicker

**Erik:** DateTimePicker. Dit is waar het even ingewikkeld wordt. Dit bestaat
sowieso al in de reisbalans-app als twee losse velden, toch?

**Rafaël:** Ja, alleen het is best een complex component in de reisbalans-app.
Die moet zeker goed bekeken worden.

**Erik:** Op het moment heeft de DateTimePicker allemaal logica om bijvoorbeeld
ranges te kunnen doen: single, multiple en dat soort dingen. En dan heb je ook
nog de input-component — waar je op klikt, dan komt deze picker, en dan klik je
weer... Dit is allemaal in één groot component.

**Rafaël:** De vraag is: heb je al die logica van een range dan niet meer nodig
in dit component? Dat weet ik dus niet. En ook: moet die logica wél in het
component zitten, of moet die buiten het component liggen?

**Erik:** Wat ik hier hoor is nog heel veel complexiteit en onduidelijkheid.
Misschien moet je die even opschuiven.

**Rafaël:** Ja?

**Erik:** Als je realistisch naar deze hele lijst kijkt: je hebt al deze
componenten nodig voor het deelplatform. Alex gaat hier waarschijnlijk volgende
sprint aan werken. Verwacht jij dat hij die hele lijst kan afwerken?

**Rafaël:** Niet per se, nee.

**Erik:** Dan zou ik de meest complexe even laten voor wat ze zijn en daar
gewoon rustig naar kijken als er wat meer tijd is. Anders zit je nu te haasten.
Dan kun je beter tien componenten opleveren dan dat er één complexe tussen zit
die alles vertraagt.

**Rafaël:** Ja, maar verandert de complexiteit dan met de tijd?

**Erik:** Nee, maar dan heb je iets meer tijd om erover na te denken. Als je nu
in deze refine-sessie zo'n component moet gaan uitwerken, daar moet je niet aan
willen. Daar kun je beter even een dag rustig voor gaan zitten.

### Besluit: DateTimePicker wordt doorgeschoven naar volgende sprint

---

## 7. Empty State Component

**Erik:** Dan de empty state. Die beschrijving was eerst gewoon: "Jij hebt nog
geen reserveringen. Maak een reservering." Dit oogt bij ons als een empty state
component. Hebben jullie die?

**Rafaël:** Wij hebben niet per se een empty state component, maar we hebben wel
een "icon met titel en message" — om het generieker te maken. Dat zit al in
reisbalans, en als het goed is ook in reisrewards.

**Erik:** Oké, en wat mist er dan nog?

**Rafaël:** Ik dacht dat de titel of de beschrijving miste, maar als ik de
componentnaam zo lees — icon met titel en message — zit dat er gewoon in. En de
button ook.

**Erik:** Nou, dan is het niet zo spannend. Is de button verplicht?

**Rafaël:** Er moet op z'n minst iéts zijn — ik kan geen situatie bedenken
zonder.

### Stemming: 2 punten

---

## 8. Checkbox met label

**Rafaël:** Checkbox met label.

**Erik:** Is dat niet eigenlijk dezelfde opzet als de switch? Het is niet echt
een checkbox meer als je er een label bij hebt, toch?

---

## 9. TextArea

**Erik:** TextArea component. Is er al een goede implementatie ergens?

**Rafaël:** Nee, niet echt. Het is of we een bestaande implementatie uitkleden,
of opnieuw bouwen.

**Erik:** Ik denk dat je hem opnieuw bouwt, maar dat je wel kunt afkijken hoe de
input-component het doet. Het is ook goed om te kijken naar andere
formulierachtige velden, zodat je de API's enigszins in lijn houdt met elkaar.

**Rafaël:** Dit ding heeft een placeholder-tekst, zag ik in het design. Is het
een vereiste dat je het maximaal aantal regels instelt?

**Erik:** Ik denk dat het er zo'n vijf zijn. Maar begin met de minimale
vereisten — we hoeven niet meer te bouwen dan nodig. De scope van dit ticket is:
ik wil deze placeholder, de border-radius, de shadow — dat is het.

### Stemming: 3 punten

---

## 10. Banner Component

**Erik:** De banner. We hebben al zoiets, toch?

**Rafaël:** Ja, alleen ze moeten een klein beetje aangepast worden zodat het
overeenkomt met het design. Bijvoorbeeld: de ene had de tekst midden uitgelijnd,
en bij reisbalans staat het boven uitgelijnd.

**Erik:** Je kunt één banner-component hebben die zowel globaal als inline kan
werken. Als de banner verschijnt, moet de content naar beneden schuiven — de
content gaat omlaag.

**Rafaël:** Oké, dat is een schermverandering — de wrapper moet ook aangepast
worden.

### Stemming: 2 punten

---

## 11. Toaster

_(Kort besproken, details niet uitgewerkt in deze sessie.)_

---

## QA en testing

**Erik:** Niks hiervan is testbaar voor QA, omdat het allemaal naar de component
library gaat. Het enige wat QA zou kunnen doen is zeggen: "Je ziet het in de
component library, ziet het er goed uit — ja of nee?" Maar zelfs dan is het nog
niet bewezen, want wij bouwen eigenlijk in web om het te previewen. En QA kan er
nog niet bij, want het wordt nergens gedeployed.

---

## Algemene afspraken

- **Aanpak:** We kijken naar bestaande implementaties in reisbalans en
  reisrewards, nemen de beste als basis, en bouwen het zo simpel mogelijk voor de
  deelvervoer-app. Downstream projecten breiden later uit waar nodig.
- **Design tokens:** Zorg dat elk component werkt met de design tokens.
- **DateTimePicker:** Doorgeschoven — even rustig uitwerken buiten de
  refine-sessie.
- **Alex** werkt volgende sprint aan deze componenten.
- **Tips:** Bij het aanmaken van tickets, gooi een screenshotje erbij zodat je
  weet waar het over gaat.

---

## Schattingen samenvatting

| Component         | Punten | Opmerking                                   |
| ----------------- | ------ | ------------------------------------------- |
| Switch + label    | 3      | Kopiëren + aanpassen uit reisbalans/rewards  |
| Icon Button       | 2      | Relatief simpel, kleine ronde button         |
| Button            | 3      | Leading/trailing icon-patroon                |
| Status Label      | 2      | Op kleur, niet semantisch                    |
| DateTimePicker    | —      | Doorgeschoven, te complex voor nu            |
| Empty State       | 2      | Bestaat al grotendeels                       |
| Checkbox + label  | 2      | Vergelijkbaar met switch-aanpak              |
| TextArea          | 3      | Opnieuw bouwen, simpel houden                |
| Banner            | 2      | Aanpassen van bestaande implementatie         |
| Toaster           | —      | Kort besproken                               |
