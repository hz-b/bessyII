import sys
from os import path

from setuptools import find_packages, setup

import versioneer

setup(name='bessyii',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      description='A collection of tools and scripts useful for data collection and analsis at BESSY II',
      url='https://gitlab.helmholtz-berlin.de/sissy/experiment-control/bessyii',
      author='Will Smith, Simone Vadilonga, Sebastian Kazarski',
      author_email='william.smith@helmholtz-berlin.de',
      # license='MIT',
      packages=find_packages(exclude=['docs', 'tests']),
      install_requires=[
          'ophyd==1.6.1',
          'bluesky==1.7.0',
          'msgpack',
          'event_model',
          'numpy'
      ]
      # zip_safe=False
)
