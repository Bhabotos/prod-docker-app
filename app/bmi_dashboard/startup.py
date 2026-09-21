import logging

from bmi_dashboard import db
from bmi_dashboard.config import bmi_settings
from bmi_dashboard.migrations import run_migrations
from bmi_dashboard.models import Base

logger = logging.getLogger(__name__)


def startup() -> bool:
    """Prepare the BMI feature. Returns False (and does nothing) when not configured.

    Any failure while migrating propagates on purpose: the container then never
    becomes healthy and the deploy script rolls back to the previous image.
    """
    if not bmi_settings.enabled:
        logger.warning("BMI dashboard disabled; missing configuration: %s", ", ".join(bmi_settings.missing()))
        return False
    url = bmi_settings.database_url()
    if url.startswith("sqlite"):  # tests only
        db.init_engine(url)
        Base.metadata.create_all(db.get_engine())
    else:
        run_migrations(url)
        db.init_engine(url)
    logger.info("BMI dashboard enabled")
    return True
