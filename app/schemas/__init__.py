# import all schemas into the schemas/__init__.py file to
# make them available directly from the app.schemas package instead of
# always specify e.g. app.schemas.brick
from .account import *
from .auth import *
from .brick import *
from .brick_override import *
from .collection import *
from .context_search import *
from .forced_alignment import *
from .learner import *
from .learning_card import *
from .readability import *
from .review import *
from .snippet_interaction import *
from .status import *
from .text import *
