# import all schemas into the schemas/__init__.py file to 
# make them available directly from the app.schemas package instead of
# always specify e.g. app.schemas.brick
from .account import *
from .brick import *
from .collection import *
from .context_search import *
from .learner import *
from .token import *
from .learning_card import *
from .review import *