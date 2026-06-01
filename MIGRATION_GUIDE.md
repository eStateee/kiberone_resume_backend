# AlfaCRM Migration Guide: Переход на новый инстанс

## Что было сделано

### 1. Новый management command: `migrate_alfacrm_ids`

**Файл:** `app_resumes/management/commands/migrate_alfacrm_ids.py`

Одноразовый скрипт миграции, который:

| Фаза | Действие | Ключ сопоставления |
|------|----------|--------------------|
| 1 | Обновляет `TutorProfile.tutor_crm_id`, `branch`, `branch_ids` | `phone_number` |
| 2 | Обновляет `Group.crm_group_id`, `branch_ids`, `teacher_ids` и доп. поля | `name` (название группы) |
| 3 | Обновляет `Student.student_crm_id` | `student_name` внутри новой группы |
| 4 | Каскадно обновляет `Resume.student_crm_id` | словарь old→new из фазы 3 |
| 5 | Каскадно обновляет `ParentReview.student_crm_id` | словарь old→new из фазы 3 |

**Ключевые свойства команды:**
- `--dry-run` — показывает план без записи в БД
- `--branches 1,2,3,4` — переопределяет список ID филиалов новой CRM
- `transaction.atomic()` — всё или ничего; при ошибке БД откатывается
- Двухфазное обновление UNIQUE-полей (временные значения → финальные), чтобы не получить `IntegrityError` при перестановке ID
- Предупреждения о дубликатах имён студентов/групп в новой CRM

### 2. Рефактор `crm_integration.py`

Хардкод `branches = [1, 2, 3, 4]` в `get_all_groups()` заменён на `settings.CRM_BRANCH_IDS`.

### 3. Новая переменная в `settings.py`

```python
CRM_BRANCH_IDS = [int(b) for b in os.getenv("CRM_BRANCH_IDS", "1,2,3,4").split(",")]
```

---

## Риски и их митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Тьютор не найден по телефону (разный формат номера) | Средняя | `--dry-run` показывает всех ненайденных **до** применения |
| Дубликат имени студента в группе | Низкая | Скрипт выводит `WARNING` в консоль и в итоговый отчёт |
| Группа не найдена по имени (пробелы, регистр) | Средняя | `--dry-run` + ручная проверка имён в интерфейсе CRM |
| ID филиалов изменились в новой CRM | Высокая | Проверить в новой CRM → прописать в `.env` как `CRM_BRANCH_IDS=5,6,7,8` |
| Скрипт упал на середине | Низкая | `transaction.atomic()` откатывает всё; БД остаётся в исходном состоянии |
| Старый токен Redis из старой CRM | Высокая | Скрипт вызывает `clear_crm_auth_token()` перед авторизацией |
| `Resume`/`ParentReview` "оторвутся" от студента | Практически 0 | Каскадное обновление внутри той же транзакции |

---

## Как протестировать локально

### Предварительные требования

```
Python venv активирован
Redis запущен (redis-server)
Локальная db.sqlite3 содержит тестовые данные
```

### Шаг 1 — Сделать резервную копию БД

```bash
# Windows
copy db.sqlite3 db.sqlite3.backup

# Linux/macOS
cp db.sqlite3 db.sqlite3.backup
```

### Шаг 2 — Прописать новые учётные данные в `.env`

```env
CRM_API_URL=https://NEW_INSTANCE.s20.online
CRM_EMAIL=your@email.com
CRM_API_KEY=new-api-key-here

# Если ID филиалов изменились, добавить:
CRM_BRANCH_IDS=5,6,7,8
```

> ⚠️ **Важно:** Перед этим зайдите в новую CRM → Настройки → Филиалы и выпишите новые ID.

### Шаг 3 — Сбросить кэшированный токен Redis

```bash
redis-cli del crm_auth_token
# или полная очистка:
redis-cli flushall
```

### Шаг 4 — Запустить Dry Run

```bash
cd backend
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

python manage.py migrate_alfacrm_ids --dry-run
```

**Что проверить в выводе:**

- `✓ Авторизация в новой CRM успешна` — новые credentials работают
- Все тьюторы имеют статус `✓` (не `✗`)
- Все группы имеют статус `✓`
- Процент найденных студентов — 100% (или близко к этому)
- Раздел `⚠ Предупреждения` — пуст или содержит только ожидаемые записи

### Шаг 5 — Анализ предупреждений

Если в dry-run есть строки `✗ НЕ НАЙДЕН`:

1. **Тьютор не найден** — проверьте формат телефона в новой CRM (с/без `+`, с/без кода страны)
2. **Группа не найдена** — проверьте точное название в новой CRM (пробелы, спецсимволы)
3. **Студент не найден** — возможно, он был удалён из новой CRM или переименован

### Шаг 6 — Запустить реальную миграцию

Только если dry-run показал 0 критичных несоответствий:

```bash
python manage.py migrate_alfacrm_ids
```

### Шаг 7 — Проверка после миграции

```bash
# Проверить, что student_crm_id в Resume совпадают со Student
python manage.py shell -c "
from app_resumes.models import Resume, Student
resume_ids = set(Resume.objects.values_list('student_crm_id', flat=True))
student_ids = set(str(s) for s in Student.objects.values_list('student_crm_id', flat=True))
orphans = resume_ids - student_ids
print(f'Резюме без студента: {len(orphans)}')
if orphans: print(list(orphans)[:10])
"
```

### Шаг 8 — Восстановление из бэкапа (если что-то пошло не так)

```bash
# Windows
copy /Y db.sqlite3.backup db.sqlite3

# Linux/macOS
cp db.sqlite3.backup db.sqlite3
```

---

## Как запустить на сервере (production)

### Полный чеклист деплоя

```
[ ] 1. Сделать бэкап db.sqlite3
[ ] 2. Уточнить ID филиалов в новой CRM
[ ] 3. Обновить .env на сервере
[ ] 4. Сбросить Redis-токен
[ ] 5. Запустить --dry-run
[ ] 6. Убедиться в 0 ненайденных записей
[ ] 7. Запустить реальную миграцию
[ ] 8. Перезапустить сервисы
[ ] 9. Проверить работу приложения
```

### Пошаговые команды для сервера

```bash
# 1. Подключиться к серверу
ssh user@185.244.50.19

# 2. Перейти в директорию проекта
cd /path/to/resume/backend

# 3. Сделать бэкап
cp db.sqlite3 db.sqlite3.backup_$(date +%Y%m%d_%H%M%S)

# 4. Открыть .env и обновить параметры
nano .env
# Изменить:
#   CRM_API_URL=https://NEW_INSTANCE.s20.online
#   CRM_API_KEY=new-api-key-here
#   CRM_BRANCH_IDS=X,Y,Z   (если ID филиалов изменились)

# 5. Удалить кэшированный токен из Redis
redis-cli del crm_auth_token

# 6. Активировать venv
source venv/bin/activate

# 7. Dry-run
python manage.py migrate_alfacrm_ids --dry-run 2>&1 | tee migration_dryrun.log

# 8. Проверить лог dry-run
grep -E "(✗|НЕ НАЙДЕН|WARNING|ERROR)" migration_dryrun.log

# 9. Если всё OK — запустить боевую миграцию
python manage.py migrate_alfacrm_ids 2>&1 | tee migration_live.log

# 10. Перезапустить Gunicorn/Uvicorn
sudo systemctl restart gunicorn   # или: supervisorctl restart gunicorn

# 11. Если используется Celery
sudo systemctl restart celery

# 12. Проверить статус сервисов
sudo systemctl status gunicorn
sudo systemctl status celery
```

### Проверка работоспособности после деплоя

1. **Авторизация** — преподаватель входит через `/api/app_resumes/login/`
2. **Группы** — ответ `/api/app_resumes/groups/` содержит группы с новыми ID
3. **Студенты** — ответ `/api/app_resumes/groups/clients/?group_id=NEW_ID` возвращает список
4. **Резюме** — для студента отображаются ранее созданные резюме
5. **Отзывы** — для студента отображаются ранее созданные отзывы родителей

---

## Критерии успешной миграции

| Проверка | Ожидаемый результат |
|----------|---------------------|
| Скрипт завершился без `ERROR` | ✓ |
| `tutors_not_found = 0` | ✓ |
| `groups_not_found = 0` | ✓ |
| `students_not_found = 0` или минимум | ✓ |
| Логин преподавателя работает | ✓ |
| Группы отображаются в интерфейсе | ✓ |
| Резюме студентов сохранились | ✓ |
| Отзывы родителей сохранились | ✓ |

---

## Зависимости и порядок выполнения

```
Обновить .env (новые CRM URL + API KEY) 
       ↓
Сбросить Redis-токен (redis-cli del crm_auth_token)
       ↓
Запустить --dry-run → проверить 0 ошибок
       ↓
Запустить боевую миграцию
       ↓
Перезапустить Gunicorn + Celery
       ↓
Проверить работу приложения
```

> ⚠️ **Критическое условие:** Скрипт **ДОЛЖЕН** запускаться **ДО** того, как преподаватели начнут логиниться в новую CRM. Логин обновляет `tutor_crm_id` из новой CRM напрямую, что может создать неконсистентное состояние в БД до завершения полной миграции.
