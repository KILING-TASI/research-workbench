"""Use UTF-8 for human-facing CLI output, including redirected Windows logs."""
import sys,os

def configure():
    os.environ['PYTHONIOENCODING']='utf-8'
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):
            stream.reconfigure(encoding='utf-8',errors='backslashreplace')
