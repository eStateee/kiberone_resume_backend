"""
Django management command для миграции crm_id при переходе на новый инстанс AlfaCRM.

Алгоритм:
  1. Авторизация в новой CRM (по данным из .env).
  2. Сопоставление TutorProfile по phone_number → обновление tutor_crm_id, branch, branch_ids.
  3. Сопоставление Group по name → обновление crm_group_id, branch_ids, teacher_ids и доп. полей.
  4. Сопоставление Student по student_name внутри группы → обновление student_crm_id.
  5. Каскадное обновление student_crm_id в Resume и ParentReview.

Все изменения в БД выполняются в единой транзакции (transaction.atomic).
Поддерживается флаг --dry-run для проверки без записи.
"""

import logging
import os
import re
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from app_resumes.crm_integration import (
    BASE_HEADERS,
    clear_crm_auth_token,
    login_to_alfa_crm,
    make_authenticated_request,
)
from app_resumes.models import Group, ParentReview, Resume, Student, TutorProfile

logger = logging.getLogger("app_resume")

# Регулярка для очистки ANSI-кодов (компилируется один раз)
_ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


class _DryRunRollback(Exception):
    """Сигнальное исключение для отката транзакции в режиме dry-run."""


class Command(BaseCommand):
    help = (
        "Миграция crm_id из старой AlfaCRM в новую. "
        "Сопоставляет тьюторов по телефону, группы по названию, студентов по имени."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._log_file = None

    def _open_log_file(self, dry_run):
        """Создаёт лог-файл миграции с таймстемпом в корне проекта."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        mode = "dry_run" if dry_run else "migrate"
        filename = f"migration_alfacrm_{mode}_{timestamp}.log"
        log_dir = os.path.join(str(settings.BASE_DIR.parent), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, filename)
        self._log_file = open(log_path, "w", encoding="utf-8")
        return log_path

    def _close_log_file(self):
        """Закрывает лог-файл, если он открыт."""
        if self._log_file and not self._log_file.closed:
            self._log_file.close()

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать план миграции без внесения изменений в БД",
        )
        parser.add_argument(
            "--branches",
            type=str,
            default="1,2,3,4",
            help="ID филиалов новой CRM через запятую (по умолчанию: 1,2,3,4)",
        )

    def log_output(self, message, is_error=False):
        """Выводит сообщение в консоль (stdout/stderr) и дублирует в лог-файл."""
        if is_error:
            self.stderr.write(str(message))
        else:
            self.stdout.write(str(message))

        # Записываем в файл без ANSI-кодов
        if self._log_file and not self._log_file.closed:
            clean_message = _ANSI_ESCAPE.sub('', str(message))
            self._log_file.write(clean_message + '\n')
            self._log_file.flush()

    # ——————————————— Точка входа ———————————————

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        branches = [int(b.strip()) for b in options["branches"].split(",")]

        # Открываем лог-файл миграции
        log_path = self._open_log_file(dry_run)
        self.log_output(self.style.SUCCESS(f"📄 Лог-файл: {log_path}\n"))

        try:
            self._run_migration(dry_run, branches)
        finally:
            self.log_output(self.style.SUCCESS(f"\n📄 Полный лог сохранён: {log_path}"))
            self._close_log_file()

    def _run_migration(self, dry_run, branches):
        """Основная логика миграции, вынесена для гарантированного закрытия лог-файла."""
        if dry_run:
            self.log_output(self.style.WARNING(
                "\n╔══════════════════════════════════════════╗"
                "\n║   РЕЖИМ DRY-RUN: данные НЕ изменятся    ║"
                "\n╚══════════════════════════════════════════╝\n"
            ))

        self.log_output(f"Филиалы новой CRM: {branches}")
        self.log_output(f"API URL: {settings.CRM_API_URL}\n")

        # --- Авторизация ---
        clear_crm_auth_token()
        token = login_to_alfa_crm()
        if not token:
            self.log_output(self.style.ERROR(
                "ОШИБКА: не удалось авторизоваться в новой CRM.\n"
                "Проверьте CRM_API_URL и CRM_API_KEY в .env"
            ), is_error=True)
            raise SystemExit(1)

        self.log_output(self.style.SUCCESS("✓ Авторизация в новой CRM успешна\n"))

        # --- Фаза 1: сбор маппингов из API (read-only) ---
        tutor_updates, group_updates, student_updates, stats, warnings = (
            self._collect_all_mappings(token, branches)
        )

        # --- Оценка каскадных обновлений Resume / ParentReview ---
        student_id_map = {u["old_crm_id"]: u["new_crm_id"] for u in student_updates}
        estimated_resumes = 0
        estimated_reviews = 0
        for old_id in student_id_map:
            estimated_resumes += Resume.objects.filter(student_crm_id=str(old_id)).count()
            estimated_reviews += ParentReview.objects.filter(student_crm_id=str(old_id)).count()

        stats["resumes_updated"] = estimated_resumes
        stats["reviews_updated"] = estimated_reviews

        # --- Отчёт ---
        self._print_report(stats, warnings, dry_run)

        # --- Фаза 2: применение изменений (только без --dry-run) ---
        if not dry_run:
            self._apply_all_changes(
                tutor_updates, group_updates, student_updates,
            )
            self.log_output(self.style.SUCCESS("\n✓ Миграция успешно завершена!"))
        else:
            self.log_output(self.style.WARNING(
                "\nDry-run завершён. Для реальной миграции уберите флаг --dry-run."
            ))

    # ——————————————— Утилита запроса к CRM ———————————————

    def _crm_request(self, token, url, data=None, params=None):
        """Выполняет POST-запрос к CRM API и возвращает распарсенный JSON."""
        headers = {**BASE_HEADERS, "X-ALFACRM-TOKEN": token}
        response = make_authenticated_request(url, headers, data, params)
        response.raise_for_status()
        return response.json()

    # ——————————————— Фаза 1: сбор маппингов ———————————————

    def _collect_all_mappings(self, token, branches):
        """Собирает маппинги old_id → new_id для всех сущностей."""
        stats = {
            "tutors_matched": 0, "tutors_not_found": 0,
            "groups_matched": 0, "groups_not_found": 0,
            "students_matched": 0, "students_not_found": 0,
            "resumes_updated": 0, "reviews_updated": 0,
        }
        warnings = []

        # ═══════════════ ТЬЮТОРЫ (по телефону) ═══════════════
        self.log_output(self.style.HTTP_INFO("━" * 60))
        self.log_output(self.style.HTTP_INFO(" PHASE 1: Маппинг тьюторов (по телефону)"))
        self.log_output(self.style.HTTP_INFO("━" * 60))

        tutor_updates = []
        tutors = TutorProfile.objects.all()
        self.log_output(f"  Локальных тьюторов в БД: {tutors.count()}\n")

        for tutor in tutors:
            found = False
            for branch in branches:
                url = f"{settings.CRM_API_URL}/v2api/{branch}/teacher/index"
                result = self._crm_request(token, url, {"phone": tutor.phone_number})
                items = result.get("items", [])

                if items:
                    new_data = items[0]
                    old_id = str(tutor.tutor_crm_id)
                    new_id = str(new_data["id"])

                    tutor_updates.append({
                        "pk": tutor.pk,
                        "name": tutor.tutor_name,
                        "phone": tutor.phone_number,
                        "old_crm_id": old_id,
                        "new_crm_id": new_id,
                        "old_branch": tutor.branch,
                        "new_branch": str(branch),
                        "new_branch_ids": new_data.get("branch_ids"),
                        "new_name": new_data.get("name", tutor.tutor_name),
                    })
                    self.log_output(
                        f"  ✓ {tutor.tutor_name} ({tutor.phone_number}): "
                        f"{old_id} → {new_id}, branch {tutor.branch} → {branch}"
                    )
                    stats["tutors_matched"] += 1
                    found = True
                    break

            if not found:
                stats["tutors_not_found"] += 1
                warnings.append(f"Тьютор не найден: {tutor.tutor_name} ({tutor.phone_number})")
                self.log_output(self.style.WARNING(
                    f"  ✗ {tutor.tutor_name} ({tutor.phone_number}): НЕ НАЙДЕН"
                ))

        self.log_output("")

        # ═══════════════ ГРУППЫ (по названию) ═══════════════
        self.log_output(self.style.HTTP_INFO("━" * 60))
        self.log_output(self.style.HTTP_INFO(" PHASE 2: Маппинг групп (по названию)"))
        self.log_output(self.style.HTTP_INFO("━" * 60))

        # Загрузка всех групп из новой CRM с пагинацией
        all_new_groups = []
        for branch in branches:
            page = 0
            branch_groups_count = 0
            while True:
                url = f"{settings.CRM_API_URL}/v2api/{branch}/group/index"
                result = self._crm_request(token, url, {"page": page, "limit": 50})
                items = result.get("items", [])
                if not items:
                    break
                all_new_groups.extend(items)
                branch_groups_count += len(items)
                
                total = result.get("total", 0)
                if total > 0 and branch_groups_count >= total:
                    break
                page += 1

        self.log_output(f"  Загружено {len(all_new_groups)} групп из новой CRM")

        # Индекс по имени
        new_groups_by_name = {}
        for g in all_new_groups:
            gname = g.get("name", "").strip()
            if gname in new_groups_by_name:
                warnings.append(f"Дубликат имени группы в новой CRM: \"{gname}\"")
            new_groups_by_name[gname] = g

        group_updates = []
        matched_new_groups = {}  # name → new_group_data (нужен в Phase 3)
        # Отслеживаем, какие new_crm_group_id уже заняты в group_updates,
        # чтобы не присвоить один ID двум разным локальным группам (дубли имён).
        assigned_new_group_ids = set()

        local_groups = Group.objects.all()
        self.log_output(f"  Локальных групп в БД: {local_groups.count()}\n")

        for group in local_groups:
            name = group.name.strip()
            new_data = new_groups_by_name.get(name)

            if new_data:
                old_gid = group.crm_group_id
                new_gid = new_data["id"]

                # Защита от дубликатов: если new_gid уже присвоен другой группе
                if new_gid in assigned_new_group_ids:
                    stats["groups_not_found"] += 1
                    warnings.append(
                        f"Дубликат имени группы: \"{name}\" (pk={group.pk}, "
                        f"crm_group_id={old_gid}) — new_crm_group_id={new_gid} "
                        f"уже назначен другой группе, пропускаем"
                    )
                    self.log_output(self.style.WARNING(
                        f"  ⚠ \"{name}\" (pk={group.pk}): дубль имени, "
                        f"new_id={new_gid} уже назначен — ПРОПУЩЕНА"
                    ))
                    continue

                assigned_new_group_ids.add(new_gid)
                matched_new_groups[name] = new_data

                # Для NOT NULL полей (level_id, status_id, limit):
                # dict.get("key", default) НЕ подставит default, если ключ
                # присутствует со значением None, поэтому проверяем явно.
                _level = new_data.get("level_id")
                _status = new_data.get("status_id")
                _limit = new_data.get("limit")

                group_updates.append({
                    "pk": group.pk,
                    "name": name,
                    "old_crm_group_id": old_gid,
                    "new_crm_group_id": new_gid,
                    "new_branch_ids": new_data.get("branch_ids"),
                    "new_teacher_ids": new_data.get("teacher_ids"),
                    "new_level_id": _level if _level is not None else group.level_id,
                    "new_status_id": _status if _status is not None else group.status_id,
                    "new_company_id": new_data.get("company_id", group.company_id),
                    "new_streaming_id": new_data.get("streaming_id", group.streaming_id),
                    "new_limit": _limit if _limit is not None else group.limit,
                    "new_note": new_data.get("note", group.note),
                    "new_b_date": new_data.get("b_date", group.b_date),
                    "new_e_date": new_data.get("e_date", group.e_date),
                })
                self.log_output(f"  ✓ \"{name}\": {old_gid} → {new_gid}")
                stats["groups_matched"] += 1
            else:
                stats["groups_not_found"] += 1
                warnings.append(f"Группа не найдена: \"{name}\"")
                self.log_output(self.style.WARNING(f"  ✗ \"{name}\": НЕ НАЙДЕНА"))

        self.log_output("")

        # ═══════════════ СТУДЕНТЫ (по имени глобально) ═══════════════
        self.log_output(self.style.HTTP_INFO("━" * 60))
        self.log_output(self.style.HTTP_INFO(" PHASE 3: Маппинг студентов (по имени глобально)"))
        self.log_output(self.style.HTTP_INFO("━" * 60))

        # Загрузка всех студентов из новой CRM
        self.log_output("  Загрузка базы студентов из новой CRM для маппинга...")
        new_students_by_name = {}
        
        for branch in branches:
            page = 0
            branch_customers_count = 0
            while True:
                url = f"{settings.CRM_API_URL}/v2api/{branch}/customer/index"
                # Загружаем пачками по 100, is_study=2 значит искать по всем (лиды и клиенты)
                result = self._crm_request(token, url, {"page": page, "limit": 100, "is_study": 2})
                items = result.get("items", [])
                if not items:
                    break
                    
                for item in items:
                    cname = item.get("name", "").strip()
                    if cname:
                        # Если дубликат имени, оставляем первого найденного
                        # (или можно предупреждать, но в CRM могут быть дубли)
                        if cname.lower() not in new_students_by_name:
                            new_students_by_name[cname.lower()] = {
                                "id": item["id"], 
                                "branch": branch,
                                "original_name": cname
                            }
                            
                branch_customers_count += len(items)
                total = result.get("total", 0)
                if total > 0 and branch_customers_count >= total:
                    break
                page += 1
                
        self.log_output(f"  Загружено {len(new_students_by_name)} уникальных студентов из новой CRM\n")

        student_updates = []
        
        # Получаем всех локальных студентов (сразу с группами)
        local_students = Student.objects.select_related('group').all()
        self.log_output(f"  Локальных студентов в БД: {local_students.count()}\n")

        for student in local_students:
            sname = student.student_name.strip()
            group_name = student.group.name if student.group else "-"
            
            new_cust_data = new_students_by_name.get(sname.lower())

            if new_cust_data:
                old_sid = str(student.student_crm_id)
                new_sid = str(new_cust_data["id"])

                student_updates.append({
                    "pk": student.pk,
                    "name": sname,
                    "group_name": group_name,
                    "old_crm_id": old_sid,
                    "new_crm_id": new_sid,
                })
                self.log_output(f"  ✓ [{group_name}] {sname}: {old_sid} → {new_sid}")
                stats["students_matched"] += 1
            else:
                stats["students_not_found"] += 1
                warnings.append(f"Студент не найден: \"{sname}\" (локальная группа: \"{group_name}\")")
                self.log_output(self.style.WARNING(
                    f"  ✗ [{group_name}] {sname}: НЕ НАЙДЕН"
                ))

        self.log_output("")
        return tutor_updates, group_updates, student_updates, stats, warnings

    # ——————————————— Фаза 2: применение изменений ———————————————

    def _apply_all_changes(self, tutor_updates, group_updates, student_updates):
        """
        Атомарно применяет все собранные изменения.

        Стратегия "Вытеснение" (Eviction):
          0. Найти блокирующие записи (занимают целевые ID, но не входят в миграцию).
          1. Переместить блокираторов в безопасную зону ID (отрицательные / _archived_).
          2. Для студентов-блокираторов каскадно обновить Resume и ParentReview.
          3. Выполнить стандартную двухфазную миграцию для сопоставленных записей.
        """
        self.log_output(self.style.HTTP_INFO("\n━ Применение изменений в БД (transaction.atomic)... ━\n"))

        with transaction.atomic():
            # ──── Тьюторы ────
            if tutor_updates:
                active_pks = {u["pk"] for u in tutor_updates}
                target_crm_ids = {u["new_crm_id"] for u in tutor_updates}

                # Вытеснение: найти тьюторов, которые занимают целевые ID,
                # но сами не входят в список миграции
                blockers = TutorProfile.objects.filter(
                    tutor_crm_id__in=target_crm_ids
                ).exclude(pk__in=active_pks)

                evicted_count = 0
                for blocker in blockers:
                    old_crm_id = blocker.tutor_crm_id
                    archived_id = f"_archived_{blocker.pk}"
                    TutorProfile.objects.filter(pk=blocker.pk).update(
                        tutor_crm_id=archived_id
                    )
                    self.log_output(
                        f"  ↻ Вытеснен тьютор \"{blocker.tutor_name}\" "
                        f"(pk={blocker.pk}): tutor_crm_id {old_crm_id} → {archived_id}"
                    )
                    evicted_count += 1

                if evicted_count:
                    self.log_output(f"  ⤷ Вытеснено тьюторов-блокираторов: {evicted_count}")

                # Фаза A: временные значения для обхода UNIQUE на tutor_crm_id
                for u in tutor_updates:
                    TutorProfile.objects.filter(pk=u["pk"]).update(
                        tutor_crm_id=f"_migrate_{u['pk']}"
                    )
                # Фаза B: финальные значения
                for u in tutor_updates:
                    tutor = TutorProfile.objects.get(pk=u["pk"])
                    tutor.tutor_crm_id = u["new_crm_id"]
                    tutor.branch = u["new_branch"]
                    tutor.branch_ids = u["new_branch_ids"]
                    tutor.tutor_name = u["new_name"]
                    tutor.save()
                self.log_output(f"  ✓ Обновлено тьюторов: {len(tutor_updates)}")

            # ──── Группы ────
            if group_updates:
                active_pks = {u["pk"] for u in group_updates}
                target_crm_ids = {u["new_crm_group_id"] for u in group_updates}

                # Вытеснение: найти группы, которые занимают целевые ID,
                # но не входят в список миграции.
                # Связь со студентами идёт через ForeignKey (group_id → pk),
                # поэтому изменение crm_group_id безопасно.
                blockers = Group.objects.filter(
                    crm_group_id__in=target_crm_ids
                ).exclude(pk__in=active_pks)

                evicted_count = 0
                for blocker in blockers:
                    old_crm_id = blocker.crm_group_id
                    new_archived_id = -blocker.pk
                    Group.objects.filter(pk=blocker.pk).update(
                        crm_group_id=new_archived_id
                    )
                    self.log_output(
                        f"  ↻ Вытеснена группа \"{blocker.name}\" "
                        f"(pk={blocker.pk}): crm_group_id {old_crm_id} → {new_archived_id}"
                    )
                    evicted_count += 1

                if evicted_count:
                    self.log_output(f"  ⤷ Вытеснено групп-блокираторов: {evicted_count}")

                # Фаза A: временные отрицательные ID для обхода UNIQUE на crm_group_id
                for u in group_updates:
                    Group.objects.filter(pk=u["pk"]).update(crm_group_id=-u["pk"])
                # Фаза B: финальные значения (через update, без кастомного save)
                for u in group_updates:
                    Group.objects.filter(pk=u["pk"]).update(
                        crm_group_id=u["new_crm_group_id"],
                        branch_ids=u["new_branch_ids"],
                        teacher_ids=u["new_teacher_ids"],
                        level_id=u["new_level_id"],
                        status_id=u["new_status_id"],
                        company_id=u["new_company_id"],
                        streaming_id=u["new_streaming_id"],
                        limit=u["new_limit"],
                        note=u["new_note"],
                        b_date=u["new_b_date"],
                        e_date=u["new_e_date"],
                    )
                self.log_output(f"  ✓ Обновлено групп: {len(group_updates)}")

            # ──── Студенты ────
            if student_updates:
                active_pks = {u["pk"] for u in student_updates}
                target_crm_ids = {int(u["new_crm_id"]) for u in student_updates}

                # Вытеснение: найти студентов-блокираторов и каскадно
                # обновить их связанные Resume / ParentReview (CharField-связь),
                # чтобы новый студент не унаследовал чужие данные.
                blockers = Student.objects.filter(
                    student_crm_id__in=target_crm_ids
                ).exclude(pk__in=active_pks)

                evicted_count = 0
                for blocker in blockers:
                    old_id = str(blocker.student_crm_id)
                    new_archived_id = -blocker.pk

                    # Каскадное обновление связанных данных ПЕРЕД вытеснением
                    resumes_moved = Resume.objects.filter(
                        student_crm_id=old_id
                    ).update(student_crm_id=str(new_archived_id))

                    reviews_moved = ParentReview.objects.filter(
                        student_crm_id=old_id
                    ).update(student_crm_id=str(new_archived_id))

                    # Вытеснение самого студента
                    Student.objects.filter(pk=blocker.pk).update(
                        student_crm_id=new_archived_id
                    )

                    cascade_info = ""
                    if resumes_moved or reviews_moved:
                        cascade_info = (
                            f" (каскад: {resumes_moved} резюме, "
                            f"{reviews_moved} отзывов)"
                        )

                    self.log_output(
                        f"  ↻ Вытеснен студент \"{blocker.student_name}\" "
                        f"(pk={blocker.pk}): student_crm_id "
                        f"{old_id} → {new_archived_id}{cascade_info}"
                    )
                    evicted_count += 1

                if evicted_count:
                    self.log_output(f"  ⤷ Вытеснено студентов-блокираторов: {evicted_count}")

                # Фаза A: временные отрицательные ID для обхода UNIQUE на student_crm_id
                for u in student_updates:
                    Student.objects.filter(pk=u["pk"]).update(student_crm_id=-u["pk"])
                # Фаза B: финальные значения (через update, без кастомного save)
                for u in student_updates:
                    Student.objects.filter(pk=u["pk"]).update(
                        student_crm_id=int(u["new_crm_id"])
                    )
                self.log_output(f"  ✓ Обновлено студентов: {len(student_updates)}")

            # ──── Каскадное обновление Resume / ParentReview ────
            # Двухфазное обновление для предотвращения коллизий
            # пересекающихся ID (когда new_id одного студента совпадает
            # с old_id другого).
            #
            # Фаза А: old_id → _temp_{old_id}  (изоляция)
            # Фаза Б: _temp_{old_id} → new_id  (финализация)
            filtered_id_map = {u["old_crm_id"]: u["new_crm_id"] for u in student_updates}

            # --- Resume ---
            # Фаза А: изоляция через временный префикс
            for old_id in filtered_id_map:
                Resume.objects.filter(student_crm_id=str(old_id)).update(
                    student_crm_id=f"_temp_{old_id}"
                )
            # Фаза Б: финализация — временные ID → целевые
            total_resumes = 0
            for old_id, new_id in filtered_id_map.items():
                updated = Resume.objects.filter(student_crm_id=f"_temp_{old_id}").update(
                    student_crm_id=str(new_id)
                )
                total_resumes += updated
            if total_resumes:
                self.log_output(f"  ✓ Обновлено резюме: {total_resumes}")

            # --- ParentReview ---
            # Фаза А: изоляция через временный префикс
            for old_id in filtered_id_map:
                ParentReview.objects.filter(student_crm_id=str(old_id)).update(
                    student_crm_id=f"_temp_{old_id}"
                )
            # Фаза Б: финализация — временные ID → целевые
            total_reviews = 0
            for old_id, new_id in filtered_id_map.items():
                updated = ParentReview.objects.filter(student_crm_id=f"_temp_{old_id}").update(
                    student_crm_id=str(new_id)
                )
                total_reviews += updated
            if total_reviews:
                self.log_output(f"  ✓ Обновлено отзывов: {total_reviews}")

    # ——————————————— Итоговый отчёт ———————————————

    def _print_report(self, stats, warnings, dry_run):
        """Печатает итоговую таблицу с результатами сопоставления."""
        prefix = "[DRY-RUN] " if dry_run else ""

        self.log_output(self.style.HTTP_INFO("\n" + "═" * 60))
        self.log_output(self.style.HTTP_INFO(f" {prefix}ИТОГОВЫЙ ОТЧЕТ"))
        self.log_output(self.style.HTTP_INFO("═" * 60))

        self.log_output(
            f"\n  Тьюторы   │ найдено: {stats['tutors_matched']:>3}  "
            f"│ не найдено: {stats['tutors_not_found']:>3}"
        )
        self.log_output(
            f"  Группы    │ найдено: {stats['groups_matched']:>3}  "
            f"│ не найдено: {stats['groups_not_found']:>3}"
        )
        self.log_output(
            f"  Студенты  │ найдено: {stats['students_matched']:>3}  "
            f"│ не найдено: {stats['students_not_found']:>3}"
        )
        self.log_output(f"  Резюме    │ будет обновлено: {stats['resumes_updated']:>3}")
        self.log_output(f"  Отзывы    │ будет обновлено: {stats['reviews_updated']:>3}")

        if warnings:
            self.log_output(self.style.WARNING(f"\n  ⚠ Предупреждения ({len(warnings)}):"))
            for w in warnings:
                self.log_output(self.style.WARNING(f"    • {w}"))

        total_not_found = (
            stats["tutors_not_found"] + stats["groups_not_found"] + stats["students_not_found"]
        )
        if total_not_found == 0:
            self.log_output(self.style.SUCCESS(
                f"\n  {prefix}✓ Все записи успешно сопоставлены!"
            ))
        else:
            self.log_output(self.style.WARNING(
                f"\n  {prefix}⚠ Есть {total_not_found} ненайденных записей — проверьте вручную"
            ))
