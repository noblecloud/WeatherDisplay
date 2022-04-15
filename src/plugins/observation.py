import asyncio
from asyncio import Lock
from collections import deque
from copy import copy

from operator import add

import pytz
from dataclasses import dataclass, field
from WeatherUnits.errors import UnknownUnit
from WeatherUnits.time.time import Second

from src.logger import sendPushoverMessage
from src import logging
from uuid import uuid4
from abc import ABC, ABCMeta, abstractmethod
from datetime import datetime, timedelta, timezone as _timezones, tzinfo
from functools import cached_property, lru_cache
from typing import Any, Callable, ClassVar, Hashable, Iterable, List, Mapping, Optional, OrderedDict, Set, Tuple, Type, Union

import numpy as np
import WeatherUnits as wu
from dateutil.parser import parse
from PySide2.QtCore import QObject, Signal
from WeatherUnits import Measurement

from src import config
from plugins.translator import unitDict
from src.utils import (clearCacheAttr, closest, isa, isOlderThan, mostCommonClass, mostFrequentValue, now, Now, Period, DateKey, roundToPeriod,
                       toLiteral, TranslatorProperty,
                       UTC)
from src.catagories import CategoryDict, CategoryItem
from src.plugins import pluginLog

loop = asyncio.get_running_loop()

__all__ = ['ObservationDict', 'Observation', 'ObservationRealtime', 'ObservationTimeSeries',
           'ObservationLog', 'ObservationTimeSeriesItem', 'MeasurementTimeSeries',
           'TimeSeriesItem', 'TimeAwareValue', 'ObservationValue', 'RecordedObservationValue', 'ArchivedObservationValue', 'ArchivedObservation',
           'ObservationValueResult', 'ObservationTimestamp', 'MiniTimeSeries']

from src.utils import Accumulator

log = pluginLog.getChild('Observation')
log.setLevel(logging.ERROR)


def convertToCategoryItem(key, source: Hashable = None):
	if not isinstance(key, CategoryItem):
		key = CategoryItem(key, source=source)
	else:
		key.source = source or key.source
	return key


# def wrapClass(cls):
# 	if cls.__name__ in ValueWrapper.knownTypes:
# 		return ValueWrapper.knownTypes[cls.__name__]
# 	for attr in dir(cls):
# 		if not attr.startswith('__'):
# 			setattr(cls, attr, ValueWrapper(getattr(cls, attr)))
# 	return cls


# class CategoryKey(tuple):
#
# 	def __new__(cls, value: Union[str, tuple], parent: Optional[dict] = None):
# 		if isinstance(value, str):
# 			if '.' in value:
# 				value = tuple(value.split('.'))
# 			else:
# 				value = (value,)
# 		return super(CategoryKey, cls).__new__(cls, value)
#
# 	def __init__(self, value, parent: Optional['ObservationDict'] = None):
# 		# if parent is None:
# 		# 	parent = self.__getParent()
# 		# self.parent = parent
# 		self._name = str(value)
# 		# if isinstance(value, str):
# 		# 	value = value.split('.')
# 		# if isinstance(value, list):
# 		# 	super(CategoryKey, self).__init__(value)
#
# 	def __hash__(self):
# 		if self:
# 			return hash(self[-1])
# 		return hash(None)
#
# 	def __getParent(self):
# 		calframe = inspect.getouterframes(inspect.currentframe(), 2)
# 		parent = None
# 		while calframe:
# 			frame = calframe.pop()
# 			v = frame.frame.f_locals
# 			if 'self' in v and isinstance(v['self'], ObservationDict):
# 				parent = v['self']
# 				calframe = None
# 		return parent
#
# 	@property
# 	def __hasSimilarName(self):
# 		return self._name in categories
#
#
# 	def __repr__(self):
# 		name = self[-1]
# 		parents = [i[:3] for i in self[:-1]]
# 		if parents:
# 			return f'{".".join(parents)}.{name}'
# 		return self._name
#
# 	def __eq__(self, other):
# 		if isinstance(other, CategoryKey):
# 			return list(self) == (other)
# 		if isinstance(other, str):
# 			if '.' in other:
# 				return list(self) == other.split('.')
# 			else:
# 				return self[-1] == [other]
#
# 	def subKeys(self):
# 		return [i for j in [key for key in self.keys()] for i in j]
#
# 	def __contains__(self, item):
# 		if isinstance(item, str):
# 			if '.' in item:
# 				item = item.split('.')
# 			else:
# 				item = [item]
# 		if self._name in item:
# 			return True

# class Category(dict):
# 	_sourceKeys: List[str] = []
# 	_superCategory: 'Category'
# 	_name: str
# 	_head: 'ObservationDict'
# 	_value: Optional[Any] = None
#
#
# 	def __init__(self, category: str, superCategory: Union['Category', 'ObservationDict']):
# 		self._name = category
# 		self._superCategory = superCategory
# 		if superCategory is not None:
# 			head = superCategory
# 			while head is not self and not isinstance(head, ObservationDict) and head._superCategory is not None:
# 				head = head._superCategory
# 		else:
# 			head = self
# 		self._head = head
# 		super(Category, self).__init__()
#
# 	def hasSubKey(self, key: str):
# 		# return true if key is in the category or any of its subcategories
# 		if key in self:
# 			return True
# 		for subCategory in self._values():
# 			if subCategory.hasSubKey(key):
# 				return True
# 		return False
#
# 		# return any(sub.hasSubKey(key) if isinstance(sub, Category) else key in sub for sub in [*self._values(), *self.keys()])
#
# 	def __repr__(self):
# 		string = self._name
# 		if self._value is not None:
# 			string = f'{string} [{self._value}]'
# 		_values = [key for key, value in self.items() if isinstance(value, Category)]
# 		if _values:
# 			string = f'{string} >> {_values}'
# 		return string
#
# 	def __getitem__(self, item):
# 		if isinstance(item, str) and '.' not in item:
# 			if item in self.keys():
# 				return super(Category, self).__getitem__(item)
# 			else:
# 				for value in self._values():
# 					if isinstance(value, UnitMetaData) and value['sourceKey'] == item:
# 						return value
# 					if isinstance(value, Category) and value._name == item:
# 						return value
# 					if item in value.keys():
# 						return value[item]
# 				return self.hasSubKey(item)
# 		elif isinstance(item, str) and '.' in item:
# 			item = item.split('.')
# 		if isinstance(item, Iterable):
# 			if len(item) == 1:
# 				return self[item[0]]
# 			item, remainder = item[0], item[1:]
# 			if item in self:
# 				return self[item][remainder]
# 		return super(Category, self).__getitem__(item)
#
# 	def __setitem__(self, key, value):
# 		if isinstance(key, str):
# 			if '.' in key:
# 				key = key.split('.')
# 			else:
# 				return super(Category, self).__setitem__(key, value)
# 		if isinstance(key, Iterable):
# 			if len(key) == 1:
# 				key = key[0]
# 				if key in self:
# 					self[key].update(value)
# 				else:
# 					super(Category, self).__setitem__(key, value)
# 					if key == self._name:
# 						self._value = value
# 			else:
# 				key, remainder = key[0], key[1:]
# 				if key not in self:
# 					super(Category, self).__setitem__(key, Category(key, self))
# 				self[key][remainder] = value
# 				# self[key][remainder] = _value
# 		if self is self._head:
# 			self._sourceKeys.append(key)
#
# 	def update(self, __m: Mapping[str, Any], **kwargs: Any) -> None:
# 		for key, value in __m.items():
# 			self[key] = value
#
# 	def __contains__(self, item):
# 		if isinstance(item, str):
# 			if '.' not in item:
# 				return super(Category, self).__contains__(item)
# 				if item in self.keys():
# 					return True
# 				else:
# 					if item in self[item]:
# 						return True
# 			else:
# 				item = item.split('.')
# 				if item[0] == self._name:
# 					item.pop(0)
# 				cat = self
# 				while item[0] in cat.keys():
# 					cat = cat[item[0]]
# 					item.pop(0)
# 		if isinstance(item, Iterable):
# 			if len(item) == 1:
# 				item = item[0]
# 				return super(Category, self).__contains__(item)
# 			else:
# 				item, remainder = item[0], item[1:]
# 				subCat = self.get(item, None)
# 				if subCat is None:
# 					return False
# 				return subCat.__contains__(remainder)


class Realtime(ABC):
	pass


class RecordedObservation(ABC):
	pass


class Archivable(ABC):

	@property
	@abstractmethod
	def archived(self): ...


@dataclass(frozen=True)
class HashSlice:
	start: Hashable = field(init=True, compare=True, repr=True, hash=True)
	stop: Hashable = field(init=True, compare=True, repr=True, hash=True, default=None)
	step: Hashable = field(init=True, compare=True, repr=True, hash=True, default=None)

	def __iter__(self) -> Iterable:
		return iter((self.start, self.stop, self.step))


@dataclass
class PublishingInfo:
	observation: 'ObservationDict'
	source: 'Plugin'
	keys: Iterable


class TimeAwareValue(ABC):
	timestamp: datetime
	value: Any


TimeAwareValue.register(wu.Measurement)


class ArchivableValue(Archivable, TimeAwareValue, ABC):
	pass


class Archived(ABC):
	pass


@ArchivableValue.register
class ObservationValue(TimeAwareValue):
	__metadata: dict
	__source: 'ObservationDict'
	__timestamp: Optional[datetime]

	def __init_subclass__(cls, **kwargs):
		super(ObservationValue, cls).__init_subclass__(**kwargs)

	def __init__(self,
	             value: Any,
	             key: Union[str, CategoryItem],
	             source: Any,
	             container: 'ObservationDict',
	             metadata: dict = None,
	             **kwargs):
		self.__rawValue = None
		self.__timestamp = None
		if isinstance(value, TimeSeriesItem):
			timeAware = value
			value = None
		elif isinstance(value, ObservationValue):
			rawValue = toLiteral(value.rawValue)
			timeAware = TimeSeriesItem(rawValue, value.timestamp)
			metadata = value.metadata
			value = rawValue
		else:
			timeAware = None
		if metadata is None:
			metadata = source.translator.getUnitMetaData(key, source)
			if metadata['key'] != key:
				metadata['sourceKey'] = key
				if isinstance(key, CategoryItem):
					kSource = key.source
				else:
					kSource = None
				key = CategoryItem(metadata['key'], kSource)
				source.__sourceKeyMap__[metadata['sourceKey']] = metadata['key']
			metadata['key'] = key
		if isinstance(value, Measurement):
			sourceUnit = metadata['sourceUnit']
			if value.unit != sourceUnit:
				try:
					value = value[sourceUnit].real
					if timeAware:
						timeAware.value = value

				except UnknownUnit:
					log.warning(f'Failed to convert {key} from {value.unit} to {sourceUnit}.  This may cause issues later conversion accuracy.')
		self.__metadata = metadata
		self.__source = source
		self.__container = container
		self.__value = None
		self.value = timeAware or value
		if str(key) == 'environment.precipitation.precipitation':
			self.convertFunc(self.rawValue).localize

	def __getitem__(self, item):
		if item.startswith('@'):
			value = self.__getattribute__('value')
			result = getattr(value, item[1:], None)
			if result is not None:
				return result
			else:
				raise AttributeError
		if item in self.__metadata:
			return self.__metadata[item]
		return self.__getattribute__(item)

	def __getattr__(self, item):
		if item.startswith('@'):
			value = self.__getattribute__('value')
			return value.__getattribute__(item[1:])
		return self.__getattribute__(item)

	@property
	def value(self):
		if self.__value is None:
			try:
				value = self.__convertFunc(self.rawValue)
			except Exception as e:
				value = self.rawValue
			if hasattr(value, 'localize'):
				value = value.localize
			self.__value = value
		return self.__value

	@value.setter
	def value(self, value):
		timestamp = None
		if isinstance(value, ObservationValue):
			timestamp = value.timestamp
			value = value.rawValue
		if isinstance(value, TimeSeriesItem):
			timestamp = value.timestamp
			value = value.value
		if isinstance(value, datetime):
			timestamp = value
		if timestamp is None and 'time' not in str(self.__metadata["key"]):
			log.warning(f'{self.__metadata["key"]} does not have a timestamp')
		self.__timestamp = timestamp
		self.__rawValue = value
		self.__value = None

	@property
	def sourceUnitValue(self):
		return self.__convertFunc(self.rawValue)

	@property
	def rawValue(self):
		return self.__rawValue

	@property
	def __convertFunc(self):
		typeString = self.__metadata.get('type', None)
		unitDef = self.__metadata.get('sourceUnit', None)
		kwargs = kwargs = self.__metadata.get('kwargs', {})

		if typeString == 'datetime':
			if 'tz' in kwargs:
				if isinstance(kwargs['tz'], TranslatorProperty):
					value = kwargs['tz']
					kwargs['tz'] = value()
				if isinstance(kwargs['tz'], str):
					kwargs['tz'] = pytz.timezone(kwargs['tz'])
			else:
				kwargs['tz'] = config.tz
			if unitDef == 'epoch':
				return lambda value: datetime.fromtimestamp(value, **kwargs)
			elif unitDef == 'ISO8601':
				format = self.__metadata.get('format', None)
				if format@isa@Iterable:
					for f in format:
						try:
							datetime.strptime(self.rawValue, f).astimezone(config.tz)
							return lambda value: datetime.strptime(value, f).astimezone(config.tz)
						except ValueError:
							pass

				return lambda value: datetime.strptime(value, format).astimezone(config.tz)
		if typeString == 'icon':
			if self.__metadata['iconType'] == 'glyph':
				alias = self.__metadata['alias']
				return lambda value: alias.get(str(value), value)
		if isinstance(unitDef, str) and unitDef in unitDict:
			return lambda value: unitDict[unitDef](value, **kwargs)
		if isinstance(unitDef, Iterable):
			if len(unitDef) == 2:
				n, d = unitDef
				if isinstance(n, str) and n in unitDict:
					n = unitDict[n]
				if isinstance(d, str) and d in unitDict:
					d = unitDict[d]
				if isinstance(d, TranslatorProperty):
					d = d()
				elif isinstance(d, type):
					d = d(1)
				if hasattr(d, 'value'):
					d = d.value
				comboCls = unitDict['special'][typeString][n, type(d)]
				return lambda value: comboCls(value, d, **kwargs)
		if typeString is not None and unitDef is not None:
			if isinstance(unitDef, str):
				cls = unitDict['str']
				return lambda value: cls(value, **kwargs)

		return lambda value: value

	@property
	def convertFunc(self):
		return self.__convertFunc

	def __str__(self):
		return str(self.value)

	@property
	def key(self) -> CategoryItem:
		return self.__metadata['key']

	def setTimestamp(self, timestamp: datetime):
		self.__timestamp = timestamp

	@property
	def timestamp(self) -> datetime:
		if self.__timestamp is None:
			return self.__source.timestamp
		return self.__timestamp

	def __repr__(self):
		if self.timestamp is None:
			return f'{self.value} @ UnknownTime'
		if self.timestamp != self.__source.timestamp:
			timestamp = f' @{self.timestamp.strftime("%-I:%M%p %m/%d")}'
		else:
			timestamp = ''
		return f'{{\'{self.value.__class__.__name__}\'}} {self.value}{timestamp}'

	@property
	def archived(self) -> 'ArchivedObservationValue':
		return ArchivedObservationValue(self)

	@property
	def metadata(self):
		return self.__metadata

	@property
	def source(self):
		return self.__source

	@property
	def container(self):
		return self.__container

	def __eq__(self, other):
		if isinstance(other, ObservationValue):
			return self.value == other.value
		return self.value == other

	def __ne__(self, other):
		return not self.__eq__(other)

	def __lt__(self, other):
		if isinstance(other, ObservationValue):
			return self.value < other.value
		return self.value < other

	def __le__(self, other):
		if isinstance(other, ObservationValue):
			return self.value <= other.value
		return self.value <= other

	def __gt__(self, other):
		if isinstance(other, ObservationValue):
			return self.value > other.value
		return self.value > other

	def __ge__(self, other):
		if isinstance(other, ObservationValue):
			return self.value >= other.value
		return self.value >= other

	def __float__(self):
		return float(self.value)

	def __int__(self):
		return int(self.value)

	def __hash__(self):
		return hash((self.value, self.key, self.timestamp))

	def __len__(self):
		return 1

	def __iadd__(self, other):
		return ObservationValueResult(self, other)


@Archived.register
class ArchivedObservationValue(ObservationValue):
	__slots__ = ('value', 'rawValue', 'source', 'metadata', 'timestamp', 'sourceUnitValue')

	def __init__(self, origin: Archivable, **kwargs):
		self.value = kwargs.get('value', origin.value)
		self.metadata = kwargs.get('metadata', origin.metadata)
		self.source = kwargs.get('source', origin.source)
		self.timestamp = kwargs.get('timestamp', origin.timestamp)
		self.rawValue = kwargs.get('rawValue', origin.rawValue)
		self.sourceUnitValue = kwargs.get('sourceUnitValue', origin.sourceUnitValue)

	def __setattr__(self, name, value):
		if hasattr(self, name):
			raise AttributeError(f'{name} is read-only')
		elif name in self.__slots__:
			super().__setattr__(name, value)

	@ObservationValue.key.getter
	def key(self):
		return self.metadata['key']

	def __repr__(self):
		if self.timestamp is None:
			return f'{self.value} @ UnknownTime'
		if self.timestamp != self.source.timestamp:
			timestamp = f' @{self.timestamp.strftime("%-I:%M%p %m/%d")}'
		else:
			timestamp = ''
		return f'{{\'{self.value.__class__.__name__}\'}} {self.value}{timestamp}'

	def __str__(self):
		return str(self.__value)

	@property
	def archived(self):
		return self


@ArchivableValue.register
class ObservationValueResult(ObservationValue):
	__values: set

	def __init__(self, *values: tuple[TimeAwareValue], operation: Callable = add):
		self.__values = set()
		key = values[0].key
		source = values[0].source
		metadata = values[0].metadata
		self.operation = operation
		super().__init__(None, key, source, metadata)
		self.value = values

	@property
	def value(self):
		try:
			value = self.convertFunc(self.__rawValue)
		except TypeError:
			value = self.__rawValue
		if hasattr(value, 'localize'):
			value = value.localize
		return value

	@value.setter
	def value(self, values):
		if values is None:
			return
		if not isinstance(values, Iterable):
			values = [values]
		for v in values:
			if isinstance(v, ObservationValueResult):
				self.__values.update(v.values)
				continue
			if isinstance(v, ObservationValue):
				v = TimeSeriesItem(v.rawValue, v.timestamp)
			if isinstance(v, TimeSeriesItem):
				self.__values.add(v)
			elif isinstance(v, (int, float)):
				t = self.value.timestamp
				self.__values.add(TimeSeriesItem(v, t))

	@property
	def __rawValue(self):
		return TimeSeriesItem.average(*self.__values)

	@property
	def values(self):
		return self.__values

	def __iadd__(self, other):
		self.value = other
		return self

	@property
	def timestamp(self):
		return self.__rawValue.timestamp


class TimeSeriesItem(TimeAwareValue):
	__slots__ = ('value', 'timestamp')
	value: Hashable
	timestamp: datetime

	def __init__(self, value: Any, timestamp: datetime = None):
		if timestamp is None:
			if isinstance(value, TimeAwareValue):
				timestamp = value.timestamp
			else:
				timestamp = datetime.utcnow().replace(tzinfo=_timezones.utc)

		if isinstance(timestamp, TranslatorProperty):
			timestamp = timestamp()
		elif isinstance(timestamp, ObservationTimestamp):
			timestamp = timestamp.value

		value = toLiteral(value)
		self.value = value
		self.timestamp = timestamp

	def __repr__(self):
		return f'{self.value} @ {self.timestamp}'

	def __add__(self, other):
		if type(other) is TimeSeriesItem:
			timestamp = datetime.fromtimestamp((self.timestamp.timestamp() + other.timestamp.timestamp())/2)
			other = other.value
		else:
			timestamp = self.timestamp
		value = self.value + other
		return TimeSeriesItem(value, timestamp)

	def __iadd__(self, other):
		if type(other) is TimeAwareValue:
			other = TimeSeriesItem(other.value, other.timestamp)
		if type(other) is TimeSeriesItem:
			return MultiValueTimeSeriesItem(self, other)
		return NotImplemented

	def __radd__(self, other):
		if not other:
			return self
		return self.__add__(other)

	def __sub__(self, other):
		if type(other) is TimeSeriesItem:
			timestamp = datetime.fromtimestamp((self.timestamp.timestamp() + other.timestamp.timestamp())/2)
			other = other.value
		else:
			timestamp = self.timestamp
		value = self.value - other
		return TimeSeriesItem(value, timestamp)

	def __rsub__(self, other):
		if not other:
			return self
		return self.__sub__(other)

	def __mul__(self, other):
		if type(other) is TimeSeriesItem:
			timestamp = datetime.fromtimestamp((self.timestamp.timestamp() + other.timestamp.timestamp())/2)
			other = other.value
		else:
			timestamp = self.timestamp
		value = self.value*other
		return TimeSeriesItem(value, timestamp)

	def __rmul__(self, other):
		if not other:
			return self
		return self.__mul__(other)

	def __truediv__(self, other):
		if type(other) is TimeSeriesItem:
			timestamp = datetime.fromtimestamp((self.timestamp.timestamp() + other.timestamp.timestamp())/2)
			other = other.value
		else:
			timestamp = self.timestamp
		value = self.value/other
		return TimeSeriesItem(value, timestamp)

	def __rtruediv__(self, other):
		if not other:
			return self
		return self.__truediv__(other)

	def __gt__(self, other):
		if hasattr(other, 'value'):
			other = other.value
		if isinstance(other, datetime) and not isinstance(self.value, datetime):
			return self.timestamp > other
		return self.value > type(self.value)(other)

	def __lt__(self, other):
		if hasattr(other, 'value'):
			other = other.value
		if isinstance(other, datetime) and not isinstance(self.value, datetime):
			return self.timestamp < other
		return self.value < type(self.value)(other)

	def __ge__(self, other):
		if hasattr(other, 'value'):
			other = other.value
		if isinstance(other, datetime) and not isinstance(self.value, datetime):
			return self.timestamp >= other
		return self.value >= type(self.value)(other)

	def __le__(self, other):
		if hasattr(other, 'value'):
			other = other.value
		if isinstance(other, datetime) and not isinstance(self.value, datetime):
			return self.timestamp <= other
		return self.value <= type(self.value)(other)

	def __eq__(self, other):
		if hasattr(other, 'value'):
			other = other.value
		if isinstance(other, datetime) and not isinstance(self.value, datetime):
			return self.timestamp == other
		try:
			return type(self.value)(other) == self.value
		except (TypeError, ValueError):
			return False

	def __ne__(self, other):
		if hasattr(other, 'value'):
			other = other.value
		if isinstance(other, datetime) and not isinstance(self.value, datetime):
			return self.timestamp != other
		return type(self.value)(other) != self.value

	def __hash__(self):
		return hash((self.value, self.timestamp))

	def __float__(self):
		try:
			return float(self.value)
		except ValueError as e:
			raise TypeError(f'{self.value} is not a float') from e

	def __int__(self):
		try:
			return int(self.value)
		except ValueError as e:
			raise TypeError(f'{self.value} is not an int') from e

	def __str__(self):
		return str(self.value)

	def __bytes__(self):
		try:
			return bytes(self.value)
		except ValueError as e:
			raise TypeError(f'{self.value} is not a bytes') from e

	def __complex__(self):
		return complex(self.value)

	def __round__(self, n=None):
		if isinstance(n, timedelta):
			return roundToPeriod(self.value | isa | datetime or self.timestamp, n)
		return round(self.value, n)

	def __floor__(self):
		return int(self.value)

	def __ceil__(self):
		return int(self.value) + 1

	@classmethod
	def average(cls, *items: 'TimeSeriesItem') -> 'TimeSeriesItem':
		valueCls = mostCommonClass(item.value for item in items)
		if valueCls is str:
			value = mostFrequentValue([str(item) for item in items])
			times = [item.timestamp.timestamp() for item in items if str(item) == value]
		else:
			values = [item.value for item in items]
			value = sum(values)/len(values)
			times = [item.timestamp.timestamp() for item in items]
		timestamp = datetime.fromtimestamp(sum(times)/len(times)).astimezone(_timezones.utc).astimezone(tz=config.tz)
		if issubclass(valueCls, Measurement) and {'denominator', 'numerator'}.intersection(valueCls.__init__.__annotations__.keys()):
			ref = values[0]
			n = type(ref.n)
			d = type(ref.d)(1)
			value = valueCls(numerator=n(value), denominator=d)
			return TimeSeriesItem(value, timestamp)
		return TimeSeriesItem(valueCls(value), timestamp)


@ArchivableValue.register
class MultiValueTimeSeriesItem(TimeSeriesItem):
	values: Set[TimeSeriesItem]

	def __init__(self, *values: Tuple[TimeSeriesItem]):
		self.__value = None
		if values:
			if not isinstance(values, set):
				values = set(values)
			self.values = values

	@property
	def value(self) -> Union[Hashable]:
		if self.__value is None:
			self.__value = self.average(*self.values)
		return self.__value

	@value.setter
	def value(self, value):
		if not isinstance(value, Iterable):
			value = (value,)
		self.values.update(value)
		self.__value = None

	@property
	def timestamp(self) -> datetime:
		return self.value.timestamp

	def __iadd__(self, other):
		if isinstance(other, TimeSeriesItem):
			self.values.add(other)
			self.__value = None
			return self
		return NotImplemented


@ArchivableValue.register
class MiniTimeSeries(deque):
	__resolution: Union[timedelta, List[timedelta]]
	__superTimeSeries: Optional['MiniTimeSeries']
	__samples: int
	__timeOffset: int
	__itemType: Type

	def __init__(self, start: datetime, timespan: timedelta, resolution: timedelta, *args, **kwargs):
		self.__resolution = resolution
		if start is Now():
			timespan = timedelta(minutes=-5)
		elif isinstance(timespan, Period):
			if timespan is Period.Now:
				timespan = timedelta(minutes=-5)
			else:
				timespan = timespan.value
		samples = max(int(max(timedelta(minutes=1), abs(timespan))/resolution), 1)
		self.__timespan = timespan
		self.__samples = samples
		if start is None:
			start = now()
		self.startTime = start
		super().__init__([list() for _ in range(samples)], maxlen=samples)

	@property
	def startTime(self) -> int:
		if self.__startTime is Now():
			return int(roundToPeriod(self.__startTime.now(), self.__resolution).timestamp())
		return int(self.__startTime.timestamp())

	@startTime.setter
	def startTime(self, value: datetime):
		if value is Now():
			self.__startTime = now()
			return
		value = value.astimezone(_timezones.utc)
		value = roundToPeriod(value, self.__resolution)
		self.__startTime = value

	@property
	def timestamp(self):
		value = self.last.timestamp
		value = roundToPeriod(value, self.__resolution)
		return value

	def filterKey(self, key: Union[int, datetime, timedelta]) -> int:
		seconds = int(self.__resolution.total_seconds())
		if isinstance(key, datetime):
			key = key.astimezone(_timezones.utc)
			index = int(((round(key.timestamp()/seconds)*seconds) - self.startTime)/seconds)
		elif isinstance(key, timedelta):
			index = round(key.total_seconds()/seconds)*seconds
		elif isinstance(key, int):
			index = key
		else:
			raise TypeError(f'Invalid key type {type(key)}')
		return self.__samples - 1 + index

	def setValue(self, value: Union[float, int, TimeSeriesItem], key: Union[int, datetime, timedelta] = None):
		if key is None:
			assert isinstance(value, TimeSeriesItem)
			key = value.timestamp
		index = self.filterKey(key)
		maxLength = self.__samples
		if index >= self.__samples:
			extendAmount = abs(index - self.__samples) + 1
			self.extend([list() for _ in range(extendAmount)])
			index = self.__samples - 1
			self.startTime = key
		if index < 0:
			earliest = self.startTime - len(self)*self.resolution.total_seconds()
			outOfBoundsBy = earliest - key.timestamp()
			if abs(outOfBoundsBy) > 900:
				log.warning(f'TimeSeries tried to set a value out of bounds by {wu.Time.Second(outOfBoundsBy).autoAny}')
			log.warning(f'TimeSeries tried to set a value out of bounds by {wu.Time.Second(outOfBoundsBy).autoAny}')
			return
		if not isinstance(value, TimeSeriesItem):
			value = TimeSeriesItem(value, key)
		self[index].append(value)

	def getValue(self, key: Union[int, datetime, timedelta]) -> Optional[TimeSeriesItem]:
		index = self.filterKey(key)
		if index >= self.__samples:
			index = self.__samples - 1
		value = self[index]
		if not value:
			return 0
		if len(value) == 1:
			return value[0]
		return TimeSeriesItem.average(*value)

	@property
	def value(self) -> TimeSeriesItem:
		return self.last.value

	@property
	def last(self):
		if all(len(item) == 0 for item in self):
			return None
		i = -1
		item = self[-1]
		while len(item) == 0:
			i -= 1
			item = self[i]
		return item[-1]

	@property
	def first(self):
		if all(len(item) == 0 for item in self):
			return None
		i = 0
		item = self[0]
		while len(item) == 0:
			i += 1
			item = self[i]
		return item[0]

	def __getitem__(self, item) -> TimeAwareValue:
		if isinstance(item, slice):
			if isinstance(item.start, datetime):
				start = item.start or self.timestamp
				end = item.stop or (start - self.__resolution*(self.__samples - 1))
				step = item.step

				# determine the start and end index
				startI, endI = sorted(i for i in [self.filterKey(start), self.filterKey(end)])

				# keep it in bounds and if the step is greater than 1 go one step out of bounds
				startI = min(max(0, startI - 1 if step else 0), len(self) - 1)
				endI = max(min(len(self), endI + 2 if step else 1), 0)
				if endI == startI:
					if startI >= len(self):
						raise IndexError(f'Index {startI} is out of bounds')
					elif startI < 0:
						raise IndexError(f'Index {startI} is out of bounds')
					values = [self[startI]]
				values = list(self)[startI:endI]

				if step and startI != 0 and endI != len(self):
					values = [i for j in values for i in j if start <= i.timestamp <= end]
					if isinstance(step, timedelta):
						resolution = step.total_seconds()
						span = (end - start).total_seconds()
						lenth = int(span/resolution) + 1
						items = [[] for _ in range(lenth)]
						for i in range(len(values)):
							index = round((values[i].timestamp - start).total_seconds()/resolution)
							items[index].append(values[i])
						values = [TimeSeriesItem.average(*i) for i in items if i]
					elif step > 1:
						values = values[::step]
				else:
					# If the step is zero, each slot is averaged to a single value
					values = [TimeSeriesItem.average(*i) for i in values if len(i)]

				return values
			if isinstance(item.start, float):
				values = [i for j in self for i in j]
		return super().__getitem__(item)

	def rollingAverage(self, *window: Union[int, timedelta, Tuple[datetime, datetime]]) -> TimeSeriesItem:
		if len(window) == 1:
			window = window[0]
		if isinstance(window, timedelta):
			if window.total_seconds() > 0:
				window = -window
			start = self.last.timestamp
			end = start + window
		elif isinstance(window, int):
			start = self.startTime
			end = start + self.__resolution*window
		elif isinstance(window, tuple):
			start, end = window
		values = self[start:end:1]
		if values:
			return TimeSeriesItem.average(*values)
		return None

	@property
	def resolution(self) -> timedelta:
		if isinstance(self.__resolution, timedelta):
			return self.__resolution
		return self.__resolution[0]

	@property
	def archived(self) -> TimeSeriesItem:
		return TimeSeriesItem(self.value, self.timestamp)

	def flatten(self) -> List[TimeSeriesItem]:
		return list(set(i for j in self for i in j))


@ArchivableValue.register
class RecordedObservationValue(ObservationValue):
	__history: MiniTimeSeries
	__resolution: timedelta

	"""
	Keeps a record of all the values that are reported to it in a deque. For this class, there
	is a fixed start and stop time for which the values are recorded.
	"""

	def __init__(self, value, key, source: Any,
	             container: 'ObservationDict',
	             metadata: dict = None, timeAnchor: datetime = None,
	             duration: timedelta = None, resolution: timedelta = None):
		if duration is None:
			if hasattr(container, 'period'):
				duration = container.period
				if isinstance(duration, Period):
					duration = duration.value
			else:
				duration = timedelta(minutes=5)
		if isinstance(value, TimeAwareValue):
			timeAnchor = value.timestamp
		else:
			timeAnchor = timeAnchor or source.timestamp
		if isinstance(timeAnchor, ObservationTimestamp):
			timeAnchor = timeAnchor.value

		# This assumes that the observation time series keys are being rounded,
		# which is the case for the ObservationTimeSeries
		if isinstance(container, Realtime):
			start = Now()
		else:
			start = roundToPeriod(timeAnchor - timedelta(seconds=1), duration) - duration/2

		self.__history = MiniTimeSeries(start=start, timespan=duration, resolution=resolution or timedelta(seconds=15))
		self.__lastCollection = datetime.now().astimezone(_timezones.utc)
		super().__init__(value, key, source, metadata)
		flat = self.__history.flatten()
		if not flat:
			self.__history = MiniTimeSeries(start=start, timespan=duration, resolution=resolution or timedelta(seconds=15))
			self.value = value

	@property
	def __rawValue(self):
		if self.__history:
			return self.__history.value
		return None

	@__rawValue.setter
	def __rawValue(self, value):
		self.__value = None

	@property
	def rawValue(self):
		return self.__rawValue

	@property
	def value(self):
		if self.__value is None:
			try:
				value = self.convertFunc(self.rawValue)
			except TypeError:
				value = self.rawValue
			if hasattr(value, 'localize'):
				value = value.localize
			self.__value = value
		return self.__value

	@value.setter
	def value(self, value):
		if isinstance(value, ObservationValue):
			if isinstance(value.rawValue, TimeAwareValue):
				value = value.rawValue
			else:
				value = TimeSeriesItem(toLiteral(value.rawValue), value.timestamp)
		elif not isinstance(value, TimeSeriesItem):
			value = TimeSeriesItem(value, self.source.timestamp)
		self.__history.setValue(value)
		self.__value = None

	@property
	def history(self) -> MiniTimeSeries:
		return self.__history

	@property
	def resolution(self):
		return self.__resolution

	@resolution.setter
	def resolution(self, value):
		self.__resolution = value

	@property
	def timestamp(self):
		return self.__history.timestamp

	def archivedFrom(self, from_: datetime = None, to: datetime = None) -> TimeSeriesItem:
		from_ = from_ or self.first.timestamp
		to = to or self.last.timestamp
		rawValue = self.history.rollingAverage(from_, to)
		value = self.convertFunc(rawValue.value) if rawValue is not None else None
		sourceUnitValue = self.convertFunc(rawValue) if rawValue is not None else None
		if hasattr(value, 'localize'):
			value = value.localize
		if value:
			return ArchivedObservationValue(origin=self, value=value, rawValue=rawValue, sourceUnitValue=sourceUnitValue)
		return None

	@property
	def archived(self):
		lastCollection = self.__lastCollection
		self.__lastCollection = thisCollection = UTC()
		value = self.archivedFrom(lastCollection, thisCollection)
		return value

	@property
	def first(self):
		return self.__history.first

	@property
	def last(self):
		return self.__history.last

	def rollingAverage(self, *window: Union[int, timedelta, Tuple[datetime, datetime]]) -> ObservationValue:
		value = self.history.rollingAverage(*window)
		if value:
			metadata = self.metadata
			source = self.source
			return ObservationValue(value, self.key, container=self.container, source=source, metadata=metadata)
		return None


class ObservationTimestamp(ObservationValue):

	def __init__(self, data: dict, source: 'ObservationDict', extract: bool = True, roundedTo: timedelta = None):
		self.__roundedTo = roundedTo

		if isinstance(data, ObservationDict):
			value = data.timestamp
			key = 'time.time'
		elif isinstance(data, dict):
			if CategoryItem('time.time') in data:
				key = 'time.time'
			else:
				key = source.translator.findKey('time.time', data)
			if extract:
				value = data.pop(key, None)
			else:
				value = data[key]
		elif isinstance(data, datetime):
			value = data
			key = CategoryItem('time.time')
		else:
			print(f'Unable to find valid timestamp in {data}.  Using current time.')
			value = datetime.now().astimezone(_timezones.utc)
			key = CategoryItem('time.time')
		super(ObservationTimestamp, self).__init__(value, key, container=source, source=source)
		if isinstance(value, datetime):
			self.__value = value
			if self.__value.tzinfo is None:
				# This assumes the timezone for the provided timestamp is the local timezone
				preVal = self.__value
				self.__value = self.__value.astimezone().astimezone(_timezones.utc)
				postVal = self.__value.replace(tzinfo=None)
				pluginLog.warning(f"Timestamp {self} does not have a timezone.  "
				                  f"Assuming Local Timezone and converting to UTC with a "
				                  f"difference of {Second((abs((preVal - postVal)).total_seconds()).autoAny)}")

	@ObservationValue.value.getter
	def value(self):
		value = super(ObservationTimestamp, self).value
		if self.__roundedTo:
			return roundToPeriod(value, self.__roundedTo)
		return value

	@property
	def __timestamp(self):
		if isinstance(self.rawValue, datetime):
			value = self.rawValue
		else:
			value = self.value
		if self.__roundedTo:
			return roundToPeriod(value, self.__roundedTo)
		return value

	def __repr__(self):
		return f'{self.value.strftime("%-I:%M%p %m/%d")}'

	def __str__(self):
		return self.__repr__()

	def __lt__(self, other):
		if isinstance(other, ObservationTimestamp):
			return self.__timestamp < other.__timestamp
		return self.__timestamp < other

	def __le__(self, other):
		if isinstance(other, ObservationTimestamp):
			return self.__timestamp <= other.__timestamp
		return self.__timestamp <= other

	def __eq__(self, other):
		if isinstance(other, ObservationTimestamp):
			return self.__timestamp == other.__timestamp
		return self.__timestamp == other

	def __ne__(self, other):
		if isinstance(other, ObservationTimestamp):
			return self.__timestamp != other.__timestamp
		return self.__timestamp != other

	def __gt__(self, other):
		if isinstance(other, ObservationTimestamp):
			return self.__timestamp > other.__timestamp
		return self.__timestamp > other

	def __ge__(self, other):
		if isinstance(other, ObservationTimestamp):
			return self.__timestamp >= other.__timestamp
		return self.__timestamp >= other

	def __hash__(self):
		return hash(self.__timestamp)


@ArchivedObservationValue.register
class MultiSourceValue(ObservationValue):

	def __init__(self, anonymousKey: CategoryItem, source: 'ObservationDict', metadata: dict = None):
		self.__key = anonymousKey.anonymous
		self.__source = source
		self.__rawValue = True

	@property
	def value(self):
		sourceValues: list[ObservationValue] = [self.__source[_] for _ in self.__source if not _.isAnonymous and _.anonymous == self.__key]
		sourceValues = sorted(sourceValues, key=lambda x: x.timestamp)
		return sourceValues[-1].value

	def __repr__(self):
		return f'Mulitsource: {self.value}'

	@property
	def rawValue(self):
		return


from typing import Dict, List, Optional, Union

T = Dict[CategoryItem, ObservationValue]
SeriesData = Dict[Union[ObservationTimestamp, datetime], T]


class PublishedDict(T, metaclass=ABCMeta):
	accumulator: Optional[Accumulator]


class ObservationDict(PublishedDict):
	_source: 'Plugin'
	_time: datetime
	period = Period.Now
	_ignoredFields: set[str] = set()
	__timestamp: Optional[ObservationTimestamp] = None

	__sourceKeyMap__: ClassVar[Dict[str, CategoryItem]]
	__recorded: ClassVar[bool]
	__keyed: ClassVar[bool]
	itemClass: ClassVar[Type[ObservationValue]]

	accumulator: Accumulator
	dataName: Optional[str]

	@property
	def name(self):
		return self.dataName or self.__class__.__name__

	def __init_subclass__(cls, category: str = None,
	                      published: bool = None,
	                      recorded: bool = None,
	                      sourceKeyMap: Dict[str, CategoryItem] = None,
	                      itemClass: Union[Type[ObservationValue], Type['Observation']] = None,
	                      keyed: bool = False,
	                      **kwargs):
		cls.__sourceKeyMap__ = sourceKeyMap
		if cls.__sourceKeyMap__ is None:
			print('No sourceKeyMap provided for', cls.__name__)
			cls.__sourceKeyMap__ = {}
		k = kwargs.get('keyMap', {})

		if category is not None:
			cls.category = CategoryItem(category)

		if published is not None:
			cls.__published = published

		cls.__recorded = recorded

		cls.__keyed = keyed

		if itemClass is not None:
			cls.itemClass = itemClass
		else:
			if recorded:
				RecordedObservation.register(cls)
				cls.itemClass = type(cls.__name__ + 'Value', (RecordedObservationValue,), {})
				RecordedObservation.register(cls.itemClass)
				if 'Realtime' in cls.__name__ or issubclass(cls, Realtime):
					Realtime.register(cls.itemClass)

			else:
				cls.itemClass = type(cls.__name__ + 'Value', (ObservationValue,), {})

		cls.log = pluginLog.getChild(cls.__name__)
		return super(ObservationDict, cls).__init_subclass__()

	def __init__(self, published: bool = None, recorded: bool = None, timestamp: Optional[ObservationTimestamp] = None, *args, **kwargs):
		self._uuid = uuid4()
		self.__lock = kwargs.get('lock', None) or Lock()
		self.__timestamp = timestamp
		self._published = published
		self._recorded = recorded
		self.dataName = None

		if self.published:
			self.accumulator = Accumulator(self)

		if not self.__class__.__recorded and recorded:
			RecordedObservation.register(self)
			self.__class__.__recorded = True

		super(ObservationDict, self).__init__()

	def __hash__(self):
		return hash(self._uuid)

	def __repr__(self):
		return f'{self.__class__.__name__}: {self._uuid}'

	def __contains__(self, item):
		item = convertToCategoryItem(item)
		return super(ObservationDict, self).__contains__(item)

	def extractTime(self, data: dict):
		return

	async def asyncUpdate(self, data, **kwargs):
		# async with self.__lock:
		self.update(data, **kwargs)

	def update(self, data: dict, **kwargs):
		if self.published:
			self.accumulator.muted = True

		source = kwargs.get('source', None) or data.get('source', [self.source.name])
		if source[0] != self.source.name:
			source = [self.source.name, *source]
		if self.dataName in data:
			data = data[self.dataName]
		if 'data' in data:
			data = data.pop('data')
		timestamp = ObservationTimestamp(data, self, extract=True).value
		for key, item in data.items():
			key = convertToCategoryItem(key, source if self.keyed else None)
			if not isinstance(item, TimeAwareValue):
				item = TimeSeriesItem(item, timestamp)
			self[key] = item
		self.calculateMissing()
		afterKeys = set(self.keys())
		# newKeys = [container for key in newKeys if key if (container := self.source[key]) is not None]
		if self.published:
			self.accumulator.muted = False

	def extractTimestamp(self, data: dict) -> datetime:
		if self.__timestamp is None:
			self.__timestamp = ObservationTimestamp(data, self, extract=True)
		return self.__timestamp

	def setTimestamp(self, timestamp: Union[datetime, dict, ObservationTimestamp]):
		if timestamp is None:
			return
		if isinstance(timestamp, ObservationTimestamp):
			self.__timestamp = timestamp
		elif isinstance(timestamp, dict):
			self.__timestamp = ObservationTimestamp(timestamp, self, extract=True)
		else:
			self.__timestamp = ObservationTimestamp(timestamp, self)

	def __setitem__(self, key, value):
		if key in self.__sourceKeyMap__:
			key = self.__sourceKeyMap__[key]
		if key in self.keys():
			self[key].value = value
		else:
			if isinstance(value, self.itemClass):
				super(ObservationDict, self).__setitem__(value.key, value)
			elif isinstance(value, ObservationValue):
				value = self.itemClass(value=value, key=key, source=value.source, container=self)
				super(ObservationDict, self).__setitem__(value.key, value)
			elif value is not None:
				value = self.itemClass(value=value, key=key, source=self, container=self)  # Eventually 'source' should be the gathered from 'update()
				valueKey = convertToCategoryItem(value.key)
				key = valueKey
				super(ObservationDict, self).__setitem__(valueKey, value)
			else:
				super(ObservationDict, self).__setitem__(key, None)
		# item = super(ObservationDict, self).get(key, None)
		# if item is not None:
		# 	if isinstance(item, ValueWrapper):
		# 		if isinstance(value, ValueWrapper):
		# 			value.update(**value.toDict())
		# 		item.updateValue(**value)
		# 	else:
		# 		super(ObservationDict, self).__setitem__(key, value)
		# else:
		# 	if isinstance(value, MeasurementTimeSeries):
		# 		super(ObservationDict, self).__setitem__(key, value)
		# 	elif not bool(value):
		# 		return super(ObservationDict, self).__setitem__(key, value)
		# 	elif isinstance(value, datetime) and key == 'time':
		# 		super(ObservationDict, self).__setitem__(key, value)
		# 	elif not isinstance(value, ValueWrapper):
		# 		value = ValueWrapper(**value)
		# 		super(ObservationDict, self).__setitem__(key, value)
		if self.published:
			self.accumulator.publishKeys(key)

	def __getitem__(self, item):
		#### ObservationDict __get__

		item = convertToCategoryItem(item)

		if item in self.__sourceKeyMap__:
			item = self.__sourceKeyMap__[item]

		try:
			if self.keyed and item.source is None:
				value = MultiSourceValue(anonymousKey=item, source=self)
				super(ObservationDict, self).__setitem__(item, value)
				return value
			return super(ObservationDict, self).__getitem__(item)
		except KeyError:
			pass
		# if key contains wildcards return a dict containing all the _values
		# Possibly later change this to return a custom subcategory
		if any('*' in i for i in item):
			return self.categories[item]
			# if the last value in the key assume all matching _values are being requested
			wildcardValues = {k: v for k, v in self.items() if k < item}
			if wildcardValues:
				return wildcardValues
			else:
				raise KeyError(f'No keys found matching {item}')
		else:
			return self.categories[item]

	def calculateMissing(self, keys: set = None):
		if keys is None:
			keys = set(self.keys()) - self._calculatedKeys
		light = {'environment.light.illuminance', 'environment.light.irradiance'}

		if 'environment.temperature.temperature' in keys:
			temperature = self['environment.temperature.temperature']
			timestamp = temperature.timestamp
			temperature = temperature.sourceUnitValue

			if 'environment.humidity.humidity' in keys:
				humidity = self['environment.humidity.humidity']

				if 'environment.temperature.dewpoint' not in keys:
					self._calculatedKeys.add('environment.temperature.dewpoint')
					dewpoint = temperature.dewpoint(humidity.value)
					dewpoint.key = CategoryItem('environment.temperature.dewpoint')
					dewpoint = TimeSeriesItem(dewpoint, timestamp=timestamp)
					self['environment.temperature.dewpoint'] = dewpoint

				if 'environment.temperature.heatIndex' not in keys and self.translator.get('environment.temperature.heatIndex', None):
					self._calculatedKeys.add('environment.temperature.heatIndex')
					heatIndex = temperature.heatIndex(humidity.value)
					heatIndex.key = CategoryItem('environment.temperature.heatIndex')
					heatIndex = TimeSeriesItem(heatIndex, timestamp=timestamp)
					self['environment.temperature.heatIndex'] = heatIndex
					keys.add('environment.temperature.heatIndex')

			if 'environment.wind.speed.speed' in keys:
				windSpeed = self['environment.wind.speed.speed']
				if isinstance(windSpeed, RecordedObservationValue):
					windSpeed = windSpeed.rollingAverage(timedelta(minutes=-5)) or windSpeed
				if 'environment.temperature.windChill' not in keys and self.translator.get('environment.temperature.windChill', None):
					self._calculatedKeys.add('environment.temperature.windChill')
					windChill = temperature.windChill(windSpeed.value)
					windChill.key = CategoryItem('environment.temperature.windChill')
					windChill = TimeSeriesItem(windChill, timestamp=timestamp)
					self['environment.temperature.windChill'] = windChill
					keys.add('environment.temperature.windChill')

			if 'environment.temperature.feelsLike' not in keys and all(i in keys for i in ['environment.temperature.windChill', 'environment.temperature.heatIndex']):
				self._calculatedKeys.add('environment.temperature.feelsLike')
				if temperature.f > 80 and humidity.value > 40:
					feelsLike = heatIndex.value
				elif temperature.f < 50:
					feelsLike = windChill.value
				else:
					feelsLike = temperature
				feelsLike = TimeSeriesItem(float(feelsLike), timestamp=timestamp)
				self['environment.temperature.feelsLike'] = feelsLike

		if 'indoor.temperature.temperature' in keys:
			temperature = self['indoor.temperature.temperature']
			timestamp = self['indoor.temperature.temperature'].timestamp
			temperature = temperature.sourceUnitValue

			if 'indoor.humidity.humidity' in keys:
				humidity = self['indoor.humidity.humidity']

				if 'indoor.temperature.dewpoint' not in keys:
					self._calculatedKeys.add('indoor.temperature.dewpoint')
					dewpoint = temperature.dewpoint(humidity.value)
					dewpoint.key = CategoryItem('indoor.temperature.dewpoint')
					dewpoint = TimeSeriesItem(dewpoint, timestamp=timestamp)
					self['indoor.temperature.dewpoint'] = dewpoint

				if 'indoor.temperature.heatIndex' not in keys:
					self._calculatedKeys.add('indoor.temperature.heatIndex')
					heatIndex = temperature.heatIndex(humidity.value)
					heatIndex.key = CategoryItem('indoor.temperature.heatIndex')
					heatIndex = TimeSeriesItem(heatIndex, timestamp=timestamp)
					self['indoor.temperature.heatIndex'] = heatIndex

	def __preprocess(self, data: dict):
		if data:
			dict.__setitem__(self, CategoryItem('time.time'), self.__processTime(data))
		return data

	def timeKey(self, data) -> str:
		if 'time.time' in data:
			return 'time.time'
		unitData = self.translator.getExact(CategoryItem('time.time')) or {}
		srcKey = unitData.get('sourceKey', None)
		if isinstance(srcKey, (str, CategoryItem)):
			return srcKey
		for key in srcKey:
			if key in data:
				return key
		else:
			return (set(data.keys()).intersection({'time', 'timestamp', 'day_start_local', 'date', 'datetime'})).pop()

	def timezoneKey(self, data) -> str:
		if 'time.timezone' in data:
			return 'time.timezone'
		if 'time.timezone' in self.translator:
			return self.translator['time.timezone']['sourceKey']
		else:
			value = set(data.keys()).intersection({'timezone', 'timezone_name', 'tz'})
			if value:
				return value.pop()
			else:
				return None

	@property
	def timestamp(self):
		return self.__timestamp

	def __processTime(self, data: dict) -> datetime:
		timeKey = self.timeKey(data)
		tzKey = self.timezoneKey(data)
		if tzKey is not None:
			tz = pytz.timezone(data.get(tzKey, None))
		else:
			tz = config.tz
		if tz is None:
			tz = config.tz
		value = data.pop(timeKey, None)
		if value is not None:
			value = self.translator.convert(self, timeKey, value)['value']
		if isinstance(value, datetime):
			if value.tzinfo is None:
				value = value.replace(tzinfo=tz)
			return value
		try:
			return parse(value).astimezone(tz)
		except TypeError:
			return datetime.fromtimestamp(value).astimezone(tz)

	@property
	def lock(self) -> Lock:
		return self.__lock

	@property
	def published(self) -> bool:
		if self._published is None:
			return self.__published
		else:
			return self._published

	@property
	def recorded(self):
		if self._recorded is None:
			return self.__recorded
		return self._recorded

	@property
	def keyed(self) -> bool:
		return self.__keyed

	@property
	def translator(self):
		return self.source.translator

	@cached_property
	def normalizeDict(self):
		return {value['sourceKey']: key for key, value in self.translator.items() if 'sourceKey' in value}

	@property
	def source(self):
		return self._source

	@source.setter
	def source(self, value):
		if hasattr(value, 'observations'):
			self._source = value
			if self.published:
				self.accumulator.connectSlot(value.publisher.addBulk)

	@cached_property
	def categories(self):
		return CategoryDict(self, self, None)

	def __cleanup(self):
		pass


@Archivable.register
class Observation(ObservationDict, published=False, recorded=False):
	unitDict = unitDict
	_translator: dict
	_time: datetime = None
	_calculatedKeys: set

	def __init_subclass__(cls, **kwargs):
		super().__init_subclass__(**kwargs)
		cls._calculatedKeys = set()

	def __init__(self, *args, **kwargs):
		super(Observation, self).__init__(*args, **kwargs)

		values = kwargs.get('values')

	# if values is not None:
	# 	pass
	# else:
	# 	values = {}
	# 	for value in [value for value in args if isinstance(value, dict)]:
	# 		values.update(value)
	# 	self.update(values)

	@property
	def sortKey(self):
		time: ObservationTimestamp = self.timestamp
		if time is None:
			return timedelta(0)
		if isinstance(time, ObservationTimestamp):
			time = time.value
		return datetime.now(tz=time.tzinfo) - time

	@property
	def archived(self):
		return ArchivedObservation(self)


@Archived.register
class ArchivedObservation(Observation, published=False, recorded=False):

	# def __new__(cls, source: Archivable, *args, **kwargs):
	# 	if hasattr(source, '__archivedClass__'):
	# 		cls = source.__archivedClass__
	# 	else:
	# 		cls = type(type(source).__name__, (cls, type(source),), {})
	# 		source.__archivedClass__ = cls
	# 	return super().__new__(cls, source, *args, **kwargs)

	def __init__(self, source: Optional[Archivable] = None, *args, **kwargs):
		timestamp = kwargs.get('timestamp', None) or (source.timestamp if source is not None else None)
		if timestamp is not None:
			self.timestamp = timestamp
		if source:
			values = {key: value.archived if isinstance(value, ArchivableValue) else copy(value) for key, value in source.items()}
			values = {key: value for key, value in values.items() if value is not None}
			dict.__init__(self, values)
		else:
			dict.__init__(self)

	def __setattr__(self, key, value):
		if key == 'timestamp' and (not hasattr(self, 'timestamp') or self.timestamp is None):
			self.__dict__[key] = value
			return
		raise AttributeError('ArchivedObservation is immutable')

	def __delattr__(self, key):
		raise AttributeError('ArchivedObservation is immutable')

	def __setitem__(self, key, value):
		raise AttributeError('ArchivedObservation is immutable')

	def __delitem__(self, key):
		raise AttributeError('ArchivedObservation is immutable')

	def update(self, *args, **kwargs):
		if len(self) > 0:
			dict.update(*args, **kwargs)
		raise AttributeError('ArchivedObservation is immutable')

	def calculateMissing(self):
		return

	@property
	def timestamp(self):
		return self.__dict__.get('timestamp')


@Realtime.register
class ObservationRealtime(Observation, published=True, recorded=True):
	time: datetime
	timezone: tzinfo
	subscriptionChannel: str = None
	_indoorOutdoor: bool = False

	def __init__(self, source: 'Plugin', *args, **kwargs):
		self._source = source
		super(ObservationRealtime, self).__init__(*args, **kwargs)

	def udpUpdate(self, data):
		self.update(data)

	@property
	def timestamp(self):
		timestamps = [value.timestamp.timestamp() for value in self.values() if isinstance(value, TimeAwareValue)] or [datetime.now().astimezone(_timezones.utc).timestamp()]
		average = sum(timestamps)/len(timestamps)
		return datetime.fromtimestamp(average).astimezone(config.tz)


class ObservationTimeSeriesItem(Observation, published=False):

	def __init__(self, *args, timeseries: 'ObservationTimeSeries', **kwargs):
		super(ObservationTimeSeriesItem, self).__init__(*args, **kwargs)
		self.__timeseries = timeseries
		self.setTimestamp(kwargs.get('timestamp'))

	@property
	def timeseries(self):
		return self.__timeseries

	@property
	def period(self):
		return self.__timeseries.period

	@property
	def source(self):
		return self.__timeseries.source

	def archive(self):
		for key, value in self.items():
			if isinstance(value, ArchivableValue):
				if hasattr(value, 'history'):
					value = value.history.archived
				super(ObservationTimeSeriesItem, self).__setitem__(key, value)


class ObservationTimeSeries(ObservationDict, published=True):
	__knownKeys: set[CategoryItem]
	_ignoredFields: set[CategoryItem] = set()
	period: timedelta
	timeframe: timedelta
	__timeseries__: dict[DateKey, Observation]

	itemClass: Type[ObservationTimeSeriesItem]

	def __init_subclass__(cls, **kwargs):
		recorded = kwargs.get('recorded', None)
		sourceKeyMap = kwargs.get('sourceKeyMap', {})
		published = kwargs.get('published', False)
		itemClass = type(f'{cls.__name__}Item', (ObservationTimeSeriesItem,), {}, published=published, recorded=recorded, sourceKeyMap=sourceKeyMap)
		if recorded and hasattr(cls, 'FrozenValueClass'):
			itemClass.FrozenClass = cls.FrozenValueClass
		super().__init_subclass__(itemClass=itemClass, **kwargs)

	def __init__(self, source: 'Plugin', *args, **kwargs):
		self._source = source
		super(ObservationTimeSeries, self).__init__(*args, **kwargs)
		self.__knownKeys = set()
		self.__timeseries__ = {}

	def calculateMissing(self):
		if 'precipitationAccumulation' not in self.knownKeys and (key := self.keySelector('precipitation', 'precipitationRate')):
			accumulation = self[key][0].__class__(self[key][0].__class__.Millimeter(0)).localize
			for obs in self['time'].values():
				accumulation += obs[key]
				obs['precipitationAccumulation'] = accumulation
		self['datetime'] = [time.datetime for time in self['time'].keys()]

	def keySelector(self, *keys) -> Union[bool, str]:
		s = set(keys).intersection(self.knownKeys)
		if s:
			return list(s)[0]
		return False

	@property
	def knownKeys(self):
		return list(list(self['time'].values())[0].keys())

	def update(self, data: dict, **kwargs):
		keyMap = data.get('keyMap', {})

		source = [self.source.name]
		if 'source' in kwargs:
			source.append(*kwargs['source'])
		if 'source' in data:
			source.append(data['source'])
		if self.dataName in data:
			data = data[self.dataName]
		if 'data' in data:
			raw = data.pop('data')
		else:
			raw = data

		if isinstance(raw, dict):
			# incoming item is a single observation
			if any(isinstance(value, (ObservationValue, int, float, str)) for value in raw.values()):
				raw = [raw]
			# incoming item is a list of observations
			else:
				raw = list(raw.values())

		keys = set()
		if isinstance(raw, List):
			for rawObs in raw:
				if not isinstance(rawObs, Mapping):
					rawObs = {k: v for k, v in zip(keyMap, rawObs)}
				key = ObservationTimestamp(rawObs, self, False, roundedTo=self.period)
				obs = self.__timeseries__.get(key, None) or self.buildObservation(key)
				obs.update(rawObs, source=source)
				keys.update(obs.keys())
		# self.calculatePeriod(raw)
		self.__knownKeys.update(keys)

		keys = {key for key in keys if key.category not in self._ignoredFields and key.category ^ 'time'}

		self.removeOldObservations()
		for key in keys.intersection(self.keys()):
			self[key].refresh()
		if self.published:
			self.accumulator.publishKeys(*keys)

	def __missing__(self, key):
		if key in self.__knownKeys:
			timeseries = MeasurementTimeSeries(self, key)
			dict.__setitem__(self, key, timeseries)
			return timeseries
		else:
			raise KeyError(f'{key} is not a known key')

	def __contains__(self, key):
		if isinstance(key, str):
			key = CategoryItem(key)
		if isinstance(key, CategoryItem):
			return key in self.__knownKeys
		elif isinstance(key, ObservationTimestamp):
			return key in self.__timeseries__
		elif isinstance(key, datetime):
			return key in self.__timeseries__
		return False

	def removeOldObservations(self):
		return
		now = roundToPeriod(datetime.now(tz=config.tz), self.period, method=int)
		toPass = {}
		for key in {(key, value) for key, value in self.__timeseries__.items() if key < now}:
			toPass[key] = self.destroyObservation(key)
		if toPass:
			self.accumulator.publishKeys(*toPass.keys())
			self.source.ingestHistorical(toPass)

	def buildObservation(self, timestamp: ObservationTimestamp) -> Observation:
		item = self.itemClass(timeseries=self, source=self.source, timestamp=timestamp, published=False, lock=self.lock)
		self[timestamp] = item
		return item

	def destroyObservation(self, key: ObservationTimestamp):
		return
		return self.__timeseries__.pop(key)

	def calculatePeriod(self, data: list):
		if isinstance(data[0], dict):
			time = np.array([self._observationClass.observationKey(v).timestamp() for v in data])
		elif isinstance(data[0], list):
			time = np.array([x[0] for x in data])
		else:
			raise TypeError(f'{type(data[0])} is not supported yet')
		meanTime = datetime.fromtimestamp(int(np.mean(time)), tz=config.tz)
		period = timedelta(seconds=((time - np.roll(time, 1))[1:].mean()))
		if period.total_seconds() > 0 and meanTime < datetime.now(tz=config.tz):
			period = timedelta(-period.total_seconds())
		self._period = period

	def __updateObsKey(self, key):
		# self[key] = {k1: _value[key] for k1, _value in self['time'].items() if key in _value.keys()}
		# self[key] = MeasurementTimeline(self, key)
		self[key] = MeasurementTimeSeries(self, key, [x[key] if key in x.keys() else None for x in self['time'].values()])

	def __genObsValueForKey(self, key):
		self[key] = [None if key not in x.keys() else x[key] for x in self['time'].values()]

	def observationKey(self, data) -> DateKey:
		timeData = self.translator['time']['time']
		timeValue = data[self.timeKey(data)]
		tz = data.get(self.timezoneKey(data), config.tz)
		if timeData['sourceUnit'] == 'epoch':
			return DateKey(datetime.fromtimestamp(timeValue, tz))
		if timeData['sourceUnit'] == 'ISO8601':
			key = DateKey(parse(timeValue).astimezone(tz))
			return key

	def extractTimestamp(self, data: dict) -> datetime:
		key = self.translator.findKey('time.time', data)
		self[key] = data.pop(key)

	@property
	def timeseries(self):
		return self.__timeseries__

	@property
	def period(self) -> timedelta:
		if self._period is None:
			return timedelta(seconds=1)
		return self._period

	@property
	def timeframe(self) -> timedelta:
		if self.timestamps:
			return self.timestamps[-1].datetime - self.timestamps[0].datetime
		else:
			return timedelta(0)

	@property
	def timestamps(self):
		return list(self['time'].keys())

	@property
	def translator(self):
		## Todo: find a better way for this
		return self.source.translator

	def observationKeys(self):
		return list({key for obs in (self['time'].values() if isinstance(self['time'], dict) else self['time']) for key in obs.keys()})

	def timeseriesValues(self):
		return self.__timeseries__.values()

	def timeseriesKeys(self):
		return self.__timeseries__.keys()

	def timeseriesItems(self):
		return self.__timeseries__.items()

	def __iter__(self):
		return self.__timeseries__.__iter__()

	def __makeKey(self, data: dict):
		return self.observationKey(data)

	def __getitem__(self, key) -> Union[List[Measurement], Observation]:
		if isinstance(key, CategoryItem):
			if key in self.__knownKeys:
				return super(ObservationTimeSeries, self).__getitem__(key)
			else:
				raise KeyError(f'{key} is not a known key')
		if isinstance(key, (ObservationTimestamp, datetime)):
			return self.__timeseries__[key]
		return super(ObservationTimeSeries, self).__getitem__(key)

	def __setitem__(self, key, value):
		if isinstance(key, ObservationTimestamp):
			if self._period is None:
				self.calculatePeriod(value)

			self.__timeseries__[key] = value
			self.__knownKeys.add(key)
		else:
			raise KeyError(f'Only "ObservationTimestamp" is supported as key')

	# # if not any(key in k for k in self.observationKeys()):
	# #
	# # 	if isinstance(key, int):
	# # 		return list(self['time'].values())[key]
	# #
	# # 	if isinstance(key, datetime):
	# # 		timestamp = int(key.timestamp())
	# # 		key = closest(list(self['time'].keys()), timestamp)
	# # 		return self['time'][key]
	#
	# else:
	# 	# _values = {K: MeasurementTimeSeries(self, K, [i[K] for i in self['time']._values()]) for K in self.observationKeys() if key in K}
	# 	# if len(_values) == 1:
	# 	# 	return _values.popitem()[1]
	# 	# return _values
	# 	if key in self.observations:
	# 		return self.observations[key]
	# 	if key in self.observationKeys():
	# 		value = [i[key] for i in self['time'].values()]
	# 		series = MeasurementTimeSeries(self, key, value)
	# 		self.observations[key] = series
	# 		return series
	# 	else:
	# 		raise KeyError(key)

	@cached_property
	def categories(self):
		return CategoryDict(self, self.keys(), None)

	@cached_property
	def valueKeys(self) -> set[str]:
		if 'time' not in self:
			try:
				return (delattr(self, 'valueKeys'))
			except AttributeError:
				return set()
		elif 'time' in self and len(self['time']) == 0:
			try:
				return (delattr(self, 'valueKeys'))
			except AttributeError:
				return set()
		else:
			allKeys = set()
			for obs in self['time'].values():
				allKeys.update(obs.keys())
			return allKeys

	def parseData(self, data):
		for field in self._ignoredFields:
			data.pop(field)

		normalizeDict = {value['sourceKey']: key for key, value in self.translator.items()}
		data = {normalizeDict[key]: value for key, value in data.items()}

		finalData = {}
		for key, value in data.items():
			finalData[key] = self.convertValue(key, value)
		return finalData

	@property
	def raw(self):
		return self['raw']

	@property
	def sortKey(self):
		return self.period


class ObservationLog(ObservationTimeSeries, published=False, recorded=True):
	archiveAfter: timedelta = timedelta(minutes=15)

	# def __init_subclass__(cls, **kwargs):
	# 	cls.ArchivedItemClass = type('Archived'+cls.itemClass.__name__, (ArchivedObservation,), {})
	# 	super().__init_subclass__(**kwargs)

	@ObservationTimeSeries.period.getter
	def period(self) -> timedelta:
		p = super(ObservationLog, self).period or timedelta(seconds=-1)
		if p.total_seconds() > 0:
			p *= -1
		return p

	def removeOldObservations(self):
		keepFor = timedelta(days=2)
		cutoff = roundToPeriod(datetime.now(tz=config.tz), self.period) - keepFor
		for key in [k for k in self if k < cutoff]:
			del self.__timeseries__[key]

	def __setitem__(self, key, value):
		super(ObservationLog, self).__setitem__(key, value)

		if key.value | isOlderThan | timedelta(minutes=15):
			self.__timeseries__[key].archive()
		else:
			archiveAfter = self.archiveAfter.total_seconds() - (key.value.timestamp() - datetime.now().timestamp())
			loop.call_later(archiveAfter, self.__timeseries__[key].archive)

	def buildObservation(self, key: ObservationTimestamp) -> Observation:
		item = self.itemClass(timeseries=self, source=self.source, timestamp=key, published=False, lock=self.lock)
		self[key] = item
		return item


class TimeSeriesSignal(QObject):
	__signal = Signal()
	__connections: Set[Hashable]
	__lastHash: int
	__parent: 'MeasurementTimeSeries'

	def __init__(self, parent: 'MeasurementTimeSeries'):
		self.__parent = parent
		self.__lashHash = 0
		self.__connections = set()
		super(TimeSeriesSignal, self).__init__()

	def __repr__(self):
		return f'<{repr(self.__parent)}.Publisher>'

	def publish(self):
		self.__signal.emit()

	def connectSlot(self, slot):
		self.__connections.add(slot.__self__)
		self.__signal.connect(slot)
		if len(self.__connections) == 1:
			self.__parent.refresh()

	def disconnectSlot(self, slot):
		try:
			self.__connections.discard(slot.__self__)
			self.__signal.disconnect(slot)
		except TypeError:
			pass
		except RuntimeError:
			pass

	@property
	def hasConnections(self) -> bool:
		return len(self.__connections) > 0

	@property
	def connectedItems(self):
		return list(self.__connections)


class MeasurementTimeSeries(OrderedDict):
	_key: str
	_source: ObservationTimeSeries
	offset = 0
	log = pluginLog.getChild('MeasurementTimeSeries')
	__lashHash: int
	__references: Set[Hashable]
	__nullValue: Optional[TimeAwareValue]

	def __init__(self, source: Union[ObservationTimeSeries, 'Plugin'], key: str):
		self.__lashHash = 0
		self.__references = set()
		self.__nullValue = None
		self._source = source
		self._key = key
		self.signals = TimeSeriesSignal(self)
		super(MeasurementTimeSeries, self).__init__()
		self.signals.blockSignals(True)
		self.signals.blockSignals(False)
		if self.isMultiSource:
			source: 'Plugin'
			source.publisher: 'KeySignal'
			source.publisher.connectChannel(self._key, self.sourceChanged)

	def __valuesHash(self) -> int:
		return hash(tuple(self.items()))

	def __hash__(self):
		return hash((self._key, self.__valuesHash()))

	def __repr__(self):
		if isinstance(self._source, ObservationTimeSeries):
			return f'{self._source.__class__.__name__}.{self._key.name}{" [uninitialized]" if len(self) == 0 else ""}'
		else:
			return f'{self._source.name}.{self._key.name}'

	def __str__(self):
		return self.__repr__()

	def __len__(self):
		return len(self.keys())

	def sourceLen(self):
		pass

	def pullUpdate(self):
		self.update()

	def addReference(self, reference: Hashable):
		self.__references.add(reference)

	def refresh(self):
		self.__clearCache()
		if self.signals.hasConnections or len(self.__references) > 0:
			log.debug(f'Refreshing {self}')
			self.update()
		else:
			log.debug(f'Refreshing {self}...item has 0 references, aborting')

	def sourceChanged(self, sources: 'Plugin'):
		if self.isMultiSource and not any(s.period > Period.Minute for s in sources):
			return
		elif not self.isMultiSource and self._source not in sources:
			return

		if self.signals.hasConnections or len(self.__references) > 0:
			lenBefore = len(self)
			self.__clearCache()
			self.update()
			self.log.debug(f'{repr(self)} refreshed: {lenBefore} -> {len(self)}')

	@property
	def hasForecast(self):
		if isinstance(self._source, ObservationTimeSeries):
			return any(v[self._key].timestamp > datetime.now(config.tz) for v in reversed(self._source.timeseries.values()) if self._key in v)
		for item in (e[self._key] for e in self._source.observations if self._key in e and hasattr(e[self._key], 'hasForecast')):
			if item.hasForecast and item.hasValues:
				return True
		return False

	@property
	def sources(self):
		if self.isMultiSource:
			return [e[self._key] for e in self._source.observations if self._key in e]
		else:
			return None

	@property
	def isMultiSource(self) -> bool:
		return not isinstance(self._source, ObservationTimeSeries)

	@property
	def hasValues(self):
		return any(v[self._key] for v in self._source.timeseries.values() if self._key in v)

	def update(self) -> None:
		currentLength = len(self)
		log.debug(f'{self} updating')
		self.clear()
		log.debug(f'{self} cleared with length {len(self)}')
		key = self._key
		if isinstance(self._source, ObservationTimeSeries):
			log.debug(f'{self} updating from single source of length {len(self._source.timeseries)}')
			itemCount = 0
			for item in (v[key] for v in self._source.timeseries.values() if key in v):
				itemCount += 1
				# self.updateItem(item)
				if item.value is None or item is None:
					sendPushoverMessage(title='Error', message=f'{self} has null value for {item.timestamp}')
					print(item.value)
				self[item.timestamp] = item
			log.debug(f'{self} updated from single source with {itemCount} expected items and a change of {len(self) - currentLength} [{currentLength} -> {len(self)}]')
		else:
			values = self.__sourcePull()

			for item in values:
				self[item.timestamp] = item
			log.debug(f'{self} updated from multiple sources with {len(self) - currentLength} [{currentLength} -> {len(self)}]')
		# self.removeOldValues()

		thisHash = self.__valuesHash()
		if thisHash != self.__lashHash:
			log.debug(f'{self} has changed...clearing cache and emitting signal')
			self.__clearCache()
			self.publish()
		else:
			log.debug(f'{self} has not changed')
		self.__lashHash = thisHash

	def __sourcePull(self) -> list[ObservationValue]:
		def calculatePeriod(arr) -> float:
			if len(arr) == 0:
				return timedelta(seconds=-1)
			timestamps = np.array([i.timestamp.timestamp() for i in arr])
			return (timestamps[1:-2] - np.roll(timestamps, 1)[1:-2]).mean()

		assert hasattr(self._source, 'observations')
		values: list[ObservationValue] = []
		sources: List[MeasurementTimeSeries, ObservationRealtime] = [e[self._key] for e in self._source.observations if self._key in e]

		log.debug(f'{self} refreshing sources')
		for item in sources:
			if isinstance(item, MeasurementTimeSeries):
				item.addReference(self)
				item.refresh()
				log.debug(f'{self} refreshed {item} with length: {len(item)}')

		sourcesString = ', '.join(f'{s} with length {len(s)}' for s in sources)
		expectedLength = sum(len(s) for s in sources)
		for item in sources:
			log.debug(f'Pulling from {item}')
			if isinstance(item, MeasurementTimeSeries):
				values.extend(item)
				log.debug(f'Pulled from {item} with length: {len(item)}')
			else:
				values.append(item)
				log.debug(f'Pulled from {item}')
		log.debug(f'{"✅" if len(values) == expectedLength else "❌"} {self} pulled from sources {len(sources)} with a new length of: {len(values)}.  Expected a length of: {expectedLength}')
		values.sort(key=lambda x: x.timestamp)
		return values

	def publish(self):
		self.signals.publish()

	def roll(self):
		self.__clearCache()

	def removeOldValues(self):
		keysToPop = []
		for key in self.keys():
			if key < datetime.now(key.tzinfo):
				keysToPop.append(key)
		for key in keysToPop:
			self.pop(key)

	# def __setitem__(self, key, value):
	# if isinstance(value, ValueWrapper) and not isinstance(key, (datetime, timedelta, DateKey)):
	# 	key = value.timestamp
	# if isinstance(key, (datetime, timedelta)):
	# 	key = DateKey(key)
	# if key in self and self[key] != value:
	# 	self.log.debug('Stored value is not the same as the new value, this should never happen')
	# else:
	# 	# self._source.signals.valueAdded.emit({'source': self._source, 'key': key, 'value': value})
	# 	# value.valueChanged.connect(self.__clearCache)
	# 	super(MeasurementTimeSeries, self).__setitem__(key, value)

	def __getitem__(self, key):
		if isinstance(key, slice):
			hashArgs = HashSlice(key.start, key.stop, key.step)
			return self.__getSlice(hashArgs)
		if len(self) == 0:
			self.update()
		if isinstance(key, (datetime, timedelta, Period)):
			if isinstance(key, timedelta):
				key = Now() + key
			if isinstance(key, Period):
				key = key.value
			if key in self or self.__withinExtendedRange(key):
				key = closest(list(self.keys()), key)
				return super(MeasurementTimeSeries, self).__getitem__(key)
		elif isinstance(key, int):
			return self.list[key]
		return super(MeasurementTimeSeries, self).__getitem__(key)

	def __missing__(self, key):
		source = sorted(list(self._source.timeseriesKeys()), key=lambda x: x.timestamp or x.value)
		start = source[0].value
		if key < start and abs(key - start) >= self.period:
			key = start
		stop = source[-1].value
		if key > stop and abs(key - stop) >= self.period:
			key = stop
		if start <= key <= stop:
			if self.__nullValue is None:
				cls = self._source.itemClass.itemClass
				itemSource = self._source[key]
				self.__nullValue = cls(value=None, key=self._key, source=itemSource, metadata=self.first.metadata)
			return self.__nullValue
		else:
			raise KeyError(key)

	def __withinExtendedRange(self, key, extend: timedelta = None):
		period = extend or self.period
		if isinstance(period, Period):
			period = period.value
		start = self.first.timestamp - period
		stop = self.last.timestamp + period
		return start <= key <= stop

	def __contains__(self, key):
		if isinstance(key, datetime):
			return super(MeasurementTimeSeries, self).__contains__(key) or self.first.timestamp <= key <= self.last.timestamp

	# previousKey = key - self.period
	# if super(MeasurementTimeSeries, self).__contains__(previousKey):
	# 	key -= self.period
	# 	return True
	# nextKey = key + self.period
	# if super(MeasurementTimeSeries, self).__contains__(nextKey):
	# 	key += self.period
	# 	return True

	def __convertKey(self, key) -> DateKey:
		if isinstance(key, int):
			key = datetime.now().astimezone(_timezones.utc) + timedelta(seconds=key*self.period.total_seconds())
		if isinstance(key, (datetime, timedelta)):
			key = DateKey(key)
		return key

	@lru_cache(maxsize=64)
	def __getSlice(self, key):
		if any(isinstance(item, datetime) for item in key):
			start = key.start or self.first.timestamp
			stop = key.stop or self.last.timestamp
			start, stop = sorted((start, stop))
			# step = key.step if key.step is not None else timedelta(minutes=1)
			if start.tzinfo is None:
				start = start.replace(tzinfo=config.tz)
			if stop.tzinfo is None:
				stop = stop.replace(tzinfo=config.tz)
			return [k for k in self if start <= k.timestamp <= stop]

	def __delitem__(self, key):
		key = self.__convertKey(key)
		if key in self:
			super(MeasurementTimeSeries, self).__delitem__(key)
			self.__clearCache()

	def __iter__(self):
		return iter(self.list)

	def __clearCache(self):
		log.debug(f'Clearing cache for {self}')
		clearCacheAttr(self, 'array')
		clearCacheAttr(self, 'timeseries')
		clearCacheAttr(self, 'timeseriesInts')
		clearCacheAttr(self, 'start')
		clearCacheAttr(self, 'list')
		self.__getSlice.cache_clear()

	def updateItem(self, value):
		key = DateKey(value.timestamp)
		self[key] = value

	@property
	def period(self):
		if self.isMultiSource:
			return max(self._source.observations.forecasts, key=lambda x: len(x)).period
		return self._source.period

	@cached_property
	def start(self):
		return self.list[0].timestamp

	@cached_property
	def array(self) -> np.array:
		return np.array([i.value for i in self.list])

	@cached_property
	def list(self):
		if len(self) == 0:
			self.update()
		l = list(self.values())
		return sorted(l, key=lambda x: x.timestamp)

	@cached_property
	def timeseries(self) -> np.array:
		return [i.timestamp for i in self.list]

	@cached_property
	def timeseriesInts(self) -> np.array:
		return np.array([x.timestamp.timestamp() for x in self.list])

	@property
	def last(self):
		return self.list[-1]

	@property
	def first(self):
		return self.list[0]
