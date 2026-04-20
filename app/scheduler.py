"""APScheduler jobs: daily AI report + low-stock alerts."""
import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)
_scheduler = None


def start_scheduler(app):
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone='Africa/Accra')

    def daily_report():
        with app.app_context():
            try:
                from app.ai_engine import get_health_report
                from app.notifications import telegram_daily_report
                report = get_health_report(app)
                telegram_daily_report(report)
                log.info('Daily AI report sent via Telegram.')
            except Exception as e:
                log.exception(f'Daily report failed: {e}')

    def low_stock_check():
        with app.app_context():
            try:
                from app.models import Product
                from app.notifications import telegram_low_stock
                low = Product.query.filter(
                    Product.status == 'active',
                    Product.stock_quantity <= 5
                ).all()
                if low:
                    telegram_low_stock(low)
            except Exception as e:
                log.exception(f'Low stock check failed: {e}')

    report_hour = int(os.environ.get('DAILY_REPORT_HOUR', '8'))
    _scheduler.add_job(daily_report, CronTrigger(hour=report_hour, minute=0),
                       id='daily_report', replace_existing=True)
    _scheduler.add_job(low_stock_check, CronTrigger(hour='*/6'),
                       id='low_stock', replace_existing=True)

    try:
        _scheduler.start()
        log.info('APScheduler started.')
    except Exception as e:
        log.exception(f'Scheduler failed to start: {e}')
