import glob
import os.path
import pandas
import pygplates


#########################################################################
# Script to extract the optimized 005-000 rotations, from the output    #
# of the optimization workflow, and insert them into the original       #
# rotation files such that a 005-000 sequence is not required.          #
#########################################################################

optimised_model_name = None

# If model name not manually specified above then read it from the main 'Optimised_APM' module.
if not optimised_model_name:
    import Optimised_APM  # To get 'model_name'
    optimised_model_name = Optimised_APM.model_name
    
# The main data directory is the directory containing this source file.
base_dir = os.path.abspath(os.path.dirname(__file__))

# Directory containing the original rotation files.
original_rotation_data_dir = os.path.join(base_dir, 'data', 'Global_Model_WD_Internal_Release_2016_v3')

# Directory containing the optimised rotation files.
optimised_rotation_data_dir = os.path.join(original_rotation_data_dir, 'optimisation')

# The combined optimised rotation file generated by the optimisation workflow.
optimised_rotation_filename = os.path.join(
    optimised_rotation_data_dir,
    'all_rotations_{0}.rot'.format(optimised_model_name))

# Gather all the original '.rot' files (these are our output files).
original_rotation_filenames = glob.glob(os.path.join(original_rotation_data_dir, '*.rot'))


# Read original rotation files.
original_rotation_feature_collections = [pygplates.FeatureCollection(filename)
        for filename in original_rotation_filenames]

# The original rotation model before we modify it below.
original_rotation_model = pygplates.RotationModel(original_rotation_feature_collections)


print "Extracting optimized rotations from model: %s" % optimised_model_name

# Read optimized rotation file.
optimised_rotation_features = pygplates.FeatureCollection(optimised_rotation_filename)


# Extract the 005-000 sequence so we can access the times of its rotation samples.
# We'll also use the 005-000 sequence to build a RotationModel to extract those rotations.
# We only need a rotation model to extract the optimized 005-000 rotations (ignoring everything else).
# Note that the optimisation workflow currently generates only a single 005-000 sequence.
absolute_plate_motion_rotation_feature = None
absolute_plate_motion_rotation_sample_times = None
for rotation_feature in optimised_rotation_features:
    total_reconstruction_pole = rotation_feature.get_total_reconstruction_pole()
    if total_reconstruction_pole:
        fixed_plate_id, moving_plate_id, rotation_sequence = total_reconstruction_pole
        if fixed_plate_id == 0 and moving_plate_id == 5:
            if absolute_plate_motion_rotation_feature:
                raise ValueError('Expected a single 005-000 sequence in output rotation file of optimisation workflow')
            absolute_plate_motion_rotation_feature = rotation_feature
            absolute_plate_motion_rotation_sample_times = [pygplates.GeoTimeInstant(sample.get_time())
                for sample in rotation_sequence.get_enabled_time_samples()]

if absolute_plate_motion_rotation_feature is None:
    raise ValueError('Output rotation file of optimisation workflow does not contain a 005-000 sequence')

absolute_plate_motion_rotation_model = pygplates.RotationModel(absolute_plate_motion_rotation_feature)


# For any rotation features referencing fixed plate 005, merge the optimised 005-000 sequence into it and have it reference 000.
for rotation_feature_collection_index, rotation_feature_collection in enumerate(original_rotation_feature_collections):
    modified_rotation_feature_collection = False
    
    for rotation_feature in rotation_feature_collection:
        total_reconstruction_pole = rotation_feature.get_total_reconstruction_pole()
        if total_reconstruction_pole:
            fixed_plate_id, moving_plate_id, rotation_sequence = total_reconstruction_pole
            # If the current rotation feature references plate 000 then we need to adjust using the
            # optimized absolute rotations (005-000).
            if fixed_plate_id == 0 and moving_plate_id != 999:
                rotation_samples = rotation_sequence.get_enabled_time_samples()
                # Record the current sample times (as GeoTimeInstant so we can compare them within an epsilon).
                rotation_sample_times = [pygplates.GeoTimeInstant(sample.get_time()) for sample in rotation_samples]
                
                # Add in new samples corresponding to sample times of 005-000 that do not coincide with the current sequence.
                # We don't want to generate duplicate samples (ie, with the same time).
                new_rotation_samples = list(rotation_samples)
                for sample_time in absolute_plate_motion_rotation_sample_times:
                    if sample_time not in rotation_sample_times:
                        interpolated_original_rotation = original_rotation_model.get_rotation(
                            sample_time,
                            moving_plate_id,
                            fixed_plate_id=0)
                        interpolated_rotation_sample = pygplates.GpmlTimeSample(
                            # Note that we'll add in the optimized absolute rotation later...
                            pygplates.GpmlFiniteRotation(interpolated_original_rotation),
                            sample_time,
                            'Optimized absolute plate motion')
                        new_rotation_samples.append(interpolated_rotation_sample)
                
                # Need to re-sort the rotation samples because we essentially merged two sequences.
                new_rotation_samples.sort(key = lambda sample: sample.get_time())
                
                # Add in the optimized absolute rotations (005-000).
                for rotation_sample in new_rotation_samples:
                    # Extract the 005-000 absolute rotation at the current sample time.
                    absolute_plate_motion_rotation = absolute_plate_motion_rotation_model.get_rotation(
                        rotation_sample.get_time(),
                        5,
                        fixed_plate_id=0)
                    
                    # Our sequence now references fixed plate 000 instead of 005 so we need to adjust its rotations.
                    #
                    #   R_opt(0->t,000->005) * R(0->t,000->moving) -> R(0->t,000->moving)
                    #
                    rotation = rotation_sample.get_value().get_finite_rotation()
                    rotation = absolute_plate_motion_rotation * rotation
                    rotation_sample.get_value().set_finite_rotation(rotation)
                
                # Store the new sequence of samples in the current rotation feature.
                rotation_feature.set_total_reconstruction_pole(
                    0,
                    moving_plate_id,
                    pygplates.GpmlIrregularSampling(new_rotation_samples))
                
                # Mark the rotation feature's collection as modified (so we can later write it out to disk).
                modified_rotation_feature_collection = True
    
    # Write a modified version of the current original rotation feature collection to disk.
    if modified_rotation_feature_collection:
        # Each output filename is the input filename with a 'optAPM' appended (before the extension).
        input_rotation_filename = original_rotation_filenames[rotation_feature_collection_index]
        base_filename, filename_ext = os.path.splitext(os.path.basename(input_rotation_filename))
        filename_root = os.path.join(optimised_rotation_data_dir, base_filename)
        output_rotation_filename = ''.join((filename_root, '_', optimised_model_name, filename_ext))
        
        print "Writing: %s" % os.path.basename(output_rotation_filename)
        
        rotation_feature_collection.write(output_rotation_filename)
