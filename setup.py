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
import distutils.ccompiler
from distutils.command.build_ext import build_ext
from wheel.bdist_wheel import bdist_wheel

from os import path

pkg_version = '0.0.3'

env = os.environ.copy()

cc_override = None

# print("sys.platform is: ", sys.platform)

if sys.platform.startswith('win'):

   # NOTE: PyPy builds are failing due to a .def file containing a PyInit_ symbol which is specific to CPython
   # See generated build/temp.win-amd64-pypy38/Release/build/temp.win-amd64-pypy38/release/_pyecrt.pypy38-pp73-win_amd64.def
   # and https://github.com/python-cffi/cffi/issues/170

   # This approach works with Python 3.8
   def get_mingw(plat=None):
       return 'mingw32'

   distutils.ccompiler.get_default_compiler = get_mingw

   # This approach works with Python 3.9+
   class CustomBuildExt(build_ext):
      def initialize_options(self):
         super().initialize_options()
         self.compiler = 'mingw32'

   def get_gcc_target():
       try:
           output = subprocess.check_output(['gcc', '-dumpmachine'], universal_newlines=True)
           return output.strip()
       except Exception:
           return None

   def check_gcc_multilib():
       try:
           output = subprocess.check_output(['gcc', '-v'], stderr=subprocess.STDOUT, universal_newlines=True)
           return '--enable-multilib' in output
       except Exception:
           return False

   def is_gcc_good_for(archBits):
       target = get_gcc_target()
       if target is None:
           return True
       supports_multilib = check_gcc_multilib()

       if target.startswith('x86_64'):
           return archBits == 64
       elif target.startswith('i686') or target.startswith('i386'):
           return archBits == 32
       else:
           return True # Unknown

   def check_i686_w64_available():
       try:
           result = subprocess.run(
               ['i686-w64-mingw32-gcc', '--version'],
               stdout=subprocess.PIPE,
               stderr=subprocess.PIPE,
               check=True,
               universal_newlines=True
           )
           return True
       except (subprocess.CalledProcessError, FileNotFoundError):
           return False

   if platform.architecture()[0] == '64bit':
      # Ensure ProgramFiles(x86) is set
      if 'ProgramFiles(x86)' not in env:
         env['ProgramFiles(x86)'] = r"C:\Program Files (x86)"
   else:
      if 'ProgramFiles(x86)' in env:
         del os.environ['ProgramFiles(x86)']
      if is_gcc_good_for(32) == False:
         if check_i686_w64_available():
            cc_override = ['GCC_PREFIX=i686-w64-mingw32-']

dir = os.path.dirname(__file__)
if dir == '':
   rwd = os.path.abspath('.')
else:
   rwd = os.path.abspath(dir)
with open(os.path.join(rwd, 'README.md'), encoding='u8') as f:
   long_description = f.read()

cpu_count = multiprocessing.cpu_count()
eC_dir = os.path.join(os.path.dirname(__file__), 'eC')
eC_c_dir = os.path.join(os.path.dirname(__file__), 'eC', 'bindings', 'c')
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
      if not os.path.exists(artifacts_dir):
         make_and_args = [make_cmd, f'-j{cpu_count}', 'SKIP_SONAME=y', 'ENABLE_PYTHON_RPATHS=y'] #, 'V=1']
         if cc_override is not None:
            make_and_args.extend(cc_override)

         subprocess.check_call(make_and_args, cwd=eC_dir, env=env)
         prepare_package_dir([
            (os.path.join(lib_dir, dll_prefix + 'ecrt' + dll_ext), os.path.join(dll_dir, dll_prefix + 'ecrt' + dll_ext)),
            (os.path.join(lib_dir, dll_prefix + 'ectp' + dll_ext), os.path.join(dll_dir, dll_prefix + 'ectp' + dll_ext)),
            (os.path.join(eC_dir, 'obj', platform_str, 'lib', 'libecrtStatic.a'), os.path.join('lib', 'libecrtStatic.a')),
            (os.path.join(bin_dir, 'ecp' + exe_ext), os.path.join('bin', 'ecp' + exe_ext)),
            (os.path.join(bin_dir, 'ecc' + exe_ext), os.path.join('bin', 'ecc' + exe_ext)),
            (os.path.join(bin_dir, 'ecs' + exe_ext), os.path.join('bin', 'ecs' + exe_ext)),
            (os.path.join(bin_dir, 'ear' + exe_ext), os.path.join('bin', 'ear' + exe_ext)),
            (os.path.join(eC_py_dir, 'cffi-ecrt.h'), os.path.join('include', 'cffi-ecrt.h')),
            (os.path.join(eC_c_dir, 'ecrt.h'),       os.path.join('include', 'ecrt.h')),
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
   'cffi-ecrt.h',
   'ecrt.h'
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
   if sys.platform.startswith('win'):
      cmdclass['build_ext'] = CustomBuildExt

setup(
    name='ecdev',
    version=pkg_version,
    setup_requires=['setuptools'],
    packages=packages,
    package_dir=package_dir,
    package_data=package_data,
    include_package_data=True,
    ext_modules=[],
    cmdclass=cmdclass,
    description='eC Software Development Kit',
    url='https://ec-lang.org',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Jérôme Jacovella-St-Louis, Ecere Corporation',
    author_email='jerome@ecere.com',
    license='BSD-3-Clause',
    keywords='eC sdk compiler transpiler archiver runtime type-system object-model reflection file-system collections datetime json-parser econ serialization',
    classifiers=[
       'Development Status :: 4 - Beta',
       'Intended Audience :: Developers',
       'Operating System :: Microsoft :: Windows',
       'Operating System :: POSIX :: Linux',
       'Programming Language :: Other',
       'Programming Language :: Python :: 3',
       'Topic :: File Formats :: JSON',
       'Topic :: Software Development :: Compilers',
       'Topic :: Software Development :: Internationalization',
       'Topic :: Software Development :: Libraries',
       'Topic :: System :: Archiving',
    ]
)
