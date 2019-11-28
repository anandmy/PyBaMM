import os
import sys
import subprocess
import tarfile
import wget
try:
    from setuptools import setup, find_packages
    from setuptools.command.build_ext import build_ext
    import setuptools.command.install as orig
except ImportError:
    from distutils.core import setup, find_packages
    from disutils.command.build_ext import build_ext
from distutils.cmd import Command
from platform import python_version

def download_extract_library(url):
    archive=wget.download(url)
    tar = tarfile.open(archive)
    tar.extractall()

def yes_or_no(question):
    while "the answer is invalid":
        reply = str(input(question+' (y/n): ')).lower().strip()
        if reply[0] == 'y':
            return True
        if reply[0] == 'n':
            return False

def update_LD_LIBRARY_PATH(install_dir):
        """ Look for current virtual python env and add export statement for LD_LIBRARY_PATH
        in activate script.
        If no virtual env found, then the current user's .bashrc file is modified instead.
        """
        export_statement='export LD_LIBRARY_PATH={}/lib:$LD_LIBRARY_PATH'.format(install_dir)
        venv_path = os.environ.get('VIRTUAL_ENV')
        if venv_path:
            script_path = os.path.join(venv_path, 'bin/activate')
        else:
            script_path = os.path.join(os.environ.get('HOME'), '.bashrc')

        if '{}/lib'.format(install_dir) in os.environ['LD_LIBRARY_PATH']:
            print("{}/lib was found in LD_LIBRARY_PATH.".format(install_dir))
            print("--> Not updating venv activate or .bashrc scripts")
        else:
            with open(script_path, 'a+') as fh:
                if not export_statement in fh.read():
                    fh.write(export_statement)
                    print("Adding {}/lib to LD_LIBRARY_PATH"
                          " in {}".format(install_dir, script_path))

def install_sundials(sundials_src, sundials_inst):
    pybamm_dir = os.path.abspath(os.path.dirname(__file__))
    build_temp = 'build_sundials'

    # Check that the sundials source dir contains the CMakeLists.txt
    if sundials_src:
        must_download_sundials = False
        CMakeLists=os.path.join(sundials_src,'CMakeLists.txt')
        assert os.path.exists(CMakeLists), ('Could not find {}.'.format(CMakeLists))
    else:
        must_download_sundials = True

    try:
        out = subprocess.check_output(['cmake', '--version'])
    except OSError:
        raise RuntimeError(
            "CMake must be installed to build the SUNDIALS library.")

    # Temp build directory, note that final dir (containing the sundials
    # lib) is self.install_dir
    build_directory = os.path.abspath(build_temp)

    if must_download_sundials:
        question="About to download sundials, proceed?"
        url = 'https://computing.llnl.gov/projects/sundials/download/sundials-4.1.0.tar.gz'
        if yes_or_no(question):
            download_extract_library(url)
            sundials_src=os.path.join(pybamm_dir,'sundials-4.1.0')
        else:
            print("Exiting setup.")
            sys.exit()

    cmake_args = [
        '-DBLAS_ENABLE=ON',
        '-DLAPACK_ENABLE=ON',
        '-DSUNDIALS_INDEX_TYPE=int32_t',
        '-DBUILD_ARKODE:BOOL=OFF',
        '-DEXAMPLES_ENABLE:BOOL=OFF',
        '-DKLU_ENABLE=ON',
        '-DCMAKE_INSTALL_PREFIX=' + sundials_inst,
        build_directory,
    ]

    cmake_args.append(sundials_src)

    if not os.path.exists(build_temp):
        print('-'*10, 'Creating build dir', '-'*40)
        os.makedirs(build_temp)

    # CMakeLists.txt is in the same directory as this setup.py file
    print('-'*10, 'Running CMake prepare', '-'*40)
    subprocess.run(['cmake', sundials_src] + cmake_args,
                   cwd=build_temp)

    print('-'*10, 'Building the sundials', '-'*40)
    make_cmd = ['make', 'install']
    subprocess.run(make_cmd, cwd=build_temp)

    update_LD_LIBRARY_PATH(sundials_inst)

class BuildKLU(Command):
    """ A custom command to compile the SuiteSparse KLU library as part of the PyBaMM
        installation process.
    """

    description = 'Compiles the SuiteSparse KLU module.'
    user_options = [
        # The format is (long option, short option, description).
        ('sundials-src=', None, 'Absolute path to sundials source dir'),
        ('suitesparse-src=', None, 'Absolute path to sundials source dir'),
    ]
    pybamm_dir = os.path.abspath(os.path.dirname(__file__))

    def initialize_options(self):
        """Set default values for option(s)"""
        # Each user option is listed here with its default value.
        self.suitesparse_src = None
        self.sundials_src = None

    def finalize_options(self):
        """Post-process options"""
        # Any unspecified option is set to the value of the 'install' command
        # This could be the default value if 'build_sundials' is invoked on its own
        # or a user-specified value if 'build_sundials' is called from 'install'
        # with options.
        self.set_undefined_options('install',
                                   ('suitesparse_src', 'suitesparse_src'),
                                   ('sundials_src', 'sundials_src'))
        # Check that the sundials source dir contains the CMakeLists.txt
        if self.suitesparse_src:
            self.must_download_suitesparse = False
            klu_makefile=os.path.join(self.suitesparse_src,'KLU','Makefile')
            assert os.path.exists(klu_makefile), ('Could not find {}.'.format(klu_makefile))
        else:
            self.must_download_suitesparse = True

    def run(self):
        try:
            out = subprocess.check_output(['make', '--version'])
        except OSError:
            raise RuntimeError(
                "Make must be installed to compile the SuiteSparse KLU module.")

        if self.must_download_suitesparse:
            question="About to download SuiteSparse, proceed?"
            url='https://github.com/DrTimothyAldenDavis/SuiteSparse/archive/v5.6.0.tar.gz'
            if yes_or_no(question):
                download_extract_library(url)
                self.suitesparse_src=os.path.join(self.pybamm_dir,'SuiteSparse-5.6.0')
            else:
                print("Exiting setup.")
                sys.exit()

        # The SuiteSparse KLU module has 4 dependencies:
        # - suitesparseconfig
        # - amd
        # - COLAMD
        # - btf
        print('-'*10, 'Building SuiteSparse_config', '-'*40)
        make_cmd = ['make']
        build_dir = os.path.join(self.suitesparse_src,'SuiteSparse_config')
        subprocess.run(make_cmd, cwd=build_dir)

        print('-'*10, 'Building SuiteSparse KLU module dependencies', '-'*40)
        make_cmd = ['make', 'library']
        for libdir in ['AMD', 'COLAMD', 'BTF']:
            build_dir = os.path.join(self.suitesparse_src,libdir)
            subprocess.run(make_cmd, cwd=build_dir)

        print('-'*10, 'Building SuiteSparse KLU module', '-'*40)
        build_dir = os.path.join(self.suitesparse_src,'KLU')
        subprocess.run(make_cmd, cwd=build_dir)


        self.run_command('build_idaklu_solver')

class InstallSundials(Command):
    """ A custom command to compile the SUNDIALS library as part of the PyBaMM
        installation process.
    """

    description = 'Download an compiles the SUNDIALS library.'
    user_options = [
        # The format is (long option, short option, description).
        ('sundials-src=', None, 'Absolute path to sundials source dir'),
        ('install-dir=', None, 'Absolute path to sundials install directory'),
        ('klu', None, 'Wether or not to build the the sundials with klu on'),
    ]

    def initialize_options(self):
        """Set default values for option(s)"""
        # Each user option is listed here with its default value.
        self.sundials_src = None
        self.sundials_inst = None

    def finalize_options(self):
        """Post-process options"""
        # Any unspecified option is set to the value of the 'install' command
        # This could be the default value if 'build_sundials' is invoked on its own
        # or a user-specified value if 'build_sundials' is called from 'install'
        # with options.
        self.set_undefined_options('install',
                                   ('sundials_src', 'sundials_src'),
                                   ('sundials_inst', 'sundials_inst'))

    def run(self):
        install_sundials(self.sundials_src, self.sundials_inst)

class BuildIDAKLUSolver(build_ext):
    """ A custom command to build the PyBaMM idaklu solver using
    cmake and pybind11.
    """
    description = 'Compile idaklu solver.'
    user_options = build_ext.user_options + [
        # The format is (long option, short option, description).
        ('sundials-src=', None, 'Path to SUNDIALS source dir'),
        ('suitesparse-src=', None, 'Path to SuiteSparse source dir'),
    ]

    def initialize_options(self):
        """Set default values for option(s)"""
        build_ext.initialize_options(self)
        # Each user option is listed here with its default value.
        self.sundials_src = None
        self.suitesparse_src = None

    def finalize_options(self):
        """Post-process options"""
        self.set_undefined_options('build_klu',
                                   ('sundials_src', 'sundials_src'),
                                   ('suitesparse_src', 'suitesparse_src'))
        build_ext.finalize_options(self)

    def run(self):
        try:
            out = subprocess.run(['cmake', '--version'])
        except OSError:
            raise RuntimeError(
                "CMake must be installed to build the following extensions: " +
                ", ".join(e.name for e in self.extensions))

        py_version = python_version()
        cmake_args = ['-DPYBIND11_PYTHON_VERSION={}'.format(py_version)]

        print('-'*10, 'Running CMake for idaklu solver', '-'*40)
        subprocess.run(['cmake'] + cmake_args)

        print('-'*10, 'Running Make for idaklu solver', '-'*40)
        subprocess.run(['make'])

class InstallODES(Command):
    """ A custom command to install scikits.ode with pip as part of the PyBaMM
        installation process.
    """

    description = 'Installs scikits.odes using pip.'
    user_options = [
        # The format is (long option, short option, description).
        ('sundials-inst=', None, 'Absolute path to sundials installation directory.')
    ]

    def initialize_options(self):
        """Set default values for option(s)"""
        # Each user option is listed here with its default value.
        self.sundials_inst = None

    def finalize_options(self):
        """Post-process options"""
        # Any unspecified option is set to the value of the 'install' command
        # This could be the default value if 'install_odes' is invoked on its own
        # or a user-specified value if 'install_odes' is called from 'install'
        # with options.
        # If option specified the check dir exists
        self.set_undefined_options('install', \
                                   ('sundials_inst', 'sundials_inst'))
        try:
            assert os.path.exists(self.sundials_inst)
        except AssertionError:
            print("Error: Could not find SUNDIALS installation directory"
                  " {}".format(self.sundials_inst))
            print("If you downloaded and installed the SUNDIALS library manually,"
                  "you can specify the directory as\n"
                  "  python setup.py install_odes --sundials-inst=<path/to/directory>")
            print("To download and compile the SUNDIALS automatically, run\n"
                  "  python setup.py install_sundials")
            sys.exit();

    def run(self):
        # At the time scikits.odes is pip installed, the path to the sundials
        # library must be contained in an env variable SUNDIALS_INST
        # see https://scikits-odes.readthedocs.io/en/latest/installation.html#id1

        os.environ['SUNDIALS_INST'] = self.sundials_inst
        env = os.environ.copy()
        subprocess.run(['pip', 'install', 'scikits.odes'], env=env)

class InstallPyBaMM(orig.install):
    """ Install the PyBaMM package, along with the SUNDIALS and
    scikits.odes package
    """
    # This custom command is an overloading of the setuptools.command.install command,
    # which itself overload the distutils.command.install command.
    # This class is therefore inspired from the setuptools.command.install command

    user_options = orig.install.user_options + [
        ('no-sundials', None, "Do not install the SUNDIALS library. scikits.odes is not installed."),
        ('sundials-src=', None, 'Absolute path to sundials source dir'),
        ('sundials-inst=', None, 'Absolute path to sundials install directory'),
        ('suitesparse-dir', None, 'Absolute path to SuiteSparse root directory'),
        ('klu',None, 'Wether or not to build the the sundials with klu on'),
    ]

    pybamm_dir = os.path.abspath(os.path.dirname(__file__))

    def initialize_options(self):
        """Set default values for option(s)"""
        orig.install.initialize_options(self)
        # Each user option is listed here with its default value.
        self.sundials_src = None
        self.sundials_inst = os.path.join(self.pybamm_dir,'sundials')
        self.suitesparse_src = None
        self.no_sundials = None
        self.klu = None

    def finalize_options(self):
        """Post-process options"""
        orig.install.finalize_options(self)
        if self.no_sundials:
            self.build_sundials = False
        else:
            self.build_sundials=True

    def run(self):
        """Install PyBaMM"""
        orig.install.run(self)
        if self.build_sundials:
            self.run_command('build_sundials')
            self.run_command('install_odes')

# Load text for description and license
with open("README.md") as f:
    readme = f.read()

# Read version number from file
def load_version():
    try:
        import os

        root = os.path.abspath(os.path.dirname(__file__))
        with open(os.path.join(root, "pybamm", "version"), "r") as f:
            version = f.read().strip().split(",")
        return ".".join([str(int(x)) for x in version])
    except Exception as e:
        raise RuntimeError("Unable to read version number (" + str(e) + ").")

setup(
    cmdclass = {
        'install_sundials': InstallSundials,
        'install_odes': InstallODES,
        'build_klu': BuildKLU,
        'build_idaklu_solver': BuildIDAKLUSolver,
        'install': InstallPyBaMM,
    },
    name="pybamm",
    version=load_version()+".post4",
    description="Python Battery Mathematical Modelling.",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/pybamm-team/PyBaMM",
    include_package_data=True,
    packages=find_packages(include=("pybamm", "pybamm.*")),
    package_data={
        "pybamm": [
            "./version",
            "../input/parameters/lithium-ion/*.csv",
            "../input/parameters/lithium-ion/*.py",
            "../input/parameters/lead-acid/*.csv",
            "../input/parameters/lead-acid/*.py",
        ]
    },
    # List of dependencies
    install_requires=[
        "numpy>=1.16",
        "scipy>=1.0",
        "pandas>=0.23",
        "anytree>=2.4.3",
        "autograd>=1.2",
        "scikit-fem>=0.2.0",
        # Note: Matplotlib is loaded for debug plots, but to ensure pybamm runs
        # on systems without an attached display, it should never be imported
        # outside of plot() methods.
        # Should not be imported
        "matplotlib>=2.0",
        # Wget is not exactly a dependency for PyBaMM itself, but is needed
        # in order to download extra libraries as part of the installation process.
        "wget>=3.2",
    ],
    extras_require={
        "docs": ["sphinx>=1.5", "guzzle-sphinx-theme"],  # For doc generation
        "dev": [
            "flake8>=3",  # For code style checking
            "black",  # For code style auto-formatting
            "jupyter",  # For documentation and testing
        ],
    },
)
