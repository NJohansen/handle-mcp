# Research: nemlig.com, BilkaToGo og REMA 1000

Trin 1 af v1. Skrevet 2026-11-01.

**Kilder:** kode, docs, tests og fixtures i
[eisbaw/nemlig_cli](https://github.com/eisbaw/nemlig_cli) (`nemlig_api.md`),
[kraenhansen/nemlig-mcp](https://github.com/kraenhansen/nemlig-mcp),
[nickknissen/bilkatogo](https://github.com/nickknissen/bilkatogo) (fixtures er rigtige, redigerede svar) og
[stigvoss/bilkatogo-mcp](https://github.com/stigvoss/bilkatogo-mcp) (ingen licens: kun læst for fakta).

Skrevet før de første live kald. Punkter markeret **⚠ live** er stadig ikke bekræftet med en rigtig konto; de står samlet under "Åbne spørgsmål" sidst. Det, der er bekræftet siden, står under "Bekræftet live".

## Kort svar

| Spørgsmål | nemlig.com | BilkaToGo |
|---|---|---|
| Login | 3 kald: XSRF → Bearer → `/webapi/login` | 3 kald: Gigya login → Gigya JWT → `LoginJWT` |
| Session holder | `.ASPXAUTH`-cookie: 1 år. Bearer-token: 5 min | Bilka-JWT: 24 t. Log ind igen med email/kode |
| Læse ledige tider | `GET /webapi/v2/Delivery/GetDeliveryDays` med pris pr. tid | `GET shop/v3/AvailableDeliveryDates`. Ingen pris pr. tid: fast gebyr i kurven |
| Valgt tid | `GET /webapi/Order/DeliverySpot` → `TimeSlot` | Kurvens `deliveryDate` → `intervalStart/End` |
| Gebyrer fra API | Ja: `DeliveryPrice` i kurv | Ja: `stat.delivery_price`, `stat.packing` (Pakkeservice) |
| Minimumskøb fra API | Ja: `MinimumOrderTotal`, `IsMinTotalValid` | Ja: `stat.minimum_left`, `deliveryAddress.minimum_buy` |
| Hjemlevering eller afhentning | Altid hjemlevering | Kurven har `hd_available`, `missing_hd_address`. Hjem: `dawa_uid` eller `recipient_name`. Afhentning: `sid` og `name` "Bilka …" (ADR 0006) |
| EAN/GTIN i søgning | **Nej** (ikke i kendte svar) | **Ja:** `gtin` i Algolia-hit |

## nemlig.com

### Login og session
1. `GET /webapi/AntiForgery` → `X-XSRF-TOKEN` + cookie.
2. `GET /webapi/Token` → Bearer JWT, `expires_in: 300` (5 min).
3. `POST /webapi/login` med XSRF + Bearer → cookie `.ASPXAUTH` (1 år).

Konsekvens: gem kun cookies lokalt (`~/.config/handle-mcp/nemlig.json`, chmod 600). Hent ny Bearer ved 401. Log ind igen, kun hvis cookien er død.

Krævede headers: `Platform: web`, `Device-Size: desktop`, `Version: <app-version>`, `X-Correlation-Id: <uuid4>`. Versionen kan ændre sig. **⚠ live:** hvad sker der med en gammel `Version`?

### Søgning
`GET https://webapi.prod.knl.nemlig.it/searchgateway/api/search?query=…&take=…&timeslotUtc=…&deliveryZoneId=…`

- `timeslotUtc` og `deliveryZoneId` kommer fra page settings. Pris og lager kan altså afhænge af tid og zone.
- Svaret har `Id` (nemligs varenummer), navn, brand, pris, `UnitPriceLabel` (fx "kr./Kg."), kampagne (`ProductCampaignBuyXForY`, `ProductCampaignMixOffer`).
- **Ingen EAN/GTIN** i de kendte svar. **⚠ live:** tjek produktsiden (`/webapi/…/product`) for EAN. Ellers: match på navn + mængde + brand i v1. EAN-match bliver kun muligt for Bilka.

**Tilbud (set live 2026-11-01):**
- `DiscountItem: true` uden `Campaign` er nemligs faste "Discount"-mærke (står også i `Labels`). Det er ikke et tilbud.
- `ProductCampaignDiscountPercent` og `ProductCampaignDiscount`: `Price` er prisen FØR tilbud. Du betaler `CampaignPrice`, og enhedsprisen er `CampaignUnitPrice`.
- `ProductCampaignMixOffer` og `ProductCampaignBuyXForY`: `Price` er stykprisen. Tilbuddet er `MinQuantity` for `TotalPrice`.
- Kampagner vises allerede aftenen før `IntervalStart`.

### Kurv
- `GET /webapi/basket/GetBasket`. Svaret er stort (~1,5 KB pr. linje + analytics). Returnér kun udvalgte felter som standard (kraenhansen: `BASKET_FIELDS`).
- Nyttige felter: `TotalPrice`, `DeliveryPrice`, `TotalBagsPrice`, `TotalDepositsPrice`, `MinimumOrderTotal`, `IsMinTotalValid`, `FormattedDeliveryTime`, `ValidationFailures`.
- `POST /webapi/basket/AddToBasket` med `ProductId`, `quantity`. Antallet er **absolut**. 0 fjerner linjen.
- Persondata i kurven: `InvoiceAddress`, `DeliveryAddress`, `CustomerName`, `MobileNumber`, `Email`, `DoorCode`, `UnattendedNotes`. Skal fjernes.

### Leveringstider
- Kun `GET /webapi/Order/DeliverySpot` er kendt. Den viser den **valgte** tid (`TimeSlot`, `EditDeadline`) for den åbne ordre. Den har også `CustomerName` → privacy-filter.
- Ledige tider (fundet 2026-11-02 i `main.js`, kun GET): `GET /webapi/v2/Delivery/GetDeliveryDays?days=3&showForSubscriptions=false` (valgfri `startDate`; næste side = svarets `NextRangeStart`). Virker uden login, men så med standardzonens priser. Logget ind = husstandens priser.
- Pr. tid i `DayRangeHours[].DayHours[]`: `Date` + `StartHour`/`EndHour` (lokal tid), `DeliveryPrice` (kr), `Type` (0 = Personlig, 1 = Fleksibel), `Availability` (0 ledig, 1 efter deadline, 2 udsolgt, 3 ikke aktiv), `Deadline`. Bekræftet: Fleksibel 14-21 = 25 kr, Personlig tir 14-21 = 19 kr, ons 14-21 = 0 kr.
- Samme klasse har `UpdateDeliveryTime` / `TryUpdateDeliveryTime` (POST, vælger tid). Må aldrig kaldes: står i `tests/test_safety.py`.
- `list_delivery_slots` viser listen. `get_delivery_info` viser valgt tid + `EditDeadline`. Ingen valg af tid.

### Opskrifter og madplan (fundet 2026-11-06, kun GET, intet login)
- Intet opskrift-API. bilkatogo.dk er et statisk Nuxt-build: hver side har sine data i `/_nuxt/static/<build>/inspiration/opskrifter/<sti>/payload.js` (`__NUXT_JSONP__`, Magnolia CMS). Det er et JavaScript-objekt: nøgler uden anførselstegn, `void 0` for undefined.
- Build-id'et skifter ved hver deploy. Det står i hver HTML-side (`staticAssetsBase:"/_nuxt/static/<build>"`). En ukendt side eller et gammelt build svarer HTTP 200 med hjemmesidens HTML, ikke 404.
- Opskrift: titel (Heading h1), fakta ("4 personer", "35 minutter"; nogle "16 stk." eller "1 glas"), tekst som HTML under h2 "Ingredienser" og "Fremgangsmåde" (eller "Sådan gør du"), tips under "Alternativer og justeringer", billede (`imageJCR` på digitalassets.sallinggroup.com).
- "Det skal du bruge": `CuratedSlider.sourceProperties.curatedSkuList`, Bilka-varenumre (samme som Algolia `objectID` og kurven). Ingen mængde pr. vare, ingen kobling ingredienslinje → varenummer, intet "har du hjemme". Kan have huller (`void 0`).
- Kategorier: `ContentCard.hierarchy` med egne undersider (eller en underkategoris, fx "Pita"), og `CarouselContentCard` under en overskrift. `aftensmad` har 15 underkategorier, nogle med endnu et niveau (`sandwiches-pita-og-wraps/sandwiches`).
- Madplan: `/inspiration/opskrifter/madplaner/`: 7 aftensmåltider (man-søn) i en carousel under "Madplan til uge NN", plus "Køb alt" (alle varenumre) og en indkøbsliste som tekst.
- Ingen søgning og ingen tags.

### Ordrer
Kendt i `nemlig_cli` (ordrehistorik og ordredetaljer). Indeholder adresse og navn → privacy-filter.

### Endpoints, der aldrig må være i koden
`/webapi/Order/PlaceOrderLoggedIn`, `/webapi/Checkout/GetCreditCards`, `/webapi/Checkout/GetCardsFees`. En test skal grep'e efter dem.

## BilkaToGo

### Login og session
1. `POST https://accounts.eu1.gigya.com/accounts.login` (offentlig `GIGYA_API_KEY`) med email/kode → `login_token`.
2. `POST accounts.eu1.gigya.com/accounts.getJWT` → Gigya JWT.
3. `POST https://api.bilkatogo.dk/api/auth/LoginJWT` → Bilka-session (cookies + JWT, 24 t).

- Forny 5 min før udløb (nickknissen: `JWT_RENEWAL_MARGIN`).
- Udløbet session: fejl-body `{"code": 1, "msg": "Du er ikke logget ind"}`. **Kun** den betyder "log ind igen". Andre fejl-bodies er rigtige fejl.
- **Fælde:** `LoginJWT` erstatter kontoens kurv med kurven bag `cart`-cookien. Send aldrig en `cart`-cookie ved login.

### Søgning
Algolia, ikke Bilkas eget API. App `F9VBJLR1BK`, index `prod_BILKATOGO_PRODUCTS`, offentlig søgenøgle. Hardkod dem.

Nyttige felter pr. hit: `objectID` (varenummer til kurven), `gtin` (**EAN findes**), `name`, `brand`, `netcontent`, `units`, `uom`, `unitOfMeasurePrice` (pris pr. kg/l), `storeData[<sid>]` (pris, tilbud, lager pr. butik), `isInOffer`, `cpOfferPrice`, `is_multibuy`.

- Pris og lager afhænger af butik-id (`sid`). For hjemlevering: brug `sid` fra kurvens `deliveryAddress`.
- Brug `objectID`, ikke `article`, som varenummer (nickknissen v0.3.0 breaking change).

**Tilbud (set live 2026-11-01, beløb i øre):**
- `storeData.<butik>.price` er det, du betaler. Top-feltet `price` er prisen uden tilbud. `beforePrice` er altid 0.
- `unitsOfMeasurePrice` er enhedsprisen uden tilbud. `unitsOfMeasureShowPrice` er den med tilbud.
- `offerDescription` "Se Her" er et avistilbud uden egen tekst. "Skarp pris" er også et tilbud med lavere pris.
- `offerFrom` og `offerUntil` er altid tomme. Derfor kender vi ikke slutdatoen for et Bilka-tilbud, og et tilbud tæller med, selvom det slutter før levering.
- Mængdetilbud på tværs af varer ("Mix 10 for 25" på bananer og pærer) regnes kun inden for én linje.

### Kurv
- Læs: `GET shop/v6/Cart?u=w&extra=deliveryAddress,deliveryDate`. Tilføj `without_cache=1`, når du tjekker en ændring.
- Skriv: `GET shop/v6/ChangeLineCount?u=w&productId=<objectID>&count=<n>&fullCart=0`. Antal er **absolut**. 0 fjerner.
- Svaret er HTTP 200, også ved fejl. Afvist = fejl-body (fx `eid: 410`) **eller** `productAmount` ≠ ønsket antal. `message`/`offerLimitMessage` på en godkendt ændring er en advarsel.
- Beløb er i **øre**.
- Gebyrer i `stat`: `delivery_price`, `packing` (Pakkeservice, 3900 øre = 39 kr i fixture), `packaging_price`, `deposit`. Linjerne "Papirpose" og "Pakkeservice" er gebyrer, ikke varer.
- Minimumskøb: `stat.minimum_left` (+ tekst) og `deliveryAddress.minimum_buy`.
- Hjemlevering: kurven har `hd_available` og `missing_hd_address`. Fixturen er afhentning (`hd_available: false`). **Bekræftet live 2026-11-01:** `delivery_price` = 39 kr + pakkeservice 39 kr, minimum 500 kr, `deliveryAddress` = hjemmeadresse (filtreres).
- Skift til hjemlevering ændrer tilstand (`SetDeliveryAddress`). v1 gør det **ikke**. Er kurven sat til afhentning, svarer tool'et klart: "Vælg hjemlevering på bilkatogo.dk".

### Leveringstider
- Valgt tid: kurvens `deliveryDate` (`deliveryDate`, `intervalStart`, `intervalEnd`, `delivery_message`).
- Næste ledige dag: `deliveryAddress.nextAvailableDeliveryDate`. Det er et læse-felt.
- Ledige tider (fundet 2026-11-02, kun GET): `GET https://api.bilkatogo.dk/api/shop/v3/AvailableDeliveryDates?u=w`, logget ind. Følger kurvens leveringsadresse. `availableIntervals[].intervals[]`: `intervalStart`/`intervalEnd`, `closed` (1 = lukket), `availability_bit` (1 = ledig, 2 = udsolgt), `orderBeforeTime`, `info[].message` (HTML). Dagen har `closed_text` ("udsolgt").
- Ingen pris pr. tid: gebyret er fast (`stat.delivery_price` i kurven, 39 kr). Hjemlevering er her kun nat (00-06, kommer mellem 20 og 06).
- `SetDeliveryDate` (vælger tid) må aldrig kaldes: står i `tests/test_safety.py`.

### Ordrer
`POST shop/v7/OrderHistory`, `GET shop/v7/OrderDetails`. Status-koder (`Bestilt`, `Leveret`, `Faktureret`) mappes til hjemmesidens ord (nickknissen ADR 0003). Ordrer kan have `home_delivery` og adresse → privacy-filter.

## REMA 1000 (fra Go-porten, 2026-11-07)

Kilde: [McAndersDK/handle-mcp-go](https://github.com/McAndersDK/handle-mcp-go) (MIT), `docs/research.md` og ADR 0008. Kun GET og ét login. Vi har ikke selv kaldt REMA endnu: punkterne bekræftes, når vores egne fixtures fanges.

- **Net og API:** siden er `shop.rema1000.dk`, API'et `api.digital.rema1000.dk/api`. Ingen kø og intet bot-tjek set. Headers: `Accept: application/json`, `X-Device: web`, `X-Locale: da`, `X-Timezone: Copenhagen/Europe`, og `Authorization: Bearer <access_token>` med login.
- **Levering:** kun Køb & Hent (afhentning), kun i nogle butikker (`is_click_and_collect_active`). Ingen hjemlevering.
- **Søgning (offentlig):** `GET search/products?query=&per_page=&page=`, ens logget ind og ud. `prices` er en liste af perioder, den gældende først: `price`, `compare_unit`/`compare_unit_price`, `is_campaign`, `is_advertised`, `starting_at`, `ending_at`, `max_quantity`, `price_over_max_quantity`. `underline` er "størrelse / mærke". `barcodes` er EAN. REMA skriver `HK.` for hakket.
- **Tilbud (offentlig):** avisvarer er `search/products?filter[labels]=9001&sort=department` (mærket Avisvare). 285 varer set 2026-11-07.
- **Opskrifter (offentlig):** `GET search/recipes?query=` og `GET rema1000dk/entities?filter[type]=recipe&filter[slug]=...`. Ingredienser har `digitalProduct` med `amount` = pakker ved opskriftens egne personer.
- **Login:** REMA's egen OAuth: `POST cphapp.rema1000.dk/api/oauth2/login` med e-mail og kode, derefter redirects, der sætter cookies `access_token` (JWT, ca. 1 time), `refresh_token`, `api_session`, `AWSALB`, `AWSALBCORS`. Fornyelse: `POST shop.rema1000.dk/api/auth/refresh`; uden `api_session` og `AWSALB` svarer den 500. Fornyelsen virker efter mindst 1 time og 19 minutter (2026-11-11). Svaret giver nyt `refresh_token`; det gamle kan ikke bruges igen. Hvor længe `refresh_token` lever, er ukendt.
- **Butikker og tider:** `GET v3/stores` (pagineret) og `GET v3/stores/{id}/time-slots` (dag -> `{from, to, is_available}` i UTC, 2 timer pr. tid, ingen pris). `v3/stores` svarer uden login (443 butikker, 5 sider à 100, 2026-11-09); `time-slots` svarer 401 uden login. En butik har `id`, `name`, `postal_code`, `city`, `is_click_and_collect_active`, men også telefon og købmandens navn: dem læser handle-mcp ikke.
- **Indkøbslister:** `GET v3/users/{id}/shopping-lists`, `GET v2/shoppinglists/{id}?with=items` (aldrig `with=users`). Linjer har `amount`, `bought`, `store_item_id` og `store_item.pricing` (`price`, `normal_price`, `max_quantity`, `price_over_max`, `deposit`). Skrivning som sidens SDK: `POST v2/shoppinglists`, `POST .../items`, `PATCH .../items/{id}`, `PATCH v2/shoppinglists/{id}` med `{items:[{id, delete:true}]}`. **Ikke prøvet live.** Se ADR 0007.
- **Kurv og betaling:** en rigtig kurv knyttet til butik, tid og kupon, og betalingsjobs. Rører vi aldrig (ADR 0001, 0007).
- **Mangler:** intet ordre-endpoint, intet gebyr og intet minimumskøb i de kendte kald. Køb & Hent har pakke- og emballagegebyr efter ordrens størrelse ([handelsbetingelser](https://rema1000.dk/information/handelsbetingelser-scan-selv), 7.1).
- **Vilkår (læst 2026-11-08):** en Køb & Hent-ordre starter fra indkøbslisten (afsnit 3). Intet forbud mod automatisk adgang fundet; REMA kan spærre ved mistanke om misbrug. `rema1000.dk/robots.txt` udelukker `/api/*` og `/konto/*` (sider, ikke `api.digital.rema1000.dk`).

## Konsekvenser for v1

1. **Varematch:** EAN kun hos Bilka. `compare_basket` matcher på normaliseret navn + mængde + enhed, og bruger EAN, når begge sider har det. Usikre match markeres.
2. **Gebyrer og minimumskøb** kommer fra API'et hos begge butikker. Ingen config nødvendig, kun som fallback.
3. **Leveringstider:** valgt tid (begge), næste ledige dag (Bilka) og listen over ledige tider med pris (`list_delivery_slots`). Intet valg.
4. **Privacy-filter** skal dække: `InvoiceAddress`, `DeliveryAddress`/`deliveryAddress` (kun ved hjemlevering), navne-, email-, telefon-felter, `DoorCode`, `UnattendedNotes`, `uid`, `tid`, `CustomerName`.
5. **Forbudte endpoints-test:** grep efter `PlaceOrder`, `Checkout/`, `SetDeliveryAddress`, `EmptyCart` i `src/`.

## Næringsindhold (2026-11-11)

- **BilkaToGo:** Algolia-indekset har `infos` med kode `nutritional_100`: rækker `{type: 2, title, value}`, første række "Næringsindhold pr." = "100 g", "Energi" to gange ("233 kJ", "55 kcal"). Kommer også med i en almindelig søgning, når `infos` er i `attributesToRetrieve`. Opslag på `objectID` virker uden login. `energyInfo` findes, men er tom.
- **nemlig:** `GET productbff/api/web/productDetails/{id}` med den anonyme token: `product.detailDeclaration[].tableHeader` ("Næringsindhold pr. 100 ml") og `tableItems` ([label, værdi], "329 kJ / 78 Kcal"). Ét kald pr. vare. Ingen EAN, hverken her eller i søgningen.
- **REMA 1000:** `GET api/v3/products/{id}?include=nutrition_info` uden login, som produktsiden selv spørger: `nutrition_info` = `[{name, value}]` ("Energi" = "318 KJ / 75 kcal", "Fedt" = "< 0,5", ingen enhed). Tabellen siger "Pr. 100 g/ml"; prisens `compare_unit` (kg/ltr) siger hvilken. Søgningen har den ikke (dens `declaration` er ingredienserne). Ukendt id: 404. Siden har også `POST api/v3/batch`, som vi ikke bruger.
- **Frisk kød** (hakket oksekød, flanksteak) og bananer har ingen deklaration i nogen af butikkerne. REMA har dog tal for hakket hvidkål.
- **Open Food Facts** har samme tal som Bilka for skyr (EAN 5711953011399), men mangler frisk kød. Ikke brugt: nemlig har ingen EAN, og Bilka har tallene selv.

## Bekræftet live (2026-11-01, hjemlevering valgt)

- **BilkaToGo `Cart`:** `stat.delivery_price` = 39 kr (levering) + 39 kr (pakkeservice), minimumskøb 500 kr. Hjemlevering ses på `deliveryAddress.dawa_uid` / `recipient_name`.
- **nemlig:** leveringsgebyret afhænger af den valgte tid (19-51 kr). Aflæst i tidsvælgeren på hjemmesiden, ikke fra et API-felt. Tiderne kan ses uden login.
- **Privacy:** hele `deliveryAddress`-blokken fjernes af `privacy.scrub()`, så `dawa_uid` og `recipient_name` når aldrig modellen.

## Åbne spørgsmål

Hvis du finder svaret i DevTools → Network (Fetch/XHR): kopier kun URL og svar-felter, aldrig cookies, og læg et redigeret svar i `tests/fixtures/`.

1. **nemlig:** står EAN/GTIN på produktsiden (`/webapi/…/product`)? Søgesvaret har det ikke.
2. **nemlig:** hvad svarer API'et på en forældet `Version`-header? (I dag: `HANDLE_NEMLIG_APP_VERSION` kan sættes som env var.)

Indtil da matcher v1 på navn + mængde i stedet for EAN hos nemlig.
