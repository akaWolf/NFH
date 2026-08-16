# Pass 4 — name twins (одноимённые сущности с разными владельцами)

Источник: src/Assembly-CSharp/*.cs; порт: runtime/*.py, tools/export_level.py;
данные: levels/s1|s2/*.json; файлы текстур: textures/s1 (2624 png), textures/s2 (3584 png).

## Счётчики

| категория | перечислено | из них gameplay-relevant | проверено глубоко | verified OK | находок |
|---|---|---|---|---|---|
| C#-поля-тёзки (одно имя, ≥2 класса) | 231 имя | 131 (оба владельца в порте) | 52 имени построчно + ~45 behavior-локальных пакетно | 92 | 3 (F1, F5-часть, F6-часть) |
| C#-методы-тёзки | 152 имени (47 override-цепочек + 105 несвязанных) | ~60 | 24 построчно против порта | 17 | 6 (F2–F5, F7, F8) |
| ассеты (ссылки текстур из JSON) | 1487 различных (имя, сезон) | — | все прогнаны через симуляцию кэша | 1487−… | 3 группы (F9–F11) + 2 latent (F12) |

Missing-текстур: 0. `~N`-ссылки (квады/заборы/аудио): все 40+ резолвятся в точный файл.
Кейс-твины (два файла, разный регистр, один каталог): 0.

---

## НАХОДКИ

### F1. HIGH — TrickItem.KidActions: ветка SandSculpture привязана к тёзке-ПЕШКЕ вместо Item.Kid (TrickItem)

Точный повтор генератора «два разных KidActions».

- C#: `TrickItem.KidActions` (TrickItem.cs:632-641) для **SandSculpture** играет
  `Kid.AnimController.PlayAnimationSequence(Kid.UseNormalSequence / UseTrickedSequence)`,
  где `Kid` — **Item.Kid (Item.cs:522, `public TrickItem Kid`)** — айтем OlgaKid,
  и последовательности — **item-side** (`ItemAnimationState[]` самого OlgaKid).
  Для **SandCastle** (cs:642-652) — `GameInfo.Instance.Rottweiler.kid`
  (Rottweiler.cs:122, `public Kid kid` — **пешка**) и её pawn-side сиквенсы.
- Порт: `Routine._trick_kid_actions` (runtime/world.py:1651-1670) для ОБОИХ имён берёт
  `kid = w.pawns.get('Kid')` и `spec = self.level.pawns.get('Kid')` — т.е. пешку и
  pawn-спеки (scene.py:1917-1918) — и играет на `kid.anim`.
- Данные: levels/s2/Level205.json — SandSculpture (TrickItem) сериализует
  `Kid = {'path': 285, 'name': 'OlgaKid', 'type': 'TrickItem'}`; pid 285 OlgaKid:
  `UseNormalSequence=['N2TrickItemIdleTricked']`, `UseTrickedSequence=['N2TrickItemUseTricked']`,
  `Animating=True`. **Пешки Kid в L205 нет вообще** (0 компонентов `Kid`).
- Эффект: в L205 при использовании скульптуры соседом OlgaKid обязан сыграть свою
  реакцию — порт делает `return` на `kid is None`, OlgaKid не шевелится никогда.
  Поле-то нужное уже есть: `it.kid_item` (scene.py:495) — но здесь не использовано.
- Ветка SandCastle (L207, пешка Kid есть) — сверена, корректна, включая linked-условие.

### F2. HIGH — GroundItem.CanWoodyUse / InspectItem.CanWoodyUse не портированы: клик «использует» и трикует то, что клику не поддаётся

- C#: `GroundItem.CanWoodyUse` (GroundItem.cs:3-9) и `InspectItem.CanWoodyUse`
  (InspectItem.cs:5-21) — безусловный `SwitchToStandAnimation + ShowItemTooltip + return false`
  (InspectItem с веткой `ItemThatChangesTooltip.GotTricked → DescriptionPrimedString`).
- Порт: `World._can_woody_use` (runtime/world.py:5385-5656) диспатчит kind только для
  Drawing (5507-5509) и TrickItem-кровати (5511-5516). Веток `GroundItem`/`InspectItem`
  НЕТ → базовый поток проходит до `return True` (5656) →
  `_woody_try_use` (5771-5836) играет `Animation` (=Walk_Down!) на Вуди,
  `_woody_trick_done` (5838-5935) ставит `used=True`, `_get_tricked(item, True)`
  (5869, 5937-5941) и `TrickLaugh` (5922-5923).
- Данные: SlipperyGround (GroundItem) — в Intro102/103 и L103–L108+ (14+ уровней),
  `IsFloor=False` (обход `is_floor`-ветки world.py:5281 не срабатывает), BoxCollider есть,
  `CanUse=True, RequirePriming=False, Locked=False, RequiredInventory=IT_NONE`.
  CarnivorPlant (InspectItem, L110): те же поля, `Dexterity=False`,
  `ItemThatChangesTooltip=CarnivorPlantSpray(319)`.
- Эффект: пустой клик по слизкому полу/растению — Вуди играет Walk_Down на месте,
  предмет помечается использованным и **триканутым**, Вуди смеётся. В оригинале —
  только тултип-описание. Порча состояния `tricked` у CarnivorPlant ломает L110-логику.
  Тултип-свитч InspectItem (DescriptionPrimedString) тоже отсутствует
  (check_description_tooltip, world.py:5745-5769, веток этих kind не имеет).

### F3. HIGH — SearchItem.PlayItemAnimation: крабий обмен зон уходит в тёзку TrickItem и глохнет на поле-тёзке Animating

Двойной твин: метод-тёзка + поле-тёзка.

- C#: `SearchItem.PlayItemAnimation` (SearchItem.cs:68-89) — БЕЗ гейта Animating,
  с безусловным `SetObjectHidden(false)`. `TrickItem.PlayItemAnimation`
  (TrickItem.cs:1018-1050) — `if (Animating)`, ветка `UseAnimationType→PlayAnimationDirectly`,
  эхо AnimateDependant. **`Animating` объявлено ТОЛЬКО на TrickItem (TrickItem.cs:54)** —
  у SearchItem такого поля нет.
- Порт: обе версии существуют — `play_item_anim` (world.py:4644, TrickItem-семантика) и
  `search_play` (world.py:4671, SearchItem-семантика). Но `crab_animations`
  (world.py:5110-5137, порт Pawn.CrabAnimations cs:1560-1596 → SearchItem.PlayFullanimationZoneEnter/Leave
  cs:275-293) для SearchItem-веток зовёт **play_item_anim** (5121, 5126).
  `scene.py:320` читает `Animating` у всех kind → у SearchItem ключа нет →
  `animating=False` навсегда → `play_item_anim` — вечный no-op для любого SearchItem.
- Данные: SearchItem-крабы CrayFish в levels/s2/Level202.json и Level207.json
  (`EnterZone=N2TrickItemIdleNormal, LeaveZone=N2TrickItemIdleTricked, Animating` отсутствует).
- Эффект: вход в зону краба не прячет его, выход не играет Enter — обе анимации
  никогда не срабатывают. Условия (инвертированные strips) в порте верные, глушится
  именно play-путь. `search_play` в crab_animations не используется (единственный его
  вызов — OlgaBraBehavior, behaviors.py:1913).

### F4. MEDIUM — TrickItem.GetTrickScore потерян: compound-трик платит TrickScore вместо Item.CompoundTrickScore

Поле-тёзка `CompoundTrickScore` (GameInfo.cs:43 `=4` и Item.cs:68) + срезанный override.

- C#: `TrickItem.GetTrickScore` (TrickItem.cs:391-397): `Compound && CompoundTricked →
  return CompoundTrickScore` (поле Item.cs:68); все `GameInfo.TrickDone(GetTrickScore())`
  (Item.cs:2121-2152) идут через виртуал.
- Порт: `_on_trick_done` (world.py:4270-4292) всегда платит `item.trick_score`.
  Item-овский твин хранится (`compound_trick_score_v`, scene.py:660), но не читается нигде
  (grep: единственные вхождения — scene.py:245,660). GameInfo-овский твин привязан верно
  (world.py:1431,1448 — формула рейтинга, GameInfo.cs:396-401).
- Данные: levels/s1/Level114.json — Shotgun (pid 480): `Compound=True, TrickScore=10,
  CompoundTrickScore=13`. `compound_tricked` в порте живой (world.py:5411).
- Эффект: compound-трик дробовика приносит 10 вместо 13 → FinalTrickScore/рейтинг L114 ниже.

### F5. MEDIUM — Item.OnTrickDone: пропущен второй TrickDone по ExtraCoinLinkedTrick

- C#: Item.cs:2137-2146 — ветка «оба linked новые»: `LinkedTrick=true; TrickDone(...);
  if (ExtraCoinLinkedTrick) TrickDone(GetTrickScore());` — второй вызов добавляет ещё
  +1 к `CompletedTricksCount` (GameInfo.cs:467-478).
- Порт: world.py:4285-4289 — один trick_done, флага `extra_coin_linked` в _on_trick_done нет
  (он используется только в NFH2-лестнице злости, world.py:4093 — это другой механизм,
  Rottweiler.cs:645).
- Данные: единственный носитель — levels/s2/Level207.json SandCastle
  (`ExtraCoinLinkedTrick=True, TrickScore=0`).
- Эффект: связка SandCastle+linked в L207 даёт 2 зачтённых трюка вместо 3 —
  `completed` занижен → % рейтинга (completed*90/total) и порог Won смещены.

### F6. MEDIUM — Rottweiler.IsAlarmPostponed сплющен в тёзку RoutineActionUse.IsAlarmPostponed

Метод-тёзка о 4 владельцах: RoutineAction.cs:164 (virtual), RoutineActionGrab.cs:26,
RoutineActionUse.cs:573, и **приватный богатый Rottweiler.IsAlarmPostponed (Rottweiler.cs:1047-1070)**.

- C# (Rottweiler.cs:1047-1070), 6 веток: SurpriseNear→true; SurpriseFar.PostponeAlarm;
  Move→NextAction.IsAlarmPostponed() (виртуал → Use.PostponeAlarm);
  Grab.PostponeAlarm; Use → `PostponeAlarm || PostponeAlarmDuringUseOnly || Item.IsTricked()`.
  Вызовы: OnAlarmRaised (cs:1036-1044), release пендинга (cs:233), HearAlerter (cs:272).
- Порт: `Routine.is_alarm_postponed` (world.py:2857-2860) =
  `a.get('postpone_alarm') and state == USING` — только один твин. Пропущено:
  1. **`PostponeAlarmDuringUseOnly`** (RoutineActionUse.cs:55) — вообще не экспортируется
     (scene.py:1593 читает только `PostponeAlarm`). Данные: levels/s1/Level105.json —
     действия Piano и PlantStink сериализуют `PostponeAlarm=False, DuringUseOnly=True`,
     и в L105 есть CauseAlarm-предмет Mobile → путь `_raise_alarm` (world.py:4887-4900 =
     Rottweiler.OnAlarmRaised cs:1036-1044) достижим: трик телефона во время игры соседа
     на пианино в порте прерывает use немедленно, в оригинале тревога паркуется.
  2. **`Item.IsTricked()`-плечо** — на путях `_raise_alarm` (world.py:4896) и release
     пендинга (3428, 3480) порт отпускает тревогу, оригинал держит, пока текущий
     предмет соседа трикнут. (В hear_alerter, 3239-3240, обратная поправка cs:272
     `|| Tricked` смоделирована — там расхождения нет.)
  3. **Фаза MOVING**: гейт `state == USING` отбрасывает ветку Move→NextAction (cs:1057) —
     с `PostponeAlarm=True` (L114 Polish, L105 Window/Football) оригинал держит тревогу и
     на подходе к действию.
  4. SurpriseNear / SurpriseFar.PostponeAlarm — в данных SurpriseFar-флаг нигде не true
     (latent), SurpriseNear транзиентен.
  5. Смежное: `use_fixing_action['postpone_alarm']` читается (world.py:3445), но
     scene.py:1943-1950 этот ключ НЕ заполняет (только sequence/should_return/return_sequence) —
     мёртвый read. Данные L110: `UseFixingItemAction.PostponeAlarm=True`, маскируется
     одновременным `GrabFixingItemAction.PostponeAlarm=True` (заполняется, scene.py:1940-1941).

### F7. MEDIUM — двери: все не-Woody роли получают строчки Ротвейлера; Mother/Olga-анимации дверей не играются никогда

- C#: Door.cs:18-24 — четыре пары полей (Woody/Rottweiler/Olga/Mother Enter/Leave);
  `Mother.PlayDoorEnter/LeaveAnimation` (Mother.cs:63-73) зовут `PlayMotherEnter/LeaveAnimation`
  (Door.cs:127-139).
- Порт: scene.py:930-933 читает только Woody+Rottweiler пары; `Pawn._door_anims`
  (world.py:841-844): `role == 'Woody' → (leave, enter); ИНАЧЕ → (rott_leave, rott_enter)`.
- Данные: 90 дверей S1 и 8 дверей S2 (L211-214) сериализуют
  `MotherDoorBackEnter/MotherDoorBackLeave`. В S1 пешки Mother нет (latent);
  в S2 матери ходят между зонами (L211 DeckChairMother↔OlgaChild, L212 MumWaitZone3↔4,
  L213 Zone2↔5, L214 DeckChairMother↔MotherWait).
- Эффект: там, где мать проходит такую дверь, дверной лист (содержащий фигуру идущей)
  играет строчку ротвейлера (или ничего) вместо материнской; сама пешка на время
  транзита скрыта → рисуется чужая фигура.

### F8. MEDIUM — zone_reaction: инлайн TrickItem.PlayItemAnimation теряет ветку UseAnimationType и unhide

- C#: `TrickItem.PlayZoneEnter/PlayZoneLeave` (TrickItem.cs:1095-1113) →
  `TrickItem.PlayItemAnimation` (cs:1018-1041): `UseAnimationType → PlayAnimationDirectly`
  (сохраняет serialized Type, т.е. Looping-строчка зациклится), иначе Looping/Single;
  у Leave — предварительный unhide (cs:1104-1108); гейт Leave — «сырое» `Tricked` (cs:1104),
  у Enter — `IsTricked()` (cs:1097).
- Порт: `zone_reaction` (world.py:5139-5152) всегда `p.play_single(anim)`;
  unhide на leave нет; гейт для обеих сторон — `is_tricked` (5145).
- Данные: 4 предмета с зонными анимациями и `UseAnimationType=True, Animating=True`:
  Dove (L107, L111), **BBQ (L110: EnterZone=BBQFullSmoke, Type=Looping)**, Snake (L208).
- Эффект (наблюдаемый): дым BBQFullSmoke при входе в зону должен зациклиться —
  в порте проигрывается один раз и застревает. Остальные строчки Type=Single —
  расхождение только в модели вызова.
- Примечание: основной use-путь (`play_item_anim`, world.py:4657-4658) ветку
  use_anim_type→play_directly имеет — потеряна она только в zone_reaction.

### F9. HIGH (ассеты) — коллизии базовых имён листов анимаций: генератор ms_0000 жив на пути TextureFileName

Квады/заборы/типсы экспортёр нумерует по path_id (`~N`) — эти 40+ ссылок сверены, все
точные. Но **листы анимаций** идут как `basename(BaseAnimationPath + TextureFileName)`
(scene.py:37) без path_id — кэш (render.py:58-97: raw → flattened → basename → sanitized,
каждый кандидат сначала exact, потом case-insensitive) берёт `X.png`, тогда как на диске
лежит и `X~2.png` (другой ассет с тем же m_Name). Сверка аспекта (OriginalWidth:Height
против пиксельного) даёт:

Подтверждённо неверный выбор (аспект-мэтч у соседа, у выбранного — мимо):

| имя | уровень (anim) | нужно (ratio) | кэш берёт | правильный кандидат |
|---|---|---|---|---|
| bull | L212 idle (2.84), L213 idle (3.42) | лист быка | bull.png **109x72 (иконка)** | bull~2.png 1011x356 (L212), bull~3.png 1059x310 (L213) — «три разных bull» |
| ms_0000 | L202 idle сундука (2.03) | 512x256 | **ms_0000.png 1402x980 — та самая палуба L211 из уже чиненного бага** | ms_0000~8.png 512x256 (2.00) |
| F_Jump | L206 Extra1 (1.42) | 780x549 | F_Jump.png 1024x512 (2.00) | F_Jump~2.png 780x549 (точное совпадение) |
| bar | L212 idle (2.47) | 64x32 | bar.png 109x71 (иконка) | bar~2.png 64x32 |
| picnic | L213 idle (2.40) | 256x128 | picnic.png 109x71 (иконка) | picnic~2.png 256x128 |
| mat | L214 idle (3.65) | 64x16 | mat.png 109x71 (иконка) | mat~2.png 64x16 |
| pistol | L214 idle (0.67) | 64x64 | pistol.png 109x71 | pistol~2.png 64x64 |
| jade | L204 idle (0.83) | 64x128 | jade.png 109x71 | jade~2.png 64x128 |
| tortilla | L213 idle (1.09) | 64x64 | tortilla.png 109x71 | tortilla~2.png 64x64 |
| bucket | L207 idle (2.11) | 64x32 | bucket.png 128x128 | bucket~2.png 64x32; при этом L214 (1.32) хочет как раз bucket.png — одно имя, два листа |
| controls | L213 idle (1.11) | 64x64 | controls.png 256x128 | controls~2.png 64x64; L214 (2.49) хочет controls.png — та же вилка |

Правдоподобно-верные выборы (совпадение аспекта): toilet, bike, shell, manip, boat,
whip, turban, throne, pinata. Неразрешимые по аспекту (нужен path_id):
statue (обе 1:2), rock (2.98 между 4.0 и 2.0), phone, hotdog, rockets,
sub_takesub/sub_takeshark (1024x1024 vs 1024x512; референсятся и Item-, и
PawnAnimationController'ом), F_Fifi (~2 бинарно идентичен — безвреден).
109x71 — стандартный размер NFH2-иконки; сами эти файлы из JSON не референсятся
ничем (бабблы резолвятся раньше через BUBBLE_BASES → textures_nfh2_bubbles_*,
hud.py:42,1119-1123 — проверено, korrект).

Механизм починки существует в экспортёре (как у квадов: tools/export_level.py:108-144
через `_extract_texture_names`), на TextureFileName не применён.

### F10. MEDIUM (ассеты) — `_resolve_asset_ref` возвращает голое m_Name для Texture2D: HUD/ProgressBar/MouseCursor теряют идентичность при коллизиях

- Код: tools/export_level.py:266-268 (class_id 28 → `Reader(...).astr()`), тогда как
  заборы/типсы/аудио используют коллизионные таблицы (cs. 461-510, 276-280).
- Затронутые ссылки с парами-тёзками на диске (обе копии лежат в ОБОИХ сезонных
  каталогах, так что порядок каталогов не спасает):
  - `Mutter_dis_001` — ProgressBar.MotherHUDProgressFull (L109 s1; L202/206/207/208 s2).
    Файлы: 106x114 vs ~2 114x114 (разные лица S1/S2) → у одного из сезонов лицо
    матери на слип-баре чужое.
  - `progress_back` / `progress_front` — ProgressBar.Empty/Full (те же 5 уровней);
    пары 372x51, но **контент различается** (md5 f7181127a7≠2757c50508, 9ee246f2f0≠fed2df6ac9).
  - `camera` — MouseCursor.TrickCameraIcon (32x32, правдоподобно) И
    HUD.TrickCameraBackground (нужен, судя по паре, camera~2 1024x512) — оба поля
    получают 32x32. Latent: TrickCamera в hud.py пока не рисуется (grep пуст).
  - `abrechnungsscreen` (550x400 vs ~2 552x401, контент различен) — HUD.OriginalScoreboard;
    `bar_left_HNonly` (256x256 vs ~2 145x127) — HUD.RottweilerOnlyBackground.
  - `bar_mid_HNonly~2`, `F_Fifi~2` — бинарные дубли, безвредны.

### F11. LOW (ассеты) — аудио-тёзки в кадровых звуках

12 коллизионных семей WAV в audio/s1|s2 (`~2`-копии). Кадровые звуки анимаций
(Sounds[].FileName) резолвятся голым именем (audio_out.py:46-58, name+.wav/.ogg exact) —
две ссылки попадают в коллизионные семьи: `but_hover1`, `na_slip_up1` (файл-тёзка
`~2` содержит другой клип). Клипы MusicPlayer при этом идут через коллизионную
таблицу экспортёра (`titel~2`, `jingle_*~2` в JSON) — сверено, точные.

### F12. LOW — кросс-сезонные контент-тёзки и смешанная сессия

23 имени существуют в обоих каталогах с разными пикселями (C_Idle, N_Weights, N_Cry,
M_appear, W_Fear, beer, ms_0000, …). Порядок каталогов «сезон открытого уровня первым»
(viewer.py:24-35) решает верно, НО порядок фиксируется один раз по наличию ЛЮБОГО
s2-пути в списке уровней: сессия `viewer.py levels/s1/... levels/s2/...` даст s2-приоритет
и для s1-уровня. Latent.

### F13. LOW — мелочь по методам-тёзкам

- Rake+compound-инвентарь до трика: TrickItem.cs:526-531 показывает `ShowItemTooltip(HideString)`;
  порт (world.py:5406-5408) объединил условие и пузыря не показывает.
- `set_primed` (world.py:5162-5177): у WaterPuddle не отзеркалено
  `FinalDeltaLocationNormal = -FinalDeltaLocationNormal` (Item.cs:1196-1200); докстринг
  утверждает «name-hack не портирован», хотя dx/dy-половина портирована.
- `_move_to_empty_space` докстринг (world.py:6271-6272) называет копии «идентичными» —
  у Mother.MoveToEmptySpace (Mother.cs:142) на самом деле НЕТ финального сдвига на
  MinDistanceToNearestDoor; на поведение не влияет (порт правильно зовёт её только
  для Ротвейлера, world.py:6252, т.к. у материнской копии нет вызывающих).

---

## Таблица 1 — поля-тёзки (gameplay-relevant), вердикты

Полный перечень 231 имени — scratchpad/twins2.txt; здесь — проверенные владельцы.
«OK» = каждое чтение порта привязано к правильному классу-владельцу (по содержащему
компоненту/объекту, не по имени).

| имя | владельцы (файл:строка) | привязка порта | вердикт |
|---|---|---|---|
| IgnoreWoody | Mother.cs:16, Rottweiler.cs:66 | scene.py:1921 в _find_pawns: per-pawn из СВОЕГО дикта компонента | OK |
| DelayStart | Mother.cs:18=1.5, Olga.cs:8=1.5, Rottweiler.cs:24 (Start cs:153 → 1.5) | world.py:1504 хардкод 1.5 на всех | OK |
| Frozen | ActionManager.cs:33 (serialized), Woody.cs:70, CameraMover.cs:57 | scene.py:1677 (из ActionManager-дикта) / world.py:361 / world.py:3850 — три раздельных атрибута | OK |
| CompoundTrickScore | GameInfo.cs:43 (=4), Item.cs:68 | GameInfo-сторона world.py:1431,1448 OK; Item-сторона мертва | **F4** |
| UseNormalSequence / UseTrickedSequence | Kid.cs:11/13 (pawn anims), TrickItem.cs:80/86 (item anims) | item: scene.py:592/527 + world.py:4608/4624 (item-плеер); Kid: scene.py:1917-1918 + world.py:1663-1670 (kid.anim); IndianPlatform magician → item-сторона (behaviors.py:1885-1888 = IndianPlatformBehavior.cs:41) | OK как поля; **F1** — выбор владельца в _trick_kid_actions |
| KidActions (методы) | ActionManager.cs:394, TrickItem.cs:632 | world.py:1672 (StartNextAction ✓ cs:193) и 1651 (RottweilerUse ✓ cs:569) | AM-версия OK (вкл. Item.Kid на OlgaMatBeach, world.py:1708-1717 = cs:415-418); **F1** |
| Kid | Item.cs:522 (TrickItem!), SandCastleBehavior.cs:7 (пешка), IndianPlatform.cs:5, L211Behavior.cs:11 (Item) | scene.py:495 kid_item; behaviors.py:1101, 1864 — свои дикты; SandCastle через world.pawns['Kid'] (единственная пешка — эквивалентно) | OK |
| Alerter | Zone.cs:10, GameInfo.cs:57, Woody.cs:148 | Zone.Alerter — рантайм-обратная ссылка (Alerter.cs:45 `Zone.Alerter=this`); порт ищет по `fsm.item.zone` (world.py:5067-5068) — эквивалент; данные: все 9 Alerter-ов согласованы, зоны back-pointer не сериализуют | OK |
| AlerterDelay | Alerter.cs:24 (=1f), DexterityComponent.cs:80 (private, несериализуемо) | scene.py:471, дефолт 1.0 = C# | OK |
| EndString / HideString / WithString / NameString / DescriptionString / LongDescription / DeltaDescriptionLocation | Woody.cs / Item.cs / Zone.cs / Inventory.cs | pawn-спек scene.py:1927-1934 (Woody-префиксы) + item scene.py:703-737 + zone scene.py:1344-1345 + inventory scene.py:443-451; hud.py:562/569 склейка = HUD.cs:1053 (Woody.EndString + Zone.EndString), дверь через link_to-зону = MouseCursor.cs:316-341 | OK |
| EnterZone/LeaveZone, Looping, HideWhenNotAnimating, DisableColliderAfterUse, DexterityAlert | SearchItem vs TrickItem (поля-сиблинги) | один атрибут на объект, per-object дикт — привязка верна; семантика play-путей → **F3** | OK (поля) |
| Animating | ТОЛЬКО TrickItem.cs:54 | scene.py:320 читает у всех kind — у SearchItem маскирующий False | **F3** |
| ComplexMove | Item.cs:218 (serialized), Step.cs:25 (runtime) | scene.py:952 / world.py:710-713 ('cpoint') | OK |
| Passable | только Item.cs:432 (Step обращается через Target: Pawn.cs:1034) | scene.py:331/987, world.py:1154 | OK (в декомпиле не тёзка) |
| DeltaLocation | Item.cs:86 (V3), AnimationInstance.cs:36 (V2), AnimationControllerBase.cs:45 (V2) | scene.py:1394 (item) / :45 (anim) / :1752 (controller) — три раздельных чтения | OK |
| Duration | RoutineAction.cs:9, AnimationSequenceProperties.cs:17, ProgressBarTrick.cs:11 | scene.py:1597 (action) / world.py:3783-3784 (ProgressBar.AnimationSequences) / ProgressBarTrick не портирован (задокументировано, behaviors.py:592) | OK |
| Actions / CurrentAction / MoveLocation / Item / Zone / DoorsToUnlock / ItemsToUnlock | ActionManager+RoutineAction* vs LevelScript(Action) | routine-дикты свои (scene.py:1582-1660); LevelScript (туториалы) не смоделирован — второй владелец вне порта | OK |
| OneTime | ActionManager.cs:79 (runtime), MusicPlayer.cs:39 (serialized), Inventory.cs:59, поведенческие | world.py:1537 one_time_olga / scene.py:1286 (MusicPlayer-дикт) / behaviors-локальные | OK |
| SameZone | ActionManager.cs:51 (bool runtime), SandCastleBehavior.cs:15 (Zone) | world.py:1521 `_same_zone` / behaviors.py:1341 `self.zone('SameZone')` | OK |
| IsAlarmPostponed (методы) | Rottweiler.cs:1047 vs RoutineAction/Grab/Use | порт взял Use-твина на Rottweiler-гейты | **F6** |
| PostponeAlarm | RoutineActionGrab.cs:10, SurpriseFar.cs:7, Use.cs:53 (+Use.cs:55 DuringUseOnly) | Use: scene.py:1593; Grab: scene.py:1940-1941; UseFixingItem: НЕ заполнен (читается world.py:3445); SurpriseFar: не читается; DuringUseOnly: не читается | **F6** |
| Toilet | Pawn.cs:105, ToiletBehavior.cs:7 (в C# оба мертвы; рабочий путь — ToiletAction) | scene.py:1979-1984 ToiletAction; behaviors.py:1991+ читает Paper | OK |
| TrickItem (поле) | Pawn.cs:69 (мёртвое в C#), RoutineActionUse.cs:101 (runtime) | не читается / runtime-модель | OK |
| TrickedItem | Item.cs:524, Rottweiler.cs:48, UseFixingItem.cs:13 | runtime-модели (_fix_target и пр.) | OK |
| SearchingItem | Item.cs:268 (serialized), Pawn.cs:67 (runtime) | scene.py:763 (item) / поток поиска в world | OK |
| IsTutorial | GameInfo.cs:119, Level.cs:68 | порт читает GameInfo-овский (scene.py:1532) — именно он в формуле cs:396 | OK |
| InventoryItems / UsedInventory | SearchItem.cs:5 / InventoryManager.cs:5,11 / Item.cs:440 | scene.py:443 (item-дикт); inventory.used (менеджер); item_used_inventory (world.py:5801, = Item.UsedInventory) | OK |
| Speed / Velocity / EntranceLocation / EntranceZone | Pawn/Level vs behaviors | pawn-спек scene.py:1874; behaviors из своих диктов (behaviors.py:455-459, 1487) | OK |
| StartFallIndex | ParrotLedgeFall.cs:9 (=40), ParrotLedgeJump.cs:33 (=13) | behaviors.py:1686 (=40), 1721 (=13) — свои дефолты | OK |
| TakeAnimation | Item.cs:84 (=TakeInventory), OlgaBraBehavior.cs:7 (=OlgaShowerTakeBra) | scene.py:337 / behaviors.py:1908 с верным дефолтом | OK |
| BubbleIcon(+Mother/Active) | Actor.cs:34 (runtime, из Path), Zone.cs:46 (serialized), RoutineActionMove (property) | items: пути + BUBBLE_BASES (hud.py:42,1119-1123); зоны: exporter bubble_icons по pid (export_level.py:536-556) + hud.py:1113-1117 (MoveOnly = RoutineAction.cs:53) | OK |
| HitWoodyAction, Sequence1-4 | Mother.cs:8 (MotherHitWoody) vs Rottweiler.cs:90 (HitWoody) | scene.py:1952-1959 per-pawn; GetRandomSequence-твины идентичны (оба 25/50/75), порт world.py:6258-6261 | OK |
| CanStart | Pawn.cs:121, Alerter.cs:28 (IntroAnimation.cs:282-297 ставит всем) | интро не моделируется → порт стартует can_start=True (world.py:1245) для FSM, пешки без гейта — соответствует пост-интро | OK |
| OldZone | Helpers.cs:21 (static), Pawn.cs:135 | H['original_start_zone'] / локальные old_zone | OK |
| Fifi | FifiBehavior.cs:5, Level206RoutineBehavior.cs:5 (в C# мёртвое) | behaviors.py:1267 своё; 206Routine не читает — как в C# | OK |
| Bucket/BucketAux/Bull/BullAux/BullControls/Boat/FireChannel/LaunchPad/Piano/ParrotCrap/ParrotLedge/RottPos/RottPosAux/SecondTime/EndPosition/StartPosition/Acceleration/CurrentAnim/currentAnimationState/LastAnimation/TargetItem/TargetMother/TargetRottweiler/TargetAnimation/TargetSequenceIndex/Fish/Olga/Rottweiler/Woody/Mother-рефы | behavior-локальные тёзки (по 2-19 владельцев) | каждый behavior-класс читает СВОЙ экспортированный дикт через self.item/pawn/zone/value/anim_name (behaviors.py:30-56) или хардкодит константы СВОЕГО ctor | OK (пакетная проверка) |
| Visible/Progress/SecondsCount/ProgressBar*/DataStyle/DeltaProgressRect | ProgressBar vs ProgressBarTrick vs LevelLoader/LevelTransition/MainMenu | ProgressBar: scene.py:1110-1142; ProgressBarTrick и меню-владельцы не портированы (документировано) | OK |
| MainValveOpen, Locked, CloseTime, Instance, GameCamera, MouseCursor, EscapeAux, TrickCamera, LevelsCount, Durations/TricksTotal/MinRatings | второй владелец вне модели порта (меню/утилиты) либо runtime | — | OK/n.a. |

## Таблица 2 — методы-тёзки, вердикты

| метод | владельцы | порт | вердикт |
|---|---|---|---|
| CanWoodyUse | Item.cs:1373, TrickItem.cs:507, Door.cs:230, Drawing.cs:81, GroundItem.cs:3, InspectItem.cs:5 | _can_woody_use (world.py:5385-5656): TrickItem-ветки ✓ (compound 5406-5418, кровать 5513, UseAtOtherPlace через clickable=False экв.), Drawing ✓ 5507, Door ✓ отдельно (world.py:5349-5360); GroundItem/InspectItem ОТСУТСТВУЮТ | **F2**; Rake-пузырь → F13 |
| SetPrimed | Item.cs:1169, TrickItem.cs:996 | world.py:5162-5203: kind-гейт TRICK_KINDS ✓, PlayPrimedAnimation-выбор = cs:483-491 ✓ (данных с Looping/UseAnimationType у primed-анимаций нет) | OK; WaterPuddle-мелочь → F13 |
| PlayItemAnimation | SearchItem.cs:68 vs TrickItem.cs:1018 (несвязанные тёзки!) | обе есть: search_play (4671) / play_item_anim (4644); маршрутизация в crab_animations неверна | **F3** |
| GetTrickScore | Item.cs:2156, TrickItem.cs:391 | override отброшен | **F4** |
| OnTrickDone | Item.cs:2121, Alerter.cs:194 (пустой) | _on_trick_done без kind-гейта, но Alerter недостижим в этих путях; ExtraCoinLinkedTrick-ветка пропущена | **F5**; Alerter-твин latent-OK |
| InternalUse | Item.cs:1919, SearchItem.cs:156, HideItem.cs:32 | HideItem: немедленный hide+Hide_In (world.py:5802-5808) ✓ (UseAfterAnimation нигде не true — проверено данными); Item-флаги 5903-5918 ✓; SearchItem → _woody_search_step | OK |
| PreUse | Item.cs:2225, SearchItem.cs:126 | 5789-5799: SearchItem открывает мебель, общие hide-флаги | OK |
| ShouldUseAfterAnimationFinishes | Item/TrickItem/SearchItem/HideItem | зашито маршрутизацией use-потока; HideItem-флаг сверен по данным | OK |
| OnUseAnimationCompleted | Item.cs:1997, TrickItem.cs:268, HideItem.cs:51, Television.cs:15 | TrickItem-тело = _woody_trick_done; HideItem WoodyLeaving в hide/unhide-потоке; Television в сценах отсутствует (0 компонентов) | OK |
| Fix | Item.cs:2063, TrickItem.cs:412, Drawing.cs:30, Television.cs:23 | Drawing skip_action ✓ (scene.py:814), фикс-строки ✓ (world.py:4390-4392); Television — нет данных | OK (глубоко не построчно) |
| IsAlarmPostponed | 4 владельца | — | **F6** |
| PlayDoorEnter/LeaveAnimation + Door.Play*Animation | Pawn/Woody/Rott/Mother/Olga + Door.cs:85-139 | выбор строчки _door_anims не различает Mother/Olga | **F7**; позиционные дельты (delta_exit/delta_mother_exit, world.py:958-974) OK |
| OnDoorEnterAnimationFinished | Pawn.cs:1637, Woody.cs:465, Rottweiler.cs:161, Mother.cs:54 | Woody delta_exit ✓, Mother delta_mother_exit ✓, Rott y-снап при !ShouldWalkUp ✓ (world.py:978) | OK |
| UpdateWalkingAnimation | Pawn/Woody/Rott/Mother/Olga | _walk_anim (world.py:428-453): Rott-лестница пропсов, Woody sneaking-инверсия, Mother/Olga urgent→Run | OK |
| IsAtUseLocation | Pawn.cs:1690, Woody.cs:744 | world.py:506-533: Woody-ветка use_woody_extra/woody_delta_use_height | OK |
| TryUseItem | Pawn.cs:1792, Woody.cs:499, Olga.cs:137 | set_olga_x_on_use гейтится role=='Olga' (world.py:2195) | OK |
| GetPortalUp/DownAnimation | Pawn/Rott/Woody | world.py:455-477 | OK |
| MoveToEmptySpace | Mother.cs:142 vs Rottweiler.cs:1156 (у Rott доп. сдвиг) | только Rott зовёт (world.py:6252, верно: у Mother-копии нет вызывающих), сдвиг есть (6289-92) | OK (докстринг-мелочь → F13) |
| HitWoody / GetRandomSequence | Mother vs Rottweiler | тела идентичны; порт один путь + per-pawn сиквенсы | OK |
| KidActions | ActionManager vs TrickItem | — | AM ✓ / **F1** |
| PlayZoneEnter/Leave (+ Zone.PlayItemsZone*) | TrickItem.cs:1095-1113, Zone.cs:64-79 | zone_reaction: инлайн без UseAnimationType/unhide, гейт leave | **F8** |
| CrabAnimations цепочка | Pawn.cs:1560-1596 → SearchItem.cs:275-293 | условия ✓, play-путь ✗ | **F3** |
| CanSeeWoody | Alerter.cs:81, Mother.cs:103, Rottweiler.cs:1218, ActorBehavior.cs:25 | AlerterFSM.can_see_woody отдельно; пешки через can_*_see_woody | OK (не построчно) |
| PostponeAlarm (метод) | Pawn.cs:1807, Rottweiler.cs:1126 | pawn.alarm_postponed + routine.postpone_alarm | OK |
| Freeze | ActionManager/CameraMover/Mother/Rottweiler/Woody | r.frozen / camera_frozen / woody.frozen — раздельно | OK |
| Не углублялся (низкий риск/вне ядра): IsUsingItem, WarpThroughDoor, UpdateMoveLocation, OnPathFinished, PostWalk, ShouldAbortMove/ShouldExitDoorNow/ShouldGoToItem, CheckTargetItem, OnSingleAnimationEnded, ContinueAlarm/ContinueAngryAnimation, MoveToToilet, OnFinishedEntrance, AddItemStep, CheckMoveLocationY (позиционные дельты сверены полево), GetName/With/DescriptionString-оверрайды (hud.py:434-494 — kind-ветки на месте, построчно не сверял) | | | — |

## Таблица 3 — ассеты: группы коллизий

- **Резолвер** (render.py:58-97): кандидаты raw → `/`→`_` → basename → sanitized; каждый
  кандидат exact-case по каталогам, затем case-insensitive; каталоги: сезон уровня,
  другой сезон, textures/ (viewer.py:24-35).
- Плоских ссылок с `~N`-соседями на диске: 46 (полный список — scratchpad/assets.txt);
  из них листы анимаций с подтверждённым неверным выбором — F9 (11 позиций),
  правдоподобно-верных — 9, неразрешимых по аспекту — 7.
- `~N`-ссылки в JSON (экспортёр по path_id): квады book_ms~2, trashcan_me~2 (импликация:
  plain book_ms/trashcan_me на других уровнях — верные первые копии), workbench_ms~2 ×4,
  ms_0000~2/3/9/10 (квады L201) + заборы ms_0000~4/5/6 + open_0000~2; аудио jingle_*~2,
  titel~2, ingame2_fast~2, levelstart~2 — все резолвятся в точный файл: OK.
- HUD/ProgressBar/MouseCursor PPtr-имена без нумерации — F10.
- Кросс-сезонные пары с разным контентом: 23 (C_Idle, C_idle, M_appear, M_disappear,
  N_Cry, N_Ladder, N_Search, N_Weights, N_weights, W_Appear, W_Disappear, W_Fear,
  W_NoNo, W_Whats_Up, beer, ms_0000 и др.) — F12.
- Кейс-твины в одном каталоге: нет. Материалы: единственный PrimedMaterial-ref
  (L108 firstaid_open) резолвится экспортёром до имени текстуры — OK.
- Аудио: F11.

## Замечание по контексту

runtime/README.md:1004-1009 документирует починку этого класса багов для квадов,
заборов и типс-иконок; README:60-97 описывает резолвер и коллизии flat-извлечения.
Всё перечисленное там в находки не включалось; F9/F10 — непокрытые той починкой пути
(TextureFileName-листы и `_resolve_asset_ref`).
