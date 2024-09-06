import sys

sys.path.append("/var/www/peregrine/")
sys.path.append("/peregrine/")
from wsgi import app as application
