# import all schemas into the schemas/__init__.py file to 
# make them available directly from the app.schemas package instead of
# always specify e.g. app.schemas.brick
from .account import *
from .audio import *
from .brick import *
from .chat import *
from .collection import *
from .learner import *
from .sentence import *
from .token import *
