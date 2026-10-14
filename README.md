# SmartList

Flutter-приложение для списков покупок.

## Структура

- `lib/` — мобильное приложение Flutter.
- `backend/` — FastAPI-бэкенд из архива `smart_list.zip`.
- `backend/SETUP.md` — инструкция запуска бэкенда на диске `D`.

## Flutter

```powershell
flutter pub get
flutter run
```

## Backend

Бэкенд перенесен в `backend` без архивного `venv` и кэшей Python. Запуск и
настройки описаны в [backend/SETUP.md](backend/SETUP.md).
