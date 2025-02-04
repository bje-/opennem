# pylint: disable=no-name-in-module
# pylint: disable=no-self-argument
# pylint: disable=no-member
import logging
import platform

from huey import PriorityRedisHuey, crontab

from opennem.crawl import CrawlerSchedule, run_crawls_all, run_crawls_by_schedule
from opennem.db.tasks import refresh_material_views
from opennem.monitors.aemo_intervals import aemo_wem_live_interval
from opennem.monitors.emissions import alert_missing_emission_factors
from opennem.monitors.facility_seen import facility_first_seen_check
from opennem.monitors.opennem import check_opennem_interval_delays
from opennem.notifications.slack import slack_message
from opennem.settings import settings  # noqa: F401
from opennem.workers.aggregates import run_aggregates_all, run_aggregates_all_days
from opennem.workers.daily_summary import run_daily_fueltech_summary
from opennem.workers.emissions import run_emission_update_day
from opennem.workers.facility_data_ranges import update_facility_seen_range
from opennem.workers.gap_fill import run_energy_gapfill

# Py 3.8 on MacOS changed the default multiprocessing model
if platform.system() == "Darwin":
    import multiprocessing

    try:
        multiprocessing.set_start_method("fork")
    except RuntimeError:
        # sometimes it has already been set by
        # other libs
        pass

logger = logging.getLogger("openenm.scheduler.db")

redis_host = None

if settings.cache_url:
    redis_host = settings.cache_url.host  # type: ignore

huey = PriorityRedisHuey("opennem.scheduler.db", host=redis_host)


# 5:45AM and 8:45AM AEST
@huey.periodic_task(crontab(hour="6", minute="45"))
@huey.lock_task("db_refresh_material_views")
def db_refresh_material_views() -> None:
    refresh_material_views("mv_facility_all")
    refresh_material_views("mv_region_emissions")
    refresh_material_views("mv_interchange_energy_nem_region")
    slack_message("Ran refresh of material views on {}".format(settings.env))


@huey.periodic_task(crontab(hour="10", minute="45"))
@huey.lock_task("db_run_daily_fueltech_summary")
def db_run_daily_fueltech_summary() -> None:
    run_daily_fueltech_summary()


@huey.periodic_task(crontab(hour="*/1", minute="15"))
@huey.lock_task("db_refresh_material_views_recent")
def db_refresh_material_views_recent() -> None:
    refresh_material_views("mv_facility_45d")
    refresh_material_views("mv_region_emissions_45d")


# run gap fill tasks
@huey.periodic_task(crontab(hour="*/1", minute="15"))
@huey.lock_task("db_run_energy_gapfil")
def db_run_energy_gapfil() -> None:
    run_energy_gapfill(days=14)


@huey.periodic_task(crontab(hour="*/3", minute=45))
@huey.lock_task("db_run_aggregates")
def db_run_aggregates() -> None:
    run_aggregates_all_days(days=2)


@huey.periodic_task(crontab(hour="8", minute="30"))
@huey.lock_task("db_run_aggregates_year")
def db_run_aggregates_year() -> None:
    run_aggregates_all()


@huey.periodic_task(crontab(hour="6", minute="45"))
@huey.lock_task("db_run_emission_tasks")
def db_run_emission_tasks() -> None:
    try:
        run_emission_update_day(2)
    except Exception as e:
        logger.error("Error running emission update: {}".format(str(e)))


# monitoring tasks
@huey.periodic_task(crontab(minute="*/60"), priority=80)
@huey.lock_task("monitor_opennem_intervals")
def monitor_opennem_intervals() -> None:
    if settings.env != "production":
        return None

    for network_code in ["NEM", "WEM"]:
        check_opennem_interval_delays(network_code)


@huey.periodic_task(crontab(minute="*/60"), priority=50)
@huey.lock_task("monitor_wem_interval")
def monitor_wem_interval() -> None:
    if settings.env != "production":
        return None

    aemo_wem_live_interval()


@huey.periodic_task(crontab(hour="8", minute="45"), priority=10)
@huey.lock_task("monitor_emission_factors")
def monitor_emission_factors() -> None:
    alert_missing_emission_factors()


# worker tasks
@huey.periodic_task(crontab(hour="10", minute="1"))
@huey.lock_task("schedule_facility_first_seen_check")
def schedule_facility_first_seen_check() -> None:
    """Check for new DUIDS"""
    if settings.env == "production":
        facility_first_seen_check()


@huey.periodic_task(crontab(hour="9,18", minute="45"))
@huey.lock_task("db_facility_seen_update")
def db_facility_seen_update() -> None:
    update_facility_seen_range()
    slack_message(f"Updated facility seen range on {settings.env}")


# crawler tasks
@huey.periodic_task(crontab(minute="*/1"))
@huey.lock_task("crawler_scheduled_live")
def crawler_scheduled_live() -> None:
    run_crawls_by_schedule(CrawlerSchedule.live)


@huey.periodic_task(crontab(minute="*/5"))
@huey.lock_task("crawler_scheduled_frequent")
def crawler_scheduled_frequent() -> None:
    run_crawls_by_schedule(CrawlerSchedule.frequent)


@huey.periodic_task(crontab(minute="*/15"), retries=3, retry_delay=30)
@huey.lock_task("crawler_scheduled_quarter_hour")
def crawler_scheduled_quarter_hour() -> None:
    run_crawls_by_schedule(CrawlerSchedule.quarter_hour)


@huey.periodic_task(crontab(hour="*", minute="3,33"), retries=3, retry_delay=30)
@huey.lock_task("crawler_scheduled_half_hour")
def crawler_scheduled_half_hour() -> None:
    run_crawls_by_schedule(CrawlerSchedule.half_hour)


@huey.periodic_task(crontab(hour="*/1", minute="2"), retries=5, retry_delay=90)
@huey.lock_task("crawler_scheduled_hourly")
def crawler_scheduled_hourly() -> None:
    run_crawls_by_schedule(CrawlerSchedule.hourly)


@huey.periodic_task(crontab(hour="5,8,16", minute="15"), retries=5, retry_delay=120)
@huey.lock_task("crawler_scheduled_day")
def crawler_scheduled_day() -> None:
    run_crawls_by_schedule(CrawlerSchedule.daily)


@huey.periodic_task(crontab(hour="*/1", minute="31"), retries=5, retry_delay=120)
@huey.lock_task("crawler_schedule_all_fallback")
def crawler_schedule_all_fallback() -> None:
    run_crawls_all()
