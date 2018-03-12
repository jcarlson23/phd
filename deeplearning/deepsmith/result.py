"""This file defines the result class."""
import binascii
import datetime
import hashlib
import pathlib
import typing

import sqlalchemy as sql
from sqlalchemy import orm

import deeplearning.deepsmith.profiling_event
import deeplearning.deepsmith.testbed
import deeplearning.deepsmith.testcase
from deeplearning.deepsmith import db
from deeplearning.deepsmith.proto import deepsmith_pb2

# The index types for tables defined in this file.
_ResultId = sql.Integer
_ResultOutputSetId = sql.Binary(16)  # MD5 checksum.
_ResultOutputId = sql.Integer
_ResultOutputNameId = db.StringTable.id_t
_ResultOutputValueId = sql.Integer


class Result(db.Table):
  id_t = _ResultId
  __tablename__ = "results"

  # Columns.
  id: int = sql.Column(id_t, primary_key=True)
  date_added: datetime.datetime = sql.Column(
      sql.DateTime, nullable=False, default=db.now)
  testcase_id: int = sql.Column(
      deeplearning.deepsmith.testcase.Testcase.id_t,
      sql.ForeignKey("testcases.id"), nullable=False)
  testbed_id: int = sql.Column(
      deeplearning.deepsmith.testbed.Testbed.id_t,
      sql.ForeignKey("testbeds.id"), nullable=False)
  returncode: int = sql.Column(sql.SmallInteger, nullable=False)
  outputset_id: bytes = sql.Column(
      _ResultOutputSetId, sql.ForeignKey("result_outputsets.id"),
      nullable=False)

  # Relationships.
  testcase: deeplearning.deepsmith.testcase.Testcase = orm.relationship(
      "Testcase", back_populates="results")
  testbed: deeplearning.deepsmith.testbed.Testbed = orm.relationship(
      "Testbed", back_populates="results")
  outputset: typing.List["ResultOutput"] = orm.relationship(
      "ResultOutput", secondary="result_outputsets",
      primaryjoin="ResultOutputSet.id == Result.outputset_id",
      secondaryjoin="ResultOutputSet.output_id == ResultOutput.id")
  profiling_events: typing.List["ResultProfilingEvent"] = orm.relationship(
      "ResultProfilingEvent", back_populates="result")

  # Constraints.
  __table_args__ = (
    sql.UniqueConstraint('testcase_id', 'testbed_id', name='unique_result'),
  )

  @property
  def outputs(self) -> typing.Dict[str, str]:
    """Get the generator inputs.

    Returns:
      A map of result outputs.
    """
    return {output.name.string: output.value.truncated_value
            for output in self.outputset}

  def SetProto(self, proto: deepsmith_pb2.Result) -> deepsmith_pb2.Result:
    """Set a protocol buffer representation.

    Args:
      proto: A protocol buffer message.

    Returns:
      A Result message.
    """
    self.testcase.SetProto(proto.testcase)
    self.testbed.SetProto(proto.testbed)
    proto.returncode = self.returncode
    for output in self.outputset:
      proto.outputs[output.name.string] = output.value.truncated_value
    for profiling_event in self.profiling_events:
      event = proto.profiling_events.add()
      profiling_event.SetProto(event)
    return proto

  def ToProto(self) -> deepsmith_pb2.Result:
    """Create protocol buffer representation.

    Returns:
      A Result message.
    """
    proto = deepsmith_pb2.Result()
    return self.SetProto(proto)

  @classmethod
  def GetOrAdd(cls, session: db.session_t,
               proto: deepsmith_pb2.Result) -> "Result":
    testcase = deeplearning.deepsmith.testcase.Testcase.GetOrAdd(
        session, proto.testcase
    )
    testbed = deeplearning.deepsmith.testbed.Testbed.GetOrAdd(
        session, proto.testbed
    )

    # Build the list of outputs, and md5sum the key value strings.
    outputs = []
    md5 = hashlib.md5()
    for proto_output_name in sorted(proto.outputs):
      proto_output_value = proto.outputs[proto_output_name]
      md5.update((proto_output_name + proto_output_value).encode("utf-8"))
      output = db.GetOrAdd(
          session, ResultOutput,
          name=ResultOutputName.GetOrAdd(
              session, string=proto_output_name,
          ),
          value=ResultOutputValue.GetOrAdd(
              session, string=proto_output_value
          ),
      )
      outputs.append(output)

    # Create invariant optset table entries.
    outputset_id = md5.digest()
    for output in outputs:
      db.GetOrAdd(session, ResultOutputSet, id=outputset_id, output=output)

    result = db.GetOrAdd(
        session, cls,
        testcase=testcase,
        testbed=testbed,
        returncode=proto.returncode,
        outputset_id=outputset_id,
    )

    # Add profiling events.
    for event in proto.profiling_events:
      deeplearning.deepsmith.profiling_event.ResultProfilingEvent.GetOrAdd(
          session, event
      ).result = result

    return result


class ResultOutputSet(db.Table):
  """A set of result outputs.

  An outputset groups outputs for results.
  """
  __tablename__ = "result_outputsets"
  id_t = _ResultOutputSetId

  # Columns.
  id: bytes = sql.Column(
      id_t, sql.ForeignKey("results.outputset_id"), nullable=False)
  output_id: int = sql.Column(
      _ResultOutputId, sql.ForeignKey("result_outputs.id"), nullable=False)

  # Relationships.
  results: typing.List[Result] = orm.relationship(
      "Result", foreign_keys=[Result.outputset_id])
  output: "ResultOutput" = orm.relationship("ResultOutput")

  # Constraints.
  __table_args__ = (
    sql.PrimaryKeyConstraint(
        "id", "output_id", name="unique_result_outputset"),
  )

  def __repr__(self):
    hex_id = binascii.hexlify(self.id).decode("utf-8")
    return f"{hex_id}: {self.input_id}={self.input}"


class ResultOutput(db.Table):
  """A result output consists of a <name, value> pair."""
  id_t = _ResultOutputId
  __tablename__ = "result_outputs"

  # Columns.
  id: int = sql.Column(id_t, primary_key=True)
  date_added: datetime.datetime = sql.Column(
      sql.DateTime, nullable=False, default=db.now)
  name_id: _ResultOutputNameId = sql.Column(
      _ResultOutputNameId, sql.ForeignKey("result_output_names.id"),
      nullable=False)
  value_id: _ResultOutputValueId = sql.Column(
      _ResultOutputValueId, sql.ForeignKey("result_output_values.id"),
      nullable=False)

  # Relationships.
  name: "ResultOutputName" = orm.relationship(
      "ResultOutputName", back_populates="outputs")
  value: "ResultOutputValue" = orm.relationship(
      "ResultOutputValue", back_populates="outputs")

  # Constraints.
  __table_args__ = (
    sql.UniqueConstraint("name_id", "value_id", name="unique_result_output"),
  )

  def __repr__(self):
    return f"{self.name}: {self.value}"


class ResultOutputName(db.StringTable):
  """The name of a result output."""
  id_t = _ResultOutputNameId
  __tablename__ = "result_output_names"

  # Relationships.
  outputs: typing.List[ResultOutput] = orm.relationship(
      ResultOutput, back_populates="name")


class ResultOutputValue(db.Table):
  id_t = _ResultOutputValueId
  __tablename__ = "result_output_values"

  # Truncate everything after
  max_len = 128000

  # Columns.
  id: int = sql.Column(id_t, primary_key=True)
  date_added: datetime.datetime = sql.Column(
      sql.DateTime, nullable=False, default=db.now)
  original_md5: bytes = sql.Column(
      sql.Binary(16), nullable=False, index=True, unique=True)
  original_linecount = sql.Column(sql.Integer, nullable=False)
  original_charcount = sql.Column(sql.Integer, nullable=False)
  truncated_value: str = sql.Column(
      sql.UnicodeText(length=max_len), nullable=False)
  truncated: bool = sql.Column(sql.Boolean, nullable=False)
  truncated_md5: bytes = sql.Column(sql.Binary(16), nullable=False)
  truncated_linecount = sql.Column(sql.Integer, nullable=False)
  truncated_charcount = sql.Column(sql.Integer, nullable=False)

  # Relationships.
  outputs: typing.List[ResultOutput] = orm.relationship(
      ResultOutput, back_populates="value")

  @classmethod
  def GetOrAdd(cls, session: db.session_t, string: str) -> "ResultOutputValue":
    """Instantiate a ResultOutputValue entry from a string.

    Args:
      session: A database session.
      string: The string.

    Returns:
      A ResultOutputValue instance.
    """
    original_charcount = len(string)
    original_linecount = string.count("\n")
    md5_ = hashlib.md5()
    md5_.update(string.encode("utf-8"))
    original_md5 = md5_.digest()
    if original_charcount > cls.max_len:
      truncated = string[:cls.max_len]
      md5_ = hashlib.md5()
      md5_.update(truncated.encode("utf-8"))
      truncated_md5 = md5_.digest()
      truncated_linecount = truncated.count("\n")
      truncated_charcount = cls.max_len
    else:
      truncated = string
      truncated_md5 = original_md5
      truncated_linecount = original_linecount
      truncated_charcount = original_charcount
    return db.GetOrAdd(
        session, cls,
        original_md5=original_md5,
        original_linecount=original_linecount,
        original_charcount=original_charcount,
        truncated=True if original_charcount > cls.max_len else False,
        truncated_value=truncated,
        truncated_md5=truncated_md5,
        truncated_linecount=truncated_linecount,
        truncated_charcount=truncated_charcount,
    )

  def __repr__(self):
    return self.truncated_value[:50] or ""


class PendingResult(db.Table):
  """A pending result is created when a testcase is issued to a testbed.

  It is used to prevent a testcase from being issued to the same testbed
  multiple times. When a testbed requests a testcase, a PendingResult is
  created. Pending results have a deadline by which the result is expected.
  The testcase will not be issued again to a matching testbed until this
  deadline has passed.

  PendingResults are removed in two cases:
    - A Result is received with the same testcase and testbed.
    - The deadline passes (this is to prevent the result being permanently
      lost in case of a testbed which never responds with a result).
  """
  id_t = Result.id_t
  __tablename__ = "pending_results"

  # Columns:
  id: int = sql.Column(id_t, primary_key=True)
  date_added: datetime.datetime = sql.Column(
      sql.DateTime, nullable=False, default=db.now)
  # The date that the result is due by.
  deadline: datetime.datetime = sql.Column(sql.DateTime, nullable=False)
  # The testcase that was issued.
  testcase_id: int = sql.Column(
      deeplearning.deepsmith.testcase.Testcase.id_t,
      sql.ForeignKey("testcases.id"), nullable=False)
  # The testbed that the testcase was issued to.
  testbed_id: int = sql.Column(
      deeplearning.deepsmith.testbed.Testbed.id_t,
      sql.ForeignKey("testbeds.id"), nullable=False)

  # Relationships:
  testcase: deeplearning.deepsmith.testcase.Testcase = orm.relationship(
      "Testcase", back_populates="pending_results")
  testbed: deeplearning.deepsmith.testbed.Testbed = orm.relationship(
      "Testbed", back_populates="pending_results")

  # Constraints:
  __table_args__ = (
    sql.UniqueConstraint(
        'testcase_id', 'testbed_id', name='unique_pending_result'),
  )
