
USER_F5_DIR = "/root/machinegate/f5restapi/"

USER_DATABASES_DIR = USER_F5_DIR + "databases/"

USER_VAR_STATS = USER_F5_DIR + "var/stats/"

USER_NAME = ""

USER_PASSWORD = ""

ENCAP_PASSWORD = ""

LOG_FILE = USER_F5_DIR + "access.log"

THREAD_TIMEOUT = 1

# define the number for the stats rest api return number, 900 means 3day if you set up 5 minutes
STATS_VIEWER_COUNT = 900

# define the number how many days you can save, 31 means 1 month
STATS_SAVEDDATA_MULTI = 31

STATS_TOP_COUNT = 10

RUNSERVER_PORT = '8080'

# define the number how many days you rollback 288 mean, 1day
ROLLBAK_INTERVAL = 288
