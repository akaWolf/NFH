# Проход 1: контракты движка (аудит)

Сверка всех Unity-API вызовов портированных подсистем с runtime/. Сокращения:
`AR` = Helpers.AdjustRectangle (x*W, y*H, **w*W, h*H**),
`ARRS` = AdjustRectangleRelatizeSize (x*W, y*H, **w/800*W, h/600*H**),
`W2S` = Camera.main.WorldToScreenPoint + y-флип `Screen.height - y`.

## Таблица контрактов

| API (место) | Контракт | Порт | Вердикт |
|---|---|---|---|
| AnimationControllerBase.DrawAnimation (cs:153-170) | W2S + дельты*(Height/OriginalHeight); UV-кадр снизу-слева | render.draw_sprite | ✔ (сверено ранее) |
| AnimationInstance.SetDimensions (cs:145-149) | Height=OH*H/600; Width=OW*H/600 | render scale=h/600 | ✔ |
| HUD.AdjustRectangles (HUD.cs:519-573) | все ректы ARRS, **кроме TrickCameraBackgroundRect (AR)** | hud._adj = ARRS | ✔ для всего портированного; TrickCamera не портирован |
| HUD.OnGUI (617-627) | SetGUIDepth(HUD=11); Repaint-only; DrawHUD + TrickCameraHUD | hud.draw | ✔ (TrickCamera спит: настройка PlayerPrefs=0, ForceTrickCamera=false во всех 28) |
| DrawHUD порядок (629-661) | Description→Base→Inventory→Tooltip→Buttons→AngryMeter→Tricks+Time (не тутор)→Characters→Lives(Modern)→Extra→Score→AngryCount | draw(): dex→base→inv→tooltip→buttons→meter→tricks+time→chars→bars→score→angry | ✔ кроме Description (см. Р1) |
| DrawDescription (673-700) | пузырь на W2S(DescriptionPosition), x-w/2, y-h*1.25; Long/обычный по флагу; DescriptionStyle | — | **НЕТ** (Р1) |
| DrawTooltip (1082-1094) | TextArea(TooltipRect, Colored?ColoredStyle:TooltipStyle) | _text(TooltipRect, small) | частично: нет жёлтой фиксации (Р2) |
| DrawBase (1096-1114) | 3 текстуры по наличию Mother | _draw_base | ✔ |
| DrawTime (1116-1138) | mm:ss / --:--; скрыто при NFH2Path; TimeStyle/TimeShadowStyle ARRS | _draw_time | ✔ |
| DrawCharacters (1140-1190) | лица из массивов; think bubble + BubbleIcon/Active | _draw_characters | ✔ |
| DrawTricks (1195-1223) | лестница TricksRects (InitializeTricks), TrickDone анимация, Statue | _draw_tricks | ✔ формулы (визуальную сверку даст проход 4) |
| DrawAngryMeter (1230-1252) | empty; full **через UV-клип AngryMeterFullUVRect** (не BeginGroup); WhistleRects[frame] | _draw_angry_meter | fill ✔; whistle **НЕТ** (Р12) |
| DrawAngryCount (664-671) | DrawLabel(AngryCountRect, "xN", TimeStyle); гейты DontShow / NFH2Path | _draw_angry_count | ✔ |
| DrawScore (712-765) | TextField'ы; **ScoreStyleHover при hover** | _draw_score | текстуры ✔, hover-стиль текста нет (Р15) |
| DrawLives (767-774) | только GameMode.Modern | — | Modern-режим вне скоупа Classic — документировать |
| DrawInventory (947-1021) | pres/hov/norm; бабл после 1 c; **LongTextBubble для длинных** (1001) | _draw_inventory | ✔ кроме Long-варианта и стиля текста (Р13) |
| DrawActionButton (825-895) | hover/norm/pressed; **InfoBtn: touch-удержание → ShowInteractionIcon=true, отпуск → false** (860-895) | _draw_buttons | кнопка ✔, **info-механика НЕТ** (найдено в основной сессии) |
| Item.OnGUI (2740-2760) | ItemTipIcon при ShowInteractionIcon; W2S; WidthRatio=W/800 per-axis, HeightRatio=H/600; depth ItemsFront=24 | — | **НЕТ** (в связке с info-кнопкой; основная сессия) |
| Level.OnGUI (322-341) | заборы: W2S(FencePositions[i]), размеры FenceRects (LoadFenceSize: w=H/W*1.75/0.75 при !IgnoreFenceSize, потом AR), depth LevelFence=13 | — | **НЕТ** (основная сессия; 4 уровня живых) |
| HUD.CheckClick (1246-1385) | порядок: ExitConf→(ending: score/power+ToggleMenu)→inventory→**фиксация тултипа**→prev→**info(съесть)**→sneak→next→power→complete→**лица=SnapTo***→ClearTooltip | check_click | частично: Р2, Р4, Р17, Р18 |
| Woody.FindInput (581-624) | Esc=меню; **правый клик == левый** (StartMoveToLocation игнорирует кнопку); **idle-анимации через 30 с** Random.Range(0,n) | viewer.run | idle **НЕТ** (Р6) |
| Woody.CheckMouseClick (631-672) | HUD.CheckClick ∥ **MouseOverHUD** ∥ timeScale==0 ∥ … → игнор; Hiding→Unhide+буфер; **InputLocked/Blocking→StoreBlockedInput** (буфер, реплей в 336/484); Run_Up/Walk_Up — игнор кликов | viewer.run | гейты частично: Р4, Р5 |
| Pawn.MoveToLocation (394-421) | Physics.Raycast(MoveLocation, cam.forward) — **ближайший по z коллайдер** | viewer._item_at (порядок словаря) | приемлемо; краевой случай (Р22) |
| Pawn.GetMoveDestination (556-...) | предмет: CanUse+ShouldGoToItem, иначе WontGo; двери: locked Transition=игнор, инвентарь в руках=WontGo, своя зона=LinkTo+StopAtExitDoor, чужая=к двери, locked=использовать как Item | world/viewer | гейты **НЕТ** (Р7); дверные ветки — сверка в проходе 2 |
| Helpers.GetItemFromCollider | GetComponent("Item") строго на объекте коллайдера | level.items по коллайдеру | ✔ |
| Helpers.GetZoneFromCollider | GetComponentInChildren<Zone> | zone_at | ✔ |
| Woody.StartMoveToLocation (712-741) | неудачный raycast → **ClearTooltip + SetUsedInventory(null)** + LoadMoveState | viewer: печать "no route" | **НЕТ** (Р3b) |
| SetCurrentInventory/SetUsedInventory (1046-1075) | двухступенчато: Current (выбран) → Used (применён при клике в мир) | InventoryState.used одноступенчато | модельное расхождение (Р3) |
| DexterityComponent.StartDexterity (137-177) | ректы **int-делением** H*80/800, W*80/1280, H*190/800, W*190/1280 + Aux-сдвиги; Cursor.lockState=Locked | DexterityState.start float-делением | int vs float: субпиксель (Р10) |
| DexterityComponent.FixedUpdate (183-271) | touch.delta*25; рандом-вектор раз в 1 с ±[20,19]*2; CheckMargins клампит и ставит FillSpeed=1.2, но **строка 243 безусловно возвращает FillSpeed=1f** → буст мёртв; sway=25-|Δцентров|*ratio; win 85 / lose 10 (пол 12) | DexterityState.tick | формулы ✔; **порт сохраняет 1.2 при wrong → дренаж быстрее оригинала** (Р9) |
| DexterityComponent.UpdateRandomMovement (341-359) | Random.Range int [-20,19]; знак Range(-1,1)<0 (50%) | randrange те же | ✔ |
| DexterityComponent.OnGUI (428-454) | bg; RotateAroundPivot(180°, центр bg)+BeginGroup(h*pct)+полная текстура → нижняя полоса, перевёрнутая, верхняя доля текстуры; потом item-ghost и pick; depth BackHUD=12; гейт !IsTrickCameraOn | hud._draw_dexterity RenderCopyEx(180) | ✔ (эквивалентность доказана: образ группы [bg.y+h-pct*h, bg.y+h]) |
| DexterityComponent.WinDexterity (369-388) | DexterityOtherAnimation = **жёстко N2TrickItemUseNormal** | w.play_item_anim(it, it.use_normal) | **проверить** (Р11) |
| DexterityAlert (414-426) | Rottweiler.AnimController.IsMoving() → сразу; иначе RottInAnimation | rott.state==WALK | ~✔ (IsMoving = контроллер в walk-анимации; краевые случаи прохода 2) |
| ProgressBar.Start (76-113) | ProgressRect и DeltaProgressRect через **AR** (w*W!); PawnHUDRect = FaceRect HUD'а; DataStyle.fontSize=CalculateFontSize(0)+3=(W/DW+H/DH)*10+3 | hud._draw_progress_bars: d['x']*W, r['width']*W | ✔ формула AR соблюдена; шрифт приближён (документировано) |
| ProgressBar.OnGUI (247-272) | группа на W2S+Delta; empty; вложенная группа w*clamp01(p) — клип слева; DrawLabel "N%" DataStyle | _draw_progress_bars src-crop слева | ✔ |
| HUDProgressBar.OnGUI (10-21) | группа (1-p)*h — клип низа, полная текстура → верхняя (1-p) доля; depth HUDGUIDepth (Menu/MainMenu=9/10, поверх HUD) | _face_fill src верх (1-p) | ✔ |
| MouseCursor.OnGUI (51-91) | depth MouseIcon=1 (поверх всего); **IgnoreRender=true навсегда в этой сборке** — порт восстанавливает десктоп; TrickCameraIcon-ветка спит | hud.draw_cursor последним | ✔ (документировано) |
| MouseCursor.UpdateHover (93-177) | transform.position = мышь(y-флип) + TextureDeltaLoc(-0.001,-0.07) — субпиксель; **MouseOverHUD = mousePosition.y < 100 (сырые px)**; touch-only raycast (десктоп-контракт восстановлен портом) | hud.update_cursor | ✔ при 800×600 (порт масштабирует 100 от 600 — при фиксированном окне идентично) |
| MouseCursor.UpdateCursor (350-404) | приоритет: Current-инвентарь(Use/Cancel) → item.MouseOverIcon (CanUse, Door только своей зоны) → дверь чужой зоны (locked→иконка двери! иначе Walking) → зона (чужая ∥ полоса [-0.6,0.16] у ног) → HUD/Default | hud.update_cursor | ✔ ветки; **cand=item∥door упрощает «ближайший по z»** (Р22) |
| MouseCursor.cursorSize | AR: w=0.0313*800=25px, h=0.0417*600=25px | draw_cursor r['width']*W | ✔ |
| CameraMover (83-197, 460-500) | камера свободная: скролл у краёв/стрелки (Windows-ветка) или drag (mobile); SnapTo* по клику на лица — интерполяция; SnapToWoodyImmediate = позиция Woody **без смещения**; кламп углов в Min/Max | viewer: follow=True + y+0.6; кламп ✔ | follow — осознанное отклонение вьюера (Р18/Р19); кламп документирован |
| GUIDepth (GUIDepth.cs) | BackItems 72 … Woody 16, LevelFenceBack 14, LevelFence 13, BackHUD 12, HUD 11, Menu 9-10, MouseIcon 1; больший=дальше | viewer: quads→sprites by depth→HUD→bars→cursor | ✔ порядок групп; заборы должны лечь **над пешками, под HUD** при фиксе |
| Random.Range остальные | Woody.FindInput idle (int [0,n-1]) | — | вместе с Р6 |
| Time.timeScale | пауза меню (Woody.ToggleMenu → InGameMenu) | world.menu_open + viewer Space | ✔ (виджеты меню вне скоупа, документировано) |
| GUIStyle-поля с данными | см. Р13/Р14: DescriptionStyle ContentOffset.y=-10, Padding 4/4, WordWrap=1; все стили TextClipping=1; TimeStyle StretchWidth=0 | _text: только m_Alignment | **частично НЕТ** |
| Camera.orthographicSize | в экспорте `objects[Camera].data == {}` — поле не выгружено | ORTHO_SIZE=3.0 | открытый вопрос (сверено ранее вне экспорта, README) |

## Расхождения (по убыванию видимости)

**Р1. Пузырь описаний (ShowItemTooltip/DrawDescription) не портирован.**
HUD.cs:673-710, Item.cs:2795-2804 (ShowItemTooltip), потребители: Door.cs:230-239 (запертая дверь), GroundItem.cs:1-11 (каждый осмотр), InspectItem.cs:5-21, Drawing.cs:94, Item.cs:1418 (MultipleItemsString), 1433 (NotPrimedTooltip), 1662/1694 (описание), Woody.cs:872-885 (WrongZoneTooltip). Пузырь висит на предмете (`position + DeltaDescriptionLocation`, LongDescription → LongTextBubble), гаснет при Woody.MoveToGoal (Woody.cs:770-775) и FinishGame (GameInfo.cs:366). Рект: x=W2S.x−w/2, y=H−W2S.y−h·1.25 (HUD.cs:697). В десктопном эталоне виден при каждом клике на не-кликабельный/запертый предмет.

**Р2. Жёлтая фиксация тултипа не портирована.** HUD.CheckClick:1319-1327: клик в мир при выбранном инвентаре фиксирует "Use X with Y" (MakePermanentTooltip, ColoredTooltip=true), DrawTooltip рисует его ColoredTooltipStyle (жёлтый 0.86,0.86,0 против белого; данные в JSON). Сброс — Woody.ClearTooltip (движение/использование/пустой клик). Порт: тултип перерисовывается каждый кадр от hover, фиксации и жёлтого нет.

**Р3. Инвентарь одноступенчатый.** Оригинал: клик по иконке = SetCurrentInventory (курсор/тултип), клик в мир = SetUsedInventory(Current) (HUD.cs:1319-1322); **неудачный raycast сбрасывает Used** (Woody.StartMoveToLocation:737-740 — ClearTooltip + SetUsedInventory(null)). Порт:선택 сразу = used; сброса по клику в пустоту нет (viewer.py:279-289).

**Р4. Клик сквозь HUD-полосу.** Woody.CheckMouseClick:637: `MouseOverHUD` (mousePosition.y<100) гасит клик даже мимо кнопок. Порт: hud.check_click возвращает False и клик уходит в мир (hud.py:979-980) — Woody ходит от кликов по нижней панели.

**Р5. Буфер заблокированного ввода.** Woody.cs:652-655 (StoreBlockedInput при InputLocked/Blocking-анимации), реплей на 336-343/484-490 (после разблокировки клик воспроизводится). Порт: `if self.woody.input_locked: continue` (viewer.py:263) — клик теряется.

**Р6. Скучающий Woody.** Woody.FindInput:612-623: без ввода и движения 30 с (IdleThreshold) → случайная из IdleAnimations (Random.Range(0,n), не-NFH2). В порте нет. Данные: IdleAnimations сериализованы на Woody каждого S1-уровня.

**Р7. Гейты клика по предмету.** Pawn.GetMoveDestination:600-618: floor-предмет + в руках не его RequiredInventory → NoNo + WrongZoneTooltip (ShouldGoToItem, Woody.cs:863-870; PlayWontGoAnimation 872-885); клик на дверь с инвентарём-от-предмета/ножом → NoNo (Pawn.cs:628-638); запертая Transition → игнор клика; запертая дверь своей зоны → «использование» двери (тултип запертости, Door.cs:230-239). Порт кликает предметы без этих гейтов.

**Р9. Dexterity: мёртвый буст дренажа.** FixedUpdate:237-243: CheckMargins ставит FillSpeed=1.2, но следом безусловное `FillSpeed = 1f` (243) — буст никогда не доживает до `PercentageDone += sway*FillSpeed*dt` (254). Порт держит 1.2, пока курсор у кромки (world.py:3399-3400, 3453-3454) — дренаж на кромке на 20 % быстрее оригинала. Чинить: FillSpeed всегда 1.

**Р10. Dexterity: int-деление ректов.** cs:158-169: `Screen.height*190/800` = 142 (int) против порта 142.5; аналогично 800*190/1280=118 vs 118.75. Субпиксель, зафиксировать в комментарии.

**Р11. Dexterity: DexterityOtherAnimation.** WinDexterity:374-379 играет жёстко `N2TrickItemUseNormal`; порт играет `it.use_normal` (world.py:3468-3470). Для носителей флага DexterityRunOtherAnimationWhenFinished сверить, что их UseNormal == N2TrickItemUseNormal, иначе чинить на буквальный enum.

**Р12. Свисток дышит размером.** HUD.cs:353-357: WhistleRects[i] = (WhistleRect.xy, (adjW+texW_i)/2, (adjH+texH_i)/2) — смешение ARRS-ширины (30px) с сырыми размерами кадров (35-43×52-61) → размер кадра свистка меняется от 32.5×60.5 до 36.5×56. Порт рисует все кадры в 30×60 (hud.py:656-658).

**Р13. DescriptionStyle не применён полностью.** Данные по всем уровням: m_ContentOffset.y=−10, m_Padding.left/right=4, m_WordWrap=1. Порт _text игнорирует всё, кроме m_Alignment (hud.py:324-358) — текст hover-пузырей инвентаря сидит на 10 дизайн-px ниже и не переносится. Также LongTextBubble для длинных описаний (HUD.cs:995-1008 — выбор по `Inventory.LongDescription`) в порте отсутствует (hud.py:597-607 всегда TextBubble).

**Р14. m_TextClipping=1 у всех стилей** — порт не клиппит текст ректом. Низкая видимость при верных шрифтах.

**Р15. Score-кнопки: hover меняет только текстуру.** Оригинал подменяет и стиль текста (ScoreStyleHover, HUD.cs:744-763).

**Р17. Power-кнопка на конце игры.** CheckClick:1302-1306 вызывает ToggleMenu и при GameEnding; порт лишь съедает клик (hud.py:935).

**Р18. Клик по лицам = снап камеры.** CheckClick:1360-1374: SnapToWoody/Rottweiler/Mother (интерполяция, CameraMover:477-500). Порт съедает клик (hud.py:976-978); follow-камера вьюера — отклонение от свободной камеры оригинала (документировать в README как решение вьюера).

**Р19. SnapToWoodyImmediate без +0.6.** CameraMover:468-471 ставит камеру ровно на Woody; порт-снап dexterity/фолоу использует +0.6 по y (viewer.py:87-90, 298-303) — в dexterity поле игры на 0.6 юнита (≈10 % высоты экрана) выше относительно оригинала.

**Р22. Один raycast vs item-приоритет.** Оригинал берёт ближайший по z коллайдер (Physics.Raycast), порт опрашивает предметы в порядке словаря и двери отдельно (viewer._item_at/_door_at, hud.update_cursor cand=item∥door). При перекрытии предмет/дверь с разными z возможен другой победитель. Ни одного конкретного пересечения не предъявлено — открытый вопрос с низким приоритетом.

## Открытые вопросы

- **Camera.orthographicSize/позиция из сцен**: экспортер пишет `Camera.data = {}` — контракт ortho=3 подтверждён только прошлой ручной сверкой (README). Доэкспортировать поле и заассертить по всем 28 сценам.
- **Р11**: собрать носителей DexterityRunOtherAnimationWhenFinished и их UseNormal (проход 3 даёт данные).
- **PawnHUDRect** берёт FaceRect ссылкой ДО/ПОСЛЕ AdjustRectangles? HUD.AdjustRectangles звана из Start (348); ProgressBar.Start читает HUD.RottweilerFaceRect — порядок Start'ов Unity не задан. Если ProgressBar.Start успел раньше HUD.Start, PawnHUDRect остаётся в долях экрана → оверлей лица микроскопический. Порт всегда берёт adjusted — вероятно, верно (Script Execution Order?), но формально порядок не доказан.
- ~~MouseDelta HUD~~ — проверено: (0,0,0) во всех 28 уровнях, вопрос закрыт.

## Сверить визуально (кандидаты в проход 4)

- лестница монет DrawTricks (фадж-факторы) — против скриншота оригинала;
- дыхание свистка (Р12) — виден ли эффект в эталонном видео;
- жёлтый тултип (Р2) и пузыри описаний (Р1) — кадры из видео прохождения.
