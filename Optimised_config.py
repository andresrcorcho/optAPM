import glob
import os.path
import warnings


#########################################
# Optimisation configuration parameters #
#########################################


##########################################################################################
# Supported parallelisation methods (or None to disable parallelisation, eg, for testing).
#
MPI4PY = 0
IPYPARALLEL = 1

# Choose parallelisation method (or None to disable parallelisation, eg, for testing).
use_parallel = MPI4PY  # For example, to use with 'mpiexec -n <cores> python Optimised_APM.py'.
#use_parallel = None
##########################################################################################
# The root input data directory ('data/').
# This is the 'data/' sub-directory of the directory containing this source file.
datadir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', '')


# The data model to run the optimisation on.
# This should be the name of the sub-directory in 'data/'.
data_model = 'Global_1000-0_Model_2017'
#data_model = 'Global_Model_WD_Internal_Release_2019_v2'


# The model name is suffixed to various output filenames.
if data_model.startswith('Global_Model_WD_Internal_Release'):
    model_name = "svn1618_run8"
elif data_model == 'Global_1000-0_Model_2017':
    model_name = "run13"
else:
    model_name = "run1"


if data_model == 'Global_1000-0_Model_2017':
    start_age = 1000
else:
    start_age = 410
# Note: You can set 'end_age' to a non-zero value if you are continuing an interrupted run.
#       In this case the workflow will attempt to re-use the existing partially optimised rotation file.
#       This can save a lot of time by skipping the optimisations already done by the interrupted optimisation run.
#       But be sure to set 'end_age' back to zero when finished.
#       Also this currently only works properly if 'interval' is the same for the interrupted and continued runs (as it should be).
end_age = 0
interval = 10

models = 100

# The original rotation files (relative to the 'data/' directory).
#
# Can either:
#   1) use glob to automatically find all the '.rot' files (you don't need to do anything), or
#   2) explicitly list all the rotation files (you need to list the filenames).
#
# 1) Automatically gather all '.rot' files (and make filenames relative to the 'data/' directory).
original_rotation_filenames = [os.path.relpath(abs_path, datadir) for abs_path in
        glob.glob(os.path.join(datadir, data_model, '*.rot'))]
# 2) Explicitly list all the input rotation files (must be relative to the 'data/' directory).
#original_rotation_filenames = [
#  'Global_Model_WD_Internal_Release_2019_v2/rotation_file1.rot',
#  'Global_Model_WD_Internal_Release_2019_v2/rotation_file2.rot',
#]

# The topology files (relative to the 'data/' directory).
#
# Can either:
#   1) use glob to automatically find all the '.gpml' files (you don't need to do anything), or
#   2) explicitly list all the topology files (you need to list the filenames).
#
# 1) Automatically gather all '.gpml' and '.gpmlz' files (and make filenames relative to the 'data/' directory).
#topology_filenames = [os.path.relpath(abs_path, datadir) for abs_path in
#        glob.glob(os.path.join(datadir, data_model, '*.gpml')) + glob.glob(os.path.join(datadir, data_model, '*.gpmlz'))]
# 2) Explicitly list all the topology files (must be relative to the 'data/' directory).
#topology_filenames = [
#  'Global_Model_WD_Internal_Release_2019_v2/topology_file1.gpml',
#  'Global_Model_WD_Internal_Release_2019_v2/topology_file2.gpml',
#]
if data_model == 'Global_1000-0_Model_2017':
    # Starting at SVN rev 1624 there are other GPML files that we don't need to include.
    topology_filenames = [
        'Global_1000-0_Model_2017/1000-410-Convergence_T12_APWP.gpml',
        'Global_1000-0_Model_2017/1000-410-Divergence_T12_APWP.gpml',
        'Global_1000-0_Model_2017/1000-410-Topologies_T12_APWP.gpml',
        'Global_1000-0_Model_2017/1000-410-Transforms_T12_APWP.gpml',
        'Global_1000-0_Model_2017/Global_Mesozoic-Cenozoic_plate_boundaries_Young_et_al_APWP.gpml',
        'Global_1000-0_Model_2017/Global_Paleozoic_plate_boundaries_Young_et_al_APWP.gpml',
        'Global_1000-0_Model_2017/TopologyBuildingBlocks_Young_et_al.gpml',
    ]
else:
    topology_filenames = [os.path.relpath(abs_path, datadir) for abs_path in
            glob.glob(os.path.join(datadir, data_model, '*.gpml')) + glob.glob(os.path.join(datadir, data_model, '*.gpmlz'))]

# The continental polygons file (relative to the 'data/' directory) used for plate velocity calculations (when plate velocity is enabled).
# NOTE: Set to None to use topologies instead (which includes continental and oceanic crust).
if data_model == 'Global_1000-0_Model_2017':
    plate_velocity_continental_polygons_file = 'Global_1000-0_Model_2017/New_polygons_static_changes.gpml'
else:
    plate_velocity_continental_polygons_file = None

# The grid spacing (in degrees) between points in the grid used for plate velocity calculations (when plate velocity is enabled).
plate_velocity_grid_spacing = 2.0

# Temporary: Allow input of GPlates exported net rotation file.
# TODO: Remove when we can calculate net rotation in pygplates for a deforming model.
#       Currently we can only calculate net rotation in pygplates for non-deforming models.
#
# Note: Set this to None for a non-deforming model.
if data_model.startswith('Global_Model_WD_Internal_Release'):
    gplates_net_rotation_filename = data_model + '/optimisation/total-net-rotations.csv'
else:
    gplates_net_rotation_filename = None

if data_model.startswith('Global_Model_WD_Internal_Release'):
    ridge_file = data_model + '/StaticGeometries/AgeGridInput/Global_EarthByte_GeeK07_Ridges_2019_v2.gpml'
    isochron_file = data_model + '/StaticGeometries/AgeGridInput/Global_EarthByte_GeeK07_Isochrons_2019_v2.gpml'
    isocob_file = data_model + '/StaticGeometries/AgeGridInput/Global_EarthByte_GeeK07_IsoCOB_2019_v2.gpml'
elif data_model == 'Global_1000-0_Model_2017':
    #
    # For (data_model == 'Global_1000-0_Model_2017') or (data_model == 'Muller++_2015_AREPS_CORRECTED') ...
    #
    ##################################################################################################################################
    #
    # There are no static geometries (besides coastlines) for this data model.
    #
    # NOTE: SO USING SAME FILES AS 'Global_Model_WD_Internal_Release_2019_v2'.
    #       THIS IS OK IF WE'RE NOT INCLUDING FRACTURE ZONES (BECAUSE THEN THESE FILES ARE NOT USED FOR FINAL OPTIMISED ROTATIONS).
    #
    ##################################################################################################################################
    ridge_file = 'Global_Model_WD_Internal_Release_2019_v2/StaticGeometries/AgeGridInput/Global_EarthByte_GeeK07_Ridges_2019_v2.gpml'
    isochron_file = 'Global_Model_WD_Internal_Release_2019_v2/StaticGeometries/AgeGridInput/Global_EarthByte_GeeK07_Isochrons_2019_v2.gpml'
    isocob_file = 'Global_Model_WD_Internal_Release_2019_v2/StaticGeometries/AgeGridInput/Global_EarthByte_GeeK07_IsoCOB_2019_v2.gpml'
else:
    #
    # Original files used in original optimisation script...
    #
    ridge_file = 'Global_EarthByte_230-0Ma_GK07_AREPS_Ridges.gpml'
    isochron_file = 'Global_EarthByte_230-0Ma_GK07_AREPS_Isochrons.gpmlz'
    isocob_file = 'Global_EarthByte_230-0Ma_GK07_AREPS_IsoCOB.gpml'


#
# Which components are enabled and their weightings and optional restricted bounds.
#
# Each return value is a 3-tuple:
#  1. Enable boolean (True or False),
#  2. Weight value (float),
#  3. Optional restricted bounds (2-tuple of min/max cost, or None).
#
# For restricted bounds, use None if you are not restricting.
# Otherwise use a (min, max) tuple.
#
# NOTE: The weights are inverse weights (ie, the constraint costs are *multiplied* by "1.0 / weight").
#
def get_fracture_zone_params(age):
    # Disable fracture zones.
    return False, 1.0, None

def get_net_rotation_params(age):
    # Note: Use units of degrees/Myr...
    #nr_bounds = (0.08, 0.20)
    
    if data_model.startswith('Global_Model_WD_Internal_Release'):
        if age <= 80:
            return True, 1.0, None
        elif age <= 170:
            # NOTE: These are inverse weights (ie, the constraint costs are *multiplied* by "1.0 / weight").
            return  True, 2.0, None  # 2.0 gives a *multiplicative* weight of 0.5
        else:
            # NOTE: These are inverse weights (ie, the constraint costs are *multiplied* by "1.0 / weight").
            return True, 5.0, None  # 5.0 gives a *multiplicative* weight of 0.2
    elif data_model == 'Global_1000-0_Model_2017':
        nr_bounds = (0.08, 0.20)
        return True, 1.0, nr_bounds
    else:
        return True, 1.0, None

def get_trench_migration_params(age):
    # Note: Use units of mm/yr (same as km/Myr)...
    #tm_bounds = [0, 30]
    
    if data_model.startswith('Global_Model_WD_Internal_Release'):
        return True, 1.0, None
    elif data_model == 'Global_1000-0_Model_2017':
        tm_bounds = [0, 30]
        return True, 1.0, tm_bounds
        #if age <= 80:
        #    return True, 1.0, tm_bounds
        #else:
        #    # NOTE: These are inverse weights (ie, the constraint costs are *multiplied* by "1.0 / weight").
        #    return True, 2.0, tm_bounds  # 2.0 gives a *multiplicative* weight of 0.5
    else:
        return True, 1.0, None

def get_hotspot_trail_params(age):
    # Only use hotspot trails for 0-80Ma.
    if age <= 80:
        return True, 1.0, None
    else:
        return False, 1.0, None

def get_plate_velocity_params(age):
    # Note: Use units of mm/yr (same as km/Myr)...
    #pv_bounds = [0, 60]
    
    if data_model.startswith('Global_Model_WD_Internal_Release'):
        return False, 1.0, None
    elif data_model == 'Global_1000-0_Model_2017':
        pv_bounds = [0, 60]
        return False, 1.0, pv_bounds
    else:
        return True, 1.0, None


#
# Which reference plate ID and rotation file to use at a specific age.
#
def get_reference_params(age):
    """
    Returns a 2-tuple containg reference plate ID and reference rotation filename (or None).
    
    If reference rotation filename is None then it means the no-net-rotation model should be used.
    """
    if data_model == 'Global_1000-0_Model_2017':
        if age <= 550:
            ref_rotation_plate_id = 701
            #ref_rotation_file = 'Global_1000-0_Model_2017/pmag/550_0_Palaeomagnetic_Africa_S.rot'
            ref_rotation_file = None  # Use NNR
        else:
            ref_rotation_plate_id = 101
            #ref_rotation_file = 'Global_1000-0_Model_2017/pmag/1000_550_Laurentia_pmag_reference.rot'
            ref_rotation_file = None  # Use NNR
    else:
        ref_rotation_plate_id = 701
        ref_rotation_file = 'Palaeomagnetic_Africa_S.rot'
    
    return ref_rotation_plate_id, ref_rotation_file


search = "Initial"
search_radius = 60
# If True then temporarily expand search radius to 90 whenever the reference plate changes.
# Normally the reference plate stays constant at Africa (701), but does switch to 101 for the 1Ga model.
# It's off by default since it doesn't appear to change the results, and may sometimes cause job to fail
# on Artemis (presumably since 'models' is increased by a factor of 2.5) - although problem manifested
# as failure to read the rotation file being optimised, so it was probably something else.
expand_search_radius_on_ref_plate_switches = False
rotation_uncertainty = 30
auto_calc_ref_pole = True

model_stop_condition = 'threshold'
max_iter = 5  # Only applies if model_stop_condition != 'threshold'


# Trench migration parameters
tm_method = 'pygplates' # 'pygplates' for new method OR 'convergence' for old method
tm_data_type = data_model


# Hotspot parameters:
interpolated_hotspot_trails = True
use_trail_age_uncertainty = True

# Millions of years - e.g. 2 million years @ 50mm per year = 100km radius uncertainty ellipse
trail_age_uncertainty_ellipse = 1

include_chains = ['Louisville', 'Tristan', 'Reunion', 'St_Helena', 'Foundation', 'Cobb', 'Samoa', 'Tasmantid', 
                  'Hawaii']
#include_chains = ['Louisville', 'Tristan', 'Reunion', 'Hawaii', 'St_Helena', 'Tasmantid']


# Large area grid search to find minima
if search == 'Initial':

    search_type = 'Random'

# Uses grid search minima as seed for targeted secondary search (optional)
elif search == 'Secondary':

    search_type = 'Uniform'
    search_radius = 15
    rotation_uncertainty = 30

    models = 60
    auto_calc_ref_pole = False

# Used when auto_calc_ref_pole is False.
no_auto_ref_rot_longitude = -53.5
no_auto_ref_rot_latitude = 56.6
no_auto_ref_rot_angle = -2.28

interpolation_resolution = 5
rotation_age_of_interest = True

hst_file = 'HotspotTrails.geojson'
hs_file = 'HotspotCatalogue2.geojson'
interpolated_hotspots = 'interpolated_hotspot_chains_5Myr.xlsx'


# Don't plot in this workflow.
# This is so it can be run on an HPC cluster with no visualisation node.
plot = False


#
# How to handle warnings.
#
def warning_format(message, category, filename, lineno, file=None, line=None):
    # return '{0}:{1}: {1}:{1}\n'.format(filename, lineno, category.__name__, message)
    return '{0}: {1}\n'.format(category.__name__, message)
# Print the warnings without the filename and line number.
# Users are not going to want to see that.
warnings.formatwarning = warning_format

# Always print warnings (not just the first time a particular message is encountered at a particular location).
#warnings.simplefilter("always")
