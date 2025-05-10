from setuptools import setup, Extension
import multiprocessing
from setuptools.command.build import build
from setuptools.command.egg_info import egg_info
import subprocess
import os
import sys
import shutil
import sysconfig
import platform
from wheel.bdist_wheel import bdist_wheel

from os import path

dir = os.path.dirname(__file__)
if dir == '':
   rwd = os.path.abspath('.')
else:
   rwd = os.path.abspath(dir)
with open(os.path.join(rwd, 'README.md'), encoding='u8') as f:
   long_description = f.read()

pkg_version       = '0.0.1'

cpu_count = multiprocessing.cpu_count()
eC_dir = os.path.join(os.path.dirname(__file__), 'eC')
eC_py_dir = os.path.join(os.path.dirname(__file__), 'eC', 'bindings', 'py')
platform_str = 'win32' if sys.platform.startswith('win') else ('apple' if sys.platform.startswith('darwin') else 'linux')
dll_prefix = '' if platform_str == 'win32' else 'lib'
dll_dir = 'bin' if platform_str == 'win32' else 'lib'
dll_ext = '.dll' if platform_str == 'win32' else '.dylib' if platform_str == 'apple' else '.so'
exe_ext = '.exe' if platform_str == 'win32' else ''
pymodule = '_pyecrt' + sysconfig.get_config_var('EXT_SUFFIX')
artifacts_dir = os.path.join('artifacts', platform_str)
lib_dir = os.path.join(eC_dir, 'obj', platform_str, dll_dir)
bin_dir = os.path.join(eC_dir, 'obj', platform_str, 'bin')
make_cmd = 'mingw32-make' if platform == 'win32' else 'make'

def prepare_package_dir(src_files, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    for src, rel_dest in src_files:
        dest_path = os.path.join(dest_dir, rel_dest)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        #print("Copying ", src, " to ", dest_path);
        shutil.copy(src, dest_path)

def build_package():
   try:
      subprocess.check_call([make_cmd, f'-j{cpu_count}', 'SKIP_SONAME=y'], cwd=eC_dir)
      prepare_package_dir([
         (os.path.join(lib_dir, dll_prefix + 'ecrt' + dll_ext), os.path.join(dll_dir, dll_prefix + 'ecrt' + dll_ext)),
         (os.path.join(lib_dir, dll_prefix + 'ectp' + dll_ext), os.path.join(dll_dir, dll_prefix + 'ectp' + dll_ext)),
         (os.path.join(eC_dir, 'obj', platform_str, 'lib', 'libecrtStatic.a'), os.path.join('lib', 'libecrtStatic.a')),
         (os.path.join(bin_dir, 'ecp' + exe_ext), os.path.join('bin', 'ecp' + exe_ext)),
         (os.path.join(bin_dir, 'ecc' + exe_ext), os.path.join('bin', 'ecc' + exe_ext)),
         (os.path.join(bin_dir, 'ecs' + exe_ext), os.path.join('bin', 'ecs' + exe_ext)),
         (os.path.join(bin_dir, 'ear' + exe_ext), os.path.join('bin', 'ear' + exe_ext)),
         (os.path.join(eC_py_dir, 'cffi-ecrt.h'), os.path.join('include', 'cffi-ecrt.h')),
         (os.path.join(eC_dir, 'crossplatform.mk'), 'crossplatform.mk'),
         (os.path.join(eC_dir, 'default.cf'), 'default.cf'),
      ], artifacts_dir)
   except subprocess.CalledProcessError as e:
      print(f"Error during make: {e}")
      sys.exit(1)

class build_with_make(build):
    def initialize_options(self):
        super().initialize_options()
    def run(self):
        build_package()
        super().run()

class egg_info_with_build(egg_info):
    def initialize_options(self):
        super().initialize_options()
    def run(self):
        build_package()
        super().run()

class setplatname_bdist_wheel(bdist_wheel):
   def finalize_options(self):
      super().finalize_options()
      system = sys.platform
      machine = platform.machine().lower()

      if system.startswith('win'):
         self.plat_name = 'win_amd64' if 'amd64' in machine or 'x86_64' in machine else 'win32'
      elif system.startswith('darwin'):
         arch = 'arm64' if 'arm' in machine else 'x86_64'
         self.plat_name = f'macosx_10_15_{arch}'
      elif system.startswith('linux'):
         arch = 'x86_64' if 'x86_64' in machine or 'amd64' in machine else machine
         self.plat_name = f'manylinux1_{arch}'
      elif system.startswith('freebsd'):
         arch = 'x86_64' if 'x86_64' in machine or 'amd64' in machine else machine
         self.plat_name = f'freebsd_{arch}'
      else:
         print("WARNING: platform not detected")
         self.plat_name = None

   def get_tag(self):
      # This package is not specific to a particular Python version
      python_tag = 'py3' # 'py2.py3'
      abi_tag = 'none'
      plat_name = getattr(self, 'plat_name', None)
      return (python_tag, abi_tag, plat_name)

lib_files = [
   'libecrtStatic.a'
]

include_files = [
   'cffi-ecrt.h'
]

bin_files = [
   'ecp' + exe_ext,
   'ecc' + exe_ext,
   'ecs' + exe_ext,
   'ear' + exe_ext,
]

if platform_str == 'win32':
   bin_files.extend([
      'libecrtStatic.a',
      os.path.join('ecrt' + dll_ext),
      os.path.join('ectp' + dll_ext),
   ])
else:
   lib_files.extend([
      'libecrtStatic.a',
      os.path.join('libecrt' + dll_ext),
      os.path.join('libectp' + dll_ext),
   ])

commands = set(sys.argv)
if 'sdist' in commands:
   packages=['ecdev']
   package_dir = { 'ecdev': 'eC' }
   package_data = {'ecdev': [] }
   cmdclass = {}
else:
   packages=['ecdev', 'ecdev.lib', 'ecdev.bin', 'ecdev.include' ]
   package_dir={
      'ecdev': artifacts_dir,
      'ecdev.lib': os.path.join(artifacts_dir, 'lib'),
      'ecdev.bin': os.path.join(artifacts_dir, 'bin'),
      'ecdev.include': os.path.join(artifacts_dir, 'include')
   }
   package_data={
      'ecdev': [ 'crossplatform.mk', 'default.cf' ],
      'ecdev.lib': lib_files,
      'ecdev.bin': bin_files,
      'ecdev.include': include_files,
   }
   cmdclass={'build': build_with_make, 'bdist_wheel': setplatname_bdist_wheel, 'egg_info': egg_info_with_build }

setup(
    name='ecdev',
    version='0.0.1',
    setup_requires=['setuptools'],
    packages=packages,
    package_dir=package_dir,
    package_data=package_data,
    include_package_data=True,
    ext_modules=[],
    cmdclass=cmdclass,
)
