import os

import flask
import gdcdatamodel
import gdcdictionary
import peregrine

from gdcdatamodel import models
import gdcdictionary
import peregrine

from peregrine.dictionary import init
from peregrine.models import init

peregrine.dictionary.init(gdcdictionary.gdcdictionary)
peregrine.models.init(gdcdatamodel.models)
blueprint = flask.Blueprint('graphql', 'submission_v0')