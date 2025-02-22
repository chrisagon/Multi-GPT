"""Redis memory provider."""
from typing import Any, List, Optional

import numpy as np
import redis
from colorama import Fore, Style
from redis.commands.search.field import TextField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query

from autogpt.logs import logger
from multigpt.memory.base import MemoryProvider
from autogpt.llm_utils import create_embedding_with_ada

SCHEMA = [
    TextField("data"),
    VectorField(
        "embedding",
        "HNSW",
        {"TYPE": "FLOAT32", "DIM": 1536, "DISTANCE_METRIC": "COSINE"},
    ),
]


class RedisMemory(MemoryProvider):
    def __init__(self, cfg, ai_key):
        """
        Initializes the Redis memory provider.

        Args:
            cfg: The config object.

        Returns: None
        """
        redis_host = cfg.redis_host
        redis_port = cfg.redis_port
        redis_password = cfg.redis_password
        self.dimension = 1536
        self.ai_key = ai_key
        self.redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=0,  # Cannot be changed
        )
        self.cfg = cfg

        # Check redis connection
        try:
            self.redis.ping()
        except redis.ConnectionError as e:
            logger.typewriter_log(
                "FAILED TO CONNECT TO REDIS",
                Fore.RED,
                Style.BRIGHT + str(e) + Style.RESET_ALL,
            )
            logger.double_check(
                "Please ensure you have setup and configured Redis properly for use. "
                + f"You can check out {Fore.CYAN + Style.BRIGHT}"
                f"https://github.com/Torantulino/Auto-GPT#redis-setup{Style.RESET_ALL}"
                " to ensure you've set up everything correctly."
            )
            exit(1)

        if cfg.wipe_redis_on_start:
            self.redis.flushall()
        try:
            self.redis.ft(f"{cfg.memory_index}-agent-id-{ai_key}").create_index(
                fields=SCHEMA,
                definition=IndexDefinition(
                    prefix=[f"{cfg.memory_index}-agent-id-{ai_key}:"], index_type=IndexType.HASH
                ),
            )
        except Exception as e:
            print("Error creating Redis search index: ", e)
        existing_vec_num = self.redis.get(f"{cfg.memory_index}-agent-id-{ai_key}-vec_num")
        self.vec_num = int(existing_vec_num.decode("utf-8")) if existing_vec_num else 0

    def add(self, data: str) -> str:
        """
        Adds a data point to the memory.

        Args:
            data: The data to add.

        Returns: Message indicating that the data has been added.
        """
        if "Command Error:" in data:
            return ""
        vector = create_embedding_with_ada(data)
        vector = np.array(vector).astype(np.float32).tobytes()
        data_dict = {b"data": data, "embedding": vector}
        pipe = self.redis.pipeline()
        pipe.hset(f"{self.cfg.memory_index}-agent-id-{self.ai_key}:{self.vec_num}", mapping=data_dict)
        _text = (
            f"Inserting data into memory at index: {self.vec_num}:\n" f"data: {data}"
        )
        self.vec_num += 1
        pipe.set(f"{self.cfg.memory_index}-agent-id-{self.ai_key}-vec_num", self.vec_num)
        pipe.execute()
        return _text

    def get(self, data: str) -> Optional[List[Any]]:
        """
        Gets the data from the memory that is most relevant to the given data.

        Args:
            data: The data to compare to.

        Returns: The most relevant data.
        """
        return self.get_relevant(data, 1)

    def clear(self) -> str:
        """
        Clears the redis server.

        Returns: A message indicating that the memory has been cleared.
        """
        self.redis.flushall()
        return "Obliviated"

    def get_relevant(self, data: str, num_relevant: int = 5) -> Optional[List[Any]]:
        """
        Returns all the data in the memory that is relevant to the given data.
        Args:
            data: The data to compare to.
            num_relevant: The number of relevant data to return.

        Returns: A list of the most relevant data.
        """
        query_embedding = create_embedding_with_ada(data)
        base_query = f"*=>[KNN {num_relevant} @embedding $vector AS vector_score]"
        query = (
            Query(base_query)
            .return_fields("data", "vector_score")
            .sort_by("vector_score")
            .dialect(2)
        )
        query_vector = np.array(query_embedding).astype(np.float32).tobytes()

        try:
            results = self.redis.ft(f"{self.cfg.memory_index}-agent-id-{self.ai_key}").search(
                query, query_params={"vector": query_vector}
            )
        except Exception as e:
            print("Error calling Redis search: ", e)
            return None
        return [result.data for result in results.docs]

    def get_stats(self):
        """
        Returns: The stats of the memory index.
        """
        return self.redis.ft(f"{self.cfg.memory_index}").info()
