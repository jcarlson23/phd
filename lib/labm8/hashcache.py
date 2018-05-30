"""A hash cache for the filesystem.

Checksums files and directories and cache results. If a file or directory has
not been modified, subsequent hashes are cache hits. Hashes are recomputed
lazily, when a directory (or any of its subdirectories) have been modified.
"""

import os
import pathlib
import time
import typing

import checksumdir
import humanize
import sqlalchemy as sql
from absl import flags
from absl import logging
from sqlalchemy.ext import declarative

from lib.labm8 import crypto
from lib.labm8 import fs
from lib.labm8 import sqlutil


FLAGS = flags.FLAGS

Base = declarative.declarative_base()


class HashCacheRecord(Base):
  """A hashed file or directory."""
  __tablename__ = 'entries'

  # The absolute path to a file or directory.
  absolute_path: str = sql.Column(sql.String(4096), primary_key=True)
  # The number of seconds since the epoch that the file or directory was last
  # modified.
  last_modified: int = sql.Column(sql.Integer, nullable=False)
  # The cached hash in hexadecimal encoding. We use the length of the longest
  # supported hash function: sha256.
  hash: str = sql.Column(sql.String(64), nullable=False)


def GetDirectoryMTime(path: pathlib.Path) -> int:
  """Get the timestamp of the most recently modified file/dir in directory.

  Recursively checks subdirectory contents.

  Params:
    abspath: The absolute path to the directory.

  Returns:
    The seconds since epoch of the last modification.
  """
  return int(max(
      max(os.path.getmtime(os.path.join(root, file)) for file in files) for
      root, _, files in os.walk(path)))


class HashCache(sqlutil.Database):

  def __init__(self, path: pathlib.Path, hash_fn: str):
    """Instantiate a hash cache.

    Args:
      path:
      hash_fn: The name of the hash function. One of: md5, sha1, sha256.

    Raises:
      ValueError: If hash_fn not recognized.
    """
    super(HashCache, self).__init__(path, Base)
    self.hash_fn_name = hash_fn
    if hash_fn == 'md5':
      self.hash_fn_file = crypto.md5_file
    elif hash_fn == 'sha1':
      self.hash_fn_file = crypto.sha1_file
    elif hash_fn == 'sha256':
      self.hash_fn_file = crypto.sha256_file
    else:
      raise ValueError(f"Hash function not recognized: '{hash_fn}'")

  def GetHash(self, path: pathlib.Path) -> str:
    """Get the hash of a file or directory.

    Note that the a file's mtime is used to determine cache hits. This uses
    second granularity, so if a file has been modified within a second, this
    method will erroneously return the cached checksum of the previous version.

    Args:
      path: Path to the file or directory.

    Returns:
      Hexadecimal string hash.

    Raises:
      FileNotFoundError: If the requested path does not exist.
    """
    if path.is_file():
      return self._HashFile(path)
    elif path.is_dir():
      return self._HashDirectory(path)
    else:
      raise FileNotFoundError(f"File not found: '{path}'")

  def Clear(self):
    """Empty the cache."""
    with self.Session(commit=True) as session:
      session.query(HashCacheRecord).delete()

  def _HashDirectory(self, absolute_path: pathlib.Path) -> str:
    if fs.directory_is_empty(absolute_path):
      last_modified = int(time.time())
    else:
      last_modified = GetDirectoryMTime(absolute_path)
    return self._DoHash(absolute_path, last_modified,
                        lambda x: checksumdir.dirhash(x, self.hash_fn_name))

  def _HashFile(self, absolute_path: pathlib.Path) -> str:
    return self._DoHash(absolute_path, int(os.path.getmtime(absolute_path)),
                        self.hash_fn_file)

  def _DoHash(self, absolute_path: pathlib.Path,
              last_modified: int,
              hash_fn: typing.Callable[[pathlib.Path], str]) -> str:
    with self.Session() as session:
      cached_entry = session.query(HashCacheRecord).filter(
          HashCacheRecord.absolute_path == str(absolute_path)).first()
      if cached_entry and cached_entry.last_modified == last_modified:
        logging.debug("Cache hit: '%s'", absolute_path)
        return cached_entry.hash
      elif cached_entry:
        logging.debug("Cache miss: '%s'", absolute_path)
        session.delete(cached_entry)
      start_time = time.time()
      checksum = hash_fn(absolute_path)
      logging.debug("New cache entry '%s' in %s ms.", absolute_path,
                    humanize.intcomma(int((time.time() - start_time) * 1000)))
      new_entry = HashCacheRecord(
          absolute_path=str(absolute_path),
          last_modified=last_modified,
          hash=checksum)
      session.add(new_entry)
      session.commit()
      return new_entry.hash