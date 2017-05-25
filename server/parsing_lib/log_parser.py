"""
LogParser class
"""

import re
from datetime import datetime


class LogParser(object):
    """ Handles parsing of all logs from the Mobile API """

    @staticmethod
    def parse(message):
        """ Parses a log message from the Mobile API

        Args:
            message: the actual decoded message

        Returns:
            dict: the message data to be sent to the web browser
        """
        log_entries = []
        raw_data = message['rawLogData'].splitlines()

        # first log is not the beginning log message
        while re.search('beginning of /dev/log/', raw_data[0]) is not None:
            raw_data = raw_data[1:]

        # get first log to start checking for if an event was split across
        # different logs
        old_log = LogParser.parse_raw_log(raw_data[0])
        log_entries.append(LogParser.parse_entries(old_log))
        current_log = None

        for line in raw_data[1:]:
            # skip the beginning line and the first line stored in the old_log
            # variable
            if re.search('beginning of /dev/log/', line) is not None:
                continue

            # check if current log is like the previous log parsed
            current_log = LogParser.parse_raw_log(line)
            if (current_log['time'] != old_log['time'] or
                current_log['processId'] != old_log['processId'] or
                current_log['threadId'] != old_log['threadId'] or
                current_log['logType'] != old_log['logType'] or
                current_log['tag'] != old_log['tag']):
                log_entries.append(LogParser.parse_entries(current_log))
            else:
                # if part of the same event, add the log's text to the previous
                # parsed log
                log_entries[-1]['text'] += ('\n %s' % current_log['text'])
            old_log = current_log

        return {
            'messageType': 'logData',
            'osType': 'Android',
            'logEntries': log_entries,
        }

    @staticmethod
    def parse_entries(log_entry):
        """ Returns the elements that the web interface shows of a log

        Args:
            log_entry: the logEntry to return including processId and threadId

        Returns:
            dict: the message data to be sent to the web browser (no processId nor threadId)
        """
        return {
            'time': log_entry['time'],
            'logType': log_entry['logType'],
            'tag': log_entry['tag'],
            'text': log_entry['text'],
        }


    @staticmethod
    def parse_raw_log(log_data):
        """ Parse a raw log line

        Args:
            log_data: the raw log line

        Returns:
            dict: the log entry from the log line
        """
        parsed_log = re.search(
            '(.*) (\\d*) (\\d*) (.) (.*?): ((?:.*\\n*)*)', log_data)

        # Parse the Year, we have to add the year to the string so that it
        # parses correctly.
        current_year = datetime.now().year
        date_with_year = '%s-%s' % (str(current_year), parsed_log.group(1).strip())
        log_time = datetime.strptime(date_with_year, '%Y-%m-%d %H:%M:%S.%f')

        # Determine the log type
        log_types = {
            'I': 'Info',
            'W': 'Warning',
            'V': 'Verbose',
            'E': 'Error',
            'D': 'Debug',
            'A': 'WTF',
        }

        return {
            'time': log_time,
            'processId': parsed_log.group(2),
            'threadId': parsed_log.group(3),
            'logType': log_types[parsed_log.group(4)],
            'tag': parsed_log.group(5),
            'text': parsed_log.group(6),
        }