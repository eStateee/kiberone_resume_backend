from django.core.management.base import BaseCommand
from app_resumes.models import Group, TutorProfile
from app_resumes.crm_integration import get_all_groups

import logging

logger = logging.getLogger("app_resume")


class Command(BaseCommand):
    help = "Synchronize all groups from CRM to the database"

    def handle(self, *args, **options):
        try:
            # Get all groups from CRM
            groups_data = get_all_groups()
            if not groups_data:
                self.stdout.write(self.style.WARNING("No groups found in CRM"))
                return

            synced_count = 0
            skipped_count = 0
            for group_data in groups_data:
                # Extract fields from CRM data
                crm_group_id = group_data.get("id")
                branch_ids = group_data.get("branch_ids")
                teacher_ids = group_data.get("teacher_ids")
                name = group_data.get("name")
                level_id = group_data.get("level_id")
                status_id = group_data.get("status_id")
                company_id = group_data.get("company_id")
                streaming_id = group_data.get("streaming_id")
                limit = group_data.get("limit")
                note = group_data.get("note")
                b_date = group_data.get("b_date")
                e_date = group_data.get("e_date")
                created_at = group_data.get("created_at")
                updated_at = group_data.get("updated_at")
                custom_aerodromnaya = group_data.get("custom_aerodromnaya")

                # Проверка обязательных NOT NULL полей
                missing_fields = []
                if level_id is None:
                    missing_fields.append(f"level_id=None")
                if status_id is None:
                    missing_fields.append(f"status_id=None")
                if limit is None:
                    missing_fields.append(f"limit=None")

                if missing_fields:
                    self.stdout.write(self.style.WARNING(
                        f"ПРОПУСК группы crm_id={crm_group_id}, "
                        f"name=\"{name}\": отсутствуют обязательные поля: "
                        f"{', '.join(missing_fields)}"
                    ))
                    logger.warning(
                        f"sync_groups: пропуск группы crm_id={crm_group_id}, "
                        f"name=\"{name}\": {', '.join(missing_fields)}"
                    )
                    skipped_count += 1
                    continue

                # Try to get existing group or create new one
                group, created = Group.objects.get_or_create(
                    crm_group_id=crm_group_id,
                    defaults={
                        "branch_ids": branch_ids,
                        "teacher_ids": teacher_ids,
                        "name": name,
                        "level_id": level_id,
                        "status_id": status_id,
                        "company_id": company_id,
                        "streaming_id": streaming_id,
                        "limit": limit,
                        "note": note,
                        "b_date": b_date,
                        "e_date": e_date,
                        "created_at": created_at,
                        "updated_at": updated_at,
                        "custom_aerodromnaya": custom_aerodromnaya,
                    },
                )

                # If the group already existed, update its fields
                if not created:
                    group.branch_ids = branch_ids
                    group.teacher_ids = teacher_ids
                    group.name = name
                    group.level_id = level_id
                    group.status_id = status_id
                    group.company_id = company_id
                    group.streaming_id = streaming_id
                    group.limit = limit
                    group.note = note
                    group.b_date = b_date
                    group.e_date = e_date
                    group.created_at = created_at
                    group.updated_at = updated_at
                    group.custom_aerodromnaya = custom_aerodromnaya
                    group.save()

                synced_count += 1

            result_msg = f"Successfully synchronized {synced_count} groups"
            if skipped_count:
                result_msg += f", skipped {skipped_count} groups with missing required fields"
            self.stdout.write(self.style.SUCCESS(result_msg))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred while synchronizing groups: {str(e)}"))

