from django.apps import AppConfig

class SchedulerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'scheduler'
    verbose_name = 'Scheduler'

    def ready(self):
        # Start APScheduler when Django boots (Phase 7)
        pass
