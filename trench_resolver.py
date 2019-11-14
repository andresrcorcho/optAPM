import os
import os.path
import pygplates
import subduction_convergence_for_absolute_plate_motion as scap
import sys


class TrenchResolver(object):
    """
    Class to resolved topologies and extract resolved trenches.
    """
    
    
    def __init__(
            self,
            data_dir,
            original_rotation_filenames,  # Relative to the 'data/' directory.
            topology_features,
            data_model):
        """
        Load the topology features and load original rotation model.
        """
        
        self.data_dir = data_dir
        self.topology_features = topology_features
        
        # Load all the original rotation feature collections.
        rotation_features = []
        for rotation_filename in original_rotation_filenames:
            # Read the current rotation file.
            rotation_feature_collection = pygplates.FeatureCollection(
                    os.path.join(self.data_dir, rotation_filename))
            rotation_features.extend(rotation_feature_collection)
        
        # Load all the rotations into a rotation model.
        self.rotation_model = pygplates.RotationModel(rotation_features)
        
        # The trench migration filename (relative to the 'data/' directory) to contain resolved trenches
        # generated by 'generate_resolved_trenches()' at a particular reconstruction time.
        self.trench_migration_filename = os.path.join(
                data_model, 'optimisation', 'temp_resolved_trenches.gpml')
    
    
    def __del__(self):
        # Remove temporary trench migration file.
        try:
            os.remove(
                os.path.join(self.data_dir, self.trench_migration_filename))
        except AttributeError:
            # 'self.trench_migration_filename' might not exist if exception raised inside '__init__()'.
            pass
    
    
    def get_trench_migration_filename(self):
        """
        Return the filename (relative to the 'data/' directory) of the file containing trenches resolved
        at the reconstruction time specified in most recent call to 'generate_resolved_trenches()'.
        """
        return self.trench_migration_filename
    
    
    def generate_resolved_trenches(
            self,
            ref_rotation_start_age):
        """
        Generate the resolved trench features at the specified time and save them to the trench migration file.
        """
        
        # Resolve trench features
        resolved_trench_features = scap.resolve_subduction_zones(
                self.rotation_model,
                self.topology_features,
                ref_rotation_start_age)

        # Write resolved trenches to the trench migration file.
        pygplates.FeatureCollection(resolved_trench_features).write(
                os.path.join(self.data_dir, self.trench_migration_filename))
