from threading import Thread
import logging
import sched
import time

from availtgbot import checker, billing


# Scheduler class used for repetetive function calls over time period
class RepeatScheduler(object):
    def __init__(self):
        self.scheduler = sched.scheduler(time.time, time.sleep)
        self.eventID = 0

    def setup(self, interval, action, action_args=()):
        action(*action_args)
        self.eventID = self.scheduler.enter(interval, 1, self.setup, (interval, action, action_args))

    def run(self):
        thread = Thread(target=self.scheduler.run)
        thread.start()
        # self.scheduler.run()

    def stop(self):
        self.scheduler.cancel(self.eventID)


# Monitor organizes the checking procedure for all URLs and updates database with results.
class Monitor:
    def __init__(self, check_handler, db_path=":memory:"):
        self.billing = billing.Billing(db_path)
        self.check_handler = check_handler
        self.repeat_scheduler = RepeatScheduler()
        self.running = False
        self.logger = logging.getLogger('availtgbot.monitor.Monitor')

    # Start to moniror all the items in the DB
    def start(self):
        self.logger.debug("Starting the monitor")
        self.repeat_scheduler.setup(1, self._check_items)
        self.repeat_scheduler.run()
        self.running = True
        self.logger.debug("Monitor started")

    # Stop the monitoring procedure
    def stop(self):
        self.logger.debug("Stopping the monitor")
        self.repeat_scheduler.stop()
        self.running = False
        self.logger.debug("Monitor stopped")

    # Runs through all the items stored in the DB and starts a checker for each
    def _check_items(self):
        self.logger.debug("Running URL check round")
        for item in self.billing.get_monitor_items():
            if self._should_check(item):
                thread = Thread(target=checker.AvailChecker.check_url, args=(item, self._update_status_handler))
                thread.start()

    # Once checker finishes this method is called to calculate results
    def _update_status_handler(self, item, status):
        changed = item.last_status != status
        self.billing.update_user_item(item.user_id, item.name, status=status)
        self.check_handler(item, status, changed)

    # Returns whether a specific URL is to be checked in this round
    @staticmethod
    def _should_check(item, m_time=None):
        if m_time is None:
            m_time = int(time.time())
        return (m_time - item.offset) % item.delay == 0
