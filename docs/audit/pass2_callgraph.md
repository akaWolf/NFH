# Проход 2: замыкание графа вызовов

Методика: раскрыты тела портированных методов в src/Assembly-CSharp (Woody.cs,
Pawn.cs, Rottweiler.cs, Item.cs, TrickItem.cs выборочно, ActionManager.cs,
RoutineAction*.cs все 10, GameInfo.cs, Level.cs, Alerter.cs, Door.cs,
SearchItem.cs, HideItem.cs, Mother.cs, Olga.cs, Kid.cs, Helpers.cs, HUD.cs
выборочно, AnimationInstance.cs, InspectItem.cs, MouseCursor.cs); каждый вызов
Assembly-CSharp-метода изнутри сверен с runtime/ grep-ом по имени и по ссылке
File.cs:NNN, спорные — чтением порта. Данные уровней использовались как фильтр
мёртвых полей (0 не-дефолтных значений = мёртвое ребро).

Счётчики: раскрыто ~80 методов, проверено ~210 рёбер; непройденных рёбер 24;
доказанно мёртвых 12. Поведения (behaviors.py) проверены выборочно
(SkiBehavior построчно совпал, Level208Behaviors/OlgaExtra/KidActions
совпали) — сплошная сверка 47 классов не делалась.

Уже известные основной сессии (не дублируются): HideOwnerOnAnimationEnd,
ShowChildRenderersOnEnd, ItemTipIcon/Item.OnGUI, Level.OnGUI fences,
TrickCamera.

## Непройденные рёбра

| # | Портированный метод | Пропущенный вызов / ветка | Оригинал | Данные | Видимый эффект |
|---|--------------------|---------------------------|----------|--------|----------------|
| 1 | Item.CanWoodyUse (и все ветки отказа) | CheckDescriptionTooltip → Item.ShowItemTooltip → HUD.ShowItemTooltip → DrawDescription | Item.cs:1378, 1812-1853, 1418, 1433, 1662, 1694, 1698; HUD.cs:636-638, 673-709; сброс Woody.cs:773 (MoveToGoal), GameInfo.cs:366 | DescriptionString/InventoryTooltips/NotPrimedTooltip/MultipleItemsString у сотен предметов | Пузырь с текстом над предметом при «пустом» клике (описание, «не то в руках», «сначала заправь») не показывается вовсе. Также InspectItem.CanWoodyUse (L212), TrickItem.CheckDescriptionTooltip (занятая кровать, ItemInUseString, TrickItem.cs:545-553), Door.CanWoodyUse Locked (Door.cs:230-240), Woody.PlayWontGoAnimation WrongZoneTooltip (Woody.cs:872-884) |
| 2 | Woody.FindInput | 30-секундный idle: PlaySingleAnimation(IdleAnimations[Random.Range]) | Woody.cs:612-623 | IdleAnimations сериализованы на Woody, IdleThreshold=30 | Woody, стоя без дела 30 с, потягивается/зевает (не NFH2). Порт: стоит вечно |
| 3 | Woody.CheckMouseClick / OnBlockingAnimationEnded / OnDoorEnterAnimationFinished | StoreBlockedInput / отложенный ProcessMoveInput | Woody.cs:642-656, 336-341, 484-488, 684-700 | — | Клик во время blocking-анимации/за запертым вводом не теряется, а исполняется по её концу. Порт роняет такие клики |
| 4 | Woody.OnBlockingAnimationEnded | FearLeftShort→PlayLoopingAnimation(FearLeftRepeat) (right — аналогично) | Woody.cs:343-353 | FearLeftRepeat/FearRightRepeat в Woody-анимациях | После вздрагивания от пса Woody должен стоять и трястись в лупе, пока игрок не кликнет; порт ставит обычный stand |
| 5 | Woody.SeeAlerter | AnimationsInProgress → PostponeAlert (флинч после конца текущей анимации использования); Frozen-гейт | Woody.cs:1033-1044, 232-236 | — | Пёс замечает Woody посреди использования предмета: оригинал доигрывает use и потом флинчит; порт флинчит сразу (рвёт use-анимацию) |
| 6 | Woody.StartMoveToLocation | SaveMoveState/LoadMoveState: неудачный клик восстанавливает прежний маршрут | Woody.cs:702-741, 812-846 | — | Клик в «никуда» во время похода: оригинал продолжает прежний путь, порт бросает движение |
| 7 | Woody.ShouldAbortMove | инвентарь-в-руках мимо цели → SetUsedInventory(null)+отмена; по двери → идти к двери; WasHiding-ветка | Woody.cs:782-810 | — | Сброс выбранного предмета при промахе; повторный клик по шкафу после выхода = подойти, не прятаться |
| 8 | Woody.CheckTargetItem / ShouldGoToItem | IsFloor-предмет: без инвентаря → обычный goto; с чужим инвентарём → PlayWontGoAnimation, поход отменён | Woody.cs:848-870 | 57 IsFloor-предметов (S1) | Клик по «полу-предмету» (лужа и т.п.) без нужного предмета не должен вести Woody к TargetLocation предмета |
| 9 | Pawn.IsAtUseLocation (Woody-вариант) | + item.WoodyDeltaUseHeight; UseWoodyExtraDeltaHeight → + Woody.ExtraDeltaHeight | Pawn.cs:1690-1705, Woody.cs:744-755 | 77 предметов с WoodyDeltaUseHeight≠0; 2 с UseWoodyExtraDeltaHeight | Высота, на которой Woody останавливает climb к предмету, — у 77 предметов порог другой |
| 10 | Pawn.MoveToDoor (ExitDoor) | ShowExitConfirmation-диалог; OnDoorEnterAnimationFinished → GameInfo.FinishGameOnHUDClick | Pawn.cs:1378-1383, 1445-1452, 1500-1515; Woody.cs:552-569; Pawn.cs:1662-1665 | ExitDoor-двери на всех уровнях | Выход с уровня через выходную дверь (диалог подтверждения → финиш) в порте отсутствует |
| 11 | Pawn.WalkOnPath / BuildPath* | UseDoorAtOnce: клик в дверь, у которой уже стоишь, использует её без повторного climb | Pawn.cs:748-777, 1391-1397, 1412-1414; Woody.ShouldExitDoorNow:777-780 | — | Повторный клик от двери — мгновенный проход |
| 12 | Woody/Mother/Olga.CheckMoveLocationY | MoveLocation += TargetTransition.Delta{Woody,Mother,Olga}Location на ComplexMove-шаге | Woody.cs:939-950, Mother.cs:28-39, Olga.cs:124-135 | 61 ненулевая дельта на Transition | Точка прицеливания на лестницах смещена per-pawn; порт применяет только Door-дельты Item.GetTargetLocation |
| 13 | Mother.OnDoorEnterAnimationFinished | position = door + DeltaMotherExitLocation (вместо DoorDistanceDelta) | Mother.cs:54-61 | 1 дверь с ненулевым значением | Мать выходит из этой двери в другой точке |
| 14 | catch-флоу (порт world._catch) | RoutineActionMotherHitWoody.OnActionStarted НЕ вызывает MoveToEmptySpace | RoutineActionMotherHitWoody.cs:24-32 | MaxDist=0.8 на всех её HitWoodyAction | Порт телепортирует Мать на позицию Woody перед избиением — оригинал бьёт с места остановки (в пределах 0.8). Обратная ошибка класса MoveToEmptySpace |
| 15 | Rottweiler.PlayAngryAnimation (Classic) | PlayAudienceLaugh(Medium/Big): MediumLaughs/BigLaughs[Random.Range(0,3)], volume×20 | Rottweiler.cs:601, 609, 805-818 | клипы сериализованы на Rottweiler | Закадровый смех зала при каждой злости не звучит |
| 16 | Rottweiler.PlayAngryAnimation | ветка Modern/NFH2Path целиком: AngerAmount-лестница, ExtraCoin-хаки, статуя (OnStatueAchieved+PlayStatueAchieved+PlayWhistle), RandomFreakOut | Rottweiler.cs:613-693 | NFH2Path=true на всех 14 S2-уровнях; GameMode=Classic везде | На Season 2 порт играет Classic-злость вместо лестницы по AngerAmount; статуи и freakout не случаются. NB: RandomFreakOut = Range(0,1) — всегда RottFreakoutHead |
| 17 | HUD-морда злости | PlayRottweilerAngry(level 1/2/3) выбирается уровнем злости из PlayAngryAnimation; Restart(PlayRottweilerIdle) возвращает idle по концу | HUD.cs (PlayRottweilerAngry), Rottweiler.cs:600, 607 | RottweilerAngry1-3Anim | Порт мапит морду по angry_count_ticks: вторая подряд злость даёт Angry2 вместо Angry3; возврат в idle привязан к состоянию метра, а не к концу анимации |
| 18 | старты рутин | DelayStart 1.5 с у Rottweiler/Mother/Olga; клок и FindInput ждут IntroAnimation.Finished | Rottweiler.cs:153, 916-932; Mother.cs:18, 75-86; Olga.cs:8, 28-39; GameInfo.cs:237-254 | — | Все рутины и часы в оригинале стартуют на 1.5 с позже (плюс intro); тайминги state.jsonl сдвинуты |
| 19 | Rottweiler.MoveToAlarm | name-hack CabinPhone → AlarmAction.Urgent=true | Rottweiler.cs:869-877 | CabinPhone в Level211 | Бег (а не шаг) на телефонный алярм L211 |
| 20 | ChangeZone-реакции (порт zone_reaction) | CrabAnimations: SearchItem-крабы — вход в зону играет LeaveZone («спрятался»), выход — EnterZone+unhide; NFH2 TrickItem-канал с гейтом !Primed; door-канал гоняет только TrickItem-списки | Pawn.cs:1560-1596; SearchItem.cs:275-293; Zone.cs:64-98; TrickItem.cs:1095-1113 | 2 SearchItem (L202, L207), 4 TrickItem (L107/110/111/208) | У крабов анимация инвертирована в порте (играет enter при входе); primed-гейт не проверяется |
| 21 | Item.GetRottweilerUseAnimation | Coal name-hack: RottweilerUseAnimation[0] = CoalFuelWalk / CoalWalk по LinkedItemTrick.Tricked | Item.cs:988-1002 | Coal в Level209 | Уголь: походная анимация use не переключается на «с топливом» |
| 22 | GameInfo.OnNeighborCaughtWoody / FinishGameOnHUDClick / PlayWinAnimations | MusicPlayer.PlayCaughtMusic / PlayFailedMusic / PlaySuccess(perfect) | GameInfo.cs:304-341, 373-389 | MusicPlayer в каждой сцене | Музыка исходов (win/fail/caught) не звучит — MusicPlayer не портирован вовсе |
| 23 | тултипы курсора | зонная End-ветка (exit-зона «End: X»), Door-ветки (Locked → LookAt, Exit → End, GoTo пусто); MakePermanentTooltip/ColoredTooltip: после клика «Use X with Y» закрепляется цветным до прибытия | MouseCursor.cs:304-347; HUD.cs:640-649, 1024-1080, 1310-1330 | ColoredTooltipStyle в hud-секции | Порт перерисовывает тултип каждый кадр: цель «with …» и цветовая фиксация теряются; тултипы дверей/exit-зон отсутствуют |
| 24 | Woody.CheckMouseClick | гейт вертикального прохода (Run_Up/Walk_Up XOR), unhide-по-клику с отложенным вводом, `!NFH2Path && itemAux is Door` повторный ProcessMoveInput | Woody.cs:642-671 | — | Клики в укрытии/на лестнице обрабатываются иначе, чем в порте (порт принимает всё) |

Примечание к 14: порт применяет MoveToEmptySpace обоим ловцам — для
Rottweiler это верно (RoutineActionHitWoody.cs:28), для Матери нет.

## Доказанно мёртвые (в этой сборке)

| Ребро | Доказательство |
|-------|----------------|
| AnimationInstance.AlternateStartFrame | 11644 не-дефолтных значений в данных, ни одного чтения в Assembly-CSharp (grep: только объявление AnimationInstance.cs:18) |
| AnimationInstance.OverridesTransformation / Pawn.AnimationOverridesTransformation | 56 значений в данных; единственный потребитель Pawn.cs:893-895, у которого нет ни одного вызывающего |
| Woody.OnGetCaughtByNeighbour / Pawn.WaitWoodyGoToRott | нет вызывающих (grep по всем .cs: только объявления Woody.cs:263, Pawn.cs:147) |
| Mother.MoveToEmptySpace | нет вызывающих (Mother.cs:142; RoutineActionMotherHitWoody его не зовёт) |
| Alerter.WakeAnimation / PoorSequenceSkates | нет вызывающих (grep: только объявление Alerter.cs:198) |
| RoutineActionUse.IgnoreNextActionAfterUrgentMove | 0 не-дефолтных значений во всех 31 JSON |
| Item.PrimedOffset / ChangeScaleWhenPrimed / ObjectToHideWhenPrimed | 0 не-дефолтных значений |
| HUD.DrawLives | гейт GameMode==Modern; GameMode=Classic во всех 31 сценах |
| HUD.DrawExtra | virtual с пустым телом, override-ов нет |
| Pawn.OnGUI (DebugPath-текстуры) | debug-рисование за флагом DebugPath (дефолт false) |
| Item.NFH2Tutorial-телепорт (Rottweiler.cs:439-447) | поле true только в туториале Level201 — туториальный слой документирован как непортированный |
| GameInfo touch-скип финалки (canSkip/TapOnce, GameInfo.cs:257-289) | завязан на Input.touchCount — на десктопном эталоне недостижим; порт финалку не скипает |

## Сомнительное / мелочи (проверить при фиксах)

- Item.PrimedMaterial: один предмет (L108 FirstAid) меняет материал квада при
  prime — порт не умеет материалы квадов.
- SetTooltip(GoTo) всегда пуст — порт совпадает, но исходно зонная ветка
  дальше End не различалась; закрыто пунктом 23.
- Rottweiler.Start: NFH2Path → CanDecreaseAngryMeter=true с самого старта
  (Rottweiler.cs:155-158) — сверить, когда порт начинает тикать метр на S2.
- PlayWinAnimations фризит только Rottweiler (не Mother) до конца
  win-анимации (GameInfo.cs:304-313); порт фризит всех сразу — микро-тайминг.
- Двойной предикат поимки: Pawn.HasNeighborCaughtWoody (Pawn.cs:366-388,
  вызывается на выходе из двери и после ComplexMove) отличается от
  GameInfo.CanRottweilerSeeWoody отсутствием пары (!blocking || !sneaking) и
  Bed-кейса; порт гоняет единый предикат каждый кадр — практическая разница
  только в кадре выхода из двери.
- RoutineActionHitWoody.GetRandomSequence: пороги 25/50/75 на Range(0,100)
  дают веса 26/25/25/24 — порт использует равновероятный choice; допустимо.
