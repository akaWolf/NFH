# План после финального аудита

Порядок — по договорённости после коммита результата аудита.

1. **Полноценная игра** — СДЕЛАНО, кроме туториального слоя
   (`runtime/app.py`, `runtime/menu.py`, `runtime/prefs.py`,
   `runtime/gui.py`; раздел «The menus and the flow» в
   `runtime/README.md`; `tests/run_menu.py`): заставка
   `GameIntroAnimation`, титульные карточки `IntroAnimation`, меню Entry
   (`Control*`, `LevelDataGUIRenderer`, выбор уровней обоих сезонов,
   опции, языки, титры), `LevelLoader`/`LevelTransition`-экраны,
   `InGameMenu`, `ExitConfirmation` (включая дверь выхода), прогресс и
   настройки через PlayerPrefs-порт. Осталось из пункта: туториальный
   слой (`LevelScript`, `TutorialScriptCamera*`, стрелки и message boxes
   Intro-сцен) — см. «Not implemented».
2. **Полноэкранный режим** — СДЕЛАНО: тумблер FULLSCREEN в обоих окнах
   опций (портовое решение — у Android-декомпила нет такого SettingKey),
   pref `Fullscreen`, SDL_WINDOW_FULLSCREEN_DESKTOP поверх логического
   размера 800×600.
3. **Бандлы под Linux и Windows** с сборкой в GitHub Actions: упаковка
   рантайма (PyInstaller или аналог) с SDL2/SDL2_mixer/SDL2_ttf, извлечённые
   ассеты как отдельный шаг (данные игры не в репозитории — бандл ожидает
   apk/obb пользователя или готовые `textures/`, `audio/`, `strings/`,
   `fonts/`), артефакты релиза, матрица linux/windows.
