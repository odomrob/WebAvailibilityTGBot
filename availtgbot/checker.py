from urllib.parse import urlsplit, SplitResult
from availtgbot import billing
import http.client
import socket
import logging
import re


# Class for working with URLs and one that performs all network connectivity(not to telegram servers for chatting)
class AvailChecker:

    logger = logging.getLogger('availtgbot.checker.AvailChecker')

    def __init__(self):
        pass

    # Checking if URL is reachable and getting the response code
    @staticmethod
    def check_url(item, handler=None):
        response = 0
        try:
            url = item.get_parsed_url() if isinstance(item, billing.BillingItem) else item
            tokens = AvailChecker.parse_url(url) if not isinstance(url, SplitResult) else url
            AvailChecker.logger.debug("Checking URL: %s", "{}/{}".format(tokens.netloc, tokens.path))
            conn = http.client.HTTPConnection(tokens.netloc, timeout=5)
            conn.request("GET", tokens.path)
            response = conn.getresponse().status
        except socket.gaierror or socket.timeout:
            response = 0
        finally:
            if handler:
                handler(item, response)
        return response

    # Parsing URL into tokens
    @staticmethod
    def parse_url(url):
        scheme_reg = re.compile("^http[s]?://.+$")
        if not re.match(scheme_reg, url):
            url = "http://" + url
        AvailChecker._validate_url(url)
        tokens = urlsplit(url)
        return tokens

    # Validating the URL using some creepy regexp
    @staticmethod
    def _validate_url(url):
        url_reg = re.compile("^(http[s]?://)?[a-zA-Z0-9]+\.[a-zA-Z]+(/[a-zA-Z0-9\-]*\.*[a-zA-Z0-9\-]*)*" +
                             "(/[a-zA-Z0-9\-]*\.*[a-zA-Z0-9\-]*(\?[a-zA-Z0-9\-]+=[a-zA-Z0-9\-]+" +
                             "(&[a-zA-Z0-9\-]+=[a-zA-Z0-9\-]+)*)?)?$")
        if not re.match(url_reg, url):
            raise IOError
        try:
            result = urlsplit(url)
            if not [result.scheme, result.netloc, result.path]:
                raise IOError
        except:
            raise IOError
