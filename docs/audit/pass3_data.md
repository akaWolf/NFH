# Проход 3: данные без потребителя и «спящие» подсистемы

Скан: 28 уровней, 2395 GameObject, 99 типов компонентов; **1807 пар
(тип, поле) с недефолтными значениями**. Порт (runtime/*.py +
tools/*.py, точные имена + snake_case) не читает **581** из них.
Разбивка по потребителю в декомпиляте:

- **~143 пары** — потребитель в портированном геймплейном коде
  (Item/Door/Pawn/Rottweiler/HUD/...) → кандидаты-находки, детально ниже
  (после вычета уже известных основной сессии и ссылок-PPtr вроде
  `AnimController`, `InvManager` — реальных находок ~60);
- **43 поля** — потребителя нет ни в одном .cs → мёртвые данные;
- **~175 пар** — потребители в непортированных подсистемах из README
  «Not implemented» (меню `Control*`/`LevelDataGUIRenderer`/`InGameMenu`,
  интро `IntroAnimation`/`GameIntroAnimation`, туториалы `LevelScript`/
  `TutorialScriptCameraNFH2*`, `ExitConfirmation`, `LevelLoader`) →
  за скоупом, документировано;
- остальное — поля, которые движок Unity потребляет сам (Transform,
  Renderer.enabled, Collider size — порт воспроизводит) либо
  инициализируются кодом заново.

## Находки: потребитель в портированном коде, порт поля не читает

### Позиции и движение

| Поле | Данные | Потребитель | Эффект |
|---|---|---|---|
| `Door.DeltaExitLocation` | **196 дверей** (18 уровней), типично (±0.2, −0.4) или (0.05, −0.25), при `DoorDistanceDelta = (0,0)` | Woody.cs:476 `OnDoorEnterAnimationFinished`: `pos = door.pos + DeltaExitLocation` — Woody-override ПОВЕРХ base-варпа (`WarpThroughDoor` = `door.pos + DoorDistanceDelta`, Pawn.cs) | Woody после каждого прохода двери стоит на 0.2–0.4 юнита в стороне/ниже, чем ставит порт (`world.py _enter_played` использует только `door_delta`). Полный класс «якорь» |
| `Door.DeltaMotherExitLocation` | 1 дверь | Mother.cs:60 | то же для Матери |
| `Item.WoodyDeltaUseHeight` | 53 TrickItem + 18 SearchItem + 6 Door; плюс хардкод 0.7 (Item.cs:2568) | Pawn.cs:1702 `IsAtUseLocation`: для Woody порог = `ItemUseHeightThreshold + DeltaUseHeight + WoodyDeltaUseHeight` | вертикальное «на месте» Woody на 77 предметах шире, чем в порте (порт читает только `delta_use_height`) |
| `Door/Transition.Passable=false` | Level201 `TransitionDownwards`, Level213 `DoorBack` | Pawn.cs:1032 `CanPassTarget` → гейт снапа `pos.x = TargetLocation.x` (Pawn.cs:1734) | у непроходимой двери снап конца шага не происходит; порт («hit snap») должен гейтиться `Target != null && Target.Passable` |
| `Door.DisableOnStart` | Level214, 2 двери `DoorBack` | Door.cs:64 (Start) | двери выключаются на старте; в порте живы (рисуются, кликабельны, в графе пути) |
| `Woody.IdleAnimations` + `IdleThreshold` | 28 сцен; порог 30 c (S1) / 3000 c (S2 — фактически выкл.) | Woody.cs:616-621: `Time.time - LastInputTime > IdleThreshold` → случайная из `IdleAnimations` | Woody «скучает» (2 анимации) при простое 30 с в Season 1. Порт не играет |
| `Pawn.HelloAnimation` (+`HelloAnimationNFH2`) | все пешки | Pawn.cs:1066: в конце пути при `!FinishedEntrance` играется Hello | приветственный жест в конце входа в уровень (у пешек с сериализованным `FinishedEntrance=false` — Woody S1 ×14, S2 `Entrance`) |
| `Woody.LoseAnimation` | 28 (LoseGame/GameFailed) | Woody.cs:1120-1127 (`ShouldPlayFinish`): Won → `WinAnimation`, иначе `LoseAnimation` | при финале без победы Woody играет проигрыш; порт знает только Win |
| `Rottweiler.PortalRunUpAnimation`/`PortalRunDownAnimation` | 28 (Run_Up/Run_Down) | Rottweiler.cs:406, 423 (overrides Get-Portal-Up/Down) | сосед в urgent-беге лезет по порталам Run-вариантами; сверить `_portal_up_anim`/`_portal_down_anim` в порте |
| `Item.BlockWhenItemPick` | 179 SearchItem + 2 TrickItem | Woody.cs:534 (`InputLocked=true` + `ClearStoreBlockedInput`), разлочка Item.cs:1943 | на время анимации подбора клики игнорируются и НЕ запоминаются (в отличие от обычного сохранения клика) |
| `Item.BlockWhenUsingPickupItem` | 5 | Woody.cs:516, 1172; Item.cs:1539, 1645 | блокирующий вариант для использования с предметом в руках |
| `CameraMover.SpeedX/SpeedY/MoveVelocity/HoldInterval` | 28 (7.0/7.0/0.5/0.1) | CameraMover.cs (Update/движение) | камера в оригинале ДОГОНЯЕТ Woody с ограниченной скоростью; порт прибивает мгновенно. Видимо на каждом движении |

### Видимые объекты и анимации

| Поле | Данные | Потребитель | Эффект |
|---|---|---|---|
| `SearchItem.OpenObject` / `OpenRenderObject` | **61 предмет** (15 уровней) / 1 | SearchItem.cs:129-136 (SetActive/Renderer.enabled=true на старте обыска), :259-265 (выкл. в конце; ToolBox + `LeaveToolBoxOpen` остаётся) | ящики/шкафы буквально открываются на время обыска — отдельный GameObject «открытого» состояния |
| `TrickItem.IdleTrickedSequence` + `PlayIdleTrickedSequence` | 5 + 4 (3 уровня) | TrickItem.cs:730 | тртикнутый идл — секвенция, не одиночная анимация |
| `TrickItem.IdleNormalSequence` + `PlayIdleNormalSequence` | 1 + 1 | TrickItem.cs (тот же блок) | то же для нормального идла |
| `TrickItem.DontPlayIdleOnStart` | 1 | TrickItem.cs:214 | предмет не играет идл при загрузке |
| `Door.IgnoreIdleAnimation` | 8 дверей (4 уровня) | Door.cs:211 | дверь без идла (порт всегда играет `IdleAnimation`) |
| `TrickItem.AnimateDependant` | 3 (2 уровня) | TrickItem.cs:958, 990, 1046 | использование анимирует и `Dependant`-предмет (UseNormal/UseTricked на нём) |
| `Item.PrimedMaterial` | 1 | Item.cs:1236-1239 | квад предмета меняет материал при prime |
| `Item.DisableColliderWhenPrimed` / `EnableColliderAfterPrime` | 1 / 2 | Item.cs:1258 / 1326 | коллайдер гаснет/включается от prime (обобщение Pipe-хака, который порт хардкодит) |
| `SearchItem.TakeItemMultipleTimes` | 10 (5 уровней) | Item.cs:1415 | предмет отдаёт инвентарь повторно, пока держишь такой же; с `MultipleItemsString`-пузырём (Item.cs:1418) |
| `Kid.UseLinkedTrickSequence` | Level207 (KidPlaySingle/KidTongue/KidWeep) | TrickItem.cs:648 (SandCastle linked) | кид-реакция на связанный трюк песочного замка; `UseNormal/UseTrickedSequence` порт читает, этот — нет |
| `Rottweiler.ExtraCoinAngerAmount` | 1 | Rottweiler.cs:647 | добавка к гневу за «экстра-коин» |
| `TrickItem.CheckDependsOnTricked` | 2 (1 уровень) | TrickItem.cs:1178, 1199, 1220 | выбор идла с учётом depends-цепочки |
| `TrickItem.IgnoreDependsOnWhenFixed` | 1 | TrickItem.cs | вариация фикса depends |
| `TrickItem.BlockValveAfterFix` | 2 (1 уровень) | TrickItem.cs | вентильный хак |
| `Item.GoNextAction` | 2 (1 уровень) | ActionManager.cs:620-622 | resume после urgent прыгает на следующее действие (парный к `MarblesNextAction`, который порт знает) |
| `Item.DoNothingWhileBeeingUsed` | 1 | Item.cs:1429 | клик Woody по предмету, который сейчас использует сосед, игнорируется без NoNo |
| `Item.PickUpObjectWithoutGameObject` | 1 (Flowers) | Item.cs:1421 | цветочный хак подбора |
| `TrickItem.MainValveOpen` | **сериализован `true`** на Level113 `ValveMain` | Item.cs:1335, 1352, 1714 | порт инициализирует `main_valve_open = False` (scene.py:374) — ранний гейт unprime-свопа (Item.cs:1335, `ActionStartIndex <= 3`) в порте открыт, в оригинале закрыт до первого клика |

### Тексты, пузыри, HUD

| Поле | Данные | Потребитель | Эффект |
|---|---|---|---|
| `Item.DescriptionTrickedString` (+`Description*` семейство: Primed/Fixed/Fuckedup/Compound/CompoundTricked/LinkedTrick), `Item.DeltaDescriptionLocation` (162), `Item.LongDescription` (50), `HUD.LongTextBubbleRect/Texture` | **218 предметов** только Tricked-вариант; вся система на каждом уровне | Item.cs:1662, 1694, 1698, 1816 (fail-ветки `CanWoodyUse`) → `ShowItemTooltip(GetDescriptionString())` → HUD.ShowItemTooltip(поз. + `DeltaDescriptionLocation`, `LongDescription`) — Item.cs:1851; GetDescriptionString: Item.cs:2329+ | **речевой пузырь с описанием над предметом** при отказе использования (заперто/уже тртикнуто/не то в руках). Порт играет NoNo, но пузыря не рисует. Сюда же: `NotPrimedTooltip` (6; Item.cs:1433, 1828), `MultipleItemsString` (6; Item.cs:1418), `ItemInUseString` (1; TrickItem.cs:549), `InventoryTooltips` (2; Item.cs:1834+), `SecondRequiredItemString` (1; своп Item.cs:1751-1752), `InspectItem` (весь класс — CanWoodyUse всегда false + пузырь), `Drawing.EmptyDrawingString` (Drawing.cs) |
| `Item.NameFixedString/WithFixedString/DescriptionFixedString` + `UseFixedStrings` | 3-5 предметов | Item.cs:2113-2118 (TryFix): подмена Name/With/Description | после починки имя предмета в тултипе меняется; hud.py `_get_name_string` не знает Fixed |
| `Item.NameFuckedupString/WithFuckedupString` | 7-8 | Item.cs (GetNameString/GetWithString ветки) | имя в состоянии FuckedUp; порт не знает |
| `Item.NameCompound*/WithCompound*` | 3-4 | Item.cs | имена компаунд-состояний; порт не знает |
| `HUD.TooltipMotherRect` | 14 сцен | HUD.cs:613: при наличии Матери `TooltipRect = TooltipMotherRect` | на материнских уровнях постоянный тултип живёт в другом месте; hud.py всегда рисует в `TooltipRect` |
| `HUD.WhistlingSound` + `PlayWhistle()` | 28 | HUD.cs:1473-1481; вызовы Item.cs:2167, Rottweiler.cs:690 | свисток: звук + рестарт `WhistleAnim` при событии; порт запускает whistle-анимацию один раз на старте и звука не играет |
| `Actor.SpecialBubbleForMother` + `BubbleMotherIconPath` | 1 | RoutineAction.cs:59-70, Actor.cs:51 | материнский пузырь думания с отдельной иконкой |
| `MouseCursor.TextureDeltaLoc` | 28, (−0.001, −0.07, 0) | MouseCursor.cs:117 | сдвиг курсора — доли пикселя, эффект ничтожен; документировать |
| `ProgressBar.TexturesGUIDepth=BackHUD`, `HUDGUIDepth=Menu` | 15 | ProgressBar.cs (SetGUIDepth) | мировой бар рисуется на глубине BackHUD — ПОД панелью HUD; hud.py рисует бары после HUD → поверх. Виден при баре у нижнего края |
| `GameInfo.GameMode` | 28/28 `Classic` | GameInfo/Rottweiler/HUD | порт предполагает Classic — данными подтверждено; `NewScoreboard`/`WoodyLives` (Modern) мертвы |

### Звук (порту недоступно = не слышно)

| Поле | Данные | Потребитель | Эффект |
|---|---|---|---|
| `MusicPlayer.*` | 28 сцен × 17 полей | Level.cs:297 (`PlayLevelMusic`, фон `LevelSounds[1]`, задержка 15 с при первом старте), GameInfo.cs:312/329/339/384/388 (`PlaySuccess(perfect)` / `PlayCaughtMusic` ×2 / `PlayFailedMusic`), MusicPlayer.Start (`EntranceClap`), IntroAnimation.cs:311 (`PlayEntranceMusic`) | **вся музыка уровня**: фоновый трек, стинги поимки/успеха (обычный/перфект)/провала, аплодисменты входа. `UseAlternateSounds` (4 уровня) выбирает `AlternateLevelSounds[1]`. `PlayJokeMusic` — мёртв (нет вызовов). `HoverSound`/`ClickSound` — только меню (за скоупом) |
| `Rottweiler.MediumLaughs/BigLaughs/LaughVolume` | 28 × (3+3 клипа, 0.15) | `PlayAudienceLaugh` (Rottweiler.cs:806-818), вызовы :601 (Medium) / :609 (Big) из angry-веток | закадровый смех аудитории при трюке (обычный/компаунд). Не слышно в порте |

### Переданы из основной сессии (не дублирую)

`ItemTipIcon`-семейство (Info-кнопка), `Fence*` (заборы Level.OnGUI),
`HideOwnerOnAnimationEnd` (88), `ShowChildRenderersOnEnd` (14),
TrickCamera-подсистема (`ForceTrickCamera`=false везде, настройка
PlayerPrefs — спящая опция; `DontShowTrickCamera` 1 SearchItem).

## Мёртвые поля (потребителя нет ни в одном .cs) — 43

Вырезанный контент, документировать и не носить:
`AlarmClock, BoatCoinSlot, BoatCoins, CapHat, Captain, ChefAnimations*,
CoinScore, ConfirmTexture, DoNothingLinkedTrick, EndGame, EntranceVolume,
ExtraAnimation1/2, FinalCutScene, FixAnimationExtra (все Item, значение
"Desperate"), FlyAnimation, IgnoreTrickedExitDelta, InfoButtonsAnim,
ItemExtra, Level210, LevelStart, LifeScore, NoTexture(+Hover), Phone,
ReturnAnimation, Skii, SneakButtonsAnim, StartTimeScore, StatueScore,
Table, TestAnimationState/Type, TimeScore, ToiletWomen, ToolBoxRenderer,
UseHUDIcon, WoodyBackground, YesStyle/YesTexture(+Hover),
AnimationAngryCollapse (все Item несут "AngryCollapse" — вызова нет)`.
(`ChefAnimations` — поле мертво; Chef-хак в Rottweiler использует
литералы.) Плюс подтверждено из основной сессии: `AlternateStartFrame`
(11644 значений), `OverridesTransformation` (56; единственный потребитель
`Pawn.AnimationOverridesTransformation`, Pawn.cs:893, сам никем не
вызывается — перепроверено), `SlowAnimationsFactor` (=100.0 везде;
`Owner.ShouldSlowAnimations` никто не ставит — hook порта совместим),
`Alerter.PoorSequenceSkates` (4; единственный вызов `WakeAnimation()`
сам никем не вызывается), `PawnAnimationController.SearchAnimation*`
(отладочный Debug.Log-поиск в Start), `Actor.ExchangeIconPaths`/
`BubbleIconAlternatePath` (8; обменный метод не вызывается),
`Pawn.PawnZ` (только z-канал вставного шага — глубина, порту не нужна),
`Rottweiler/Olga.DebugPathTexture/DebugMoveLocationTexture` (debug-рисование
пути в Pawn.OnGUI за флагом RenderDebug), `HUD.MotherAngryAnim`
(`PlayMotherAngry` никем не вызывается), `HUD.CompleteEpisodeAnim` /
`InfoButtonsAnim` / `SneakButtonsAnim` (один кадр, Times=[0] — эффекта нет).

## Компоненты сцен, которых порт не инстанцирует

| Компонент | Кол-во | Вердикт |
|---|---|---|
| MusicPlayer | 28 | **портировать стинги+фон** (см. выше) |
| AudioSource | 199 | 6×28 — сорсы MusicPlayer (на Main Camera/Level), + SoundNormal/SoundScratch (граммофон L114 — документирован в README как audio-only arm) + 1 GameObject; вне музыки потребителей нет |
| AudioInstantiate | 29 | класс ПУСТ (AudioInstantiate.cs — no body) → мёртв |
| IntroAnimation | 28 | титульные карточки эпизода (лого → «Season N — Episode M»); за скоупом README (title cards not modelled), задерживают геймплей и зовут `PlayEntranceMusic` |
| GameIntroAnimation | 28 | сплэш при запуске приложения («tap to start») — за скоупом |
| InGameMenu / LevelDataGUIRenderer / Control* / ExitConfirmation / LevelLoader | 42+~500 | меню — за скоупом README |
| LevelScript | Level201, Level206 | туториалы NFH2 — за скоупом README |
| TutorialScriptCameraNFH2 / -206 | L201 / L206 | там же |
| DirectorAnimation | 30 | интро-сцены — за скоупом |
| Mobile_EventListeners, AllocMem, TaskScheduler, InputManager, BugTest, cls92, LightProbeProxyVolume | 28×
| платформенно-технические; геймплейного эффекта нет |
| InspectItem | 1 (Level212) | hover-тултип порт знает (hud.py); клик-описание — в системе речевых пузырей выше |
| Drawing / Rake | 1 / 1 | подклассы TrickItem, порт учитывает kind; их поля Description*/Name* — в находке про пузыри |
| ArrowSignDepth | **0 сцен** | класс не инстанцирован — мёртв |

## Топ-10 по видимости для игрока

1. **Музыка и стинги** (`MusicPlayer`) — не слышно вообще ничего.
2. **`Door.DeltaExitLocation`** — позиция Woody после КАЖДОЙ двери
   (196 дверей, ±0.2/−0.4).
3. **Речевой пузырь описаний** (`ShowItemTooltip` + 218 строк данных) —
   каждый отказ использования в оригинале говорит, в порте молчит.
4. **Открытые ящики** (`SearchItem.OpenObject`, 61) — обыск видимо
   открывает мебель.
5. **Смех аудитории** (`MediumLaughs`/`BigLaughs`) + **свисток**
   (`WhistlingSound`) — звуковая реакция на каждый трюк/гнев.
6. **Плавная камера** (`CameraMover.SpeedX/Y`) — вся манера движения
   экрана.
7. **`WoodyDeltaUseHeight`** (77 предметов) — вертикальное «на месте»
   Woody: недоход/перелёт у высоких предметов.
8. **Idle-вариации Woody** (30 с, S1) — заметно при простое.
9. **`HelloAnimation`** — жест в конце входа на уровень.
10. **Тултип на материнских уровнях** (`TooltipMotherRect`) — позиция
    постоянной подсказки на 14 сценах S2.

## Замечания за пределами директивы (для других проходов)

- `Rottweiler.OnFall`/`FallAction` (Rottweiler.cs:841, 859) — падение
  при walk-nearby: сверить с портом (проход 2).
- `SurpriseActionFar/Near`, `AlarmAction`, `ToiletAction` — сериализованные
  шаблоны urgent-действий; порт строит эквиваленты программно — сверить
  поля шаблонов (Duration, PostponeAlarm, ForceUseOriginalAnimation).
- Dexterity-ректы (190×190, 80×80) — порт хардкодит те же числа; данные
  одинаковы во всех 15 компонентах, риска нет.
- `Woody.GoToString` = WOODY_GOTO (28) — ключ «Идти сюда»-тултипа зоны:
  hud.py рендерит GoTo-состояние пустым (HUD.cs:1049-1051 — проверить,
  что GoTo-ветка действительно пуста и для зон с именем).
