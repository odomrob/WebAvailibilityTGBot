from signal import signal, SIGINT, SIGTERM, SIGABRT
from time import sleep

import argparse
import logging

from availtgbot.bot import Bot


__tbot__ = None
__is_idle__ = True


def signal_handler(signum, frame):
    __is_idle__ = False
    logging.warning('Exiting immediately!')
    if __tbot__.is_running():
        __tbot__.stop()
    import os
    os._exit(1)


def main():
    global __tbot__, __is_idle__

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)

    parser = argparse.ArgumentParser(prog="python -m availtgbot",description='Web Availibility telegram bot.')

    parser.add_argument('token', type=str
                        ,help='Your telegram API token.')
    parser.add_argument('-d', '--database', type=str, default=':memory:'
                        , help='Minimum interval between URL checks in sec. If not specified, in-memory storage used.')
    parser.add_argument("-i", "--interval", type=int, default=10
                        , help='Default interval between URL checks in sec.')
    parser.add_argument("-m", "--minimum", type=int, default=5
                        , help='Minimum interval between URL checks in sec.')
    parser.add_argument("-v", "--verbose", action="count"
                        , help='Output level with corresponding verbosity: -v, -vv, -vvv .')

    args = parser.parse_args()
    if args.token is None:
        parser.print_help()
        exit(1)

    verbose = max(args.verbose,3)
    levels = [logging.FATAL, logging.ERROR, logging.WARNING, logging.DEBUG]
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=levels[verbose])

    for sig in [SIGINT, SIGTERM, SIGABRT]:
        signal(sig, signal_handler)

    __tbot__ = Bot(token=args.token, db_path=args.database, default_delay=args.interval, min_delay=args.minimum)
    __tbot__.start()

    while __is_idle__:
        sleep(1)


if __name__ == "__main__":
    main()



