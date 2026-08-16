# Pass 6 — reverse audit: код без ссылок на оригинал (runtime/*.py)

Метод: AST-карта всех def/class + трёхуровневый детектор ссылок
(1: `cs:NN`/`File.cs:NN`; 2: `File.cs` без строк; 3: имя C#-метода/поля,
существующее в src/Assembly-CSharp), затем ручное чтение всех непокрытых
секций и сверка кандидатов с C#.

Важное открытие о конвенции: файл использует ТРИ стиля ссылок — полный
`File.cs:NN`, сокращённый `# cs:NN` (файл задан docstring-ом класса) и
именной (`AnimationInstance.SetStartFrame`). Сокращённых больше всего:
world.py 603, behaviors.py 266, scene.py 108, hud.py 50. Grep только по
`\.cs:\d` даёт ложную картину (behaviors.py «5 ссылок» при реальных 266).
Выборочная сверка шорткатов (RollerSkaterBehavior cs:55-57, cs:73-79;
AnimationControllerBase.cs:226-233, 254-299; Level.cs:186-189; HUD.cs:513;
TrickItem.cs:400-410) — номера строк точны (±2).

## Счётчики по файлам

| файл | defs | ссылка в самом методе | покрыт заголовком класса | без ссылки | (a) | (b) | (c) | (d)-находки |
|---|---|---|---|---|---|---|---|---|
| world.py | 263 | 232 (184 line + 48 named) | 19 | 12 | 0 | 5 | 7 | 2 |
| scene.py | 47 | 26 | 0 | 21 | 4 | 16 | 1 | 2 |
| hud.py | 51 | 37 | 0 | 14 | 7 | 7 | 0 | 2 |
| behaviors.py | 180 | 123 | 38 | 19 | 9 | 10 | 0 | 0 |
| viewer.py | 15 | 10 | 0 | 5 | 1 | 4 | 0 | 2 |
| render.py | 12 | 7 | 0 | 5 | 2 | 3 | 0 | 0 |
| record.py | 11 | 1 | 0 | 10 | 0 | 10 | 0 | 0 |
| audio_out.py | 7 | 1 | 0 | 6 | 0 | 6 | 0 | 0 |
| **итого** | **586** | **437** | **57** | **92** | **23** | **61** | **8** | **8** |

(a)/(b)/(c) — классификация 92 def-ов без собственной и без классовой
ссылки; (d) — находки уровня комментариев (заявленные эквивалентности).
SUSPECTED-INVENTION: **0** — у каждой неподкреплённой игровой логики
найден проверенный оригинал.

## (c) UNREFERENCED-LOGIC — игровая логика без ссылки (кандидаты проверены по C#)

1. **world.py:593-597 `Pawn.goto_zone`** — маршрут в заданную зону к x
   (используется urgent-переходами и поведениями). Оригинал:
   `Pawn.MoveToGoal` → `InternalMoveToGoal` (Pawn.cs:428-441); сосед
   `goto` (583-591) тоже без ссылки, его вход — `Pawn.MoveToLocation`
   (Pawn.cs:394-421). Проверено: сигнатуры и разветвление
   stopAtExitDoor совпадают.
2. **world.py:834-835 `Pawn._face_towards`** — выбор facing по знаку dx.
   Оригинал: `WasMovingLeft = Target.x < position.x` (Pawn.cs:1109) и
   выбор `Walk_Right`/`Walk_Left` (Pawn.cs:1175-1179), `IsMovingRight`
   (Pawn.cs:1192).
3. **world.py:837-838 `Pawn.walk_speed_scale`** — скорость sneaking.
   Оригинал: Pawn.cs:871-879 (`SneakFlag` → `position += Velocity * dt *
   SpeedSneaking`; SpeedSneaking=0.65 в Pawn.cs:204 — в порте берётся из
   данных, ок).
4. **world.py:841-844 `Pawn._door_anims`** — выбор leave/enter-анимаций
   двери по роли. Оригинал: пары полей `Woody/RottweilerLeave/
   EnterAnimation` (Door.cs:10-24) и `PlayWoodyEnterAnimation`/…
   (Door.cs:85-106).
5. **world.py:941-943 `Pawn._leave_played`** — сброс `door.passing` и
   возврат idle после leave-анимации. Оригинал:
   `Pawn.OnDoorLeaveAnimationFinished` (Pawn.cs:1682), вызывается из
   Door.cs:189.
6. **world.py:6054-6063 `World.start_routines`** — конструирование
   Routine по спекам + `r.start()`. Конструирование — портовая обвязка
   (в Unity ActionManager живёт в сцене), а `r.start()` соответствует
   `ActionManager.StartFirstAction` (ActionManager.cs:103). Стоит
   сослаться хотя бы на неё.
7. **world.py:6291-6295 `World._score`** — диспетчер подсчёта очков.
   Оригинал: `GameInfo.CalculateScore` (GameInfo.cs:392, вызов из
   GameInfo.cs:370); сам расчёт в `GameState.calculate_score`
   (world.py:1443) ссылки несёт — helper остался голым.
8. **scene.py:1718-1722 `Level.zone_at`** — точка→зона перебором
   BoxCollider-боксов. Это портовая замена Physics.Raycast в
   `Pawn.MoveToLocation`/`GetMoveDestination` (Pawn.cs:394-421);
   containment-тест эквивалентен попаданию луча в коллайдер зоны, но
   порядок при ПЕРЕКРЫВАЮЩИХСЯ зонах не оговорён (первая в списке
   против ближайшей по z у Raycast).

## (d) HEURISTIC — заявленные эквивалентности и их доказанность

1. **scene.py:1679-1681 `_build_graph` — «Exactly ZoneController.Start()» —
   НЕ exactly. ХУДШАЯ НАХОДКА.** Оригинал включает ребро при
   `(!Locked || TemporalLock) && LinkTo != null` (ZoneController.cs:21);
   порт отбрасывает `d.locked or d.disabled` и вовсе не знает поля
   TemporalLock (grep по runtime/ пуст). В данных 22 двери с
   `TemporalLock:true`, из них 20 одновременно `Locked:true` — все в
   s1/Intro101-103 (туториалы). Т.е. граф зон туториалов в порте беднее
   оригинального. Нюанс оригинала: при построении шагов
   `GetDoorBetweenZones` требует `!Locked` без исключения
   (Helpers.cs:194-205), так что оригинал через такое ребро строит
   null-путь (без обхода), а порт ищет обходной маршрут — поведение
   расходится, а не просто «упрощено». Надо либо чинить по коду, либо
   документировать в runtime/README.md с этими числами.
2. **scene.py:1692-1694 `find_path` — «Uniform edge cost, so BFS»** —
   длина пути доказуемо совпадает (все веса 1.0, Helpers.cs:158-192 —
   Дейкстра с `list.Sort(ZoneComparer)`), но ВЫБОР из равных по длине
   путей не доказан: у оригинала порядок извлечения задаёт
   нестабильный List.Sort + порядок `zone.Neighbors`, у порта — FIFO
   BFS по порядку дверей. Чисел/доказательства в комментарии нет.
3. **hud.py:8-10 — шрифты**: «sizes approximate
   LevelDataGUIRenderer.CalculateFontSize by plain screen scaling».
   Оригинал: `((W/800)+(H/600))*10 - adjust`
   (LevelDataGUIRenderer.cs:177-184; Description-вариант `W/800*13`,
   cs:185-192). Порт: `design_size * H/600` (hud.py:203-208, 226) с
   design_size из имени шрифта/стиля. При 800x600: оригинал 20-adjust
   против 17/13 у порта. Приближение заявлено, но числами не
   подкреплено — кандидат в README-таблицу расхождений.
4. **hud.py:219-220 `_style_font`** — кегль берётся regex-ом из хвоста
   имени шрифтового ассета (`(\d+)$`, fallback 16). Эвристика порта
   (в Unity кегль запечён в ассете), нигде не помечена как таковая.
5. **world.py:4781-4785 `set_tricked_object_hidden`** — docstring
   признаёт: оригинал (TrickItem.cs:400-410) вместе с Renderer
   переключает и BoxCollider ground-trick-оверлея, порт «approximated
   by the item's own clickability». Но тело метода clickability НЕ
   трогает — эквивалентность держится на маршрутизации кликов в другом
   месте и не доказана (нет сверки моментов включения/выключения).
6. **world.py:4711-4713 `set_active`** — «GameObject.SetActive,
   approximated to what the port models» (renderer + collider). Честная
   модель engine-API; учесть, что SetActive в Unity глушит и
   Update/Invoke дочерних компонентов — порт это моделирует лишь там,
   где явно портировано. Приемлемо, помечено.
7. **viewer.py:183-186 `_hit_at`** — «the collider nearest the camera
   wins … exactly as Physics.Raycast orders them»: модель верная
   (Raycast возвращает ближайший хит), z проброшен из `_world_box`
   (scene.py:1464-1467), но «exactly» не подкреплено данными о
   z-коллизиях/совпадениях. Пограничное (обоснование есть, чисел нет).
8. **viewer.py:428 `world.tick(min(dt, 0.1))`** — кламп кадрового dt.
   У оригинала аналога нет (Time.deltaTime как есть); это
   infra-решение вьюера, никак не помечено. Пометить как viewer-side.

## (a) COVERED-NEARBY — покрыто ссылкой класса/соседа (компактно)

- **world.py**: AnimPlayer.anim/has/waiting/_reached_end/_advance/
  _loop_to_start (docstring класса, стр. 13-21: AnimationControllerBase.
  Refresh + inline-refs в tick 239-257); AlerterFSM._play/_woody/
  _woody_moving/_alert_pair/on_notice_woody/wake_up/on_rottweiler_enter/
  on_rottweiler_leave (docstring 1233-1235: Alerter.cs);
  InventoryState.select (docstring 1365-1367: HUD.cs:1309-1322);
  Routine.action/item/_advance/_anim_by_pid (docstring 1486-1487:
  ActionManager + пофельдовые комментарии 1504-1538). `waiting`
  помечен «diagnostic only» — infra по назначению.
- **scene.py**: _anim_name (95: конвенция NONE = ItemAnimationState.cs:3);
  Zone.left/right (комментарий 113-114: Level.SetPlayLeft/SetPlayRight);
  zone_by_component (1350: пояснение сериализации).
- **hud.py**: HudAnim.__init__/restart/running/frame/update (docstring 75:
  HUDAnimation; сверено с HUDAnimation.cs — совпадает; отличие: Frame у
  порта клампится, оригинал кидает исключение — безопасное отклонение,
  не помечено); _adj (покрыт docstring-ом rect() на 255:
  AdjustRectangleRelatizeSize); _inventory_rects (поле InventoryRects).
- **behaviors.py**: 9 hook-default-ов базового Behavior (144-169) —
  секционный комментарий 140 (ActorBehavior.cs, RoutineBehavior.cs);
  сверено построчно: PlayAnimation сохраняет CurrentAnimation,
  CanSeeWoody/CanCheckSurpriseActionFar → true — совпадает. Плюс 38
  методов (почти все `__init__`-загрузчики сериализованных полей и
  мелкие хелперы), покрытых docstring-ом класса, называющим .cs-файл:
  все 46 заявленных файлов-оригиналов существуют в src/Assembly-CSharp
  (проверено пофайлово), размеры сопоставимы. Проверка глубже:
  RollerSkaterBehavior и Level212Behavior («both branches are empty») —
  совпадает с кодом.
- **viewer.py**: _item_at/_door_at — обёртки над _hit_at (ref
  Pawn.cs:403 там же).
- **render.py**: Camera.screen_to_world/world_rect_to_screen — обратные
  к world_to_screen (docstring 22-23: Camera.WorldToScreenPoint +
  y-flip).

## (b) INFRA — вьюер/рекордер/SDL/обвязка (компактно; ⚠ = не помечено явно)

- **world.py**: pawn_by_pid (4592: «resolve a serialized …» — помечено),
  set_go_renderer/set_go_active (Unity-API-шим, docstring называет
  Renderer.enabled/SetActive), player_for ⚠ (двухстрочный аксессор),
  spawn_woody ⚠ (конструирование), subscribe/fire_event (event-bus
  вместо C#-делегатов; контекст в секционном комментарии 6065-6066),
  _default_screen_point (3956-3957: «the viewer swaps in…» — помечено).
- **scene.py**: Anim.frame_at ⚠ — free-run фолбэк, единственный
  потребитель render.py:124 и пометка лежит ТАМ (render.py:123), а не у
  определения; Sprite.__init__, _o, _go_of, _transform, _pos («the
  exporter composes…» — помечено), _component, _active — аксессоры
  формата экспорта; _add_zone/_add_door/_add_item/_find_game_info —
  загрузчики сериализованных полей (имена полей = поля C#-классов Zone/
  Door/Item/GameInfo — самодокументируемо, отдельной пометки нет ⚠);
  zone_by_pid/door_by_pid/_go_of_sprite ⚠ (лукапы), _find_background
  (docstring: конвенция экспортера).
- **hud.py**: _sys_font (замена шрифтов помечена в docstring файла,
  8-10), _style_font/_style_color/_align (чтение сериализованного
  GUIStyle), _tex/_blit/_measure ⚠ (SDL-плоттинг, самоочевидно).
- **behaviors.py**: item/pawn/zone/value/anim_name/vec (секция
  «serialized-reference resolution», 29), rott/routine/routine_of/
  player ⚠ (шорткаты мира).
- **viewer.py**: texture_dirs, screenshot, main, _print_state ⚠ (печать
  состояния — по прайм-промпту как раз ожидаемая infra; docstring файла
  «Level viewer …» покрывает), follow-камера помечена (82, 124).
- **render.py**: Camera.__init__, TextureCache.missing,
  draw_zone_overlay (debug-оверлей клавиши Z; в help-строке вьюера).
- **record.py**: весь файл — module docstring объявляет его
  инструментом записи; parse_script/__init__/_click/_screen_of_item/
  _tour_tick/_mouse_tick/_state/tick/run/main. Игровые касания внутри
  снабжены ссылками (forcewin → GameInfo.cs:315-321; пауза →
  Woody.ToggleMenu; stored-click replay дублирует viewer.py:429-431,
  где лежит ссылка Woody.cs:336-341, 484-488).
- **audio_out.py**: весь файл — SDL_mixer-обвязка; docstring цитирует
  AnimationControllerBase.PlaySound, play_music — MusicPlayer.cs:143-166;
  audio_dirs/__init__/try_open/_load/play/stop_music ⚠ (самоочевидно).

## Замечания вне категорий

- Базовый Behavior не моделирует хук `ActorBehavior.OnPlayAngryAnimation`
  (ActorBehavior.cs:16-19) — пропуск, не изобретение (в пасс-6 не
  входит, зафиксировано для полноты).
- Конвенция сокращённых ссылок `# cs:NN` нигде не описана (ни в
  runtime/README.md, ни в docstring-ах) — стоит зафиксировать, иначе
  каждый следующий аудит повторит ложный вывод «behaviors.py почти без
  ссылок».
