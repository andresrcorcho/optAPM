import glob
import os.path
import pygplates

#
# Script to concatenate all rotation ('.rot') files in a directory.
#

# The main data directory is the directory containing this source file.
base_dir = os.path.abspath(os.path.dirname(__file__))

# Directory containing the input rotation files.
rotation_data_dir = os.path.join(base_dir, 'data', 'Global_Model_WD_Internal_Release_2016_v3')

# The combined output rotation file.
output_rotation_filename = os.path.join(rotation_data_dir, 'optimisation', 'all_rotations.rot')

# Gather all '.rot' files in the input directory.
input_rotation_filenames = glob.glob(os.path.join(rotation_data_dir, '*.rot'))


# Main trench migration data directory.
tm_data_dir = os.path.join(base_dir, 'data', 'TMData', 'Global_Model_WD_Internal_Release_2016_v3')


#
# Get all plate IDs used by the optimisation process.
#

required_plate_ids = set()

# Add Africa (used by Net Rotation objective function).
required_plate_ids.add(701)

# Add plate IDs are pre-resolved subduction zones.
subduction_times_start = 251
for time in xrange(0, subduction_times_start):
    
    # print time
    
    # Read TM gpml file.
    subduction_features = pygplates.FeatureCollection.read(os.path.join(tm_data_dir, 'TMData_' + str(time) + 'Ma.gpml'))
    
    # Add subduction plate IDs to the set.
    for subduction_feature in subduction_features:
        required_plate_ids.add(subduction_feature.get_reconstruction_plate_id())

print sorted(required_plate_ids)
print len(required_plate_ids)


# Read all the rotation files.
rotation_features = []
for input_rotation_filename in input_rotation_filenames:
    rotation_features.extend(
        pygplates.FeatureCollection.read(input_rotation_filename))

rotation_required = [False] * len(rotation_features)

plate_circuits = {}

for rotation_feature_index, rotation_feature in enumerate(rotation_features):

    # Get the rotation feature information.
    total_reconstruction_pole = rotation_feature.get_total_reconstruction_pole()
    if not total_reconstruction_pole:
        # Not a rotation feature.
        continue

    fixed_plate_id, moving_plate_id, rotation_sequence = total_reconstruction_pole
    
    plate_circuits.setdefault(moving_plate_id, []).append((fixed_plate_id, rotation_feature_index))
    # plate_circuits.setdefault(fixed_plate_id, []).append((moving_plate_id, rotation_feature_index))


visited_plate_ids = set()

def visit_plate_circuit(moving_plate_id):
    if moving_plate_id in visited_plate_ids:
        return
    visited_plate_ids.add(moving_plate_id)
    
    moving_plate_circuits = plate_circuits.get(moving_plate_id)
    if moving_plate_circuits:
        for fixed_plate_id, rotation_feature_index in moving_plate_circuits:
            rotation_required[rotation_feature_index] = True
            visit_plate_circuit(fixed_plate_id)

for required_plate_id in required_plate_ids:
    visit_plate_circuit(required_plate_id)


required_rotation_features = []
for rotation_feature_index, rotation_feature in enumerate(rotation_features):
    if rotation_required[rotation_feature_index]:
        required_rotation_features.append(rotation_feature)

pygplates.FeatureCollection(required_rotation_features).write(output_rotation_filename)
