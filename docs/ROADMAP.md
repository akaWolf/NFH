# План после финального аудита

Порядок — по договорённости после коммита результата аудита.

1. **Полноценная игра** — СДЕЛАНО
   (`runtime/app.py`, `runtime/menu.py`, `runtime/tutorial.py`,
   `runtime/prefs.py`, `runtime/gui.py`; разделы «The menus and the
   flow» и «The tutorial layer» в `runtime/README.md`;
   `tests/run_menu.py` + `tests/run_tutorial.py`): заставка
   `GameIntroAnimation`, титульные карточки `IntroAnimation`, меню Entry
   (`Control*`, `LevelDataGUIRenderer`, выбор уровней обоих сезонов,
   опции, языки, титры), `LevelLoader`/`LevelTransition`-экраны,
   `InGameMenu`, `ExitConfirmation` (включая дверь выхода), прогресс и
   настройки через PlayerPrefs-порт, туториальный слой (`LevelScript` +
   четыре `TutorialScriptCamera*`) для Intro101–103 и L201/L206.
2. **Полноэкранный режим** — СДЕЛАНО: тумблер FULLSCREEN в обоих окнах
   опций (портовое решение — у Android-декомпила нет такого SettingKey),
   pref `Fullscreen`, SDL_WINDOW_FULLSCREEN_DESKTOP поверх логического
   размера 800×600.
3. **Бандлы под Linux и Windows** с сборкой в GitHub Actions: упаковка
   рантайма (PyInstaller или аналог) с SDL2/SDL2_mixer/SDL2_ttf, извлечённые
   ассеты как отдельный шаг (данные игры не в репозитории — бандл ожидает
   apk/obb пользователя или готовые `textures/`, `audio/`, `strings/`,
   `fonts/`), артефакты релиза, матрица linux/windows.
