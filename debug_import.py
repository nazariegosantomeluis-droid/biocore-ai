import sys
import traceback
print('cwd=', sys.path[0])
try:
    import biomedical
    import inspect
    print('biomedical file=', inspect.getfile(biomedical))
except Exception as e:
    print('error importing biomedical:', type(e), e)
    traceback.print_exc()
