from distutils.core import setup
import py2exe  # Don't remove
from py2exe.build_exe import Target

main_module = "testservice"
main_file = "testservice.py"

myservice = Target(
    # used for the versioninfo resource
    description = "A sample Windows NT service",
    # what to build. For a service, the module name (not the filename) must be specified!
    modules = [main_module],
    cmdline_style='pywin32',

)

setup(
    service = [myservice],
    options={'py2exe': {'bundle_files': 1, 'compressed': True}},
    windows=[{'script': main_file}],
    zipfile=None,
    )