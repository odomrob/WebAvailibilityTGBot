# WebAvailibilityTGBot
Bot that allows clients to monitor availibility of web resourse by URL and recieve
 notifications once the resource is down. Written entirely in python.

### Dependencies
* sqlalchemy
* telegram

### Usage:
From command line:
   
    $ python3 -m availtgbot -h
    usage: python -m availtgbot [-h] [-d DATABASE] [-i INTERVAL] [-m MINIMUM] [-v]
                                token
    
    Web Availibility telegram bot.
    
    positional arguments:
      token                 Your telegram API token.
    
    optional arguments:
      -h, --help            show this help message and exit
      -d DATABASE, --database DATABASE
                            Minimum interval between URL checks in sec. If not
                            specified, in-memory storage used.
      -i INTERVAL, --interval INTERVAL
                            Default interval between URL checks in sec.
      -m MINIMUM, --minimum MINIMUM
                            Minimum interval between URL checks in sec.
      -v, --verbose         Output level with corresponding verbosity: -v, -vv,
                            -vvv .
Example:
    
    $ python3 -m availtgbot API_TOKEN_GOES_HERE -i 10 -m 3 -vvv

In-code usage:

    >>> import availtgbot
    >>> bot = availtgbot.Bot(token="API_TOKEN_GOES_HERE")
    >>> bot.start()
    >>> # Do something
    >>> bot.stop()
    >>> 
