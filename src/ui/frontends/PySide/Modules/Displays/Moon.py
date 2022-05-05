from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Iterable, Tuple

import numpy as np
import pylunar
from PySide2.QtCore import QPointF, Qt, QTimer, Signal
from PySide2.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QTransform
from PySide2.QtWidgets import QApplication, QGraphicsPathItem, QGraphicsRectItem, QGraphicsBlurEffect, QGraphicsItem
from pysolar import solar

from src.ui.frontends.PySide.utils import colorPalette
from src.ui.frontends.PySide.Modules.Panel import Panel
from src.ui.frontends.PySide.utils import addCrosshair
from src.utils.shared import clearCacheAttr
from src.config import userConfig

golden = (1 + np.sqrt(5))/2
dark = QColor(28, 29, 31, 255)

__all__ = ["Moon"]


class ThreeDimensionalPoint:
	__slots__ = ["x", "y", "z"]

	def __init__(self, x: float, y: float, z: float):
		self.x = x
		self.y = y
		self.z = z

	def __repr__(self):
		return f'<ThreeDimensionalPoint> x: {self.x}, y: {self.y}, z: {self.z}'

	def __add__(self, other: "ThreeDimensionalPoint") -> "ThreeDimensionalPoint":
		return ThreeDimensionalPoint(self.x + other.x, self.y + other.y, self.z + other.z)

	def __sub__(self, other: "ThreeDimensionalPoint") -> "ThreeDimensionalPoint":
		return ThreeDimensionalPoint(self.x - other.x, self.y - other.y, self.z - other.z)

	def __mul__(self, other: float) -> "ThreeDimensionalPoint":
		return ThreeDimensionalPoint(self.x*other, self.y*other, self.z*other)

	def __truediv__(self, other: float) -> "ThreeDimensionalPoint":
		return ThreeDimensionalPoint(self.x/other, self.y/other, self.z/other)

	def toQPointF(self) -> QPointF:
		return QPointF(self.x, self.y)

	def multipliedQPointF(self, other: float) -> QPointF:
		return QPointF(self.x*other, self.y*other)


class MoonBack(QGraphicsPathItem):

	def __init__(self, parent: 'Moon'):
		super().__init__()
		self.setParentItem(parent)
		self.setAcceptHoverEvents(False)
		self.setAcceptedMouseButtons(Qt.NoButton)
		self.setPen(QPen(Qt.NoPen))
		self.setBrush(QBrush(dark))
		self.setZValue(-1)
		self.draw()

	def draw(self):
		bounds = self.parentItem().rect()
		path = QPainterPath()
		radius = min(bounds.width(), bounds.height())/2
		path.addEllipse(QPointF(0, 0), radius, radius)
		self.setPath(path)

	def paint(self, painter: QPainter, option, widget):
		tW = painter.worldTransform()
		scale = min(tW.m11(), tW.m22())
		tW.scale(1/tW.m11(), 1/tW.m22())
		tW.scale(scale, scale)
		painter.setWorldTransform(tW, False)
		super().paint(painter, option, widget)


class MoonFront(QGraphicsPathItem):

	def __init__(self, parent: 'Moon'):
		super().__init__()
		self.setParentItem(parent)
		self.setAcceptHoverEvents(False)
		self.setAcceptedMouseButtons(Qt.NoButton)
		self.setPen(QPen(Qt.NoPen))
		self.setBrush(colorPalette.windowText().color())
		self.setZValue(1)
		self.draw()

	def sphericalToCartesian(self, ascension: float, declination: float) -> ThreeDimensionalPoint:
		ascension += 90
		ascension = np.deg2rad(ascension)
		declination = np.deg2rad(declination)
		return ThreeDimensionalPoint(x=float(np.sin(ascension)*np.sin(declination)), y=float(np.cos(declination)), z=float(np.cos(ascension)*np.sin(declination)))

	def sphericalToCartesianArray(self, ascension: float, declination: Iterable) -> ThreeDimensionalPoint:
		values = np.array(list(declination))
		values = np.deg2rad(values)
		ascension = np.deg2rad(ascension + 90)
		x = np.sin(ascension)*np.sin(values)
		y = np.cos(values)
		# z = np.cos(ascension) * np.sin(values)
		return np.array([x, y]).T

	@cached_property
	def pathPoints(self):
		## Todo: try to rewrite this to use an ellipse/curve rather than 240 lines
		phase = self.parentItem().phase
		r1 = range(0, 180, 3)
		r2 = range(180, 360, 3)
		if phase < 180:
			p1 = self.sphericalToCartesianArray(phase, r1)
			p2 = self.sphericalToCartesianArray(180, r2)
		else:
			p1 = self.sphericalToCartesianArray(180, r1)
			p2 = self.sphericalToCartesianArray(phase, r2)

		points = np.concatenate((p1, p2), axis=0)

		return points

	def draw(self):
		path = QPainterPath()
		points = [QPointF(*point) for point in self.pathPoints*self.parentItem().radius]
		path.moveTo(points[0])
		for point in points:
			path.lineTo(point)
		path.closeSubpath()
		t = QTransform()
		t.rotate(self.parentItem().getAngle())
		path = t.map(path)
		self.setPath(path.simplified())

		self.setTransformOriginPoint(self.parentItem().rect().center())

	def paint(self, painter, option, widget):
		# addCrosshair(painter, color=Qt.green, size=10, width=2)
		tW = painter.worldTransform()
		scale = min(tW.m11(), tW.m22())
		tW.scale(1/tW.m11(), 1/tW.m22())
		tW.scale(scale, scale)
		painter.setWorldTransform(tW, False)
		super().paint(painter, option, widget)


# def paint(self, painter, option, widget):
# 	# painter.drawPath(self.path())
# 	super(MoonFront, self).paint(painter, option, widget)


class MoonGlowEffect(QGraphicsBlurEffect):
	def __init__(self):
		super().__init__(None)
		self.setBlurRadius(10)
		# self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
		self.setBlurHints(QGraphicsBlurEffect.QualityHint)

	def draw(self, painter: QPainter):
		tW = painter.worldTransform()
		painter.setRenderHint(QPainter.HighQualityAntialiasing)
		scale = min(tW.m11(), tW.m22())
		tW.scale(1/tW.m11(), 1/tW.m22())
		tW.scale(scale, scale)
		painter.setTransform(tW, False)

		self.drawSource(painter)
		painter.setCompositionMode(QPainter.CompositionMode_Lighten)
		super().draw(painter)


class Moon(Panel):
	moonFull: QPainterPath
	moonPath: QPainterPath
	_date: datetime
	_phase: float = 0
	rotation: float = 0.0
	_interval = timedelta(minutes=5)

	valueChanged = Signal(float)

	def __init__(self, *args, **kwargs):
		self.__phase = 0
		self.lat, self.lon = userConfig.loc
		self._date = datetime.now(userConfig.tz)
		self.refreshData()
		super(Moon, self).__init__(*args, **kwargs)
		self.setFlag(self.ItemHasNoContents, False)
		self.moonFull.setParentItem(self)
		self.moonPath.setParentItem(self)
		self.moonPath.setPos(self.boundingRect().center())
		self.moonPath.setGraphicsEffect(MoonGlowEffect())

		# Build timer
		self.timer = QTimer()
		self.timer.setInterval(1000*self._interval.total_seconds())
		# self.timer.setInterval(200)
		self.timer.setTimerType(Qt.VeryCoarseTimer)
		self.timer.timeout.connect(self.updateMoon)
		self.timer.start()
		self.updateFromGeometry()
		self._acceptsChildren = False
		self.updateMoon()

	@property
	def isEmpty(self):
		return False

	@cached_property
	def moonFull(self) -> MoonBack:
		return MoonBack(self)

	@cached_property
	def moonPath(self) -> MoonFront:
		return MoonFront(self)

	@cached_property
	def _moonInfo(self) -> pylunar.MoonInfo:
		return pylunar.MoonInfo(self.deg2dms(self.lat), self.deg2dms(self.lon))

	@property
	def visibleWidth(self):
		return self.rect().width()

	@property
	def visibleHeight(self):
		return self.rect().height()

	@property
	def radius(self) -> float:
		return min(self.visibleHeight, self.visibleWidth)/2

	def refreshData(self):
		self._date = datetime.now(timezone.utc)
		self._moonInfo.update(tuple(self._date.timetuple()[:-3]))
		self._phase = self._moonInfo.fractional_age()*360

	def updateMoon(self):
		self.refreshData()
		self.redrawMoon()

	def redrawMoon(self):
		clearCacheAttr(self, 'pathPoints')
		self.moonPath.draw()
		self.moonFull.draw()

	# self.moonPath.setRotation(self.getAngle())

	def getAngle(self) -> float:
		"""https://stackoverflow.com/a/45029216/2975046"""

		sunalt = solar.get_altitude_fast(self.lat, self.lon, self._date)
		sunaz = solar.get_azimuth_fast(self.lat, self.lon, self._date)
		moonaz = self._moonInfo.azimuth()
		moonalt = self._moonInfo.altitude()

		dLon = (sunaz - moonaz)
		y = np.sin(np.deg2rad(dLon))*np.cos(np.deg2rad(sunalt))
		x = np.cos(np.deg2rad(moonalt))*np.sin(np.deg2rad(sunalt)) - np.sin(np.deg2rad(moonalt))*np.cos(np.deg2rad(sunalt))*np.cos(np.deg2rad(dLon))
		brng = np.arctan2(y, x)
		brng = np.rad2deg(brng)
		return (brng + 90)%360

	@staticmethod
	def deg2dms(dd: float) -> Tuple[float, float, float]:
		mnt, sec = divmod(dd*3600, 60)
		deg, mnt = divmod(mnt, 60)
		return deg, mnt, sec

	@property
	def phase(self):
		return self._phase

	def setRect(self, rect):
		super().setRect(rect)
		self.moonPath.setPos(rect.center())
		self.moonPath.draw()
		self.moonFull.setPos(rect.center())
		self.moonFull.draw()
		effect = self.moonPath.graphicsEffect()
		self.setCacheMode(QGraphicsItem.CacheMode.ItemCoordinateCache)
		if effect is not None:
			effect.updateBoundingRect()
			effect.update()

# def paint(self, painter: QPainter, option, widget):
# 	painter.setPen(Qt.red)
# 	painter.drawRect(self.rect())
# 	w = self.rect().width() / 2
# 	one = QPointF(w, 0)
# 	two = QPointF(w, self.rect().height())
# 	painter.drawLine(one, two)
# 	super(Moon, self).paint(painter, option, widget)


if __name__ == '__main__':
	from PySide2.QtWidgets import QApplication, QGraphicsView, QGraphicsScene
	from PySide2.QtCore import QSize, QRectF
	from src import app
	from GridView import TestWindow
	import sys

	QApplication.setAttribute(Qt.AA_UseDesktopOpenGL)
	# app = QApplication(sys.argv)

	window = TestWindow()

	# window.scene().addItem(rect)
	# rect.setPos(100, 100)
	# marginHandles = Handles(rect)
	# d = DrawerHandle(rect)
	moon = Moon(parent=window.graphicsScene.base)
	# moon.setParentItem()
	window.show()

	g = window.geometry()
	screen = app.screens()[-1].geometry()
	g.setWidth(screen.width()*0.8)
	g.setHeight(screen.height()*0.8)
	g.moveCenter(screen.center())

	window.setGeometry(g)

	g = window.geometry()
	g.setSize(QSize(800, 600))
	# g.moveCenter(app.screens()[1].geometry().center())
	window.setGeometry(g)
	window.show()
	# marginHandles.update()
	sys.exit(app.exec_())

	# window.phase = 2
	display_monitor = 1
	# monitor = QDesktopWidget().screenGeometry(display_monitor)
	window.move(monitor.left(), monitor.top())
	# SECOND_DISPLAY = True
	# if SECOND_DISPLAY:
	# 	display = app.screens()[1]
	# 	window.setScreen(display)
	# 	window.move(display.geometry().x() + 200, display.geometry().y() + 200)
	window.show()

	sys.exit(app.exec_())