'''
    Bessy augmentation of Best Effort Callback.
    
    in base.py:
    #from bluesky.callbacks.best_effort import BestEffortCallback
    from bessyii.bec.bec_bessy import BestEffortCallbackBessy
    bec = BestEffortCallbackBessy()

    in tools.py:
    #imports from bessyii
    from .base import *
    # bec standard detectors
    from .beamline import *
    bec.define_standard_detectors(['noisy_det','det1', 'det2'])
    st_det = [noisy_det,det1, det2]
'''
from cycler import cycler
from datetime import datetime
from io import StringIO
import itertools
import numpy as np
import matplotlib.pyplot as plt
from pprint import pformat
import re
import sys
import threading
import time
from warnings import warn
import weakref

from bluesky.callbacks.core import LiveTable, make_class_safe
from bluesky.callbacks.fitting import PeakStats
from bluesky.callbacks.mpl_plotting import LivePlot, LiveGrid, LiveScatter, QtAwareCallback
from bluesky.callbacks.best_effort import BestEffortCallback,LivePlotPlusPeaks
import logging

logger = logging.getLogger(__name__)


@make_class_safe(logger=logger)
class BestEffortCallbackBessy(BestEffortCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.standard_detectors = None
    
    def define_standard_detectors(self, standard_detectors):
        "Define standard detectors as a list of strings"
        self.standard_detectors=standard_detectors
    
    def descriptor(self, doc):
        ''' This method is modified to avoid plotting a detector in the
            standard detector list unless is defined by the user
        '''
        self._descriptors[doc['uid']] = doc
        stream_name = doc.get('name', 'primary')  # fall back for old docs

        if stream_name not in self._stream_names_seen:
            self._stream_names_seen.add(stream_name)
            if self._table_enabled:
                print("New stream: {!r}".format(stream_name))
        
        # this line is if we decide to not redefine plans as classes
        if self.standard_detectors != None and len(self._start_doc['detectors'])>len(self.standard_detectors):
        
        # this line is if we decide to redefine plans as classes
        #if self.standard_detectors != None:
            # Simo
            # here we make a list of detectors that should not be plotted
            # the detectors to not be plot are the ones defined in 
            # self.standard_detectors
            detectors_to_not_plot = self.standard_detectors
            
            # here we check if in the detector list passed to the scan
            # there are duplicates. If there are duplicates it's beacuse
            # they appear once in the user defined detectors, and once in the
            # standard detectors, so we remove them from the list of detectors to not be plot
            
            seen = set()
            dupes = [] # here we store the duplicates detectors
        
            for x in self._start_doc['detectors']:
                if x in seen:
                    dupes.append(x)
                else:
                    seen.add(x)
            # here we remove the duplicates detectors from the list of detectors to not be plot
            detectors_to_not_plot = [x for x in self.standard_detectors if x not in dupes]
            #print('detectors_to_not_plot', detectors_to_not_plot)
        else:
            detectors_to_not_plot = None
        
        columns = hinted_fields(doc, st_det=detectors_to_not_plot)

        # ## This deals with old documents. ## #

        if stream_name == 'primary' and self._cleanup_motor_heuristic:
            # We stashed object names in self.dim_fields, which we now need to
            # look up the actual fields for.
            self._cleanup_motor_heuristic = False
            fixed_dim_fields = []
            for obj_name in self.dim_fields:
                # Special case: 'time' can be a dim_field, but it's not an
                # object name. Just add it directly to the list of fields.
                if obj_name == 'time':
                    fixed_dim_fields.append('time')
                    continue
                try:
                    fields = doc.get('hints', {}).get(obj_name, {})['fields']
                except KeyError:
                    fields = doc['object_keys'][obj_name]
                fixed_dim_fields.extend(fields)
            self.dim_fields = fixed_dim_fields

        # Ensure that no independent variables ('dimensions') are
        # duplicated here.
        columns = [c for c in columns if c not in self.all_dim_fields]

        # ## DECIDE WHICH KIND OF PLOT CAN BE USED ## #

        plot_data = True

        if not self._plots_enabled:
            plot_data = False
        if stream_name in self.noplot_streams:
            plot_data = False
        if not columns:
            plot_data = False
        if ((self._start_doc.get('num_points') == 1) and
                (stream_name == self.dim_stream) and
                self.omit_single_point_plot):
            plot_data = False

        if plot_data:

            # This is a heuristic approach until we think of how to hint this in a
            # generalizable way.
            if stream_name == self.dim_stream:
                dim_fields = self.dim_fields
            else:
                dim_fields = ['time']  # 'time' once LivePlot can do that

            # Create a figure or reuse an existing one.

            fig_name = '{} vs {}'.format(' '.join(sorted(columns)),
                                         ' '.join(sorted(dim_fields)))
            if self.overplot and len(dim_fields) == 1:
                # If any open figure matches 'figname {number}', use it. If there
                # are multiple, the most recently touched one will be used.
                pat1 = re.compile('^' + fig_name + '$')
                pat2 = re.compile('^' + fig_name + r' \d+$')
                for label in plt.get_figlabels():
                    if pat1.match(label) or pat2.match(label):
                        fig_name = label
                        break
            else:
                if plt.fignum_exists(fig_name):
                    # Generate a unique name by appending a number.
                    for number in itertools.count(2):
                        new_name = '{} {}'.format(fig_name, number)
                        if not plt.fignum_exists(new_name):
                            fig_name = new_name
                            break
            ndims = len(dim_fields)
            if not 0 < ndims < 3:
                # we need 1 or 2 dims to do anything, do not make empty figures
                return

            if self._fig_factory:
                fig = self._fig_factory(fig_name)
            else:
                fig = plt.figure(fig_name)

            if not fig.axes:
                if len(columns) < 5:
                    layout = (len(columns), 1)
                else:
                    nrows = ncols = int(np.ceil(np.sqrt(len(columns))))
                    while (nrows - 1) * ncols > len(columns):
                        nrows -= 1
                    layout = (nrows, ncols)
                if ndims == 1:
                    share_kwargs = {'sharex': True}
                elif ndims == 2:
                    share_kwargs = {'sharex': True, 'sharey': True}
                else:
                    raise NotImplementedError("we now support 3D?!")

                fig_size = np.array(layout[::-1]) * 5
                fig.set_size_inches(*fig_size)
                fig.subplots(*map(int, layout), **share_kwargs)
                for ax in fig.axes[len(columns):]:
                    ax.set_visible(False)

            axes = fig.axes

            # ## LIVE PLOT AND PEAK ANALYSIS ## #

            if ndims == 1:
                self._live_plots[doc['uid']] = {}
                self._peak_stats[doc['uid']] = {}
                x_key, = dim_fields
                for y_key, ax in zip(columns, axes):
                    dtype = doc['data_keys'][y_key]['dtype']
                    if dtype not in ('number', 'integer'):
                        warn("Omitting {} from plot because dtype is {}"
                             "".format(y_key, dtype))
                        continue
                    # Create an instance of LivePlot and an instance of PeakStats.
                    live_plot = LivePlotPlusPeaks(y=y_key, x=x_key, ax=ax,
                                                  peak_results=self.peaks)
                    live_plot('start', self._start_doc)
                    live_plot('descriptor', doc)
                    peak_stats = PeakStats(
                        x=x_key, y=y_key,
                        calc_derivative_and_stats=self._calc_derivative_and_stats
                    )
                    peak_stats('start', self._start_doc)
                    peak_stats('descriptor', doc)

                    # Stash them in state.
                    self._live_plots[doc['uid']][y_key] = live_plot
                    self._peak_stats[doc['uid']][y_key] = peak_stats

                for ax in axes[:-1]:
                    ax.set_xlabel('')
            elif ndims == 2:
                # Decide whether to use LiveGrid or LiveScatter. LiveScatter is the
                # safer one to use, so it is the fallback..
                gridding = self._start_doc.get('hints', {}).get('gridding')
                if gridding == 'rectilinear':
                    self._live_grids[doc['uid']] = {}
                    slow, fast = dim_fields
                    try:
                        extents = self._start_doc['extents']
                        shape = self._start_doc['shape']
                    except KeyError:
                        warn("Need both 'shape' and 'extents' in plan metadata to "
                             "create LiveGrid.")
                    else:
                        data_range = np.array([float(np.diff(e)) for e in extents])
                        y_step, x_step = data_range / [max(1, s - 1) for s in shape]
                        adjusted_extent = [extents[1][0] - x_step / 2,
                                           extents[1][1] + x_step / 2,
                                           extents[0][0] - y_step / 2,
                                           extents[0][1] + y_step / 2]
                        for I_key, ax in zip(columns, axes):
                            # MAGIC NUMBERS based on what tacaswell thinks looks OK
                            data_aspect_ratio = np.abs(data_range[1]/data_range[0])
                            MAR = 2
                            if (1/MAR < data_aspect_ratio < MAR):
                                aspect = 'equal'
                                ax.set_aspect(aspect, adjustable='box')
                            else:
                                aspect = 'auto'
                                ax.set_aspect(aspect, adjustable='datalim')

                            live_grid = LiveGrid(shape, I_key,
                                                 xlabel=fast, ylabel=slow,
                                                 extent=adjusted_extent,
                                                 aspect=aspect,
                                                 ax=ax)

                            live_grid('start', self._start_doc)
                            live_grid('descriptor', doc)
                            self._live_grids[doc['uid']][I_key] = live_grid
                else:
                    self._live_scatters[doc['uid']] = {}
                    x_key, y_key = dim_fields
                    for I_key, ax in zip(columns, axes):
                        try:
                            extents = self._start_doc['extents']
                        except KeyError:
                            xlim = ylim = None
                        else:
                            xlim, ylim = extents
                        live_scatter = LiveScatter(x_key, y_key, I_key,
                                                   xlim=xlim, ylim=ylim,
                                                   # Let clim autoscale.
                                                   ax=ax)
                        live_scatter('start', self._start_doc)
                        live_scatter('descriptor', doc)
                        self._live_scatters[doc['uid']][I_key] = live_scatter

            else:
                raise NotImplementedError("we do not support 3D+ in BEC yet "
                                          "(and it should have bailed above)")
            try:
                fig.tight_layout()
            except ValueError:
                pass

        # ## TABLE ## #

        if stream_name == self.dim_stream:
            if self._table_enabled:
                # plot everything, independent or dependent variables
                self._table = LiveTable(list(self.all_dim_fields) + columns, separator_lines=False)
                self._table('start', self._start_doc)
                self._table('descriptor', doc)



def hinted_fields(descriptor, st_det=None):
    'Simo'
    # Figure out which columns to put in the table.
    #print("descriptor['object_keys']", descriptor['object_keys'])
    obj_names = list(descriptor['object_keys'])
    #print('obj_names',obj_names)
    #print('st_det',st_det)
    if st_det != None:
        obj_names = [x for x in obj_names if x not in st_det]
    #print('new obj_names',obj_names)
            
    # We will see if these objects hint at whether
    # a subset of their data keys ('fields') are interesting. If they
    # did, we'll use those. If these didn't, we know that the RunEngine
    # *always* records their complete list of fields, so we can use
    # them all unselectively.
    columns = []
    for obj_name in obj_names:
        try:
            fields = descriptor.get('hints', {}).get(obj_name, {})['fields']
        except KeyError:
            fields = descriptor['object_keys'][obj_name]
        columns.extend(fields)
    return columns
