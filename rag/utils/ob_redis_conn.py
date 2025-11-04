import collections
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import trio
from peewee import IntegrityError, ProgrammingError

from api.db.db_models import RetryingPooledMySQLDatabase
from api.utils.configs import decrypt_database_config
from rag.utils.redis_able import RedisAble

DATABASE = None


def get_db():
    global DATABASE
    if DATABASE is not None:
        return DATABASE
    database_config = decrypt_database_config(name="mysql").copy()
    db_name = database_config.pop("name")
    logging.debug(f"use ob mysql to mock redis, db_name:{db_name}")
    DATABASE = RetryingPooledMySQLDatabase(db_name, **database_config)
    return DATABASE


# 由于这里数据库 message 返回值是str,而 redis_conn stream 接口返回的是 dict,所以 RedisMsg 接口初始化略有不同，因此单独声明一个 RedisMsg
class RedisMsg:
    def __init__(self, consumer, queue_name, group_name, msg_id, message):
        self.__consumer = consumer
        self.__queue_name = queue_name
        self.__group_name = group_name
        self.__msg_id = str(msg_id)
        self.__message = json.loads(message)["message"]

    def ack(self):
        try:
            self.__consumer.xack(self.__queue_name, self.__group_name, self.__msg_id)
            return True
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning("[EXCEPTION]ack" + str(self.__queue_name) + "||" + str(e))
        return False

    def get_message(self):
        return self.__message

    def get_msg_id(self):
        return self.__msg_id


def is_table_missing_exception(e):
    return isinstance(e, ProgrammingError) and e.args[0] == 1146


class OceanBaseRedisDb(RedisAble):
    """
        基于 OceanBase 的 Redis 接口，主要包含：
            1 基本KV 操作
            2 set
            3 sorted set (zset）
            4 redis stream
        依赖 GET_LOCK 和 RELEASE_LOCK 语法，因此要求 OB 版本大于 4.3.5.0
        理论上也可以在 Mysql 8.0 上运行
        set 和 zset 这部分目前对性能要求不高，暂时使用锁实现, 后续可以改为表实现
    """

    def __init__(self, db=None):
        self.db = db if db else get_db()

    def register_scripts(self) -> None:
        raise NotImplementedError("Not implemented")

    def health(self):
        try:
            self.db.execute_sql("select 1 from dual")
            return True
        except Exception:
            return False

    def is_alive(self):
        return self.health()

    def exist(self, k):
        if not self.db:
            return
        try:

            cursor = self.db.execute_sql('select count(1) from cache where cache_key = %s and expire_time > now()', (k))

            ret = cursor.fetchone()
            return ret[0] == 1
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning("RedisDB.exist " + str(k) + " got exception: " + str(e))

    def delete_if_equal(self, key: str, expected_value: str) -> bool:
        try:
            cursor = self.db.execute_sql('delete from cache where cache_key = %s and cache_value = %s and expire_time '
                                         '> now()', (key, expected_value))
            return cursor.rowcount == 1
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning(
                    "RedisDB.delete_if_equal " + str(key) + ":" + str(expected_value) + " got exception: " + str(e))
            return False

    def delete(self, key) -> bool:
        try:
            self.db.execute_sql('delete from cache where cache_key = %s ', (key))
            return True
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning("RedisDB.delete " + str(key) + " got exception: " + str(e))
        return False

    def deleteIfExpired(self, key) -> bool:
        try:
            self.db.execute_sql('delete from cache where cache_key = %s and expire_time < now() ', key)
            return True
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning("RedisDB.delete " + str(key) + " got exception: " + str(e))
        return False

    def get(self, k):
        if not self.db:
            return None
        try:
            cursor = self.db.execute_sql('select cache_value from cache '
                                         'where cache_key = %s and expire_time > now()', k)
            ret = cursor.fetchone()
            return ret[0] if ret else None
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning("RedisDB.get " + str(k) + " got exception: " + str(e))

    def set_obj(self, k, obj, exp=3600):
        try:
            self.set_object(k, obj, exp)
            return True
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning("RedisDB.set_obj " + str(k) + " got exception: " + str(e))
        return False

    def set_object(self, k, obj, exp=3600):
        expire_time = datetime.now() + timedelta(seconds=exp)
        self.db.execute_sql('replace into cache (cache_key, cache_value, expire_time) values (%s, %s, %s)',
                            (k, json.dumps(obj, ensure_ascii=False), expire_time))
        return True

    def set(self, k, v, exp=3600):
        try:
            expire_time = datetime.now() + timedelta(seconds=exp)
            self.db.execute_sql('replace into cache (cache_key, cache_value, expire_time) values (%s, %s, %s)',
                                (k, v, expire_time))
            return True
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning("RedisDB.set " + str(k) + " got exception: " + str(e))
        return False

    def setNx(self, k, v, exp=3600):
        try:
            # 删除过期的kv
            self.deleteIfExpired(k)
            expire_time = datetime.now() + timedelta(seconds=exp)
            self.db.execute_sql('insert into cache (cache_key, cache_value, expire_time) values (%s, %s, %s)',
                                (k, v, expire_time))
            return True
        except IntegrityError:
            pass
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning("RedisDB.setNx " + str(k) + " got exception: " + str(e))
        return False

    # 本项目中并未用到 pipeline ，其实作用相当于 setNx
    def transaction(self, key, value, exp=3600):
        return self.setNx(key, value, exp)

    # zset
    def zadd(self, key: str, member: str, score: float):
        try:
            with self.db.atomic():
                cursor = self.db.execute_sql("select id, cache_value from cache where cache_key = %s and expire_time > "
                                             "now() for update wait 3", key)
                ret = cursor.fetchone()
                if ret is None:
                    mp = {member: score}
                    return self.set_object(key, mp)
                else:
                    id = ret[0]
                    cursor = self.db.execute_sql(
                        "update cache set cache_value = JSON_MERGE_PATCH(cache_value, %s) where id = %s",
                        (json.dumps({member: score}), id))
                    ret = cursor.rowcount
                    if ret == 1:
                        return True
                    else:
                        return False
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning("RedisDB.zadd " + str(key) + " got exception: " + str(e))
            return False

    def zcount(self, key: str, min, max: float):
        try:
            cursor = self.db.execute_sql(
                "SELECT COUNT(*) FROM JSON_TABLE((SELECT cache_value FROM cache WHERE cache_key = %s and expire_time > now() ), '$.*' COLUMNS(value FLOAT PATH '$')) AS jt WHERE value BETWEEN %s AND %s",
                (key, min, max))
            ret = cursor.fetchone()
            if ret is None:
                return 0
            else:
                return ret[0]
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning("RedisDB.zcount " + str(key) + " got exception: " + str(e))
            return 0

    def zpopmin(self, key: str, count: int):
        try:
            with self.db.atomic() as trx:
                cursor = self.db.execute_sql(
                    "select cache_value from cache where cache_key = %s and expire_time > now() for update wait 3 ",
                    key)
                ret = cursor.fetchone()
                if ret is None:
                    return None
                else:
                    mp = json.loads(ret[0])
                    sorted_map = collections.OrderedDict(sorted(mp.items(), key=lambda x: x[1]))
                    ret = {}
                    for k, v in sorted_map.items():
                        ret[k] = v
                        if len(ret) == count:
                            break
                    for k, v in ret.items():
                        del mp[k]
                    self.set_object(key, mp)
                    return ret
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning("RedisDB.zpopmin " + str(key) + " got exception: " + str(e))
            return None

    def sadd(self, key: str, member: str):
        try:
            with self.db.atomic():
                cursor = self.db.execute_sql("select cache_value from cache where cache_key = %s and expire_time > "
                                             "now() for update wait 3", key)
                ret = cursor.fetchone()
                if ret is None:
                    st = {member}
                    return self.set_object(key, list(st))
                else:
                    st = set(json.loads(ret[0]))
                    st.add(member)
                    return self.set_obj(key, list(st))
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning("RedisDB.sadd " + str(key) + " got exception: " + str(e))
            return False

    def srem(self, key: str, member: str):
        try:
            with self.db.atomic():
                cursor = self.db.execute_sql("select cache_value from cache where cache_key = %s and expire_time > "
                                             "now() for update wait 3", key)
                ret = cursor.fetchone()
                if ret is None:
                    return True
                else:
                    st = set(json.loads(ret[0]))
                    st.discard(member)
                    return self.set_object(key, list(st))
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning("RedisDB.srem " + str(key) + " got exception: " + str(e))
            return False

    def smembers(self, key: str):
        try:
            cursor = self.db.execute_sql("select cache_value from cache where cache_key = %s and expire_time > "
                                         "now()", key)
            ret = cursor.fetchone()
            if ret is None:
                return []
            else:
                return json.loads(ret[0])
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning("RedisDB.smembers " + str(key) + " got exception: " + str(e))
            return []

    def zrangebyscore(self, key: str, min: float, max: float):
        try:
            cursor = self.db.execute_sql("select cache_value from cache where cache_key = %s and expire_time > now() ",
                                         key)
            ret = cursor.fetchone()
            if ret is None:
                return None
            else:
                mp = json.loads(ret[0])
                ret = []
                for k, v in mp.items():
                    if min <= v <= max:
                        ret.append(k)
                ret.sort()
                return ret
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning("RedisDB.zrangebyscore " + str(key) + " got exception: " + str(e))
            return None

    # 以下是redis stream
    def queue_product(self, queue, message) -> bool:
        """
            向消息队列推送消息，如果消息队列不存在，则创建消息队列
        """
        for _ in range(3):
            try:
                payload = {"message": message}
                self.db.execute_sql("insert into message (stream, message) values(%s, %s)",
                                    (queue, json.dumps(payload)))
                return True
            except Exception as e:
                if is_table_missing_exception(e):
                    pass
                else:
                    logging.exception(
                        "RedisDB.queue_product " + str(queue) + " got exception: " + str(e)
                    )
        return False

    def queue_consumer(self, queue_name, group_name, consumer_name, msg_id=b">"):
        """
            消费者拉取消息：
                若不存在消费者组，则创建订阅关系
                若 msg_id 不传，或者传的是 ">", 则拉取该队列最新的消息
                若 msg_id 传的是一个非负整数，则拉取消费者 {consumer_name} 已经读取但没有 ack 的消息
            具体参考：https://redis.io/docs/latest/commands/xreadgroup/
        """
        try:
            try:
                cursor = self.db.execute_sql("select id from message where stream = %s limit 1", queue_name)
                ret = cursor.fetchone()
                if ret is None:
                    logging.debug(f"RedisDB.queue_consumer queue {queue_name} doesn't exist")
                    return None
                cursor = self.db.execute_sql("select id from message_subscribe where stream = %s"
                                             " and group_name = %s limit 1", (queue_name, group_name))
                ret = cursor.fetchone()
                if ret is None:
                    logging.warning(
                        f"RedisDB.queue_consumer queue-consumer_group {queue_name}{group_name} doesn't exist")
                    # 如果该消费者组没有订阅该消息，则新生成订阅关系
                    with self.db.atomic():
                        self.db.execute_sql("replace into message_subscribe (stream, group_name, consumer_name) "
                                            "values (%s, %s, %s)", (queue_name, group_name, consumer_name))
                        # 生成订阅关系时生成一条 message_id 为 -1 的消费历史，以便后续查询
                        self.db.execute_sql("replace into message_consumption "
                                            "(stream, group_name, consumer_name, message_id, ack) "
                                            "values (%s, %s, %s, %s, %s)",
                                            (queue_name, group_name, consumer_name, -1, True))
            except Exception as e:
                if is_table_missing_exception(e):
                    pass
                else:
                    logging.warning(f"RedisDB.get_unacked_iterator queue {queue_name}-{group_name} failed " + str(e))

            # 最大取一条记录
            if msg_id == b">":
                # 锁记录，防止重复消费
                # 获取没有被任何消费者消费的消息
                with self.db.atomic():
                    self.db.execute_sql("select id from message_subscribe where stream = %s for update wait 3"
                                        , queue_name)
                    cursor = self.db.execute_sql("select id,message from message where stream = %s "
                                                 "and consumed = false order by id asc limit %s", (queue_name, 1))
                    ret = cursor.fetchone()
                    if ret is None:
                        return None
                    else:
                        message_id = ret[0]
                        self.db.execute_sql("update message set consumed = true where id = %s", message_id)
                        self.db.execute_sql("insert into message_consumption "
                                            "(stream, group_name, consumer_name, message_id)"
                                            "values (%s, %s, %s, %s)",
                                            (queue_name, group_name, consumer_name, message_id))
                        message = ret[1]
                        logging.debug(
                            f'*** xreadgroup {queue_name}-{group_name}-{consumer_name}-{msg_id}-{message}-{type(message)}')
                        res = RedisMsg(self, queue_name, group_name, message_id, message)
                        return res
            else:
                # 获取没有ack的消息
                self.db.execute_sql("select id from message_subscribe where stream = %s for update wait 3", queue_name)
                with self.db.atomic():
                    cursor = self.db.execute_sql(
                        "select H.message_id, M.message from "
                        "( select consumer_name, message_id "
                        "   from message_consumption where stream = %s and group_name = %s and ack = false "
                        "     and consumer_name = %s and message_id > %s order by message_id limit 1"
                        ") H left join message M on H.message_id = M.id",
                        (queue_name, group_name, consumer_name, msg_id))
                    ret = cursor.fetchone()
                    if ret is None:
                        return None
                    else:
                        message_id = ret[0]
                        message = ret[1]
                        logging.debug(
                            f'*** xreadgroup {queue_name}-{group_name}-{consumer_name}-{msg_id}-{message}-{type(message)}')
                        res = RedisMsg(self, queue_name, group_name, message_id, message)
                        return res
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.exception(
                    "RedisDB.queue_consumer "
                    + str(queue_name)
                    + " got exception: "
                    + str(e)
                )
        return None

    def get_pending_msg(self, queue, group_name):
        """
            获取消费者组 {group_name} 对消息队列 {queue} 已经读取，但是没有 ACK 的消息。
            返回 dict 接口，包含信息：
                1 消息 ID
                2 读取该消息的消费者
                3 该消息读取后到现在的时间（time_since_delivered）
        """
        try:
            cursor = self.db.execute_sql(
                "select consumer_name, message_id, time_to_usec(create_date)/1000"
                " from message_consumption where stream = %s "
                "and group_name = %s and ack = false order by message_id limit 10"
                , (queue, group_name))
            pending_messages = cursor.fetchall()
            ret = []
            if len(pending_messages) > 0:
                logging.debug(f'*** xpending_range {queue}-{group_name}-{pending_messages}-{type(pending_messages)}')
                for r in pending_messages:
                    mp = dict()
                    mp['consumer'] = r[0]
                    mp['message_id'] = r[1]
                    mp['time_since_delivered'] = float((Decimal(time.time() * 1000) - r[2]))
                    ret.append(mp)
            return ret
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning(
                    "RedisDB.get_pending_msg " + str(queue) + " got exception: " + str(e)
                )
        return []

    # 获取本消费组内没有 ack的消息
    def get_unacked_iterator(self, queue_names: list[str], group_name, consumer_name):
        """
            获取消费者组未 ack 的消息，返回一个迭代器
        """
        try:
            for queue_name in queue_names:
                try:
                    cursor = self.db.execute_sql("select id from message where stream = %s limit 1", queue_name)
                    ret = cursor.fetchone()
                    if ret is None:
                        logging.warning(f"RedisDB.get_unacked_iterator queue {queue_name} doesn't exist")
                        continue
                    cursor = self.db.execute_sql("select id from message_subscribe where stream = %s"
                                                 " and group_name = %s limit 1", (queue_name, group_name))
                    ret = cursor.fetchone()
                    if ret is None:
                        logging.warning(f"RedisDB.get_unacked_iterator "
                                        f"queue-subscribe {queue_name}-{group_name} doesn't exist")
                        continue
                except Exception as e:
                    if is_table_missing_exception(e):
                        pass
                    else:
                        logging.warning(
                            f"RedisDB.get_unacked_iterator queue {queue_name}-{group_name} failed " + str(e))
                current_min = 0
                while True:
                    payload = self.queue_consumer(queue_name, group_name, consumer_name, current_min)
                    logging.debug(
                        f'*** queue_consumer {queue_name}-{group_name}-{consumer_name}-{payload}-{type(payload)}')
                    if not payload:
                        break
                    current_min = payload.get_msg_id()
                    logging.info(f"RedisDB.get_unacked_iterator {queue_name} {consumer_name} {current_min}")
                    yield payload
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.exception(
                    "RedisDB.get_unacked_iterator got exception: "
                )

    '''
        消息重新入队
    '''

    def requeue_msg(self, queue: str, group_name: str, msg_id: object):
        """
            将未 ack 的消息重新入队列
            将旧消息 ack 掉
        """
        try:
            with self.db.atomic():
                # 如果性能不好 这里的锁可以去掉，理论上不会存在并发更新同一个 msg_id 的场景
                cursor = self.db.execute_sql("select id from message where id = %s for update wait 3", msg_id)
                ret = cursor.fetchone()
                if ret is None:
                    return
                self.db.execute_sql("insert into message (stream, message) select stream, message from message "
                                    "where id = %s", msg_id)
                self.db.execute_sql(
                    "update message_consumption set ack = true where stream = %s and group_name = %s and "
                    "message_id = %s", (queue, group_name, msg_id))
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning(
                    "RedisDB.requeue_msg " + str(queue) + " got exception: " + str(e)
                )

    def xack(self, queue: str, group_name: str, msg_id: object):
        """
            提交消息 ack
        """
        self.db.execute_sql(
            "update message_consumption set ack = true where stream = %s and group_name = %s and "
            "message_id = %s", (queue, group_name, msg_id))

    def queue_info(self, queue: str, group_name: str) -> dict | None:
        """
            获取消息队列，某个消费者组的消费情况。本项目用到的属性有：
                1 消费者组名
                2 消费者组未读取的消息数
                3 消费者已经读取 但没有 ack 的消息数目
            出于性能考虑，其他 redis 接口提供的属性暂未实现
        """
        try:
            with self.db.atomic():
                cursor = self.db.execute_sql(
                    "select count(1) from message_subscribe where stream = %s and group_name = %s", (queue, group_name))
                ret = cursor.fetchone()
                if ret == 0:
                    return None
                else:
                    cursor = self.db.execute_sql(
                        "select count(1) from message_consumption where stream = %s and group_name = %s  and ack = "
                        "false and message_id > 0", (queue, group_name))
                    pending = cursor.fetchone()
                    cursor = self.db.execute_sql(
                        "select count(1) from message where stream = %s and id > (select message_id from "
                        "message_consumption where stream = %s and group_name = %s order by message_id "
                        "desc limit 1)", (queue, queue, group_name))
                    lag = cursor.fetchone()
                    group_info = dict()
                    group_info["name"] = group_name
                    group_info["lag"] = lag[0]
                    group_info["pending"] = pending[0]
                    # 封装lag, pending 信息
                    return group_info
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning(
                    "RedisDB.queue_info " + str(queue) + " got exception: " + str(e)
                )
        return None


class MysqlDistributedLock:
    """
        基于关系数据库提供的分布式锁
    """

    def __init__(self, lock_key, lock_value=None, timeout=10, blocking_timeout=1):
        self.db = get_db()
        self.lock_key = lock_key
        if lock_value:
            self.lock_value = lock_value
        else:
            self.lock_value = str(uuid.uuid4())
        self.timeout = timeout
        # blocking_timeout 没用到，预留
        self.blocking_timeout = blocking_timeout

    def acquire(self):
        """
            获取锁
        """
        logging.debug(f"acquire:{self.lock_key}-{self.lock_value}")
        self.delete_if_equal()
        return self.doAcquire()

    async def spin_acquire(self):
        """
            轮训获取锁
        """
        logging.debug(f"spin_acquire:{self.lock_key}-{self.lock_value}")
        self.delete_if_equal()
        while True:
            if self.doAcquire():
                break
            await trio.sleep(10)

    def doAcquire(self):
        """
            以 insert 方式加锁，若冲突说明锁已经存在
        """
        logging.debug(f"do acquire:{self.lock_key}-{self.lock_value}")
        sql = 'insert into cache (cache_key, cache_value, expire_time) values (%s, %s, %s)'
        try:
            expire_time = datetime.now() + timedelta(seconds=self.timeout)
            cursor = self.db.execute_sql(sql, (self.lock_key, self.lock_value, expire_time))
            ret = cursor.rowcount
            if ret == 1:
                logging.debug(f"get lock:{self.lock_key}-{self.lock_value}")
                return True
            else:
                return False
        except IntegrityError:
            return False
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.info(f"lock acquire failed:{self.lock_key}-{self.lock_value}-{e}")
            return False

    def release(self):
        """
            释放锁
        """
        logging.debug(f"release:{self.lock_key}-{self.lock_value}")
        self.delete_if_equal()

    def delete_if_equal(self):
        """
            只有在 key 和 value 均匹配时，释放锁
        """
        try:
            logging.debug(f"delete_if_equal:{self.lock_key}-{self.lock_value}")
            sql = 'delete from cache where cache_key = %s and (cache_value= %s or expire_time < now())'
            cursor = self.db.execute_sql(sql, (self.lock_key, self.lock_value))
            ret = cursor.rowcount
            if ret == 1:
                logging.debug(f"delete lock success:{self.lock_key}-{self.lock_value}")
                return True
            else:
                return False
        except Exception as e:
            if is_table_missing_exception(e):
                pass
            else:
                logging.warning(f"release lock failed:{self.lock_key}-{self.lock_value}-{e}")
            return False


if __name__ == '__main__':
    database = get_db()
    cache = OceanBaseRedisDb(db=database)

    # test redis stream
    print("* test redis stream")
    # generate a random stream name
    stream = "stream" + str(time.time())
    # send a new message
    print("     ** test enqueue")
    cache.queue_product(stream, {"a": "hello"})
    cache.queue_product(stream, {"a": "hello world"})
    cache.queue_product(stream, {"a": "hello world ragflow"})
    # test read the latest message
    print("     ** test dequeue")
    print("         ** test dequeue, read un read message")
    msg = cache.queue_consumer(stream, 'group6', 'consumer1', b">")
    assert (msg is not None)
    assert (msg.get_message()['a'] == "hello")
    msg = cache.queue_consumer(stream, 'group6', 'consumer1', b">")
    assert (msg is not None)
    assert (msg.get_message()['a'] == "hello world")
    # test read pending message
    print("         ** test dequeue, read pending message")
    msg = cache.queue_consumer(stream, 'group6', 'consumer1', b"0")
    assert (msg is not None)
    assert (msg.get_message()['a'] == "hello")
    msg_list = cache.get_pending_msg(stream, 'group6')
    assert (msg is not None)
    assert (len(msg_list) == 2)
    print(msg_list)
    assert (msg_list[0]['consumer'] == "consumer1")

    print("     ** get_unacked_iterator")
    msg = cache.queue_consumer(stream, 'group8', 'consumer1', b'0')
    assert (msg is None)
    msg = cache.queue_consumer(stream, 'group8', 'consumer1', b">")
    assert (msg is not None)
    it = cache.get_unacked_iterator([stream], 'group8', 'consumer1')
    msg = next(it)
    assert (msg is not None)
    assert (msg.get_message()['a'] == "hello world ragflow")

    print("     ** test queue_info")
    queue_info = cache.queue_info(stream, 'group6')
    assert (queue_info['lag'] == 1)
    assert (queue_info['pending'] == 2)

    queue_info = cache.queue_info(stream, 'group8')
    assert (queue_info['lag'] == 0)
    assert (queue_info['pending'] == 1)
    print("     ** test message ack")
    msg.ack()
    queue_info = cache.queue_info(stream, 'group8')
    assert (queue_info['lag'] == 0)
    assert (queue_info['pending'] == 0)

    # test set
    print("* test set")
    print("     ** test sadd")
    cache.sadd('set', 'a')
    cache.sadd('set', 'b')
    cache.sadd('set', 'c')
    cache.sadd('set', 'b')
    print("     ** test smembers")
    print(cache.smembers('set'))
    print("     ** test srem")
    print(cache.srem('set', 'b'))
    print(cache.smembers('set'))

    # test zset
    print("* test zset")
    print("     ** test zadd")
    cache.zadd('zset', '1', 1)
    cache.zadd('zset', '1', 1)
    cache.zadd('zset', '2', 2)
    cache.zadd('zset', '3', 3)
    cache.zadd('zset', '4', 4)
    cache.zadd('zset', '4', 5)
    print("     ** test get")
    print(cache.get('zset'))
    print("     ** test zcount")
    assert (cache.zcount('zset', 1, 2.75) == 2)
    print("     ** test zrangebyscore")
    print(cache.zrangebyscore('zset', 1, 3))
    assert (len(cache.zrangebyscore('zset', 1, 3)) == 3)
    print("     ** test zpopmin")
    print(cache.zpopmin('zset', 2))
    assert (cache.zcount('zset', 1, 2.75) == 0)
    print(cache.get('zset'))
    assert (len(cache.zrangebyscore('zset', 1, 3)) == 1)

    # test RedisDistributedLock

    print("* test RedisDistributedLock")
    suffix = str(time.time() % 3600)
    print(suffix)
    lock = MysqlDistributedLock('a' + suffix, lock_value='b', timeout=1)
    print("     ** test delete_if_equal")
    assert (not lock.delete_if_equal())
    print("     ** test acquire")
    assert (lock.acquire())
    lock = MysqlDistributedLock('a' + suffix, lock_value='bc', timeout=1)
    assert (not lock.acquire())
    time.sleep(5)
    assert (lock.acquire())
    print("     ** test release")
    lock.release()

    # test Key-Value Cache
    print("* test KV")
    print("     ** test setNx")
    assert (cache.setNx('setNx' + str(time.time() % 3600), 'b'))
    print("     ** test delete")
    cache.delete('key' + suffix)
    print("     ** test exist")
    assert (not cache.exist('key' + suffix))
    cache.set('key' + suffix, '123', exp=30)
    assert (cache.delete_if_equal('key' + suffix, '123'))
    assert (not cache.delete_if_equal('key' + suffix, '123'))
    assert (not cache.exist('key' + suffix))
    print("     ** test transaction")
    assert (cache.transaction('key' + suffix, 'value', exp=2))
    assert (not cache.transaction('key' + suffix, 'value', exp=2))
    time.sleep(5)
    assert (cache.transaction('key' + suffix, 'value', exp=2))
