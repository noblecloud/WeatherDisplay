from src import logging
from uuid import uuid4
from abc import ABCMeta
from datetime import datetime, timedelta
from functools import cached_property
from typing import Iterable, List, OrderedDict, Type, Union

import numpy as np
import WeatherUnits as wu
from dateutil.parser import parse
from PySide2.QtCore import QObject, Signal
from pytz import timezone
from WeatherUnits import Measurement

from src import config
from src.translators import Translator, unitDict
from src.utils import clearCacheAttr, closest, ForecastUpdateHandler, ObservationUpdateHandler, Period, DateKey
from src.catagories import CategoryDict, CategoryItem, ValueWrapper

log = logging.getLogger(__name__)

__all__ = ['ObservationDict', 'Observation', 'ObservationRealtime', 'ObservationForecast', 'ObservationForecastItem', 'MeasurementTimeSeries']


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
# 		for subCategory in self.values():
# 			if subCategory.hasSubKey(key):
# 				return True
# 		return False
#
# 		# return any(sub.hasSubKey(key) if isinstance(sub, Category) else key in sub for sub in [*self.values(), *self.keys()])
#
# 	def __repr__(self):
# 		string = self._name
# 		if self._value is not None:
# 			string = f'{string} [{self._value}]'
# 		values = [key for key, value in self.items() if isinstance(value, Category)]
# 		if values:
# 			string = f'{string} >> {values}'
# 		return string
#
# 	def __getitem__(self, item):
# 		if isinstance(item, str) and '.' not in item:
# 			if item in self.keys():
# 				return super(Category, self).__getitem__(item)
# 			else:
# 				for value in self.values():
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

class ObservationSignal(QObject):
	valueAdded = Signal(dict)
	updated = Signal(dict)


class ObservationDict(dict, metaclass=ABCMeta):
	_api: 'API'
	_time: datetime
	_period = Period.Now

	def __init_subclass__(cls, category: str = None, **kwargs):
		if category is None:
			pass
		else:
			cls.category = CategoryItem(category)
			return super(ObservationDict, cls).__init_subclass__()

	def __init__(self, *args, **kwargs):
		api = kwargs.get('api')
		if api is None:
			from src.api import API
			api = [value for value in args if isinstance(value, API)]
			if len(api) == 1:
				pass
			else:
				raise ValueError('An API must be specified')
		# self._period = kwargs.get('period', None)
		self._api = api
		self._uuid = uuid4()
		# self._categories = Category(self.category, self)
		super(ObservationDict, self).__init__()

	def __hash__(self):
		return hash(self._uuid)

	@property
	def translator(self):
		return self._translator

	@cached_property
	def normalizeDict(self):
		return {value['sourceKey']: key for key, value in self.translator.items() if 'sourceKey' in value}

	@property
	def period(self) -> timedelta:
		return self._period

	@property
	def timeframe(self) -> timedelta:
		return timedelta(seconds=0)

	@property
	def isForecast(self) -> bool:
		return self.timeframe >= timedelta(minutes=30)

	@property
	def isRealtime(self) -> bool:
		return self.period.total_seconds() == 0

	@property
	def api(self):
		return self._api

	def __setitem__(self, key, value):
		key = self._convertToCategoryItem(key)
		item = super(ObservationDict, self).get(key, None)
		if item is not None:
			if isinstance(item, ValueWrapper):
				if isinstance(value, ValueWrapper):
					value.update(**value.toDict())
				item.updateValue(**value)
			else:
				super(ObservationDict, self).__setitem__(key, value)
		else:
			if not bool(value):
				return super(ObservationDict, self).__setitem__(key, value)
			if not isinstance(value, ValueWrapper):
				value = ValueWrapper(**value)
				super(ObservationDict, self).__setitem__(key, value)
			if isinstance(value, ValueWrapper):
				self.signals.valueAdded.emit({'source': self, 'key': key, 'value': value})

	# toRefresh = self.categories[key[:-1]]
	# if isinstance(toRefresh, (dict, CategoryDict)):
	# 	for value in toRefresh.values():
	# 		if isinstance(value, CategoryDict):
	# 			value.refresh()

	def _convertToCategoryItem(self, key):
		if not isinstance(key, CategoryItem):
			key = CategoryItem(key)
		return key

	def __getitem__(self, item):

		#### ObservationDict __get__

		item = self._convertToCategoryItem(item)

		if item == 'time':
			return self._time

		try:
			return super(ObservationDict, self).__getitem__(item)
		except KeyError:
			pass
		# if key contains wildcards return a dict containing all the values
		# Possibly later change this to return a custom subcategory
		if any('*' in i for i in item):
			return self.categories[item]
			# if the last value in the key assume all matching values are being requested
			wildcardValues = {k: v for k, v in self.items() if k < item}
			if wildcardValues:
				return wildcardValues
			else:
				raise KeyError(f'No keys found matching {item}')
		else:
			# check to see if the key is a subcategory
			# try:
			return self.categories[item]

	# except KeyError:
	# 	raise KeyError(f'No key found matching {item}')

	@cached_property
	def categories(self):
		return CategoryDict(self, self, None)

	def __contains__(self, item):
		if not super(ObservationDict, self).__contains__(item):
			item = self._convertToCategoryItem(item)
			return any([item in i for i in (list(self.keys()))])
		else:
			return True


# class Translator(dict):
#
# 	def __getitem__(self, item):
# 		try:
# 			return super(Translator, self).__getitem__(item)
# 		except KeyError:
# 			pass
# 		try:
# 			x = {f'{key.split(".")[-1]}': value for key, value in self.items()}
#
#


class Observation(ObservationDict):
	unitDict = unitDict
	_translator: dict
	_time: datetime = None

	# def __new__(cls, *args, **kwargs):
	# 	period = kwargs.get('period')
	# 	if isinstance(period, dict):
	# 		period = timedelta(**period)
	# 		cls.period = period
	# 	return cls

	def __init__(self, *args, **kwargs):
		self.signals = ObservationSignal()
		super(Observation, self).__init__(*args, **kwargs)
		if not isinstance(self.__class__._translator, CategoryDict):
			self.__class__._translator = Translator(self._translator, observation=self)

		values = kwargs.get('values')
		if values is not None:
			pass
		else:
			values = {}
			for value in [value for value in args if isinstance(value, dict)]:
				values.update(value)
		self.update(values)

	# a = c.__contains__('temperature')
	# a = c['temperature']
	# self._translator = c

	def update(self, data: dict, **kwargs):
		data = self.__preprocess(data)
		data = self.translator.translate(data, time=self._time)
		for key, item in data.items():
			self[key] = item
		self.calculateMissing()

	def __getitem__(self, item: str):
		if item in self:
			return super(Observation, self).__getitem__(item)
		else:
			if isinstance(item, datetime) and item == self._time:
				return self
			return super(Observation, self).__getitem__(item)

	# def __setitem__(self, key: str, value):
	# 	key = key.split('.')
	# 	if key[0] == self.category:
	# 		key.pop(0)
	# 	key, remainder = key[0], key[1:]
	# 	category = self.get(key, Category(key, self))
	# 	category[remainder] = value
	# 	#self[key] = category
	# 	super(Observation, self).__setitem__(key, category)

	def printItem(self, item):
		print(item)

	def calculateMissing(self):
		keys = set(self.keys())
		light = {'environment.light.illuminance', 'environment.light.irradiance'}

		if 'environment.humidity.humidity' in self.keys():
			if 'environment.temperature.dewpoint' not in self.keys():
				temperature = self['environment.temperature.temperature']
				dewpoint = temperature.dewpoint(self['environment.humidity.humidity'].value)
				dewpointDict = temperature.toDict()
				dewpointDict['value'] = dewpoint
				self['environment.temperature.dewpoint'] = dewpointDict

	# if 'heatIndex' not in self.keys():
	# 	self['heatIndex'] = self['temperature'].heatIndex(self['humidity'])

	# if 'windChill' not in self.keys() and 'windSpeed' in self.keys():
	# 	self['windChill'] = self['temperature'].windChill(self['windSpeed'])

	# if keys.intersection(light) and not keys.issubset(light):
	# 	if 'environment.light.irradiance' in self.keys():
	# 		self['environment.light.illuminance'] = self['environment.light.irradiance'].lux
	# 	else:
	# 		self['environment.light.irradiance'] = self['environment.light.illuminance'].wpm2

	def _updateValue(self, key, value):
		self[key] = self.translator.convert(key, value)

	def __preprocess(self, data: dict):
		if data:
			self._time = self.__processTime(data)
			# if not all(key in self.translator for key in data.keys()):
			# 	data = {self.normalizeDict[key]: value for key, value in data.items() if key in self.normalizeDict.keys()}
			return data
		return data

	def __processTime(self, data: dict, pop: bool = False) -> datetime:
		timeKey = self.timeKey(data)
		tzKey = self.timezoneKey(data)
		if tzKey is not None:
			tz = timezone(data.get(tzKey, None))
		else:
			tz = config.tz
		if tz is None:
			tz = config.tz
		value = data.pop(timeKey, None)
		if value is not None:
			value = self._translator.convert(timeKey, value)[1]['value']

		if isinstance(value, datetime):
			if value.tzinfo is None:
				value = value.replace(tzinfo=tz)
			return value
		try:
			return parse(value).astimezone(tz)
		except TypeError:
			return datetime.fromtimestamp(value).astimezone(tz)

	@cached_property
	def normalizeDict(self):
		return {value['sourceKey']: value.key for value in self.translator.values()}

	# elif unitDefinition == 'ISO8601':
	# 	return parse(_value).astimezone(config.tz)

	@classmethod
	def timeKey(cls, data) -> str:
		if 'time.time' in data:
			return 'time.time'
		if cls._translator['time.time']['sourceKey'] in data:
			return cls._translator['time.time']['sourceKey']
		else:
			return (set(data.keys()).intersection({'time', 'timestamp', 'day_start_local', 'date', 'datetime'})).pop()

	@classmethod
	def timezoneKey(cls, data) -> str:
		if 'time.timezone' in data:
			return 'time.timezone'
		if 'time.timezone' in cls._translator:
			return cls._translator['time.timezone']['sourceKey']
		else:
			value = set(data.keys()).intersection({'timezone', 'timezone_name', 'tz'})
			if value:
				return value.pop()
			else:
				return None

	@classmethod
	def observationKey(cls, data) -> DateKey:
		timeData = cls._translator['time.time']
		timeValue = data[cls.timeKey(data)]
		tz = data.get(cls.timezoneKey(data), config.tz)
		if timeData['sourceUnit'] == 'epoch':
			return DateKey(datetime.fromtimestamp(timeValue, tz))
		if timeData['sourceUnit'] == 'ISO8601':
			key = DateKey(parse(timeValue).astimezone(tz))
			return key

	# def convertValue(self, key, value):
	# 	measurementData = self.translator[key]
	# 	unitDefinition = measurementData['sourceUnit']
	# 	typeString = measurementData['type']
	# 	title = measurementData['title']
	# 	if isinstance(unitDefinition, list):
	# 		n, d = [self.unitDict[cls] for cls in unitDefinition]
	# 		comboCls: DerivedMeasurement = self.unitDict['special'][typeString]
	# 		measurement = comboCls(n(value), d(1), title=title, key=key, timestamp=self._time)
	# 	elif unitDefinition == '*':
	# 		specialCls = self.unitDict['special'][typeString]
	# 		kwargs = {'title': title, 'key': key, 'timestamp': self._time} if issubclass(specialCls, wu.Measurement) else {}
	# 		measurement = specialCls(value, **kwargs)
	# 	elif typeString in ['date', 'datetime']:
	# 		if isinstance(value, datetime):
	# 			measurement = value
	# 		else:
	# 			if unitDefinition == 'epoch':
	# 				measurement = datetime.fromtimestamp(value)
	# 			elif unitDefinition == 'ISO8601':
	# 				measurement = datetime.strptime(value, measurementData['format'])
	# 			else:
	# 				measurement = datetime.now()
	# 				log.warning(f'Unable to convert date value "{value}" defaulting to current time')
	# 	elif typeString == 'timedelta':
	# 		if unitDefinition == 'epoch':
	# 			measurement = self.unitDict['s'](value, title=title, key=key)
	# 		elif unitDefinition == 'ISO8601':
	# 			measurement = ISOduration(value)
	# 	else:
	# 		cls = self.unitDict[unitDefinition]
	# 		if issubclass(cls, wu.Measurement):
	# 			measurement = cls(value, title=title, key=key, timestamp=self._time)
	# 		else:
	# 			measurement = cls(value)
	#
	#
	# 	if isinstance(measurement, wu.Measurement):
	# 		measurement = measurement.localize
	# 	# else:
	# 	# 	cls = wrapClass(type(measurement))
	# 	# 	# measurement = ValueWrapper(_value=measurement, title=title, key=key, timestamp=self._time, category=category, unit=unitDefinition)
	# 	# 	# a = measurement + timedelta(seconds=100)
	# 	# 	print(measurement.now())
	# 	# 	print(measurement)
	#
	# 	return measurement

	@property
	def translator(self):
		return self._translator

	@property
	def time(self):
		return self._time


class ObservationRealtime(Observation):
	time: datetime
	timezone: timezone
	subscriptionChannel: str = None
	_indoorOutdoor: bool = False
	updateHandler: ObservationUpdateHandler

	def __init__(self, *args, **kwargs):
		# self.source = 'tcp'
		super(ObservationRealtime, self).__init__(*args, **kwargs)

	def __setitem__(self, key, value):
		# updateAfter = key not in self
		super(ObservationRealtime, self).__setitem__(key, value)

	# if updateAfter:
	# 	self.updateHandler.new(key)

	def _updateValue(self, key, value):
		if isinstance(value, wu.Measurement):
			if key in self.keys():
				self[key] |= value
			else:
				self[key] = value
		else:
			super(ObservationRealtime, self)._updateValue(key, value)
		self.updateHandler.autoEmit(key)

	def udpUpdate(self, data):
		self.update(data)

	def emitUpdate(self, key):
		if key in self.signals.keys():
			signal = self.signals[key]
			signal.emit(self[key])

	def tryToSubscribe(self, key):
		if key in self.signals.keys():
			self.signals[key]
		else:
			self.signals.update({key: [signal]})
		try:
			signal.emit(self[key])
		except KeyError:
			log.error(f'API does not have that {key} yet, will emit when added')


class ForecastValues(dict):

	def __init__(self, reference: 'ObservationForecast'):
		self.__reference = reference
		super(ForecastValues, self).__init__({})
		self.__cashedKeys = set()

	def __getitem__(self, key):
		if key not in self and key in self.__reference.valueKeys:
			self.__cashedKeys.add(key)
			ref = self.__reference
			self[key] = MeasurementTimeSeries(ref, key, [a[key] if key in a else None for a in ref['time'].values()])
		return super(ForecastValues, self).__getitem__(key)

	def items(self):
		for key in self.__reference.valueKeys:
			yield key, self[key]


class ObservationForecast(ObservationDict):
	_knownKeys: list[str] = []
	observations: dict[CategoryItem, 'MeasurementTimeSeries']
	_fieldsToPop = []
	_maxTime: int = 24 * 3
	_observationClass: Type[Observation] = Observation
	period: timedelta
	timeframe: timedelta
	keyDict: ForecastValues[str, 'MeasurementTimeSeries']

	def __init__(self, *args, **kwargs):
		self.keyDict = ForecastValues(self)
		self.signals = ObservationSignal()
		super(ObservationForecast, self).__init__(*args, **kwargs)
		self['time']: dict[DateKey, Observation] = {}
		self.observations = {}

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

		raw = data

		if isinstance(raw, dict):
			raw = list(raw.values())

		self.calculatePeriod(raw)

		keys = [self.normalizeDict[key] for key in {key for obs in (data.values() if isinstance(data, dict) else data) for key in obs.keys()} if key in self.normalizeDict.keys()]
		if isinstance(raw, List):
			for rawObs in raw:
				key = self.__makeKey(rawObs)
				obs = self['time'].get(key)
				if obs is None:
					self['time'][key] = self._observationClass(parentObservation=self, values=rawObs, api=self.api, period=self.period)
				else:
					self['time'][key].update(rawObs)
		for key in keys:
			values = [i[key] for i in self['time'].values()]
			if key in self.observations.keys():
				self.observations[key].update(values)
			else:
				self.observations[key] = MeasurementTimeSeries(self, key, values)

	# for key in self.knownKeys:
	# 	self.__updateObsKey(key)

	def calculatePeriod(self, data: list):
		time = np.array([self._observationClass.observationKey(v).timestamp() for v in data])
		time = (time - np.roll(time, 1))[1:].mean()
		self._period = timedelta(seconds=time)

	def __updateObsKey(self, key):
		# self[key] = {k1: _value[key] for k1, _value in self['time'].items() if key in _value.keys()}
		# self[key] = MeasurementTimeline(self, key)
		self[key] = MeasurementTimeSeries(self, key, [x[key] if key in x.keys() else None for x in self['time'].values()])

	def __genObsValueForKey(self, key):
		self[key] = [None if key not in x.keys() else x[key] for x in self['time'].values()]

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
		return self._observationClass._translator

	def observationKeys(self):
		return list({key for obs in (self['time'].values() if isinstance(self['time'], dict) else self['time']) for key in obs.keys()})

	def __makeKey(self, data: dict):
		return self._observationClass.observationKey(data)

	def __getitem__(self, key) -> Union[List[Measurement], Observation]:
		# if key in self._knownKeys:
		# self[key] = {k1: _value[key] for k1, _value in self['time'].items() if key in _value.keys()}
		if key in ['time', 'datetime', 'timestamp']:
			return dict.get(self, 'time')
		if isinstance(key, int):
			key = list(self['time'].keys())[key]
			return self['time'][key]
		if not any(key in k for k in self.observationKeys()):

			if isinstance(key, int):
				return list(self['time'].values())[key]

			if isinstance(key, datetime):
				timestamp = int(key.timestamp())
				key = closest(list(self['time'].keys()), timestamp)
				return self['time'][key]

		else:
			# values = {K: MeasurementTimeSeries(self, K, [i[K] for i in self['time'].values()]) for K in self.observationKeys() if key in K}
			# if len(values) == 1:
			# 	return values.popitem()[1]
			# return values
			if key in self.observations:
				return self.observations[key]
			if key in self.observationKeys():
				value = [i[key] for i in self['time'].values()]
				series = MeasurementTimeSeries(self, key, value)
				self.observations[key] = series
				return series
			else:
				raise KeyError(key)

	@cached_property
	def categories(self):
		return CategoryDict(self, self.keyDict, None)

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
		for field in self._fieldsToPop:
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


class ObservationForecastItem(Observation):

	def __init__(self, *args, parentObservation: ObservationForecast, **kwargs):
		self.__parent = parentObservation
		super(ObservationForecastItem, self).__init__(*args, **kwargs)


from collections import deque


class MeasurementTimeSeries(OrderedDict):
	_key: str
	_source: ObservationForecast
	offset = 0

	def __init__(self, source: ObservationForecast, key: str, values: Iterable):
		self._source = source
		self._key = key
		self.signals = ObservationSignal()
		super(MeasurementTimeSeries, self).__init__()
		self.signals.blockSignals(True)
		self.update(values)
		self.signals.blockSignals(False)

	def __hash__(self):
		return hash(self._key)

	def pullUpdate(self):
		self.update()

	def update(self, *V) -> None:

		if len(V) == 1:
			V = V[0]
		for v in V:
			if isinstance(v, ValueWrapper):
				self[v.timestamp] = v
		self.removeOldValues()
		self.__clearCache()
		self.signals.updated.emit(self)

	def roll(self):
		self.__clearCache()
		self.signals.updated.emit(self)

	def removeOldValues(self):
		keysToPop = []
		for key in self.keys():
			if key < datetime.now(key.tzinfo):
				keysToPop.append(key)
		for key in keysToPop:
			self.pop(key)

	def __setitem__(self, key, value):
		if isinstance(value, ValueWrapper) and not isinstance(key, (datetime, timedelta, DateKey)):
			key = value.timestamp
		if isinstance(key, (datetime, timedelta)):
			key = DateKey(key)
		if key in self:
			self[key].updateValue(**value.toDict())
		else:
			# self._source.signals.valueAdded.emit({'source': self._source, 'key': key, 'value': value})
			# value.valueChanged.connect(self.__clearCache)
			super(MeasurementTimeSeries, self).__setitem__(key, value)

	def __getitem__(self, key):
		if isinstance(key, (datetime, timedelta)):
			key = DateKey(key)
		if key in self:
			return super(MeasurementTimeSeries, self).__getitem__(key)
		elif isinstance(key, int):
			return list(self.values())[key]
		return super(MeasurementTimeSeries, self).__getitem__(key)

	def __convertKey(self, key) -> DateKey:
		if isinstance(key, int):
			key = datetime.now() + timedelta(seconds=key * self.period.total_seconds())
		if isinstance(key, (datetime, timedelta)):
			key = DateKey(key)
		return key

	def __delitem__(self, key):
		key = self.__convertKey(key)
		if key in self:
			super(MeasurementTimeSeries, self).__delitem__(key)
			self.__clearCache()

	def __iter__(self):
		return iter(self.values())

	def __clearCache(self):
		clearCacheAttr(self, 'array')
		clearCacheAttr(self, 'timeseries')
		clearCacheAttr(self, 'start')

	def updateItem(self, value):
		key = DateKey(value.timestamp)
		self[key] = value

	@cached_property
	def start(self):
		return min(self.keys())

	@property
	def period(self):
		return self._source.period

	@cached_property
	def array(self) -> np.array:
		return np.array([i.value for i in self.values()])

	@cached_property
	def timeseries(self) -> np.array:
		return np.array([x.timestamp.timestamp() for x in self.values()])
