from abc import abstractmethod
from typing import Any


class RedisAble:
    @abstractmethod
    def register_scripts(self) -> None:
        """
            load lua script to redis
        """
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def health(self) -> bool:
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def is_alive(self):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def exist(self, k):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def get(self, k):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def set_obj(self, k, obj, exp=3600):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def set(self, k, v, exp=3600):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def sadd(self, key: str, member: str):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def srem(self, key: str, member: str):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def smembers(self, key: str):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def zadd(self, key: str, member: str, score: float):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def zcount(self, key: str, min: float, max: float):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def zpopmin(self, key: str, count: int):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def zrangebyscore(self, key: str, min: float, max: float):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def transaction(self, key, value, exp=3600):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def queue_product(self, queue, message) -> bool:
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def queue_consumer(self, queue_name, group_name, consumer_name, msg_id=b">") -> Any:
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def get_unacked_iterator(self, queue_names: list[str], group_name, consumer_name):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def get_pending_msg(self, queue, group_name):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def requeue_msg(self, queue: str, group_name: str, msg_id: str):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def queue_info(self, queue, group_name) -> dict | None:
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def delete_if_equal(self, key: str, expected_value: str) -> bool:
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def delete(self, key) -> bool:
        raise NotImplementedError("Not implemented")
