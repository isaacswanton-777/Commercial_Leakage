import importlib, traceback

try:
    importlib.import_module('API')
    print('Imported API module successfully')
except Exception:
    traceback.print_exc()