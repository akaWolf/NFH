# Сырые отчёты финального аудита (docs/FINAL_AUDIT_PROMPT.md)

Черновики фоновых агентов — **не истина**: каждая заявка перепроверена по
исходнику отдельным проходом, вердикты и фиксы — в `docs/audit/verified/`,
итог — `docs/audit/FINAL_AUDIT.md`, изложение для читателя рантайма —
`runtime/README.md`, раздел «The final audit».

| Сырьё | Что | Верифицировано в |
|---|---|---|
| `pass1_pawn_woody.md` | проход 1, флаги Pawn/Woody (174 поля) | `verified/pawn_woody.md` |
| `pass1_rott_actionmgr.md` | проход 1, Rottweiler/Mother/Olga/Kid/ActionManager/RoutineAction* (127) | `verified/routine.md` |
| `pass1_item_family.md` | проход 1, Item/TrickItem/SearchItem/Door/HideItem/Alerter/… | `verified/items.md`, `verified/sprite_model.md` |
| `pass1_gameinfo_hud_anim.md` | проход 1, GameInfo/HUD/AnimationController*/ProgressBar/Dexterity/… | `verified/gameinfo_hud.md` |
| `pass4_twins.md` (+ `twins2.txt`, `methods.txt`, `xref.txt`, `assets.txt`) | проход 4, одноимённость: поля, методы, ассеты | `verified/items.md` (F1–F5, F8, F13), `verified/pawn_woody.md` (F7), `verified/routine.md` (F6), `verified/assets_refs.md` (F9–F12) |
| `pass6_backrefs.md` | проход 6, обратный аудит runtime/ | `verified/assets_refs.md` |
| `flag_inventory.py` / `flag_inventory.txt` | генератор инвентаря полей (grep по декомпиляту) | — |
| `trick_dump.py` / `trick_dump.txt` | дамп трюков/инвентаря уровней для планов прохода 3 | `verified/plans_s1a|s1b|s1c|s2a|s2b.md`, `verified/s2_plans.md` |
| `monkey_finding_l105.jsonl` | первое срабатывание обезьяны (проход 2) | раскручено координатором: stale `on_arrive` в ветке UseDoorAtOnce (Pawn.cs:480-498/595) |

Проходы без сырья (сделаны сразу как верифицированная работа): проход 2
(`tests/monkey.py`), проход 4b тихие дефолты (`verified/defaults.md`),
проход 5 видео (`verified/pass5_video.md`).
