"""Separate semantic geometry regression from bounded optional pixel comparison.

Passing a pixel threshold does not establish mathematical correctness. Semantic
receipts preserve exact source identities and every reported change; pixel
receipts preserve byte hashes, dimensions and comparison policy for replay.
"""
from __future__ import annotations

from fractions import Fraction
from hashlib import sha256
from io import BytesIO

from ..core.semantic_ir import fingerprint, rational
from .scene_graph import GeometryScene, Scene


MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_IMAGE_PIXELS = 4 * 1024 * 1024
MAX_DIFFERENCES = 10000


def _canonical_scene(scene):
    if not isinstance(scene, (Scene, GeometryScene)):
        raise ValueError('Supported scene contract required')
    data = scene.to_data()
    if isinstance(scene, GeometryScene):
        # Object declaration order is presentation-neutral, curve sample order is not.
        for field in ('points', 'segments', 'circles', 'curves', 'arrows'):
            data[field] = sorted(data[field], key=lambda value: value['name'])
        data['constraints'] = sorted(data['constraints'], key=fingerprint)
    return data


def _numeric_path(path):
    tokens = path.split('/')
    if 'model' in tokens:
        return False
    scalar = {'x', 'y', 'xmin', 'xmax', 'ymin', 'ymax', 'radius_squared', 'value'}
    arrays = {'coordinates', 'start', 'end', 'vector', 'points'}
    return tokens[-1] in scalar or (tokens[-1].isdigit() and any(token in arrays for token in tokens))


def _compare(left, right, *, tolerance):
    differences = []
    numerical = []

    def append_difference(row):
        if len(differences) >= MAX_DIFFERENCES:
            raise ValueError('Semantic change report exceeds bounded difference budget')
        differences.append(row)

    pending = [('', left, right)]
    while pending:
        path, a, b = pending.pop()
        if type(a) is type(b) and a == b:
            continue
        if type(a) is not type(b):
            append_difference({'path': path, 'kind': 'type', 'before': a, 'after': b})
        elif isinstance(a, dict):
            keys = sorted(set(a) | set(b))
            for key in reversed(keys):
                if key not in a or key not in b:
                    append_difference({'path': f'{path}/{key}', 'kind': 'field_presence',
                                        'before': a.get(key), 'after': b.get(key)})
                else:
                    pending.append((f'{path}/{key}', a[key], b[key]))
        elif isinstance(a, list):
            if len(a) != len(b):
                append_difference({'path': path, 'kind': 'length', 'before': len(a), 'after': len(b)})
            for index in range(min(len(a), len(b)) - 1, -1, -1):
                pending.append((f'{path}/{index}', a[index], b[index]))
        elif isinstance(a, str) and _numeric_path(path):
            try:
                delta = abs(rational(a) - rational(b))
            except (ValueError, ZeroDivisionError):
                append_difference({'path': path, 'kind': 'value', 'before': a, 'after': b})
            else:
                numerical.append(delta)
                append_difference({'path': path, 'kind': 'numeric', 'before': a, 'after': b,
                                    'absolute_difference': str(delta), 'within_tolerance': delta <= tolerance})
        else:
            append_difference({'path': path, 'kind': 'value', 'before': a, 'after': b})
    return differences, max(numerical, default=Fraction(0))


def compare_scenes(baseline, candidate, *, coordinate_tolerance=0):
    """Compare exact canonical scene fields; semantic names and units stay strict.

    Tolerance applies to represented numeric fields, including squared radii.
    It is not a physical distance norm or a unit conversion. Coordinates and
    metadata are independently visible in the difference list.
    """
    tolerance = rational(coordinate_tolerance)
    if tolerance < 0:
        raise ValueError('Coordinate tolerance must be nonnegative')
    left, right = _canonical_scene(baseline), _canonical_scene(candidate)
    differences, maximum = _compare(left, right, tolerance=tolerance)
    accepted = all(row['kind'] == 'numeric' and row['within_tolerance'] for row in differences)
    payload = {'schema_version': 1, 'comparison': 'semantic_scene_v1',
               'baseline_id': fingerprint(baseline.to_data()), 'candidate_id': fingerprint(candidate.to_data()),
               'canonical_baseline_id': fingerprint(left), 'canonical_candidate_id': fingerprint(right),
               'coordinate_tolerance': str(tolerance), 'differences': differences,
               'maximum_numeric_difference': str(maximum), 'accepted': accepted,
               'scope': 'supplied scene semantics; no mathematical or perceptual equivalence claim'}
    return {**payload, 'comparison_id': fingerprint(payload)}


def replay_scene_comparison(receipt, baseline, candidate):
    try:
        return receipt == compare_scenes(baseline, candidate,
            coordinate_tolerance=receipt['coordinate_tolerance'])
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return False


def _image_bytes(value):
    if not isinstance(value, bytes) or not 1 <= len(value) <= MAX_IMAGE_BYTES:
        raise ValueError('Image must be bounded nonempty bytes')
    return value


def _decode_image(value, alpha_policy):
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise RuntimeError('Pixel regression requires optional Pillow') from exc
    value = _image_bytes(value)
    try:
        with Image.open(BytesIO(value)) as image:
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise ValueError('Decoded image exceeds pixel budget')
            if getattr(image, 'n_frames', 1) != 1:
                raise ValueError('Animated or multiframe images are outside regression scope')
            image.load()
            rgba = image.convert('RGBA')
            if alpha_policy == 'composite_white':
                white = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
                rgba = Image.alpha_composite(white, rgba)
            return rgba.size, rgba.tobytes()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise ValueError('Image decode failed') from exc


def compare_pixels(baseline, candidate, *, channel_tolerance=0,
                   maximum_changed_fraction=0, maximum_mean_error=0,
                   alpha_policy='raw_rgba'):
    """Compare aligned decoded RGBA images without resize, blur or registration.

    Channel tolerance uses 0..255 channel units. Mean error averages all four
    channels. Changed fraction counts pixels with any channel beyond tolerance.
    White composition deliberately ignores RGB differences behind zero alpha.
    """
    if type(channel_tolerance) is not int or not 0 <= channel_tolerance <= 255:
        raise ValueError('Channel tolerance must be an integer in 0..255')
    changed_threshold = rational(maximum_changed_fraction)
    mean_threshold = rational(maximum_mean_error)
    if not 0 <= changed_threshold <= 1 or not 0 <= mean_threshold <= 255:
        raise ValueError('Invalid pixel acceptance thresholds')
    if alpha_policy not in {'raw_rgba', 'composite_white'}:
        raise ValueError('Unknown alpha comparison policy')
    baseline, candidate = _image_bytes(baseline), _image_bytes(candidate)
    left_size, left = _decode_image(baseline, alpha_policy)
    right_size, right = _decode_image(candidate, alpha_policy)
    payload = {'schema_version': 1, 'comparison': 'aligned_rgba_v1',
               'baseline_sha256': sha256(baseline).hexdigest(),
               'candidate_sha256': sha256(candidate).hexdigest(),
               'baseline_size': list(left_size), 'candidate_size': list(right_size),
               'channel_tolerance': channel_tolerance,
               'maximum_changed_fraction': str(changed_threshold),
               'maximum_mean_error': str(mean_threshold), 'alpha_policy': alpha_policy}
    if left_size != right_size:
        payload.update(status='dimension_mismatch', accepted=False,
                       changed_pixels=None, changed_fraction=None,
                       mean_absolute_error=None, maximum_channel_error=None,
                       changed_bounds=None)
    else:
        changed = total_error = maximum = 0
        xmin, ymin, xmax, ymax = left_size[0], left_size[1], -1, -1
        for index in range(0, len(left), 4):
            delta = [abs(left[index + channel] - right[index + channel]) for channel in range(4)]
            total_error += sum(delta)
            maximum = max(maximum, *delta)
            if max(delta) > channel_tolerance:
                changed += 1
                pixel = index // 4
                x, y = pixel % left_size[0], pixel // left_size[0]
                xmin, ymin, xmax, ymax = min(xmin, x), min(ymin, y), max(xmax, x), max(ymax, y)
        changed_fraction = Fraction(changed, left_size[0] * left_size[1])
        mean = Fraction(total_error, len(left))
        payload.update(status='compared', changed_pixels=changed,
                       changed_fraction=str(changed_fraction), mean_absolute_error=str(mean),
                       maximum_channel_error=maximum,
                       changed_bounds=None if not changed else [xmin, ymin, xmax, ymax],
                       accepted=changed_fraction <= changed_threshold and mean <= mean_threshold)
    payload['scope'] = 'aligned rendered pixels only; semantic and scientific correctness require separate checks'
    return {**payload, 'comparison_id': fingerprint(payload)}


def replay_pixel_comparison(receipt, baseline, candidate):
    try:
        return receipt == compare_pixels(baseline, candidate, **{name: receipt[name] for name in
            ('channel_tolerance', 'maximum_changed_fraction', 'maximum_mean_error', 'alpha_policy')})
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return False
