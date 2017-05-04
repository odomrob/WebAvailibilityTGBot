from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
import telegram

import logging
import pickle
import time

from availtgbot import billing, monitor, checker
from availtgbot.billing import Status


class Bot(object):
    def __init__(self, token, db_path=":memory:", default_delay=10, min_delay=5):

        self.default_delay = default_delay
        self.min_delay = min_delay
        self.billing = billing.Billing(db_path)
        self.monitor = monitor.Monitor(self._status_updated, db_path)

        self.logger = logging.getLogger('availtgbot.bot.Bot')

        self.updater = Updater(token=token)
        dispatcher = self.updater.dispatcher

        dispatcher.add_handler(CommandHandler('start', self._start_command))
        dispatcher.add_handler(MessageHandler(Filters.command, self._unknown_command))
        dispatcher.add_handler(MessageHandler(Filters.text, self._text_message))
        self.updater.dispatcher.add_handler(CallbackQueryHandler(self._menu_answer_callback))
        self.logger.debug("Bot inintialized.")

    # Start the bot
    def start(self):
        self.logger.debug("Starting the bot.")
        self.monitor.start()
        self.updater.start_polling()
        self.logger.debug("Bot Started.")

    # Stop the bot
    def stop(self):
        self.logger.debug("Stopping the bot.")
        self.monitor.stop()
        self.updater.stop()
        self.logger.debug("Bot stopped.")

    # Determine if bot is running
    def is_running(self):
        return self.updater.running or self.monitor.running

    # User interaction handlers

    # Starting new conversation
    def _start_command(self, bot, update):
        self.billing.add_session(update.message.chat_id)
        self._send_welcome(bot, update.message.chat_id)
        self._send_status(bot, update.message.chat_id)
        self.logger.debug("Started new chat: %d.", update.message.chat_id)

    # Called upon recieval of new message
    def _text_message(self, bot, update):
        user_id = update.message.chat_id
        status = Status(self.billing.get_session(user_id).status)

        self.logger.debug("New message from user %d. Actual status: %s", update.message.chat_id, status.name)

        if status is Status.STATUS_IDLE:
            bot.sendMessage(chat_id=user_id, text="Sorry, I'm not a chatting bot. " +
                                                  "Please interact with me via the menu.")
            self._send_status(bot, user_id)

        elif status is Status.STATUS_ADDING_NAME:
            text = update.message.text

            try:
                self.billing.update_session(user_id, Status.STATUS_ADDING_URL, info=text)

            except billing.Billing.UserNotFoundError:
                self.logger.warning("User not registered: %d.", user_id)
                bot.sendMessage(chat_id=user_id, text="User not registered. Please /start the conversation.")

            finally:
                self._send_status(bot, user_id, text)

        elif status is Status.STATUS_ADDING_URL:
            text = update.message.text
            name = pickle.loads(self.billing.get_session(user_id).extra_info)
            try:
                # Parse URL
                url = checker.AvailChecker.parse_url(text)

                # Validate by connecting
                if not checker.AvailChecker.check_url(url):
                    self.logger.warning("Provided URL is not reachable: %s.", str(url))
                    bot.sendMessage(chat_id=user_id, text="URL is not reachable.")
                    raise IOError

                # Add URL to the db
                self.billing.add_user_item(user_id, name, url, self.default_delay, int(time.time() + 1))
                self.billing.update_session(user_id, Status.STATUS_IDLE)

                # Send further instructions
                bot.sendMessage(chat_id=user_id, text="URL added.")
                self._send_list(bot, user_id)
                self._send_status(bot, user_id)

            except IOError:
                self.logger.debug("Caught a URL that is not incorrect.")
                bot.sendMessage(chat_id=user_id, text="URL is incorrect.")
                bot.sendMessage(chat_id=user_id, text="Please state URL to monitor for '{}'" +
                                                      " or select any menu button to start over".format(name),
                                disable_web_page_preview=True)
            except billing.Billing.MonitorItemNameExistsError:
                self.logger.debug("Tried to add a URL that already exists.")
                self.billing.update_session(user_id, Status.STATUS_IDLE)
                bot.sendMessage(chat_id=user_id, text="URL with this associated name already exists. Not added.")
                self._send_status(bot, user_id)

        elif status is Status.STATUS_REMOVE_NAME:
            text = update.message.text
            try:
                self.billing.remove_user_item(user_id, text)
                self.billing.update_session(user_id, Status.STATUS_IDLE)
                bot.sendMessage(chat_id=user_id, text="URL is now removed from the watchlist.")
            except billing.Billing.MonitorItemNotFoundError:
                self.logger.warning("Trying to remove alias that is not here: %s.", text)
                bot.sendMessage(chat_id=user_id, text="URL with name '{}' is not monitored by your user or press a" +
                                                      " button in the menu to perform another action.".format(text),
                                disable_web_page_preview=True)
            finally:
                self._send_status(bot, user_id)

        elif status is Status.STATUS_SETDELAY_NAME:
            text = update.message.text
            try:
                self.billing.update_session(user_id, Status.STATUS_SETDELAY_TIME, info=text)
            except billing.Billing.MonitorItemNotFoundError:
                self.logger.warning("Trying to remove alias that is not here: %s.", text)
                bot.sendMessage(chat_id=user_id, text="URL with name '{}' is not monitored by your user or press a" +
                                                      " button in the menu to perform another action.".format(text),
                                disable_web_page_preview=True)
            finally:
                self._send_status(bot, user_id)

        elif status is Status.STATUS_SETDELAY_TIME:
            text = update.message.text
            try:
                delay = int(text)
                if delay < self.min_delay:
                    raise ValueError

            except ValueError:
                self.logger.warning("Incorrect delay value: %s.", text)
                bot.sendMessage(chat_id=user_id, text="Delay must be represented by an integer." +
                                                      " Value must be more than {}".format(self.min_delay))
                return

            try:
                name = pickle.loads(self.billing.get_session(user_id).extra_info)
                print(name)
                print(user_id)
                self.billing.update_user_item(user_id, name, delay=delay, offset=int(time.time() + 1))
                self.billing.update_session(user_id, Status.STATUS_IDLE)
                bot.sendMessage(chat_id=user_id, text="Delay for item '{}' has been updated.".format(name))

            except billing.Billing.MonitorItemNotFoundError:
                self.logger.error("Very strange. Setting delay for inexistent name or update error: %s.", text)
                bot.sendMessage(chat_id=user_id, text="Internal error occured. Please start over.")

            finally:
                self.billing.update_session(user_id, Status.STATUS_IDLE)
                self._send_status(bot, user_id)

    # Once user hits a menu button this method is called
    def _menu_answer_callback(self, bot, update):
        query = update.callback_query.data
        user_id = update.callback_query.message.chat_id
        self.logger.debug("Menu callback from user %d: %s", user_id, query)
        print("callback ", query, user_id)
        if query == "add":
            self.billing.update_session(user_id, Status.STATUS_ADDING_NAME)

        elif query == "list":
            self.billing.update_session(user_id, Status.STATUS_IDLE)
            self._send_list(bot, user_id)

        elif query == "remove":
            self.billing.update_session(user_id, Status.STATUS_REMOVE_NAME)

        elif query == "status":
            self._send_items_status(bot, user_id)

        elif query == "set_delay":
            self.billing.update_session(user_id, Status.STATUS_SETDELAY_NAME)
        self._send_status(bot, user_id)

    # Handling an unknown command
    def _unknown_command(self, bot, update):
        self.logger.warning("Unknown command recieved: '%s'", update.message.text)
        bot.sendMessage(chat_id=update.message.chat_id, text="Sorry, I don't accept commands." +
                                                             "Please interact via the menu.")

    # Sending methods

    # Sending welcome message
    def _send_welcome(self, bot, user_id):
        self.logger.debug("Sending Welcome message to user '%d'", user_id)
        bot.sendMessage(chat_id=user_id, text="Welcome to Web Availibility Monitor bot!\n I can help you monitor " +
                                              "availibility status of your favorite internet resources!\n",
                        parse_mode=telegram.ParseMode.MARKDOWN)

    # Sending action menu
    def _send_menu(self, bot, user_id):
        self.logger.debug("Sending Menu message to user '%d'", user_id)
        keyboard = [[InlineKeyboardButton("Add URL", callback_data='add')],
                    [InlineKeyboardButton("Remove URL", callback_data='remove')],
                    [InlineKeyboardButton("List tracked URLs", callback_data='list')],
                    [InlineKeyboardButton("Status of URLs", callback_data='status')],
                    [InlineKeyboardButton("Set check delay for tracked URL", callback_data='set_delay')]
                    ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.sendMessage(chat_id=user_id, text="Please select action:", reply_markup=reply_markup)

    # Sending monitored items list
    def _send_list(self, bot, user_id):
        self.logger.debug("Sending Item list message to user '%d'", user_id)
        response = "Unknown error occured. Please proceed."
        try:
            items = self.billing.get_user_items_list(user_id)
            if not len(items):
                response = "You have no URLs monitored yet."
            else:
                response = "Your monitored URLs:\n\n" + "\n\n".join([
                                                                        "Name:\t{0}\nURL:\t{1}\nDelay:\t{2} sec"
                                                                    .format(x[0], x[1].scheme + "://" + x[1].netloc + x[
                                                                            1].path, x[2])
                                                                        for x in items])
        except billing.Billing.UserNotFoundError:
            self.logger.warning("Can't list items. User does not exist in the database yet: '%d'", user_id)
            response = "User not registered. Please /start the conversation."
        finally:
            bot.sendMessage(chat_id=user_id, text=response, disable_web_page_preview=True)

    # Sending last statuses of monitored items
    def _send_items_status(self, bot, user_id):
        self.logger.debug("Sending Items status message to user '%d'", user_id)
        response = "Unknown error occured. Please proceed."
        try:
            items = self.billing.get_user_items_status(user_id)
            if not len(items):
                response = "You have no URLs monitored yet."
            else:
                response = "Your monitored URLs:\n\n" + "\n\n".join([
                                                                    "Name:\t{0}\nLast status:\t{1}\nLast check:\t{2}"
                                                                    .format(*x)
                                                                    for x in items])
        except billing.Billing.UserNotFoundError:
            self.logger.warning("Can't list statsu. User does not exist in the database yet: '%d'", user_id)
            response = "User not registered. Please /start the conversation."
        finally:
            bot.sendMessage(chat_id=user_id, text=response, disable_web_page_preview=True)

    # Sending user a message which corresponds to actual conversation step with this user
    def _send_status(self, bot, user_id, text=None):
        status = Status(self.billing.get_session(user_id).status)
        self.logger.debug("Sending Status to user '%d': %s", user_id, status.name)
        if status is Status.STATUS_IDLE:
            self._send_menu(bot, user_id)
        elif status is Status.STATUS_ADDING_NAME:
            bot.sendMessage(chat_id=user_id, text="Please enter alias(name) for your URL.")

        elif status is Status.STATUS_ADDING_URL:
            bot.sendMessage(chat_id=user_id, text="Please state URL to monitor for '{}'".format(text),
                            disable_web_page_preview=True)

        elif status is Status.STATUS_REMOVE_NAME:
            bot.sendMessage(chat_id=user_id, text="Please enter alias(name) associated with URL to be deleted.")

        elif status is Status.STATUS_SETDELAY_NAME:
            bot.sendMessage(chat_id=user_id, text="Please enter alias(name) associated with URL for which you" +
                                                  " want to update the delay.")
        elif status is Status.STATUS_SETDELAY_TIME:
            bot.sendMessage(chat_id=user_id, text="Please enter the desired check interval in seconds.")

    # Methods for working with internal callbacks

    # Callback called by self.monitor (availtgbot.Monitor instance) when a URL response updates
    def _status_updated(self, item, status, updated):
        self.logger.debug("Sending Response update message to %s", item.user_id)
        if updated:
            split = pickle.loads(item.url)
            url = split.scheme + "://" + split.netloc + split.path
            status = status if status is not 0 else "Server not responding"
            self.updater.bot.sendMessage(chat_id=item.user_id, text=str(
                                                                "*Notification:* URL availibility status changed\n" +
                                                                "Name:\t{0}\n" +
                                                                "URL:\t{1}\n" +
                                                                "Response:\t{2}\n")
                                         .format(item.name, url, status),
                                         disable_web_page_preview=True, parse_mode="Markdown")
