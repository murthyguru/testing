from typing import Dict, List, Union
from pandas import DataFrame, Timestamp, date_range, DatetimeIndex
from pvlib.spa import calculate_deltat
from pvlib.solarposition import spa_python
from pvlib.tracking import singleaxis
from pvlib import location
from pvlib import irradiance

def get_tracker_angles_and_or_solar_elevations(query:Dict[str, Union[str, int, float, bool]], angles:bool=True, elevations:bool=True) -> Dict[str, Union[List[str], List[float]]]:
    """
    Gets the single axis tracking angles and/or solar elevations based on the
    contents of the given query dict.

    If query['timeseries_format'] evaluates to False, then 'timeseries' will not
    be included in the returned dict.

    See below for example query dict and return dict.

    Parameters
    ----------
    query : dict
        Dictionary containing the query parameters.
    angles : bool, default True
        Whether or not to include tracking angles in the returned dict.
    elevations : bool, default True
        Whether or not to include solar elevations in the returned dict.

    Returns
    -------
    dict
        The dict will have the following keys: 'timeseries' (if
        query['timeseries_format'] does not evaluate to False),
        'tracker_angles', 'tracker_angles_min_max', 'solar_elevations',
        'solar_elevations_min_max', or no keys if both `angles` and `elevations`
        evaluate to False.

    Raises
    ------
    KeyError
        If `angles` evaluates to True and the query dict is missing the 'gcr'
        key when the value associated with the 'backtrack' key evaluates to
        True.

    Example
    -------
    ```
    query_dict = {
        "start": "2021-01-25T07:30:00",  # str or datetime, ISO date or date & time
        "end": "2021-01-25T19:30:00",  # str or datetime, ISO date or date & time
        "resolution": "5min",  # str, timeseries resolution, 'S' for 1 second
        "timeseries_format": "%H:%M",  # optional, str, default '%H:%M'

        "timezone": "US/Eastern",  # str
        "latitude": 38.435324,  # float
        "longitude": -80.12345,  # float
        "elevation": 240.232,  # float, meters

        "axis_tilt": 0.0,  # float, degrees
        "axis_azimuth": 180.0,  # float, degrees
        "max_angle": 60.0,  # float, degrees
        "stow_angle": 5.0,  # optional, float, default 0.0, degrees
        "backtrack": False,  # optional, bool, default False
        "gcr": 0.4,  # optional if not backtrack, float, ratio i.e. 0.0 < gcr <= 1.0

        "round_to": 2,  # optional, int, default 2, decimal digits to round to
    }

    return_dict = {
        'timeseries': ['07:30', ..., '19:30'],  # list[str], datetime string
        'tracker_angles': [5.0, ..., 5.0],  # list[float], degrees
        'tracker_angles_min_max': (-60.0, 60.0),  # tuple(float, float), degrees
        'solar_elevations': [0.0, ..., 0.0],  # list[float], meters
        'solar_elevations_min_max': (0.0, 34.16),  # tuple(float, float), degrees
    }
    ```
    """

    query['timeseries_format'] = query.get('timeseries_format', '%H:%M')
    include_timeseries = False if not query['timeseries_format'] else True

    # nothing to do if both bool parameters are false, return an empty dict
    if not angles and not elevations and not include_timeseries:
        return {}

    if angles:
        query['stow_angle'] = query.get('stow_angle', 0.0)
        query['backtrack'] = query.get('backtrack', False)
        if not query['backtrack']:
            query['gcr'] = 0.0
        elif not 'gcr' in query:
            raise KeyError(f"missing 'gcr' key in query when query['backtrack'] evaluates to True")

    query['round_to'] = query.get('round_to', 2)

    # create start and end pandas Timestamps
    start_ts = Timestamp(query['start'], tz=query['timezone'])
    end_ts = Timestamp(query['end'], tz=query['timezone'])

    # get a pandas DatetimeIndex containing entries at the specified frequency
    # between start and end of the given date's day
    dt_index = date_range(start=start_ts, end=end_ts, freq=query['resolution'])

    solpos = None
    if angles or elevations:
        # use pvlib.spa to get delta_t
        delta_t = calculate_deltat(year=start_ts.year, month=start_ts.month)

        # get a pandas DataFrame containing the sun's apparent zenith, azimuth
        # and elevation for each entry of dt_index
        solpos = spa_python(time=dt_index,
                                        latitude=query['latitude'],
                                        longitude=query['longitude'],
                                        altitude=query['elevation'],
                                        delta_t=delta_t)
    s_elevs = None
    if elevations:
        # replace NAN and negative elevations with 0, round round_to decimal places
        s_elevs = solpos[['apparent_elevation']].fillna(0.0).clip(lower=0.0).round(query['round_to'])['apparent_elevation']

    t_thetas = None
    if angles:
        # get the tracking angle for every calculated apparent zenith and azimuth
        t_angles = singleaxis(apparent_zenith=solpos['apparent_zenith'],
                                    apparent_azimuth=solpos['azimuth'],
                                    axis_tilt=query['axis_tilt'],
                                    axis_azimuth=query['axis_azimuth'],
                                    max_angle=query['max_angle'],
                                    backtrack=query['backtrack'],
                                    gcr=query['gcr'],
                                    cross_axis_tilt=0)

        # the t_angles DataFrame can contain NaN entries due to the sun being
        # below the horizon (I think, I'm not sure, but NaN entries only appear
        # before sunrise and after sunset) so we replace NaN entries with the
        # specified stow angle
        t_thetas = t_angles[['tracker_theta']].fillna(query['stow_angle']).round(query['round_to'])['tracker_theta']

    t_series = None
    if include_timeseries:
        # get a pandas Series of 'timeseries_format' times
        t_series = DataFrame(data=dt_index.strftime(query['timeseries_format']), columns=['time'])['time']

    ret_dict = {}
    if include_timeseries:
        ret_dict['timeseries'] = t_series.values.tolist()
    if angles:
        ret_dict['tracker_angles'] = t_thetas.values.tolist()
        ret_dict['tracker_angles_min_max'] = [t_thetas.min(), t_thetas.max()]
    if elevations:
        ret_dict['solar_elevations'] = s_elevs.values.tolist()
        ret_dict['solar_elevations_min_max'] = [s_elevs.min(), s_elevs.max()]

    return ret_dict


def get_tracker_angles_and_or_solar_elevations_safe(query:Dict[str, Union[str, int, float, bool]], angles:bool=True, elevations:bool=True) -> Dict[str, Union[List[str], List[float]]]:
    """
    Gets the single axis tracking angles and/or solar elevations based on the
    contents of the given query dict.

    This function checks if all of the required keys are in the query dict
    before calling `get_tracker_angles_and_or_elevations`. If the query dict
    is missing any required keys then an informative `KeyError` exception will
    be raised.

    If query['timeseries_format'] evaluates to False, then 'timeseries' will not
    be included in the returned dict.

    See the `helpers.pvlib.get_tracker_angles_and_or_elevations` function's
    documentation for more information.

    Raises
    ------
    KeyError
        - If the query dict is missing any of the required (non-optional) keys.
        - If `angles` evaluates to True and the query dict is missing the 'gcr'
        key when the value associated with the 'backtrack' key evaluates to
        True.
    """
    required_keys = ['start', 'end', 'resolution', 'timezone', 'latitude', 'longitude', 'elevation']
    if angles:
        required_keys.append(['axis_tilt', 'axis_azimuth', 'max_angle'])

    missing_keys_str = ''.join([f" '{key}'" for key in required_keys if not key in query])
    if missing_keys_str:
        raise KeyError(f"the parameter 'query' of type 'dict' is missing the following keys:{missing_keys_str}")

    return get_tracker_angles_and_or_solar_elevations(query=query, angles=angles, elevations=elevations)

def get_poa_from_ghi (query:Dict[str, Union[str, int, float]]) -> Dict[str, Union[List[str], List[float]]]:

    """
    Estimates POA Irradiance from GHI Irradiance

    See below for example query dict.

    Parameters
    ----------
    query : dict
        Dictionary containing the query parameters.

    Returns
    -------
    float
        The float will be the predicted POA Irradiance given the starting query in W/m2

    Example
    -------
    ```
    query_dict = {

        "time": "2021-01-25T07:30:00",  # datetime

        "timezone": "US/Eastern",  # str
        "latitude": 38.435324,  # float
        "longitude": -80.12345,  # float
        "elevation": 240.232,  # float, meters

        "tilt": 0.0,  # float, degrees
        "azimuth": 180.0,  # float, degrees

        "ghi": 1000.0, # float, W/m2
        "model": "erbs", # str

        "dni_mult": 100, # float, %
        "dhi_mult": 100 # float, %

    }
    ```
    """

    if ((query["tilt"] == None) or (query["ghi"] == None) or (query["azimuth"] == None)):

        return None

    site = location.Location(query["latitude"], query["longitude"], tz = query["timezone"], altitude = query["elevation"])

    time = Timestamp(query["time"])

    dt_index = date_range(start = time, end = time, freq = 'S')

    delta_t = calculate_deltat(year = time.year, month = time.month)

    solar_position = spa_python(time = dt_index,
                                latitude = site.latitude,
                                longitude = site.longitude,
                                altitude = site.altitude,
                                delta_t = delta_t)

    if (query["model"] == 'erbs'):

        result = irradiance.erbs(query['ghi'], solar_position['apparent_zenith'], dt_index)

    poa_irradiance = irradiance.get_total_irradiance(
	surface_tilt = query["tilt"],
	surface_azimuth = query["azimuth"],
	dni = result['dni'] * (query['dni_mult'] / 100),
	ghi = query['ghi'],
	dhi = result['dhi'] * (query['dhi_mult'] / 100),
	solar_zenith = solar_position['zenith'],
	solar_azimuth = solar_position['azimuth']
	)

    return poa_irradiance['poa_global'].values.tolist()[0]