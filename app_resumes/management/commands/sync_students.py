from django.core.management.base import BaseCommand
from app_resumes.models import Group, Student, TutorProfile
from app_resumes.crm_integration import get_group_clients_from_crm


class Command(BaseCommand):
    help = "Synchronize all students from CRM to the database"

    def handle(self, *args, **options):
        try:
            # Get all groups from the database
            groups = Group.objects.all()

            if not groups:
                self.stdout.write(self.style.WARNING("No groups found in database"))
                return

            total_synced = 0

            for group in groups:
                branch_id = "1"  # Default to branch 1
                if group.branch_ids:
                    if isinstance(group.branch_ids, list):
                        if len(group.branch_ids) > 0:
                            branch_id = str(group.branch_ids[0])
                    else:
                        branch_id = str(group.branch_ids)

                group_clients = get_group_clients_from_crm(str(group.crm_group_id), branch_id)

                if group_clients:
                    for client in group_clients:
                        customer_id = client.get("customer_id")
                        client_name = client.get("client_name")

                        if customer_id and client_name:
                            study_start_date = client.get("custom_datano")
                            
                            # Create or update student record with group relationship
                            student, created = Student.objects.get_or_create(
                                student_crm_id=customer_id, 
                                defaults={
                                    "student_name": client_name, 
                                    "group_id": group.id,
                                    "study_start_date": study_start_date
                                }
                            )

                            # If student already exists, check if any fields need updating
                            if not created:
                                needs_update = False
                                
                                if student.group_id != group.id:
                                    student.group_id = group.id
                                    needs_update = True
                                    
                                if student.student_name != client_name:
                                    student.student_name = client_name
                                    needs_update = True
                                    
                                if student.study_start_date != study_start_date:
                                    student.study_start_date = study_start_date
                                    needs_update = True
                                    
                                if needs_update:
                                    student.save()

                            total_synced += 1

            self.stdout.write(self.style.SUCCESS(f"Successfully synchronized {total_synced} students"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred while synchronizing students: {str(e)}"))
