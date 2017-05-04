from sqlalchemy import Column, Integer, String, PickleType, DateTime, pool, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from enum import Enum
import pickle
import datetime
import logging

__Base__ = declarative_base()


# Representing Monitored item in the DB
class BillingItem(__Base__):
    __tablename__ = "monitoritems"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String)
    name = Column(String)
    url = Column(PickleType)
    delay = Column(Integer)
    offset = Column(Integer)
    last_check = Column(DateTime, nullable=True)
    last_status = Column(Integer, default=0)

    def get_parsed_url(self):
        return pickle.loads(self.url)

    def __repr__(self):
        return str("<BillingItem(id=%s, user_id='%s', name='%s', url='%s', delay='%s', offset='%s', last_check='%s'" +
                   " last_status=%d)>") % (
                   self.id, self.user_id, self.name, self.url, self.delay, self.offset, self.last_check,
                   self.last_status)


# User session status enumeration
class Status(Enum):
    STATUS_IDLE = 0x000
    STATUS_ADDING_URL = 0x001
    STATUS_ADDING_NAME = 0x002
    STATUS_SETDELAY_NAME = 0x010
    STATUS_SETDELAY_TIME = 0x020
    STATUS_REMOVE_NAME = 0x100


# Representing User session in the DB
class BillingStatus(__Base__):
    __tablename__ = "sessionstatus"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    status = Column(Integer, default=0)
    extra_info = Column(PickleType, nullable=True)

    def __repr__(self):
        return "<BillingStatus(id=%s, user_id='%s', status='%s')>" % (self.id, self.user_id, self.status)

# Singleton for dealing with all the DB-related stuff. Manages monitored items and user sessions.
class Billing:

    class MonitorItemNameExistsError(Exception):
        def __init__(self, user_id, name):
            self.message = "Monitor item with name " + name + " already exists for user " + str(user_id)

    class UserNotFoundError(Exception):
        def __init__(self, user_id):
            self.message = "User with id " + str(user_id) + " not found"

    class MonitorItemNotFoundError(Exception):
        def __init__(self, user_id, name):
            self.message = "Monitor item with name " + name + " not found for user " + str(user_id)

    engine = None
    logger = None
    def __init__(self, path):
        if Billing.engine is None:
            Billing.logger = logging.getLogger('availtgbot.billing.Billing')
            Billing.engine = create_engine('sqlite:///{}'.format(path), echo=False,
                                           connect_args={'check_same_thread': False},
                                           poolclass=pool.StaticPool)
            __Base__.metadata.create_all(Billing.engine, checkfirst=True)

    # Monitor item table methods

    # Check if item exists for user
    def item_exists(self, user_id, name):
        Billing.logger.debug("Item exists request for user: %d, item: %s", user_id, name)
        session = Session(Billing.engine)
        item = session.query(BillingItem).filter_by(user_id=user_id, name=name)
        return item.count() > 0

    # Get all monitored items
    def get_monitor_items(self):
        Billing.logger.debug("All monitored items request")
        return Session(Billing.engine).query(BillingItem).all()

    # Add a new item for user
    def add_user_item(self, user_id, name, url, delay, offset):
        Billing.logger.debug("Add monitor item request: user_id: %d, name: %s", user_id, name)
        if self.item_exists(user_id, name):
            Billing.logger.debug("Can't add item with name already exists: user_id: %d, name: %s", user_id, name)
            raise Billing.MonitorItemNameExistsError(user_id, name)

        log = BillingItem(user_id=user_id, name=name, url=pickle.dumps(url), delay=delay, offset=offset)
        session = Session(Billing.engine)
        session.add(log)
        session.commit()

    # Get all monitored items for a particular user
    def get_user_items_list(self, user_id):
        Billing.logger.debug("Listing items for user: user_id: %d", user_id)
        if not self.session_exists(user_id):
            Billing.logger.debug("User not found: user_id: %d")
            raise Billing.UserNotFoundError(user_id)

        items = Session(Billing.engine).query(BillingItem).filter_by(user_id=user_id)
        return [(x.name, pickle.loads(x.url), x.delay) for x in items]

    # Get all items' statuses for a user
    def get_user_items_status(self, user_id):
        Billing.logger.debug("Listing all user item statuses: user_id: %d", user_id)
        if not self.session_exists(user_id):
            Billing.logger.debug("User not found: user_id: %d")
            raise Billing.UserNotFoundError(user_id)

        items = Session(Billing.engine).query(BillingItem).filter_by(user_id=user_id)
        return [(x.name, x.last_status, x.last_check) for x in items]

    # Update information on some user item
    def update_user_item(self, user_id, name, delay=None, status=None, offset=None):
        Billing.logger.debug("Updating user item: user_id: %d, name: %s", user_id, name)
        if not self.item_exists(user_id, name):
            Billing.logger.debug("User item not found: user_id: %d, name: %s", user_id, name)
            raise Billing.MonitorItemNotFoundError(user_id, name)

        session = Session(Billing.engine)
        item = session.query(BillingItem).filter_by(user_id=user_id, name=name).first()
        if delay:
            item.delay = delay
        if status:
            item.last_status = status
            item.last_check = datetime.datetime.now()
        if offset:
            item.offset = offset
        session.commit()

    # Remove a monitored item for a specified user
    def remove_user_item(self,user_id, name):
        Billing.logger.debug("Removing user item: user_id: %d, name: %s", user_id, name)
        if not self.item_exists(user_id, name):
            Billing.logger.debug("User item not found: user_id: %d, name: %s", user_id, name)
            raise Billing.MonitorItemNotFoundError(user_id, name)
        session = Session(Billing.engine)
        item = session.query(BillingItem).filter_by(user_id=user_id, name=name).first()
        session.delete(item)
        session.commit()

    # Session table methods

    # Check if user is already registered in the system
    def session_exists(self, user_id):
        Billing.logger.debug("Checking if user session exists: user_id: %d", user_id)
        item = Session(Billing.engine).query(BillingStatus).filter_by(user_id=user_id)
        return item.count() > 0


    # Get all information about user session
    def get_session(self, user_id):
        Billing.logger.debug("Getting user session info: user_id: %d", user_id)
        if not self.session_exists(user_id):
            Billing.logger.debug("User not found: user_id: %d", user_id)
            raise Billing.UserNotFoundError(user_id)

        session = Session(Billing.engine)
        item = session.query(BillingStatus).filter_by(user_id=user_id).first()
        return item

    # Ad a new user to the system
    def add_session(self, user_id):
        Billing.logger.debug("adding new user: user_id: %d", user_id)
        if not self.session_exists(user_id):

            session = Session(Billing.engine)
            item = BillingStatus(user_id=user_id)
            session.add(item)
            session.commit()

    # Update user's session status
    def update_session(self, user_id, status, info=None):
        Billing.logger.debug("Updating user session: user_id: %d, status: %s", user_id, status.name)
        if not self.session_exists(user_id):
            raise Billing.UserNotFoundError(user_id)
        session = Session(Billing.engine)
        item = session.query(BillingStatus).filter_by(user_id=user_id).first()
        item.status = status.value
        item.extra_info = pickle.dumps(info)
        session.commit()
