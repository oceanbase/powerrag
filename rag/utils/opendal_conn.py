import opendal
import logging
import pymysql
from urllib.parse import quote_plus

from common.config_utils import get_base_config
from common.decorator import singleton

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `{}` (
    `key` VARCHAR(255) PRIMARY KEY,
    `value` LONGBLOB,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
"""
SET_MAX_ALLOWED_PACKET_SQL = """
SET GLOBAL max_allowed_packet={}
"""


def get_opendal_config():
    try:
        opendal_config = get_base_config('opendal', {})
        if opendal_config.get("scheme", "mysql") == 'mysql':
            mysql_config = get_base_config('mysql', {})
            max_packet = mysql_config.get("max_allowed_packet", 134217728)
            kwargs = {
                "scheme": "mysql",
                "host": mysql_config.get("host", "127.0.0.1"),
                "port": str(mysql_config.get("port", 3306)),
                "user": mysql_config.get("user", "root"),
                "password": mysql_config.get("password", ""),
                "database": mysql_config.get("name", "test_open_dal"),
                "table": opendal_config.get("config", {}).get("oss_table", "opendal_storage"),
                "max_allowed_packet": str(max_packet)
            }
            kwargs[
                "connection_string"] = f"mysql://{kwargs['user']}:{quote_plus(kwargs['password'])}@{kwargs['host']}:{kwargs['port']}/{kwargs['database']}?max_allowed_packet={max_packet}"
        else:
            scheme = opendal_config.get("scheme")
            config_data = opendal_config.get("config", {})
            kwargs = {"scheme": scheme, **config_data}

        # Only include non-sensitive keys in logs. Do NOT
        # add 'password' or any key containing embedded credentials
        # (like 'connection_string').
        safe_log_info = {
            "scheme": kwargs.get("scheme"),
            "host": kwargs.get("host"),
            "port": kwargs.get("port"),
            "database": kwargs.get("database"),
            "table": kwargs.get("table"),
            # indicate presence of credentials without logging them
            "has_credentials": any(k in kwargs for k in ("password", "connection_string")),
        }
        logging.info("Loaded OpenDAL configuration (non sensitive fields only): %s", safe_log_info)
        return kwargs
    except Exception as e:
        logging.error("Failed to load OpenDAL configuration from yaml: %s", str(e))
        raise


@singleton
class OpenDALStorage:
    def __init__(self):
        self._kwargs = get_opendal_config()
        self._scheme = self._kwargs.get('scheme', 'mysql')
        if self._scheme == 'mysql':
            self.init_db_config()
            self.init_opendal_mysql_table()
        self._operator = opendal.Operator(**self._kwargs)

        logging.info("OpenDALStorage initialized successfully")

    def health(self):
        bucket, fnm, binary = "txtxtxtxt1", "txtxtxtxt1", b"_t@@@1"
        return self._operator.write(f"{bucket}/{fnm}", binary)

    def put(self, bucket, fnm, binary, tenant_id=None):
        self._operator.write(f"{bucket}/{fnm}", binary)

    def put_many(self, bucket, items, tenant_id=None, replace_on_conflict: bool = False, batch_size: int = 200):
        """
        Batch write many objects.

        For OpenDAL MySQL scheme, this uses a single MySQL connection and executemany to reduce round-trips.
        For other schemes, it falls back to individual writes.

        Args:
            bucket: Bucket / namespace
            items: Iterable of (fnm, binary)
            replace_on_conflict: If True, overwrite existing keys (upsert). If False, insert will error on duplicates.
            batch_size: Number of rows per executemany batch
        """
        items = list(items or [])
        if not items:
            return

        # Non-mysql backend: no native bulk write, fallback.
        if self._scheme != "mysql":
            for fnm, binary in items:
                self.put(bucket, fnm, binary, tenant_id=tenant_id)
            return

        table = self._kwargs["table"]
        if replace_on_conflict:
            sql = (
                f"INSERT INTO `{table}` (`key`, `value`) VALUES (%s, %s) "
                f"ON DUPLICATE KEY UPDATE `value`=VALUES(`value`), `updated_at`=CURRENT_TIMESTAMP"
            )
        else:
            sql = f"INSERT INTO `{table}` (`key`, `value`) VALUES (%s, %s)"

        conn = pymysql.connect(
            host=self._kwargs["host"],
            port=int(self._kwargs["port"]),
            user=self._kwargs["user"],
            password=self._kwargs["password"],
            database=self._kwargs["database"],
            autocommit=False,  # Explicitly disable autocommit for transaction control
        )
        try:
            with conn.cursor() as cursor:
                try:
                    for i in range(0, len(items), batch_size):
                        batch = items[i:i + batch_size]
                        params = [(f"{bucket}/{fnm}", binary) for fnm, binary in batch]
                        cursor.executemany(sql, params)
                    conn.commit()
                except pymysql.err.IntegrityError as e:
                    # If replace_on_conflict is True but we still get IntegrityError,
                    # it might be due to a race condition or transaction issue.
                    # Log the error and re-raise for caller to handle.
                    if replace_on_conflict:
                        logging.warning(
                            f"IntegrityError occurred despite replace_on_conflict=True. "
                            f"This may indicate a race condition or transaction issue. "
                            f"Error: {e}. Attempting rollback..."
                        )
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    raise
                except Exception as e:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    raise
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def get(self, bucket, fnm, tenant_id=None):
        return self._operator.read(f"{bucket}/{fnm}")

    def rm(self, bucket, fnm, tenant_id=None):
        self._operator.delete(f"{bucket}/{fnm}")
        self._operator.__init__()

    def scan(self, bucket, fnm, tenant_id=None):
        return self._operator.scan(f"{bucket}/{fnm}")

    def obj_exist(self, bucket, fnm, tenant_id=None):
        return self._operator.exists(f"{bucket}/{fnm}")

    def init_db_config(self):
        try:
            conn = pymysql.connect(
                host=self._kwargs['host'],
                port=int(self._kwargs['port']),
                user=self._kwargs['user'],
                password=self._kwargs['password'],
                database=self._kwargs['database']
            )
            cursor = conn.cursor()
            max_packet = self._kwargs.get('max_allowed_packet', 4194304)  # Default to 4MB if not specified
            cursor.execute(SET_MAX_ALLOWED_PACKET_SQL.format(max_packet))
            conn.commit()
            cursor.close()
            conn.close()
            logging.info(f"Database configuration initialized with max_allowed_packet={max_packet}")
        except Exception as e:
            logging.error(f"Failed to initialize database configuration: {str(e)}")
            raise

    def init_opendal_mysql_table(self):
        conn = pymysql.connect(
            host=self._kwargs['host'],
            port=int(self._kwargs['port']),
            user=self._kwargs['user'],
            password=self._kwargs['password'],
            database=self._kwargs['database']
        )
        cursor = conn.cursor()
        cursor.execute(CREATE_TABLE_SQL.format(self._kwargs['table']))
        conn.commit()
        cursor.close()
        conn.close()
        logging.info(f"Table `{self._kwargs['table']}` initialized.")
