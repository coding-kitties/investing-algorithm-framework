import logging
from datetime import datetime, timedelta
from uuid import uuid4

from bot.constants import TimeUnit
from bot.context.bot_context import Scheduler, Appointment


logger = logging.getLogger(__name__)


def test_scheduling():
    logger.info("TEST: test scheduling")

    appointment_one = {
        'appointment_id': uuid4().__str__(),
        'time_unit': TimeUnit.always,
    }

    appointment_two = {
        'appointment_id': uuid4().__str__(),
        'time_unit': TimeUnit.minute,
        'interval': 1,
    }

    appointment_three = {
        'appointment_id': uuid4().__str__(),
        'time_unit': TimeUnit.minute,
        'interval': 30,
    }

    appointment_four = {
        'appointment_id': uuid4().__str__(),
        'time_unit': TimeUnit.hour,
        'interval': 1,
    }

    scheduler = Scheduler()
    scheduler.add_appointment(**appointment_one)

    assert appointment_one['appointment_id'] in scheduler.schedule_appointments()

    scheduler.add_appointment(**appointment_two)
    scheduler.add_appointment(**appointment_three)
    scheduler.add_appointment(**appointment_four)

    appointments = scheduler.schedule_appointments()

    assert appointment_one['appointment_id'] in appointments
    assert appointment_two['appointment_id'] in appointments
    assert appointment_three['appointment_id'] in appointments
    assert appointment_four['appointment_id'] in appointments

    appointments = scheduler.schedule_appointments()

    assert appointment_one['appointment_id'] in appointments
    assert appointment_two['appointment_id'] not in appointments
    assert appointment_three['appointment_id'] not in appointments
    assert appointment_four['appointment_id'] not in appointments

    minus_one_minute = datetime.now() - timedelta(minutes=1)

    appointments = scheduler._planning.keys()

    for appointment in appointments:
        scheduler._planning[appointment] = Appointment(
            scheduler._planning[appointment].time_unit,
            scheduler._planning[appointment].interval,
            last_run=minus_one_minute
        )

    appointments = scheduler.schedule_appointments()

    assert appointment_one['appointment_id'] in appointments
    assert appointment_two['appointment_id'] in appointments
    assert appointment_three['appointment_id'] not in appointments
    assert appointment_four['appointment_id'] not in appointments

    minus_thirty_minutes = datetime.now() - timedelta(minutes=30)

    appointments = scheduler._planning.keys()

    for appointment in appointments:
        scheduler._planning[appointment] = Appointment(
            scheduler._planning[appointment].time_unit,
            scheduler._planning[appointment].interval,
            last_run=minus_thirty_minutes
        )

    appointments = scheduler.schedule_appointments()

    assert appointment_one['appointment_id'] in appointments
    assert appointment_two['appointment_id'] in appointments
    assert appointment_three['appointment_id'] in appointments
    assert appointment_four['appointment_id'] not in appointments

    minus_one_hour = datetime.now() - timedelta(hours=1)

    appointments = scheduler._planning.keys()

    for appointment in appointments:
        scheduler._planning[appointment] = Appointment(
            scheduler._planning[appointment].time_unit,
            scheduler._planning[appointment].interval,
            last_run=minus_one_hour
        )

    appointments = scheduler.schedule_appointments()

    assert appointment_one['appointment_id'] in appointments
    assert appointment_two['appointment_id'] in appointments
    assert appointment_three['appointment_id'] in appointments
    assert appointment_four['appointment_id'] in appointments

    logger.info("TEST FINISHED")

