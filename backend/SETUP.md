# Инструкция по запуску бэкенда на диске D:

## 1. Окружение и зависимости

В каталоге `backend/` настроено изолированное виртуальное окружение Python:

```powershell
cd D:\project_android\backend
.\venv\Scripts\Activate.ps1
```

Если зависимости потребуется обновить или переустановить:
```powershell
.\venv\Scripts\python.exe -m pip install -r req.txt
```

---

## 2. Конфигурация (.env)

Файл `.env` уже создан в папке `backend/` со следующими настройками:
- `DB_HOST=127.0.0.1`
- `DB_PORT=5432`
- `DB_NAME=smart_supply_list`
- `DB_USER=postgres`
- `DB_PASSWORD=Miron_off13` (пароль локального `postgres`; общий с проектом SpaceMap)
- `JWT_SECRET_KEY=...`
- `SUGGESTIONS_PROVIDER=statistical` (табличный движок совстречаемости)

---

## 3. База данных и миграции

Для создания базы данных, применения базовой схемы (`database/database.sql`) и всех миграций (`001`, `002`, `003`, `004`):

```powershell
cd D:\project_android\backend
.\venv\Scripts\python.exe scripts\bootstrap_db.py --dbname smart_supply_list --base-schema --migrations
```

---

## 4. Наполнение каталога и правил подсказок

Запуск начального заполнения ~200 товаров и правил совстречаемости:

```powershell
.\venv\Scripts\python.exe scripts\seed_catalog.py
```

---

## 5. Запуск сервера API

```powershell
.\venv\Scripts\python.exe main.py
```

Сервер будет доступен по адресу:
- **API:** `http://127.0.0.1:8000`
- **Интерактивная документация (Swagger UI):** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`
- **Проверка состояния:** `http://127.0.0.1:8000/health`

---

## 6. Запуск тестов

```powershell
.\venv\Scripts\pytest.exe tests
```
