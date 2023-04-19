from flask_apscheduler import APScheduler

scheduler = APScheduler()


def setup_scheduler(app):

    if scheduler.state != 1:
        scheduler.init_app(app)
        scheduler.start()
    return app


