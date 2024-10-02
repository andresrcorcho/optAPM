"""This script will combine multiple .gpml or .gpmlz files into five files
containing geometries, plate boundaries, active and inactive deforming
networks, and flat slabs. Additionally, any .rot rotation files will be
combined into a single file.

The script requires pyGPlates.
"""
import os
from shutil import copy2
from sys import stderr
from tempfile import TemporaryDirectory

import pygplates

DIRNAME = os.path.dirname(__file__)
DEFAULT_INPUT = [os.path.abspath(os.path.join(DIRNAME, ".."))]


def main(**kwargs):
    args = _check_args(**kwargs)
    filenames = args["filenames"]
    outdir = args["outdir"]
    zipped = args["zipped"]
    verbose = args["verbose"]

    which = "gpmlz" if zipped else "gpml"

    with TemporaryDirectory() as tmpdir:
        clean_files(
            feature_filenames=filenames,
            output_directory=tmpdir,
            copy_all=True,
            verbose=verbose,
        )
        cleaned_files = [os.path.join(tmpdir, i) for i in os.listdir(tmpdir)]
        combine_feature_files(
            input_filenames=cleaned_files,
            output_directory=outdir,
            which=which,
            verbose=verbose,
        )
    combine_rotation_files(input_filenames=filenames, output_directory=outdir, verbose=verbose)


def clean_files(
    feature_filenames, output_directory, copy_all=False, verbose=False
):
    output_directory = os.path.abspath(output_directory)

    if not os.path.isdir(output_directory):
        if os.path.isfile(output_directory):
            raise NotADirectoryError(
                "Output directory is a file: {}".format(output_directory)
            )
        if not os.path.exists(output_directory):
            os.makedirs(output_directory, exist_ok=True)

    for filename in feature_filenames:
        if not os.path.isfile(filename):
            raise FileNotFoundError("Input file not found: {}".format(filename))

    feature_filenames = [
        i
        for i in feature_filenames
        if i.endswith(".gpml") or i.endswith(".gpmlz")
    ]

    combined_features = pygplates.FeatureCollection(
        pygplates.FeaturesFunctionArgument(feature_filenames).get_features()
    )
    features_dict = create_feature_dict(combined_features)
    topology_references = get_topological_references(combined_features)
    invalid_ids = []
    for topology_id in topology_references:
        for referenced_id in topology_references[topology_id]:
            if referenced_id in features_dict:
                break
        else:
            # No valid references
            invalid_ids.append(topology_id)

    del combined_features, features_dict, topology_references

    for filename in feature_filenames:
        bn = os.path.basename(filename)
        fc = pygplates.FeatureCollection(filename)
        fc_ids = set(i.get_feature_id() for i in fc)
        count = 0
        for invalid_id in invalid_ids:
            if invalid_id in fc_ids:
                count += 1
                fc.remove(invalid_id)
        if count > 0:
            output_filename = os.path.join(output_directory, bn)
            fc.write(output_filename)
            if verbose:
                print(
                    "Removed {} invalid topological features ".format(count)
                    + "from {}".format(bn),
                    file=stderr,
                )
        elif copy_all:
            output_filename = os.path.join(output_directory, bn)
            copy2(filename, output_filename)
    if verbose:
        print(
            "Total removed features = {}".format(len(invalid_ids)), file=stderr
        )


def combine_feature_files(
    input_filenames, output_directory, which="gpml", verbose=False
):
    if which not in {"both", "gpml", "gpmlz"}:
        raise ValueError(f"Invalid argument: {which}")

    input_filenames = [
        i
        for i in input_filenames
        if i.endswith(".gpml") or i.endswith(".gpmlz")
    ]

    if verbose:
        print("Processing input files:", file=stderr)
        for i in input_filenames:
            print("\t" + i, file=stderr)

    input_inactive = [
        i
        for i in input_filenames
        if "inactive" in os.path.basename(i).lower()
    ]
    input_filenames = [i for i in input_filenames if i not in input_inactive]

    outputs = {
        "geometries": "Feature_Geometries",
        "plates": "Plate_Boundaries",
        "networks": "Deforming_Networks_Active",
        "inactive": "Deforming_Networks_Inactive",
        "slabs": "Flat_Slabs",
    }
    for key in outputs:
        outputs[key] = os.path.join(output_directory, outputs[key])

    inactive = pygplates.FeatureCollection(
        pygplates.FeaturesFunctionArgument(input_inactive).get_features()
    )
    inactive_ids = set(i.get_feature_id() for i in inactive)
    combined = pygplates.FeatureCollection(
        pygplates.FeaturesFunctionArgument(input_filenames).get_features()
    )

    geometries = pygplates.FeatureCollection()
    plates = pygplates.FeatureCollection()
    networks = pygplates.FeatureCollection()
    slabs = pygplates.FeatureCollection()

    # Separate flat slab topologies first
    to_remove = []
    for feature in combined:
        if (
            feature.get_feature_type().to_qualified_string()
            == "gpml:TopologicalSlabBoundary"
        ):
            to_remove.append(feature.get_feature_id())
            slabs.add(feature)
    for i in to_remove:
        combined.remove(i)
    # Also separate geometries only referred to by flat slab topologies
    combined_dict = create_feature_dict(combined)
    inactive_dict = create_feature_dict(inactive)
    combined_references = _get_all_topological_references(combined)
    slabs_references = _get_all_topological_references(slabs)
    inactive_references = _get_all_topological_references(inactive)
    for id in slabs_references:
        if (id not in combined_references) and (id in combined_dict):
            slabs.add(combined_dict[id])
            combined.remove(id)
        elif (id not in inactive_references) and (id in inactive_dict):
            slabs.add(inactive_dict[id])
            inactive.remove(id)

    # Sort active features into the appropriate file
    for feature in combined:
        if not is_topological(feature):
            geometries.add(feature)
            if feature.get_feature_id() in inactive_ids:
                inactive.remove(feature.get_feature_id())
                inactive_ids = set(i.get_feature_id() for i in inactive)
            continue
        topologies = feature.get_all_topological_geometries()
        for topology in topologies:
            if isinstance(topology, pygplates.GpmlTopologicalNetwork):
                # At least one topology is a network, so assume the feature
                # is a deforming region
                networks.add(feature)
                break
            if isinstance(topology, pygplates.GpmlTopologicalPolygon):
                # At least one topology is a polygon, so assume the feature
                # is a topological plate
                plates.add(feature)
                break
        else:
            # No networks or polygons, so must be a line
            geometries.add(feature)

    # Move inactive geometry features into geometries file
    to_remove = []
    for feature in inactive:
        if not is_topological(feature):
            to_remove.append(feature.get_feature_id())
            geometries.add(feature)
    for i in to_remove:
        inactive.remove(i)

    # Write .gpml and/or .gpmlz files
    fcs = {
        "geometries": geometries,
        "plates": plates,
        "networks": networks,
        "inactive": inactive,
        "slabs": slabs,
    }
    if which == "both":
        extensions = ("gpml", "gpmlz")
    else:
        extensions = (which,)
    if verbose:
        print("Writing output files:", file=stderr)
    for key in fcs:
        for extension in extensions:
            output_filename = outputs[key] + os.extsep + extension
            if verbose:
                print("\t" + output_filename, file=stderr)
            fcs[key].write(output_filename)


def combine_rotation_files(input_filenames, output_directory, verbose=False):
    input_filenames = [i for i in input_filenames if i.endswith(".rot")]
    if not os.path.isdir(output_directory):
        os.makedirs(output_directory)
    output_filename = os.path.join(output_directory, "CombinedRotations.rot")

    if verbose:
        print("Combining rotation files:", file=stderr)
        for i in input_filenames:
            print("\t" + i, file=stderr)
        print("Output file: " + output_filename)

    with open(output_filename, "w", encoding="utf8") as outf:
        for input_filename in input_filenames:
            with open(input_filename, "r", encoding="utf8") as inf:
                outf.write(inf.read())


def _get_all_topological_references(features, id_type=pygplates.FeatureId):
    references = get_topological_references(features=features, id_type=id_type)
    combined_references = set()
    for key in references:
        combined_references.update(references[key])
    return combined_references


def _check_args(**kwargs):
    filenames = kwargs.get("filenames", DEFAULT_INPUT)
    if filenames is None:
        raise ValueError("No filenames were provided")
    filenames = [os.path.abspath(i) for i in filenames]
    tmp = []
    for filename in filenames:
        if not os.path.exists(filename):
            raise FileNotFoundError("Input file not found: " + filename)
        if os.path.isdir(filename):
            tmp.extend(
                [
                    os.path.join(filename, i)
                    for i in os.listdir(filename)
                    if i.endswith(".gpml")
                    or i.endswith(".gpmlz")
                    or i.endswith(".rot")
                ]
            )
        elif os.path.isfile(filename):
            tmp.append(filename)
    filenames = tmp
    del tmp

    outdir = os.path.abspath(kwargs.get("outdir", os.curdir))
    if not os.path.isdir(outdir):
        os.makedirs(outdir, exist_ok=True)

    zipped = kwargs.get("zipped", False)

    verbose = kwargs.get("verbose", False)

    return {
        "filenames": filenames,
        "outdir": outdir,
        "zipped": zipped,
        "verbose": verbose,
    }


def _get_args():
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Combine multiple .gpml or .gpmlz files into "
            + "five files containing geometries, plate boundaries, "
            + "active and inactive deforming networks, and flat slabs."
            + " Also combine any .rot rotation files into a single file."
        )
    )
    parser.add_argument(
        "filenames",
        metavar="<filename>",
        nargs="*",
        help="files to combine; default: all files in parent directory",
        default=DEFAULT_INPUT,
    )
    parser.add_argument(
        "-o",
        "--outdir",
        type=str,
        help="Output directory; default: current directory",
        default=os.curdir,
        dest="outdir",
    )
    parser.add_argument(
        "-z",
        "--gpmlz",
        action="store_true",
        help="write output files in compressed .gpmlz format",
        dest="zipped",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print additional information to stderr",
        dest="verbose",
    )
    args = parser.parse_args()
    return args


def create_feature_dict(features, id_type=pygplates.FeatureId):
    r"""Create a dictionary mapping feature IDs to features.
    Feature IDs can be either `str` or `pygplates.FeatureId`,
    according to `id_type`.
    Parameters
    ----------
    features : valid argument for pygplates.FeaturesFunctionArgument
        `features` may be a single `pygplates.Feature`, a
        `pygplates.FeatureCollection`, a `str` filename,
        or a (potentially nested) sequence of any combination of the above.
    id_type : {`pygplates.FeatureId`, `str`}, optional
        By default, dictionary keys will be of type `pygplates.FeatureId`;
        pass `id_type=str` to use string representations instead.
    Returns
    -------
    dict
        Dictionary for looking up features by their feature ID.
        N.B. the result will be an empty dictonary  if `features` is empty.
    Raises
    ------
    TypeError
        If `id_type` is not one of {`pygplates.FeatureId`, `str`},
        or if `features` is of an invalid type.
    OSError (including FileNotFoundError, IsADirectoryError)
        If `features` points to a non-existent or unrecognised file.
    """
    if id_type not in {str, pygplates.FeatureId}:
        raise TypeError(
            "Invalid `key_type` value: `"
            + str(id_type)
            + "` (must be one of `pygplates.FeatureId`, `str`)"
        )

    features = _parse_features_function_arguments(features)
    if id_type is str:
        return {i.get_feature_id().get_string(): i for i in features}
    else:
        return {i.get_feature_id(): i for i in features}


def get_topological_references(features, id_type=pygplates.FeatureId):
    r"""Create a dictionary mapping topological feature IDs to
    referenced features.
    The resulting dictionary maps each topological
    `pygplates.FeatureId` in `features` to the set of
    `pygplates.FeatureId` referenced by its topological
    geometry or geometries.
    Parameters
    ----------
    features : valid argument for pygplates.FeaturesFunctionArgument
        `features` may be a single `pygplates.Feature`, a
        `pygplates.FeatureCollection`, a `str` filename,
        or a (potentially nested) sequence of any combination of the above.
    id_type : {`pygplates.FeatureId`, `str`}, optional
        By default, feature IDs will be of type `pygplates.FeatureId`;
        pass `id_type=str` to use string representations instead.
    Returns
    -------
    dict
        N.B. Dictionary keys include all topological features in `features`,
        and only topological features.
    Raises
    ------
    TypeError
        If `id_type` is not one of {`pygplates.FeatureId`, `str`},
        or if `features` is of an invalid type.
    OSError (including FileNotFoundError, IsADirectoryError)
        If `features` points to a non-existent or unrecognised file.
    """
    features = _parse_features_function_arguments(features)
    features_dict = create_feature_dict(features)
    results = {}
    for feature in features:
        if not is_topological(feature):
            continue
        references = _get_topological_references(feature, features_dict)
        if len(references) == 0:
            continue
        id = feature.get_feature_id()
        if id_type is str:
            id = id.get_string()
            references = set(i.get_string() for i in references)
        results[id] = references
    return results


def is_topological(feature):
    r"""Determine whether a feature contains a topological geometry.
    Parameters
    ----------
    feature : pygplates.Feature
    Returns
    -------
    bool
        True if `feature` contains a topological geometry, else False.
    Raises
    ------
    TypeError
        If `feature` is a type other than `pygplates.Feature`
        (more precisely, if its type does not implement
        `get_all_topological_geometries`).
    """
    try:
        return len(feature.get_all_topological_geometries()) > 0
    except AttributeError as e:
        raise TypeError(
            "`is_topological` not implemented for `{}`".format(type(feature))
        ) from e


def _get_topological_references(feature, features_dict):
    if not isinstance(feature, pygplates.Feature):
        raise TypeError("Invalid feature type: `{}`".format(type(feature)))
    topologies = feature.get_all_topological_geometries()
    referenced_ids = set()
    for topology in topologies:
        if isinstance(topology, pygplates.GpmlTopologicalLine):
            sections = topology.get_sections()
        else:
            sections = topology.get_boundary_sections()
        for section in sections:
            feature_id = section.get_property_delegate().get_feature_id()
            referenced_ids.add(feature_id)
    referenced_features = set()
    for id in referenced_ids:
        if id in features_dict:
            referenced_features.add(features_dict[id])
    for referenced_feature in referenced_features:
        referenced_ids = referenced_ids.union(
            _get_topological_references(referenced_feature, features_dict)
        )
    return referenced_ids


def _parse_features_function_arguments(features):
    r"""Load features using `pygplates.FeaturesFunctionArgument`.
    This function also tries to translate some of the exceptions
    raised by `pygplates.FeaturesFunctionArgument` into regular
    Python exceptions.
    """
    try:
        features = pygplates.FeatureCollection(
            pygplates.FeaturesFunctionArgument(features).get_features()
        )
    except pygplates.FileFormatNotSupportedError as e:
        print("Invalid filename: `{}`".format(features))
        if not os.path.exists(features):
            raise FileNotFoundError("File does not exist") from e
        if os.path.isdir(features):
            raise IsADirectoryError("File is a directory") from e
        raise OSError("Unrecognised file format") from e
    except pygplates.OpenFileForReadingError as e:
        raise FileNotFoundError(
            "Could not find input file(s): `{}`".format(features)
        ) from e
    except Exception as e:
        if str(type(e)) == "<class 'Boost.Python.ArgumentError'>":
            # This is the easiest way of catching Boost.Python.ArgumentError,
            # since it cannot be directly imported into Python
            raise TypeError(
                "Invalid argument type: `{}`".format(type(features))
            ) from e
        else:
            raise e
    return features


if __name__ == "__main__":
    args = _get_args()
    main(**vars(args))
