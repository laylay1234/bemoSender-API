import logging


def debug(msg):
    # Get an instance of a logger
    # logger = logging.getLogger(__name__)
    logger = logging.getLogger('bemoSenderr.custom')
    logger.error(str(msg))
