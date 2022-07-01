
import logging
import sys

def error(message: str = None, abort: bool = True) -> None:
  """
  Print an optional error message and exit

  :param message: message to print
  :param abort: if true, exit program
  :return: None
  """
  if not message:
    message = "Unknown fatal error occurred"
  logging.error(message)
  if abort:
    sys.exit(1)


def warn(message: str = None) -> None:
  """
  Print an optional warning message and exit

  :param message: message to print
  :return: None
  """
  if not message:
    message = "Unknown warning occurred"
  logging.warning(message)
