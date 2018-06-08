# pylint: disable=unsubscriptable-object
"""
Contains values for global constants.
"""

FLAG_IS_ASYNC = 'async'
# Async scheduling configuration
ASYNC_MAX_Q_LEN = 128
ERR_ASYNC_SCHEDULING = (
    'The API is currently under heavy load and currently has too many'
    ' asynchronous tasks. Please try again later.'
)
