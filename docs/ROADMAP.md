# План после финального аудита

Порядок — по договорённости после коммита результата аудита.

1. **Полноценная игра**: то, что аудиты сознательно оставляли за скоупом
   («Not implemented» в `runtime/README.md`) — титульные карточки и интро
   (`IntroAnimation`, `GameIntroAnimation`, три Intro-сцены с
   `DirectorAnimation`), главное меню и внутриигровое меню (`Menu`,
   `MainMenu`, `InGameMenu`, `LevelDataGUIRenderer`, `Control*`,
   `ExitConfirmation`), выбор и переходы уровней (`LevelLoader`,
   `LevelPackData`/`LevelPackDetails`, `LevelUnlocker`, `Transition`-сцены,
   сохранение прогресса `LevelDataSaver`/PlayerPrefs), туториальный слой
   (`LevelScript`, `TutorialScriptCamera*`), опции звука/музыки/языка.
   Тот же метод: каждая строка — по методу оригинала.
2. **Полноэкранный режим** — в ПК-версии включался через меню настроек;
   в порте — опция меню + переключение SDL_WINDOW_FULLSCREEN(_DESKTOP) с
   сохранением 800×600-дизайна (letterbox/scale).
3. **Бандлы под Linux и Windows** с сборкой в GitHub Actions: упаковка
   рантайма (PyInstaller или аналог) с SDL2/SDL2_mixer/SDL2_ttf, извлечённые
   ассеты как отдельный шаг (данные игры не в репозитории — бандл ожидает
   apk/obb пользователя или готовые `textures/`, `audio/`, `strings/`,
   `fonts/`), артефакты релиза, матрица linux/windows.
