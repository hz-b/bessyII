import sys
from os import path

from setuptools import find_packages, setup

import versioneer

setup(name='bessyii_devices',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      description='A collection of ophyd devices that can be used with IOCs at BESSY II',
      url='https://gitlab.helmholtz-berlin.de/sissy/experiment-control/beamlineOphydDevices',
      author='Will Smith, Simone Vadilonga, Sebastian Kazarski',
      author_email='william.smith@helmholtz-berlin.de',
      # license='MIT',
      packages=find_packages(exclude=['docs', 'tests']),
      install_requires=[
          'ophyd',
          'numpy'
      ]
      # zip_safe=False
)