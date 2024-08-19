"""
helpers.globalconstants
~~~~~~~~~~~~~~~~~~~~~~~

This module defines and centralizes heavily used constants which used to be
defined all throughout the app.
"""



#                                                             Focus/Blur Related
FOCUS_URL = 'https://focus.mypv.pro/'
BLUR_URL = 'https://blur.mypv.pro/'

PORTAL_URL = FOCUS_URL
PORTAL_ENDPOINTS = {
    'daily_summary': 'api/uploads/aggregates/daily',
    'portal_upload': 'api/uploads'
}
""" Includes:
- `'daily_summary': 'api/uploads/aggregates/daily'`
- `'portal_upload': 'api/uploads'`
"""


#                                                            Standard /opt Paths
# FLASK_APP = '/opt/flask_app'
FLASK_APP = '\sos-config'
SOS_CONFIG = '\sos-config'
SOS_DATA = '\sos_data'
MODDATA_DB = '/opt/moddata.db'

CONFIG_INTERNAL = FLASK_APP + '/config_internal'

# TODO: import PLANT_CONFIG from helpers.const.config
#
# needs to be defined here for portal_daily_summary
PLANT_CONFIG = SOS_CONFIG + "/plant_config.json"


#                                                 Development/Production Related
TEST_URL = 'http://127.0.0.1:5000/'
RUNNING_APP_DIR = FLASK_APP


#                                                                   User Related
ADERIS_USERS = ('operations@solar-ops.com', 'operations@aderisenergy.com')
ADERIS_ROOT_USERS = ADERIS_USERS  # just an alias



#                                                           Integrations Related
SMTP_OUTBOX_DIR = SOS_DATA + '/todo_emails'
EMAIL_DIR = SMTP_OUTBOX_DIR  # just an alias

SMS_OUTBOX_DIR = SOS_DATA + '/todo_texts'
TEXT_DIR = SMS_OUTBOX_DIR  # just an alias

