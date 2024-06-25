from dotmap import DotMap
from core.utils import safe_deep_get, safe_deep_set

setattr(DotMap, 'safe_deep_get', safe_deep_get)
setattr(DotMap, 'safe_deep_set', safe_deep_set)
