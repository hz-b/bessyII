import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, FixedLocator, FormatStrFormatter
import numpy as np
import warnings

from lmfit.models import LinearModel, SkewedVoigtModel, Model
from lmfit import Parameters

from numpy import (arctan, copysign, cos, exp, isclose, isnan, log, pi, real,
                   sin, sqrt, where)
from scipy.special import erf, erfc
from scipy.special import gamma as gamfcn
from scipy.special import wofz


from IPython import get_ipython

'''
from .base import *
from bessyii.plans.n2fit import fit_n2 as fit_n2_internal

def fit_n2(scan, motor='pgm', detector='Keithley01',print_fit_report=False, save_img=False, fit=True,
           vc1='auto', amp_sf=6,sigma = 0.02, sigma_min=0.001,sigma_max=0.02,gamma=0.055, fix_param=True):
    RP, vp_ratio=fit_n2_internal(scan, motor, detector,print_fit_report, save_img, fit,
           vc1, amp_sf,sigma, sigma_min,sigma_max,gamma,db=db, fix_param=fix_param)
    return RP, vp_ratio
'''

#search database
def retrieve_spectra(identifier, motor=None, detector=None,db=None):
    if identifier == 'Jens':
        dat       = np.loadtxt('PETRA_III_P04_N21sF0020_tot_i_deglitched.dat')
        energy    = dat[:, 0]
        intensity = dat[:, 1]
    else:
        run       = db[identifier]
        if detector == None:
            detector  = run.metadata['start']['detectors'][0]
        if motor == None:
            motor = run.metadata['start']['motors'][0]
        spectra   = run.primary.read()
        energy    = np.array(spectra[motor])
        intensity = np.array(spectra[detector])
        
        energy,intensity = remove_neg_values(energy,intensity)
    return energy, intensity

def remove_neg_values(x,y):
    ind = np.where(y < 0)
    x = np.delete(x,ind[0])
    y = np.delete(y,ind[0])
    return x,y

def config_SkewedVoigtModel(model_name, prefix_, value_center, value_center_min, value_center_max, value_sigma, value_sigma_min, value_sigma_max, value_amp, value_amp_min, value_gamma, value_gamma_min, value_skew, pars):

    locals()[model_name] = SkewedVoigtModel(prefix=prefix_)   
    return_model_name = locals()[model_name]
    
    pars.update(getattr(return_model_name,'make_params')())
    
    pars[''.join((prefix_, 'center'))].set(     value=value_center, min=value_center_min, max=value_center_max                    )
    pars[''.join((prefix_, 'sigma'))].set(      value=value_sigma,  min=value_sigma_min,  max=value_sigma_max                     )
    pars[''.join((prefix_, 'amplitude'))].set(  value=value_amp,    min=value_amp_min                                             )
    pars[''.join((prefix_, 'gamma'))].set(      value=value_gamma,  min=value_gamma_min,                        vary=True, expr='')
    pars[''.join((prefix_, 'skew'))].set(       value=value_skew                                                                  )
    return return_model_name
    
    
def RMS(data_):
    sum_data = 0
    for i in data_:
        sum_data = sum_data + i**2          
    rms = np.sqrt((1/len(data_))*sum_data)
    return rms

def find_nearest_idx(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return idx

def guess_amp(x,y,vc):
    idx = find_nearest_idx(x,vc)
    amp = y[idx]
    return amp

def find_first_max(x,y,fwhm):
    vc1_ind = np.argmax(y)
    vc1     = x[vc1_ind]
    step    = x[1]-x[0]
    ind     = int(fwhm/step/1) # /4 required because above  multiply FWHM *2, and we need only half FWHM
    #print('vc1,vc1_ind,step, ind', vc1,vc1_ind,step, ind)
    vcl     = y[int(vc1_ind-ind)]
    #print('vcl',vcl)
    while vcl >= 0.7:
        #print ('vcl too high, I recalculate')
        vc1_ind = np.argmax(y[0:vc1_ind])
        vc1     = x[vc1_ind]
        vcl     = y[int(vc1_ind-ind)]
        #print('newind',vc1_ind)
        #print('vcl',vcl)
    return vc1

def extract_RP_fwhm_g(params_dict, fix_param=False):
    if fix_param == False:
        sigma_v2      = params_dict['v2_sigma'].value
        sigma_v2_err  = params_dict['v2_sigma'].stderr
        center_v1     = params_dict['v1_center'].value
    if fix_param == True:
        sigma_v2      = params_dict['sigma']
        sigma_v2_err  = 0
        center_v1     = params_dict['c1']
        
    return sigma_v2, sigma_v2_err,center_v1
    
    
def extract_RP_ratio(x,y,params_dict, fix_param=False):
    '''
    this function calculates the RP following the work
    of Chen and Sette: https://doi.org/10.1063/1.1141044
    '''
    if fix_param == False:
        cen_v1   = params_dict['v1_center'].value
        cen_v2   = params_dict['v2_center'].value
        cen_v3   = params_dict['v3_center'].value 

        ind_cen_v1 = find_nearest_idx(x, cen_v1)
        ind_cen_v2 = find_nearest_idx(x, cen_v2)
        ind_cen_v3 = find_nearest_idx(x, cen_v3)
        cen_valley = x[np.argmin(y[ind_cen_v1:ind_cen_v2])]
        bg_v3      = params_dict['lin_slope']*cen_v3+params_dict['lin_intercept']
        bg_valley  = params_dict['lin_slope']*cen_valley+params_dict['lin_intercept']
        amp_v3     = y[ind_cen_v3]-bg_v3
        amp_valley = np.min(y[ind_cen_v1:ind_cen_v2])-bg_valley
        warnings.filterwarnings('ignore', 'invalid value encountered in sqrt')
    if fix_param == True:
        cen_v1   = params_dict['c1']
        cen_v2   = params_dict['c2']
        cen_v3   = params_dict['c3'] 

        ind_cen_v1 = find_nearest_idx(x, cen_v1)
        ind_cen_v2 = find_nearest_idx(x, cen_v2)
        ind_cen_v3 = find_nearest_idx(x, cen_v3)
        cen_valley = x[np.argmin(y[ind_cen_v1:ind_cen_v2])]
        #bg_v3      = params_dict['lin_slope']*cen_v3+params_dict['lin_intercept']
        #bg_valley  = params_dict['lin_slope']*cen_valley+params_dict['lin_intercept']
        amp_v3     = y[ind_cen_v3]#-bg_v3
        amp_valley = np.min(y[ind_cen_v1:ind_cen_v2])#-bg_valley
        warnings.filterwarnings('ignore', 'invalid value encountered in sqrt')
    vp_ratio = amp_v3/amp_valley
    return vp_ratio


##########################
# functions specific to fix params fit_data

# tiny had been numpy.finfo(numpy.float64).eps ~=2.2e16.
# here, we explicitly set it to 1.e-15 == numpy.finfo(numpy.float64).resolution
tiny = 1.0e-15
s2   = sqrt(2)
s2pi = sqrt(2*pi)
def voigt(x, amplitude=1.0, center=0.0, sigma=1.0, gamma=None):
    """Return a 1-dimensional Voigt function.
    voigt(x, amplitude, center, sigma, gamma) =
        amplitude*wofz(z).real / (sigma*s2pi)
    For more information, see: https://en.wikipedia.org/wiki/Voigt_profile
    """
    if gamma is None:
        gamma = sigma
    z = (x-center + 1j*gamma) / max(tiny, (sigma*s2))
    return amplitude*wofz(z).real / max(tiny, (sigma*s2pi))

def skewed_voigt(x, amplitude=1.0, center=0.0, sigma=1.0, gamma=None, skew=0.0):
    """Return a Voigt lineshape, skewed with error function.
    Equal to: voigt(x, center, sigma, gamma)*(1+erf(beta*(x-center)))
    where ``beta = skew/(sigma*sqrt(2))``
    with ``skew < 0``: tail to low value of centroid
         ``skew > 0``: tail to high value of centroid
    Useful, for example, for ad-hoc Compton scatter profile. For more
    information, see: https://en.wikipedia.org/wiki/Skew_normal_distribution
    """
    beta = skew/max(tiny, (s2*sigma))
    asym = 1 + erf(beta*(x-center))
    return asym * voigt(x, amplitude, center, sigma, gamma=gamma)

def ten_svoigt(x, a1,a2,a3,a4,a5,a6,a7, c1,c2,c3,c4,c5,c6,c7, sigma,gamma,skew):
    tw = skewed_voigt(x,amplitude=a1,  center=c1,  sigma=sigma,  gamma=gamma,  skew=skew) +\
         skewed_voigt(x,amplitude=a2,  center=c2,  sigma=sigma,  gamma=gamma,  skew=skew)+\
         skewed_voigt(x,amplitude=a3,  center=c3,  sigma=sigma,  gamma=gamma,  skew=skew)+\
         skewed_voigt(x,amplitude=a4,  center=c4,  sigma=sigma,  gamma=gamma,  skew=skew)+\
         skewed_voigt(x,amplitude=a5,  center=c5,  sigma=sigma,  gamma=gamma,  skew=skew)+\
         skewed_voigt(x,amplitude=a6,  center=c6,  sigma=sigma,  gamma=gamma,  skew=skew)+\
         skewed_voigt(x,amplitude=a7,  center=c7,  sigma=sigma,  gamma=gamma,  skew=skew)
         #skewed_voigt(x,amplitude=a8,  center=c8,  sigma=sigma,  gamma=gamma,  skew=skew)+\
         #skewed_voigt(x,amplitude=a9,  center=c9,  sigma=sigma,  gamma=gamma,  skew=skew)+\
         #skewed_voigt(x,amplitude=a10, center=c10, sigma=sigma,  gamma=gamma,  skew=skew)
    return tw

# internal fit routine
def _fit_n2(x,y, print_fit_results=False, save_img=False,fit_data=True, 
            vc1='auto', amp_sf=6,sigma = 0.02, sigma_min=0.001,sigma_max=0.02,gamma=0.055, fix_param=False):
    # normalize intensity
    norm = np.max(y)
    y = y/norm

    centers       = np.array([400.58,400.805,401.02,401.22,401.46,401.68,401.87,402.05,402.24])
    diff_centers  = np.abs(400.345-centers)
    #print('diff_centers',diff_centers)

    #amp_sf    = 6 #scaling value for amplitude
    amp_min   = 0
    amp_mf    = 1.1 #scaling value for minimal amplitude
    #gamma     = 0.055
    gamma_min = 0
    #sigma     = 0.02
    #sigma_min = 0.001
    #sigma_max = 0.02
    fwhm      = 2.355*sigma*2
    lin_slope = 0.0000001
    #vc1 = 'auto'
    if vc1 == 'auto':
        vc1 = find_first_max(x,y, fwhm)
   
    if fix_param == False:
        guess = {'vc1': vc1,                  'amp1':np.max(y)/amp_sf,
                'vc2': vc1+diff_centers[0],  'amp2':guess_amp(x,y,vc1+diff_centers[0])/amp_sf,
                'vc3': vc1+diff_centers[1],  'amp3':guess_amp(x,y,vc1+diff_centers[1])/amp_sf,
                'vc4': vc1+diff_centers[2],  'amp4':guess_amp(x,y,vc1+diff_centers[2])/amp_sf,
                'vc5': vc1+diff_centers[3],  'amp5':guess_amp(x,y,vc1+diff_centers[3])/amp_sf,
                'vc6': vc1+diff_centers[4],  'amp6':guess_amp(x,y,vc1+diff_centers[4])/amp_sf,
                'vc7': vc1+diff_centers[5],  'amp7':guess_amp(x,y,vc1+diff_centers[5])/amp_sf,
                'vc8': vc1+diff_centers[6],  'amp8':guess_amp(x,y,vc1+diff_centers[6])/amp_sf,
                'vc9': vc1+diff_centers[7],  'amp9':guess_amp(x,y,vc1+diff_centers[7])/amp_sf,
                'vc10':vc1+diff_centers[8],  'amp10':guess_amp(x,y,vc1+diff_centers[8])/amp_sf,
                }
        #for key in guess.keys():
        #    print (key, guess[key])
        #                    'prefix_', value_center,    center_min,         center_max,         sigma,  sigma_min,  sigma_max,  amp,           amp_min, gamma, skew]
        dict_fit = {'voigt1': ['v1_',   guess['vc1'],    guess['vc1']-fwhm,  guess['vc1']+fwhm,  sigma,  sigma_min,  sigma_max,  guess['amp1'],  guess['amp1']/amp_mf,   gamma, gamma_min, 0.0],
                    'voigt2': ['v2_',   guess['vc2'],    guess['vc2']-fwhm,  guess['vc2']+fwhm,  sigma,  sigma_min,  sigma_max,  guess['amp2'],  guess['amp2']/amp_mf,   gamma, gamma_min, 0.0],
                    'voigt3': ['v3_',   guess['vc3'],    guess['vc3']-fwhm,  guess['vc3']+fwhm,  sigma,  sigma_min,  sigma_max,  guess['amp3'],  guess['amp3']/amp_mf,   gamma, gamma_min, 0.0],
                    'voigt4': ['v4_',   guess['vc4'],    guess['vc4']-fwhm,  guess['vc4']+fwhm,  sigma,  sigma_min,  sigma_max,  guess['amp4'],  guess['amp4']/amp_mf,   gamma, gamma_min, 0.0],
                    'voigt5': ['v5_',   guess['vc5'],    guess['vc5']-fwhm,  guess['vc5']+fwhm,  sigma,  sigma_min,  sigma_max,  guess['amp5'],  guess['amp5']/amp_mf,   gamma, gamma_min, 0.0],
                    'voigt6': ['v6_',   guess['vc6'],    guess['vc6']-fwhm,  guess['vc6']+fwhm,  sigma,  sigma_min,  sigma_max,  guess['amp6'],  guess['amp6']/amp_mf,   gamma, gamma_min, 0.0],
                    'voigt7': ['v7_',   guess['vc7'],    guess['vc7']-fwhm,  guess['vc7']+fwhm,  sigma,  sigma_min,  sigma_max,  guess['amp7'],  guess['amp7']/amp_mf,   gamma, gamma_min, 0.0],
                    'voigt8': ['v8_',   guess['vc8'],    guess['vc8']-fwhm,  guess['vc8']+fwhm,  sigma,  sigma_min,  sigma_max,  guess['amp8'],  guess['amp8']/amp_mf,   gamma, gamma_min, 0.0],
                    'voigt9': ['v9_',   guess['vc9'],    guess['vc9']-fwhm,  guess['vc9']+fwhm,  sigma,  sigma_min,  sigma_max,  guess['amp9'],  guess['amp9']/amp_mf,   gamma, gamma_min, 0.0],
                    'voigt10': ['v10_', guess['vc10'],   guess['vc10']-fwhm, guess['vc10']+fwhm, sigma,  sigma_min,  sigma_max,  guess['amp10'], guess['amp10']/amp_mf,   gamma, gamma_min, 0.0]
                }

        #for key in dict_fit.keys():
        #    print (key, dict_fit[key])
        pars = Parameters()


        ################################################################################
        ################################################################################
        # lin fit
        lin_mod = LinearModel(prefix='lin_')
        pars.update(lin_mod.make_params())
        #
        pars['lin_slope'].set(value=lin_slope)
        pars['lin_intercept'].set(value=np.average(y[-10:]))
        mod = lin_mod
                
        for key in list(dict_fit.keys()):
            model_name       = key
            prefix_          = dict_fit[key][0]
            value_center     = dict_fit[key][1]
            value_center_min = dict_fit[key][2]
            value_center_max = dict_fit[key][3]
            value_sigma      = dict_fit[key][4]
            value_sigma_min  = dict_fit[key][5] 
            value_sigma_max  = dict_fit[key][6]
            value_amp        = dict_fit[key][7]
            value_amp_min    = dict_fit[key][8]
            value_gamma      = dict_fit[key][9]
            value_gamma_min  = dict_fit[key][10]
            value_skew       = dict_fit[key][11]

            fit = config_SkewedVoigtModel(model_name, prefix_, 
                                        value_center, value_center_min, value_center_max, 
                                        value_sigma, value_sigma_min, value_sigma_max, 
                                        value_amp, value_amp_min, 
                                        value_gamma, value_gamma_min, 
                                        value_skew, 
                                        pars)
            if key == 'voigt1':
                mod = fit
            else:
                mod = mod + fit


        mod = mod + lin_mod   
    
    elif fix_param == True:
        print('Using fixed parameters fit')
        guess = {'vc1': vc1,                  'amp1':np.max(y)/amp_sf,
         'vc2': vc1+diff_centers[0],  'amp2':guess_amp(x,y,vc1+diff_centers[0])/amp_sf,
         'vc3': vc1+diff_centers[1],  'amp3':guess_amp(x,y,vc1+diff_centers[1])/amp_sf,
         'vc4': vc1+diff_centers[2],  'amp4':guess_amp(x,y,vc1+diff_centers[2])/amp_sf,
         'vc5': vc1+diff_centers[3],  'amp5':guess_amp(x,y,vc1+diff_centers[3])/amp_sf,
         'vc6': vc1+diff_centers[4],  'amp6':guess_amp(x,y,vc1+diff_centers[4])/amp_sf,
         'vc7': vc1+diff_centers[5],  'amp7':guess_amp(x,y,vc1+diff_centers[5])/amp_sf,
         'vc8': vc1+diff_centers[6],  'amp8':guess_amp(x,y,vc1+diff_centers[6])/amp_sf,
         'vc9': vc1+diff_centers[7],  'amp9':guess_amp(x,y,vc1+diff_centers[7])/amp_sf,
         'vc10':vc1+diff_centers[8],  'amp10':guess_amp(x,y,vc1+diff_centers[8])/amp_sf,
        }
        mod = Model(ten_svoigt)
       # pars = mod.make_params(a1=guess['amp1'],a2=guess['amp2'],a3=guess['amp3'],a4=guess['amp4'],a5=guess['amp5'],
       #                 a6=guess['amp6'],a7=guess['amp7'],a8=guess['amp8'],a9=guess['amp9'],a10=guess['amp10'], 
       #                 c1=guess['vc1'],c2=guess['vc2'],c3=guess['vc3'],c4=guess['vc4'],c5=guess['vc5'],
       #                 c6=guess['vc6'],c7=guess['vc7'],c8=guess['vc8'],c9=guess['vc9'],c10=guess['vc10'], 
       #                 sigma=0.02,gamma=0.055,skew=0)
        pars = mod.make_params(a1=guess['amp1'],a2=guess['amp2'],a3=guess['amp3'],a4=guess['amp4'],a5=guess['amp5'],
                        a6=guess['amp6'],a7=guess['amp7'], 
                        c1=guess['vc1'],c2=guess['vc2'],c3=guess['vc3'],c4=guess['vc4'],c5=guess['vc5'],
                        c6=guess['vc6'],c7=guess['vc7'], 
                        sigma=0.02,gamma=0.055,skew=0)
    
    #################################################################################
    ################################################################################
    # 
    init = mod.eval(pars, x=x)


    # here it plots the intial guesses if fit=False
    if fit_data == False:
        plt.rc("font", size=12,family='serif')
        fig, axes = plt.subplots(1, 1, figsize=(8.0, 16.0))
        axes.plot(x, init, 'orange' ,label='initial guess')
        axes.scatter(x, y, label='data')
        #axes.set_ylim(-.05,1.1)
        return None,None,None,None,None
    
    
    #from timer import Timer 
    #t1 = Timer()

    #t1.start()
    out = mod.fit(y, pars, x=x)
    #t1.stop()
    if print_fit_results == True:
        print(out.fit_report(min_correl=0.5))
    
    ####
    # axes 0
    plt.rc("font", size=12,family='serif')
    fig, axes = plt.subplots(3, 1, figsize=(8.0, 16.0))
    #
    # initial fit
    axes[0].plot(x, out.init_fit, 'orange' ,label='data1')
    #
    axes[0].scatter(x, y, label='data')
    #axes[0].plot(x, init, '--', label='initial fit')
    axes[0].plot(x, out.best_fit, 'r', label='best fit')

    axes[0].legend()
    axes[0].set_xlabel('Photon energy (eV)')
    axes[0].set_ylabel('Ion counts (arb. units)')

    #axes[0].set_xlim(399.8,402.5)
    #axes[0].set_ylim(0,990000)
    axes[0].tick_params(axis='both',direction='in',length=6,top=True,right=True)

    # set tick spacing
    XminorLocator = MultipleLocator(0.1)
    YminorLocator = MultipleLocator(100000)
    axes[0].xaxis.set_minor_locator(XminorLocator)
    axes[0].yaxis.set_minor_locator(YminorLocator)
    axes[0].tick_params(which='minor',axis='both',direction='in',length=3,top=True,right=True)
    #
    
    #
    ################################################################################
    # axes 1

    axes[1].plot(x, y)

    counter = 0

    if fix_param == False:
        comps = out.eval_components(x=x)
        for i in dict_fit.values():
            counter += 1
            axes[1].plot(x, comps[i[0]], '--', label='Voigt component ' + str(counter))
        axes[1].plot(x, comps['lin_'], '--', label='Linear component')
    elif fix_param == True:
        comps = out.values
        for i in range(1,8):
            ind=str(i)
            counter += 1
            axes[1].plot(x,skewed_voigt(x, amplitude=comps['a'+ind], center=comps['c'+ind], sigma=comps['sigma'], gamma=comps['gamma'], skew=comps['skew']), '--', label='Voigt component ' + str(counter))

    

    axes[1].legend()
    axes[1].set_xlabel('Photon energy (eV)')
    axes[1].set_ylabel('Ion counts (arb. units)')
    #axes[1].set_xlim(399.8,402.5)
    #axes[1].set_ylim(0,990000)
    axes[1].tick_params(axis='both',direction='in',length=6,top=True,right=True)

    XminorLocator = MultipleLocator(0.1)
    YminorLocator = MultipleLocator(100000)
    axes[1].xaxis.set_minor_locator(XminorLocator)
    axes[1].yaxis.set_minor_locator(YminorLocator)
    axes[1].tick_params(which='minor',axis='both',direction='in',length=3,top=True,right=True)
    #
    ########################################################################
    # axes 2
    residuals_inital = y - out.init_fit
    residuals_final = y - out.best_fit
    #
    axes[2].plot(x, residuals_final, label='data-best fit')
    #axes[2].plot(x, np.sqrt(y)*3.0, label='sqrt(y)*3')
    #axes[2].plot(x, np.sqrt(y)*-3.0, label='sqrt(y)*-3')
    axes[2].fill_between(x,np.sqrt(y)*-3.0,np.sqrt(y)*3.0,color='gray',alpha=0.4, label='sqrt(data)*\u00b13')

    axes[2].legend()
    axes[2].set_xlabel('Photon energy (eV)')
    axes[2].set_ylabel('Residual counts (arb. units)')
    #axes[2].set_xlim(399.8,402.5)
    #axes[2].set_ylim(-20000,20000)
    axes[2].tick_params(axis='both',direction='in',length=6,top=True,right=True)

    XminorLocator = MultipleLocator(0.1)
    YminorLocator = MultipleLocator(1000)
    axes[2].xaxis.set_minor_locator(XminorLocator)
    axes[2].yaxis.set_minor_locator(YminorLocator)
    axes[2].tick_params(which='minor',axis='both',direction='in',length=3,top=True,right=True)
    # 
    xmin_ax2, xmax_ax2 = axes[2].axes.get_xlim()
    ymin_ax2, ymax_ax2 = axes[2].axes.get_ylim()

    axes[2].text(((xmax_ax2-xmin_ax2)*0.55)+xmin_ax2, ((ymax_ax2-ymin_ax2)*0.2)+ymin_ax2, f'RMS initial = {str(np.round(RMS(residuals_inital),3))}') #, style = 'italic',fontsize = 30,  color = "green")
    axes[2].text(((xmax_ax2-xmin_ax2)*0.55)+xmin_ax2, ((ymax_ax2-ymin_ax2)*0.15)+ymin_ax2, f'RMS final   = {str(np.round(RMS(residuals_final),3))}')

    plt.subplots_adjust(left=0.14, bottom=None, right=None, top=None, wspace=0.04, hspace=0.14)
    if save_img != False:
        plt.savefig(save_img+'.pdf')
    plt.show()
    #extracting values to calculate RP
    
    if fix_param == False:    
        sigma_v2, sigma_v2_err,center_v1 = extract_RP_fwhm_g(out.params,fix_param=fix_param)
        vp_ratio = extract_RP_ratio(x, out.best_fit,out.params,fix_param=fix_param)
    elif fix_param == True:    
        sigma_v2, sigma_v2_err,center_v1 = extract_RP_fwhm_g(out.values,fix_param=fix_param)
        vp_ratio = extract_RP_ratio(x, out.best_fit,out.params,fix_param=fix_param)    
    
    return sigma_v2, center_v1,sigma_v2_err, vp_ratio
    
def fit_n2(scan, motor='pgm', detector='Keithley01',print_fit_report=False, save_img=False, fit=True,
           vc1='auto', amp_sf=6,sigma = 0.02, sigma_min=0.001,sigma_max=0.02,gamma=0.0563, db=None, fix_param = False):
    energy, intensity                  = retrieve_spectra(scan,db=db)
    sigma, center, sigma_err,vp_ratio  =_fit_n2(energy, intensity, print_fit_results=print_fit_report, save_img=save_img,fit_data=fit,
                                                vc1=vc1,amp_sf=amp_sf,sigma=sigma,sigma_min=sigma_min,sigma_max=sigma_max,gamma=gamma,
                                                fix_param=fix_param)
    if fit == False:
        return
    fwhm_g         = 2*sigma*np.sqrt(2*np.log(2))
    fwhm_l         = 2*gamma
    RP             = center/ fwhm_g
    pi_print       = u'\U0001D6D1'
    print('The Resolving Power (RP) is obtained by calculating the')
    print('gaussian contribution to the FWHM of the N2:1s-->'+pi_print+'* transition.')
    print('Estimation of the gaussian FWHM from fit parameters, assuming a fixed Lorentizian FWHM:')
    print('FWHM_g', np.round(fwhm_g*1000,2), ' meV')
    print('FWHM_l', np.round(fwhm_l*1000,2), ' meV')
    print('The estimated RP is:', np.round(RP,0),'\n')
    print('The first peak is at ', np.round(center,2), ' eV', 'the literature values is 400.8 meV')
    print('The energy shift is ', np.round(center-400.8,2) , ' eV\n')
    
    print('Estimation of the 3rd-peak to 1st-valley ratio:')
    if np.isnan(vp_ratio):
        print('Not Possible')
    else:
        print('The valley/peak ratio is', np.round(vp_ratio,2))

    return RP, vp_ratio
