import math
import os
import os.path
import points_in_polygons
import pygplates
from skimage import measure
import sys
import numpy as np


class ContinentFragmentation(object):
    """
    Class to calculate continental fragmentation (global perimeter-to-area ratio).
    """
    
    
    def __init__(
            self,
            data_dir,
            original_rotation_filenames,  # Relative to the 'data/' directory.
            continent_features,
            continent_features_are_topologies,
            age_range):
        """
        Load the continent features and use *original* rotation model to calculate fragment through all time to find normalisation factor.
        
        The normalisation factor should be such that approx 1.0 will represent the maximum fragmentation when later using optimised
        rotation model to calculate fragmentation at each time interval.
        """
        
        self.data_dir = data_dir
        self.continent_features = continent_features
        self.continent_features_are_topologies = continent_features_are_topologies

        # When continents are regular static polygons (not dynamic topologies) we need a point grid to calculate
        # contour polygons representing the boundary of reconstructed static polygons that overlap each other.
        if not self.continent_features_are_topologies:
            # 2.0 degrees seems almost better than 1.0 or 0.5 (which captures too small detail along continent boundary).
            self.contouring_point_spacing_degrees = 2.0
            lons = np.arange(-180.0, 180.001, self.contouring_point_spacing_degrees)
            lats = np.arange(-90.0, 90.001, self.contouring_point_spacing_degrees)
            self.contouring_grid_dimensions = len(lats), len(lons)

            contouring_longitude_array, contouring_latitude_array = np.meshgrid(lons, lats)
            self.contouring_points = pygplates.MultiPointOnSphere(
                    zip(contouring_latitude_array.flatten(), contouring_longitude_array.flatten()))
            
            self.debug_contour_polygons = False
            if self.debug_contour_polygons:
                self.debug_contour_polygon_features = []
                self.debug_time_interval = age_range[1] - age_range[0]
        
        # Load all the original rotation feature collections.
        rotation_features = []
        for rotation_filename in original_rotation_filenames:
            # Read the current rotation file.
            rotation_feature_collection = pygplates.FeatureCollection(
                    os.path.join(self.data_dir, rotation_filename))
            rotation_features.extend(rotation_feature_collection)
        
        # Load all original rotations into a rotation model.
        self.rotation_model = pygplates.RotationModel(rotation_features)
        
        # Find the maximum fragmentation over the age range.
        print('Calculating continental fragmentation for {0}-{1}Ma...'.format(age_range[0], age_range[-1]))
        sys.stdout.flush()
        self.fragmentations = dict((age, self._calculate_fragmentation(age)) for age in age_range)
        self.max_fragmentation = max(self.fragmentations.values())
        #print('  min:', np.min(list(self.fragmentations.values())) / self.max_fragmentation)
        #print('  mean:', np.mean(list(self.fragmentations.values())) / self.max_fragmentation)
        #print('  dev:', np.std(list(self.fragmentations.values())) / self.max_fragmentation)
        #sys.stdout.flush()

        # Debug output contour polygons to GPML.
        if self.debug_contour_polygons:
            pygplates.FeatureCollection(self.debug_contour_polygon_features).write('contour_polygons.gpmlz')
    
    
    def get_fragmentation(
            self,
            age):
        """
        Calculate the normalised continental fragmentation index at the specified time.
        """

        # Return a *normalised* version of the pre-calculated fragmentation at age.
        return self.fragmentations[age] / self.max_fragmentation
    
    
    def _calculate_fragmentation(
            self,
            age):

        total_perimeter = 0.0
        total_area = 0.0
        
        # Resolve topological plate polygons or reconstruct static continental polygons.
        if self.continent_features_are_topologies:
            # Resolve the topological plate polygons for the current time.
            resolved_topologies = []
            pygplates.resolve_topologies(
                    self.continent_features,
                    self.rotation_model,
                    resolved_topologies,
                    age)

            # Iterate over the resolved topologies.
            for resolved_topology in resolved_topologies:
                total_perimeter += resolved_topology.get_resolved_boundary().get_arc_length()
                total_area += resolved_topology.get_resolved_boundary().get_area()
            
        else:
            # Reconstruct the static continental polygons.
            reconstructed_feature_geometries = []
            pygplates.reconstruct(self.continent_features, self.rotation_model, reconstructed_feature_geometries, age)
            
            # Get a list of polygons.
            #
            # We should have polygons (not polylines) but turn into a polygon if happens to be a polyline
            # (but that actually only works if the polyline is a closed loop and not just part of a polygon's boundary).
            reconstructed_polygons = [pygplates.PolygonOnSphere(reconstructed_feature_geometry.get_reconstructed_geometry())
                    for reconstructed_feature_geometry in reconstructed_feature_geometries]
            
            # When continents are regular static polygons (not dynamic topologies) we need calculate contour polygons
            # representing the boundary(s) of the reconstructed static polygons that overlap each other.
            reconstructed_contour_polygons = self._calculate_contour_polygons(reconstructed_polygons)
            
            # Contour polygons smaller than this will be excluded.
            # Note: Units here are for normalised sphere (so full Earth area is 4*pi).
            #       So 0.03 covers an area of approximately 1,200,000 km^2.
            min_area = 0.03
            # A contour polygon's area should not be more than half the global area.
            # It seems this can happen with pygplates revisions prior to 31 when there's a sliver polygon along the dateline
            # (that gets an area that's a multiple of PI, instead of zero).
            max_area = 2 * math.pi - 1e-4

            for reconstructed_contour_polygon in reconstructed_contour_polygons:
                reconstructed_contour_polygon_area = reconstructed_contour_polygon.get_area()
                # Exclude contour polygon if smaller than the threshold.
                if (reconstructed_contour_polygon_area > min_area and
                    reconstructed_contour_polygon_area < max_area):
                    total_perimeter += reconstructed_contour_polygon.get_arc_length()
                    total_area += reconstructed_contour_polygon_area

                    # Debug output contour polygons.
                    if self.debug_contour_polygons:
                        self.debug_contour_polygon_features.append(
                                pygplates.Feature.create_reconstructable_feature(
                                        pygplates.FeatureType.gpml_unclassified_feature,
                                        reconstructed_contour_polygon,
                                        valid_time=(age + 0.5 * self.debug_time_interval, age - 0.5 * self.debug_time_interval)))

        #print('age:', age, 'frag_index:', total_perimeter / total_area); sys.stdout.flush()
        return total_perimeter / total_area
    
    
    def _calculate_contour_polygons(
            self,
            polygons):
        """
        Find the boundaries of the specified (potentially overlapping/abutting) polygons as contour polygons.

        Note that code used in this function was copied from code written by Andrew Merdith and Simon Williams.
        See https://github.com/amer7632/pyGPlates_examples/blob/master/Merdith_2019_GPC/Perimeter-to-area-ratio.ipynb
        """

        # Find the reconstructed continental polygon (if any) containing each point.
        polygons_containing_points = points_in_polygons.find_polygons(self.contouring_points, polygons)

        zval = []
        for polygon_containing_point in polygons_containing_points:
            if polygon_containing_point is not None:
                zval.append(1)
            else:
                zval.append(0)
            
        bi = np.array(zval).reshape(self.contouring_grid_dimensions[0], self.contouring_grid_dimensions[1])
    
        # To handle edge effects, pad grid before making contour polygons.
        pad_hor = np.zeros((1, bi.shape[1]))
        pad_ver = np.zeros((bi.shape[0]+1, 1))
        pad1 = np.vstack((bi, pad_hor))
        pad2 = np.hstack((pad_ver, pad1))
        pad3 = np.hstack((pad2, pad_ver))
        contours = measure.find_contours(pad3, 0.5, fully_connected='low')

        contour_polygons = []
        for contour in contours:
            # To handle edge effects again - strip off parts of polygon
            # due to padding, and adjust from image coordinates to long/lat
            contour[:,1] = (contour[:,1] * self.contouring_point_spacing_degrees) - 1
            contour[:,0] = (contour[:,0] * self.contouring_point_spacing_degrees) - 1
            contour[np.where(contour[:,0] < 0.0), 0] = 0
            contour[np.where(contour[:,0] > 180.0), 0] = 180
            contour[np.where(contour[:,1] < 0.0), 1] = 0
            contour[np.where(contour[:,1] > 360.0), 1] = 360
            
            contour_polygon = pygplates.PolygonOnSphere(zip(contour[:,0] - 90, contour[:,1] - 180))

            contour_polygons.append(contour_polygon)

        return contour_polygons
