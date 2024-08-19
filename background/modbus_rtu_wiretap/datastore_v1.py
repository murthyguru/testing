
from typing import Iterable, Dict, List, Tuple, Union

import os
import sqlite3
from datetime import datetime
from dateutil.parser import parser
from collections import namedtuple
from typing import NamedTuple
import shutil

from helpers.common import printd, printe


__TAG = '[datastore.py]'



################################################################################
# Helper Functions
################################################################################


def _to_err_msg(*args) -> str:

    return f"{__TAG} Error: {' '.join(args)}"

def _log_err(*args, **kwargs):

    # printe -> prints to stderr with ISO timestamp and module name
    printe(_to_err_msg(*args), **kwargs)


def _log(*args, **kwargs):

    # printd -> prints to stdout with ISO timestamp and module name
    printd(__TAG, *args, **kwargs)


def _to_datetime(timestamp:Union[None, datetime, str, int, float]) -> datetime:

    if isinstance(timestamp, datetime):

        return timestamp
    if timestamp is None:

        return datetime.now()
    if isinstance(timestamp, str):

        return parser.parse(timestamp)
    if isinstance(timestamp, (int, float)):

        return datetime.fromtimestamp(timestamp)

    _log_err(f"expected 'timestamp' to be one of 'datetime', 'str', 'int', 'float' or 'None', got '{type(timestamp)}'",
        f"with value '{timestamp}', using datetime.now() instead")

    return datetime.now()



################################################################################
# Wiretap Data Transfer Object Section
################################################################################


class WiretapDTO(NamedTuple):

    """
    Immutable data transfer object with 'id', 'call', 'request', 'response' and
    'timestamp' fields.

    As efficient as a standard tuple but with type hints and attribute access
    through dot notation, i.e:

    ```
        wdto = WiretapDTO(34, 215, 'r-e-q', 'r-e-s', datetime.now())
        id_call = wdto.id * 1000 + wdto.call  # => 34215
    ```
    """
    uuid:str
    id:int
    call:int
    port:str
    request:str
    response:str
    timestamp:datetime




################################################################################
# Wiretap Transient Database Section
################################################################################


class WiretapStore:
    """
    Utitlity class for wiretap storage interfacing.
    """

    STORE_NAME = 'wiretap_data_v1.db'
    base_dir = os.path.dirname(os.path.abspath(__file__))
    PRE_STORE_PATH = os.path.join(base_dir, STORE_NAME)
    DEST_DIR = os.path.join(os.getenv('USERPROFILE'), 'wiretap_files', 'python-screen-app')
    STORE_PATH = os.path.join(DEST_DIR, STORE_NAME)
    print('STORE_PATH is: ',STORE_PATH)
    STORE_SPOT = 'recent'

    @staticmethod
    def copy_datastore_db_if_not_exists(src_path=None, dest_path=None):
        if src_path is None:
            src_path = WiretapStore.PRE_STORE_PATH
        if dest_path is None:
            dest_path = WiretapStore.STORE_PATH
        
        if not os.path.exists(dest_path):
            if os.path.exists(src_path):
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(src_path, dest_path)
                print(f'Copied {src_path} to {dest_path}')
            else:
                print(f'Source database not found at {src_path}')
        else:
            print(f'Database already exists at {dest_path}. No action taken.')

    @classmethod
    def clean_all_tables(cls):
        """
        Deletes all records from all tables in the database.
        """
        with cls.__connect() as db_con:
            db_cursor = db_con.cursor()
            tables = [cls.STORE_SPOT]  # Assuming only one table 'recent'
            for table in tables:
                db_cursor.execute(f"DELETE FROM {table}")
            db_con.commit()
            db_cursor.close()
        
        # Perform VACUUM outside the transaction block
        with cls.__connect() as db_con:
            db_cursor = db_con.cursor()
            db_cursor.execute("VACUUM")
            db_cursor.close()

    @classmethod
    def __check_tuple(cls, data:Tuple[str, int, int, str, str, str, Union[str, datetime]]) -> Tuple[str, int, int, str, str, str, datetime]:

        if isinstance(data, list):

            data = tuple(data)

        # sqlite requires a tuple
        if not isinstance(data, tuple):

            return None

        if len(data) == 6:

            # append datetime now to tuple if timestamp is missing
            data = data + (datetime.now(),)

        elif len(data) >= 7 and not isinstance(data[6], datetime):

            # convert data[3] to datetime and replace in tuple
            data = data[0:6] + (_to_datetime(data[6]), )

        return data


    @classmethod
    def __connect(cls, timeout:int=10) -> sqlite3.Connection:
        return sqlite3.connect(cls.STORE_PATH, timeout=timeout, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)


    ############################################################################
    # Storage Write Methods
    ############################################################################


    @classmethod
    def insert(cls, tup_or_uuid:Union[str, Tuple[str, int, int, str, str, str, Union[str, datetime]]], id:int = None, call:int = None, port:str = None, request:str = None, response:str = None, timestamp:Union[str, datetime] = None):
        """
        Updates a 'wiretap_data.db' database row with the given 'uuid', 'id', 'call', 'port',
        'request', 'response' and 'timestamp'. If no row exists in the database
        with the given 'uuid', then a new row will be inserted.

        If 'tup_or_uuid' is a tuple, then the following holds true:

         - The parameters 'request', 'response' and 'timestamp' will be ignored.
         - The tuple should be of length 6 or 7 with 'uuid' being index 0,
           'id' being index 1, 'call' being index 2, 'port' being index 3, 'request' being index 4,
           'response' being index 5, and 'timestamp' is
           optional but if given should be index 6.
         - If the tuple is of length 6, then 'datetime.now()' will be used as
           'timestamp'.

        If 'tup_or_uuid' is not a tuple, then the following holds true:

          - 'uuid' will be set to 'tup_or_uuid'.
          - 'timestamp' is optional, if omitted it will be set to
            'datetime.now()'.
        """

        if isinstance(tup_or_uuid, (tuple, list)):

            # check time in tuple and convert list to tuple
            entry = cls.__check_tuple(tup_or_uuid)

        else:


            if not(isinstance(tup_or_uuid, str)):

                exc_msg = _to_err_msg("in 'WiretapDatabase.insert', expected parameter 'tup_or_uuid' to be of type",
                    f"'tuple' or 'list', or a parsable integer, got '{type(tup_or_uuid)}' with value '{tup_or_uuid}'")
                
                raise TypeError(exc_msg) from None

            entry = (tup_or_uuid, id, call, port, request, response, _to_datetime(timestamp))


        # with block handles closing db connection and rollbacks on error
        with cls.__connect() as db_con:

            db_cursor = db_con.cursor()

            cls.__insert(db_cursor, entry)

            # database is not locked and written to until commit
            db_con.commit()
            db_cursor.close()


    @classmethod
    def insert_dto(cls, dto:WiretapDTO):

        """
        Updates a 'wiretap_data.db' database row with the given Wiretap Data
        Transfer Object.
        """

        if not isinstance(dto, WiretapDTO):

            exc_msg = _to_err_msg("in 'WiretapDatabase.insert_dto', expected parameter 'dto' to be of type",
                    f"'WiretapDTO', got '{type(dto)}' with value '{dto}'")
            
            raise TypeError(exc_msg)

        # convert dto to tuple then insert
        cls.insert(cls.__dto_to_tuple(dto))


    @classmethod
    def __dto_to_tuple(cls, dto:WiretapDTO) -> Tuple[str, int, int, str, str, str, datetime]:
        
        return dto


    @classmethod
    def insert_many(cls, data:Iterable[Tuple[str, int, int, str, str, str, Union[str, datetime]]]):

        """
        Updates the 'wiretap_cur.db' database with each tuple or list in the
        iterable parameter 'data'. If a row with a tuple or list's 'uuid'
        does not exist in the database then a new row will be inserted.

        Each tuple or list should contain the following indexes and data:

         - [0]: the uuid of the data
         - [1]: the device id of the data
         - [2]: the call of the data
         - [3]: the port the data was retrieved from
         - [4]: the 'request' data.
         - [5]: the 'response' data.
         - [6]: optional, the timestamp as either a datetime, str, int or float.
         - If a tuple or list is of length 6, meaning timestamp was omitted,
           then 'datetime.now()' will be used.
        """
        # with block handles closing db connection and rollback on error
        with cls.__connect() as db_con:

            db_cursor = db_con.cursor()

            for entry in data:

                # if entry is a list then it will get converted to a tuple
                # in __check_tuple
                if not isinstance(entry, (tuple, list)):

                    exc_msg = _to_err_msg(f"in WiretapDatabase.insert_many: the parameter 'data' must be an iterable",
                        f"of tuples or lists, got type '{type(entry)}'")
                    
                    raise TypeError(exc_msg)

                # make sure entry tuple has a time
                entry = cls.__check_tuple(entry)
                cls.__insert(db_cursor, entry)

            # database is not locked and written-to until commit
            db_con.commit()
            db_cursor.close()


    @classmethod
    def insert_many_dto(cls, dto_list:Iterable[WiretapDTO]):

        """
        Updates the 'wiretap_cur.db' database with each Wiretap Data Transfer
        Object in the iterable parameter 'dto_list'.
        """

        # convert dto's to tuples
        dto_list = [cls.__dto_to_tuple(dto) for dto in dto_list]

        cls.insert_many(dto_list)


    @classmethod
    def __insert(cls, db_cursor:sqlite3.Cursor, data:Tuple[str, int, int, str, str, str, datetime]):
        # insert or replace handles missing row
        db_cursor.execute(f'''
            INSERT OR REPLACE INTO {cls.STORE_SPOT}
            (uuid, id, call, port, request, response, timestamp)
            VALUES
            (?, ?, ?, ?, ?, ?, ?)
        ''', data)


    ############################################################################
    # Storage Read Methods
    ############################################################################

    # modbus device id is a UINT8
    __MIN_DEVICE_ID = 0
    __MAX_DEVICE_ID = 255

    # named tuple used by __build_query and __query methods
    __QUERY = namedtuple('Query', ['string', 'params'])


    @classmethod
    def get_with_uuid(cls, uuid:Union[int, str], options:Dict[str, Union[str, int, datetime]] = None) -> Union[WiretapDTO, None]:
        
        """
        Gets a row from the 'wiretap_cur.db' database where the row's 'uuid'
        matches the given 'uuid'.

        The row's values will be returned as a WiretapDTO instance with the
        following [indexes|fields]:

         - [ 0|uuid           ]: the 'uuid' as an 'str'.
         - [ 1|id             ]: the 'id' id as an 'int'.
         - [ 2|call           ]: the 'call' id as an 'int'.
         - [ 3|port           ]: the 'port' as a 'str'.
         - [ 4|request        ]: the 'request' as a 'str'.
         - [ 5|response       ]: the 'response' as a 'str'.
         - [ 6|timestamp      ]: the 'timestamp' as a 'datetime'.

        If no row has an 'uuid' value that equals the given 'uuid', or the
        row is excluded by specified options then 'None' will be returned.

        The dict parameter 'options' can have the following key-value pairs:
         - 'before': a 'datetime', specifies to only include rows with a
            timestamp before some 'datetime'.
         - 'after': a 'datetime', specifies to only include rows with a
            timestamp after some 'datetime'.
        """

        # query database after type and value checks
        row = cls.__query_one(where = "uuid=?", params = (uuid,), options = options)

        return row


    @classmethod
    def get_all(cls, options:Dict[str, Union[str, int, datetime]] = None) -> Union[List[WiretapDTO], None]:
        
        """
        Gets all of the rows from the 'wiretap_cur.db' database as a list of
        WiretapDTO instances.

        Any rows will be returned as a list of WiretapDTO instances with the
        following [indexes|fields]:

         - [ 0|uuid           ]: the 'uuid' as an 'str'.
         - [ 1|id             ]: the 'id' id as an 'int'.
         - [ 2|call           ]: the 'call' id as an 'int'.
         - [ 3|port           ]: the 'port' as a 'str'.
         - [ 4|request        ]: the 'request' as a 'str'.
         - [ 5|response       ]: the 'response' as a 'str'.
         - [ 6|timestamp      ]: the 'timestamp' as a 'datetime'.

        If there are no rows in the database or all rows are excluded by
        specified options, then 'None' will be returned.

        The dict parameter 'options' can have the following key-value pairs:
         - 'order': 'ASC' or 'DESC', case insensitive, specifies the order of
           the returned rows.
         - 'by': one of 'uuid' or 'timestamp', specifies the column to order
           by, 'request' and 'response' can also be used.
         - 'before': a 'datetime', specifies to only include rows with a
            timestamp before some 'datetime'.
         - 'after': a 'datetime', specifies to only include rows with a
            timestamp after some 'datetime'.
         - 'limit': a parseable 'int', specifies the max number of rows to
           return.
        """

        rows = cls.__query_many(options = options)

        return rows


    @classmethod
    def get_all_with_id_from_port(cls, id:Union[int, str], port:str, options:Dict[str, Union[str, int, datetime]] = None) -> Union[List[WiretapDTO], None]:
        
        """
        Gets all of the rows from the 'wiretap_cur.db' database where a row's
        'id' equals the given 'id', in other
        words this method returns all of the rows pertaining to a device.

        Any rows will be returned as a list of WiretapDTO instances with the
        following [indexex|fields]:

         - [ 0|uuid           ]: the 'uuid' as an 'str'.
         - [ 1|id             ]: the 'id' id as an 'int'.
         - [ 2|call           ]: the 'call' id as an 'int'.
         - [ 3|port           ]: the 'port' as a 'str'.
         - [ 4|request        ]: the 'request' as a 'str'.
         - [ 5|response       ]: the 'response' as a 'str'.
         - [ 6|timestamp      ]: the 'timestamp' as a 'datetime'.

        If no rows have an 'id' value that that matches the given one, or
        all matched rows are excluded by specified options, then 'None' will be
        returned.

        The dict parameter 'options' can have the following key-value pairs:
         - 'order': 'ASC' or 'DESC', case insensitive, specifies the order of
           the returned rows by the 'call' portion of 'id_call'.
         - 'by': one of 'id_call' or 'timestamp', specifies the column to order
           by, 'request' and 'response' can also be used.
         - 'before': a 'datetime', specifies to only include rows with a
            timestamp before some 'datetime'.
         - 'after': a 'datetime', specifies to only include rows with a
            timestamp after some 'datetime'.
         - 'limit': a parseable 'int', specifies the max number of rows to
           return.
        """

        try:

            id = int(id)

        except BaseException as e:

            exc_msg = _to_err_msg(f"in WiretapDatabase.get_all_from_id: expected parameter 'id' to be a parsable",
                f"integer, got '{type(id)}' with value '{id}'")
            
            raise TypeError(exc_msg) from None

        # id can't be negative
        if id < cls.__MIN_DEVICE_ID:

            exc_msg = _to_err_msg(f"in WiretapDatabase.get_all_from_id: parameter 'id' cannot be less than",
                 f"'{cls.__MIN_DEVICE_ID}', got '{id}'")

            raise ValueError(exc_msg) from None

        # id can't be greater than 255
        if id > cls.__MAX_DEVICE_ID:

            exc_msg = _to_err_msg(f"in WiretapDatabase.get_all_from_id: parameter 'id' cannot be greater than",
                f"'{cls.__MAX_DEVICE_ID}', got '{id}'")

            raise ValueError(exc_msg) from None

        # query database after type and value checks
        rows = cls.__query_many(where = "id=? AND port=?", params = (id, port,), options = options)

        return rows


    @classmethod
    def __query_one(cls, **kwargs) -> Union[WiretapDTO, None]:

        query = cls.__build_query(**kwargs)

        rows = cls.__query(query)

        if not len(rows):

            return None

        return cls.__row_to_dto(rows[0])


    @classmethod
    def __query_many(cls, **kwargs) -> Union[List[WiretapDTO], None]:

        query = cls.__build_query(**kwargs)

        rows = cls.__query(query)

        if not len(rows):

            return None

        # extrapolate id and call from rows and convert row tuples to DTOs
        rows_as_dtos = [cls.__row_to_dto(row) for row in rows]

        return rows_as_dtos


    @classmethod
    def __row_to_dto(cls, row:tuple) -> WiretapDTO:

        return WiretapDTO(*row)

    @classmethod
    def __query(cls, query:__QUERY) -> List[tuple]:

        res = []

        with cls.__connect() as db_con:

            db_con.row_factory = sqlite3.Row
            db_cursor = db_con.cursor()

            if query.params is None:

                # simple query, don't need to '?' escape parameters
                db_cursor.execute(query.string)

            else:

                # '?' escape parameters were given
                db_cursor.execute(query.string, query.params)

            res = db_cursor.fetchall()
            db_cursor.close()

        return res


    @classmethod
    def __build_query(cls, select:str='*', where:str=None, group_by:str=None, order_by:str=None, limit:int=None, params:tuple=None, options:dict=None) -> __QUERY:

        if options:

            escape_count = (select or '').count('?') + (where or '').count('?')

            if 'before' in options:

                # insert before option into escaped query params tuple
                params = cls.__add_param(params, options['before'], escape_count)
                # update where clause for before
                where = f"{where or ''}{not where or ' AND'} timestamp < ?"
                escape_count += 1

            if 'after' in options:

                escape_count = (select or '').count('?') + (where or '').count('?')
                # insert after option into escaped query params tuple
                params = cls.__add_param(params, options['after'], escape_count)
                # update where clause for after
                where = f"{where or ''}{not where or ' AND'} timestamp > ?"
                escape_count += 1

            by = options.get('by', None)

            if by:

                order_by = "?"
                params = cls.__add_param(params, by, escape_count)
                escape_count += 1

            if 'order' in options:

                # use id_call when 'by' not given
                order_by = "? ?" if by else f"id_call ?"
                params = cls.__add_param(params, options['order'], escape_count)
                escape_count += 1

            if 'limit' in options:

                limit = '?'
                # add limit option to end of escaped query params tuple
                params = cls.__add_param(params, options['limit'])
                escape_count += 1 # don't really need to do this


        # piece together the database query
        query_str = 'SELECT {sel} FROM {table}{whr}{grp}{ord}{lim}'.format(

            sel=select,
            table=cls.STORE_SPOT,
            whr=f" WHERE {where}" if where else '',
            grp=f" GROUP BY {group_by}" if group_by else '',
            ord=f" ORDER BY {order_by}" if order_by else '',
            lim=f" LIMIT {limit}" if limit else ''

        )

        # return an instance of the __QUERY namedtuple
        return cls.__QUERY(query_str, params)


    @classmethod
    def __add_param(cls, params:tuple, to_add, at_idx:int=None) -> tuple:

        if not params:

            return (to_add,)

        if at_idx is not None:

            # adding to end of params tuple
            return params + (to_add,)

        # inserting something in to params tuple
        return params[0:at_idx] + (to_add,) + params[at_idx:]


    ############################################################################
    # Database Init Method
    ############################################################################

    @classmethod
    def __init(cls):

        db_already_exists = os.path.isfile(cls.STORE_PATH)

        # creates database if it does not exist
        with cls.__connect() as db_con:

            db_cursor = db_con.cursor()

            # creates table if it does not exist
            db_cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {cls.STORE_SPOT}
                (uuid TEXT PRIMARY KEY,
                id INTEGER,
                call INTEGER,
                port TEXT,
                request TEXT,
                response TEXT,
                timestamp TIMESTAMP)
            ''')

            # database is not locked and written-to until this point
            db_con.commit()
            db_cursor.close()

        if not os.path.isfile(cls.STORE_PATH):

            exc_msg = _to_err_msg(f"the sqlite3 database '{cls.STORE_PATH}' does not exist, meaning something went",
                "wrong when creating the database")
            raise FileNotFoundError(exc_msg)

        elif not db_already_exists:

            _log(f"Successfully created the '{cls.STORE_NAME}' database and '{cls.STORE_SPOT}' table")



# create database and table if it does not exist, this gets called on import
WiretapStore._WiretapStore__init()
