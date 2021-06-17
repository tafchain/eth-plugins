#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# filename:logger.py

import os
import logbook
from logbook import Logger, StreamHandler, FileHandler, TimedRotatingFileHandler
from logbook.more import ColorizedStderrHandler


def log_type(record, handler):
    log = "[{date}] [{level}] [{filename}] [{func_name}] [{lineno}] {msg}".format(
        date=record.time,
        level=record.level_name,
        filename=os.path.split(record.filename)[-1],
        func_name=record.func_name,
        lineno=record.lineno,
        msg=record.message
    )
    return log


LOG_DIR = os.path.join("log")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

log_std = ColorizedStderrHandler(bubble=True, level='DEBUG')
log_std.formatter = log_type

log_file = TimedRotatingFileHandler(
    os.path.join(LOG_DIR, '%s.log' % 'log'), date_format='%Y-%m-%d', bubble=True, level='INFO', encoding='utf-8')
log_file.formatter = log_type

run_log = Logger("script_log")


def init_logger():
    logbook.set_datetime_format("local")
    run_log.handlers = []
    run_log.handlers.append(log_file)
    run_log.handlers.append(log_std)


init_logger()
