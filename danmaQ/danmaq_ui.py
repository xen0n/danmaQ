#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
import sys
import re
from cgi import escape
from random import randint
from threading import Lock

from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import pyqtSignal

from .settings import load_config, multiscreen_manager

color_styles = {
    "white": ('rgb(255, 255, 255)', QtGui.QColor("black"), ),
    "black": ('rgb(0, 0, 0)', QtGui.QColor("white"), ),
    "blue": ('rgb(20, 95, 198)', QtGui.QColor("white"), ),
    "cyan": ('rgb(0, 255, 255)', QtGui.QColor("black"), ),
    "red": ('rgb(231, 34, 0)', QtGui.QColor("white"), ),
    "yellow": ('rgb(255, 221, 2)', QtGui.QColor("black"), ),
    "green": ('rgb(4, 202, 0)', QtGui.QColor("black"), ),
    "purple": ('rgb(128, 0, 128)', QtGui.QColor("white"), ),
}

OPTIONS = load_config()

if sys.platform == "win32":
    import win32api


class Danmaku(QtGui.QLabel):
    _lock = Lock()
    vertical_slots = None
    fly_slots = None

    _font_family = OPTIONS['font_family']
    _speed_scale = OPTIONS['speed_scale']
    _font_size = OPTIONS['font_size']
    _to_extend_screen = OPTIONS['to_extend_screen']
    _interval = 30
    _style_tmpl = "font-size: {font_size}pt;" \
        + "font-family: {font_family};" \
        + "font-weight: bold;" \
        + "color: {color}; "
    _lineheight = 0
    _outline_width = 5

    exited = pyqtSignal(str, name="exited")

    @classmethod
    def init_lineheight(cls, par=None):
        Danmaku("test", position='top', lifetime=10, effect='_init_lineheight', parent=par)

    @classmethod
    def set_options(cls, opts):
        cls._font_family = opts['font_family']
        cls._font_size = opts['font_size']
        cls._speed_scale = opts['speed_scale']
        cls._to_extend_screen = opts['to_extend_screen']

    @classmethod
    def escape_text(cls, text):
        text = escape(text)
        text = re.sub(r'([^\\])\\n', r'\1<br/>', text)
        text = re.sub(r'\\\\n', r'\\n', text)
        text = re.sub(r'\[s\](.+)\[/s\]', r'<s>\1</s>', text)
        return text

    def __init__(self, text="text", style='white', position='fly',
                 lifetime=10*1000, effect='dropshadow', parent=None):
        text = self.escape_text(text)
        super(Danmaku, self).__init__(text, parent)

        self._text = text
        self._style = style
        self._position = position
        self._lifetime = lifetime
        self._effect = effect

        self.setWindowTitle("Danmaku")
        self.setStyleSheet("background:transparent; border:none;")
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

        self.setWindowFlags(
            QtCore.Qt.ToolTip
            | QtCore.Qt.FramelessWindowHint
        )

        if sys.platform == "win32":
            # Win32 Dark Magic, disable window drop shadows
            win32api.SetClassLong(
                self.winId().__int__(),
                -26,
                0x0008 & ~0x00020000)

        self.init_text(text, style)

        self._width = self.frameSize().width()
        self._height = self.frameSize().height()
        self._slot = None

        self.screenIdx = multiscreen_manager.get_screen_idx(self._to_extend_screen)
        self.screenGeo = multiscreen_manager.geometry(self.screenIdx)
        # self._shift = QtGui.QDesktopWidget().availableGeometry(screen=0).width()
        self._offset_x = multiscreen_manager.get_offset_x(self.screenIdx, False)
        self._origin_y = multiscreen_manager.get_origin_y(self.screenIdx)
        self._traveled_x = 0
        self._total_distance = self.screenGeo.width() + self._width
        with Danmaku._lock:
            if Danmaku.vertical_slots is None:
                Danmaku._lineheight = self._height
                Danmaku.vertical_slots = [0] * \
                    ((self.screenGeo.height() - 20) // self._height)
                Danmaku.fly_slots = [0] * \
                    ((self.screenGeo.height() - 20) // self._height)

        self.quited = False
        self.position_inited = False
        self.init_position()

    def init_text(self, text, style):
        # self.label = QtGui.QLabel(text, parent=self)
        tcolor, bcolor = color_styles.get(style, color_styles['white'])

        if self._effect == 'dropshadow':
            effect = QtGui.QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(7)
            effect.setColor(bcolor)
            effect.setOffset(0, 0)
            self.setGraphicsEffect(effect)
            self.setContentsMargins(0, 0, 0, 0)
        elif self._effect == 'outline':
            w = self._outline_width
            self.setContentsMargins(w, w, w, w)

        self.setStyleSheet(
            self._style_tmpl.format(
                font_size=self._font_size,
                font_family=self._font_family,
                color=tcolor,
            )
        )


        # layout = QtGui.QVBoxLayout()
        # layout.addWidget(self.label, 0, QtCore.Qt.AlignVCenter)
        # layout.setContentsMargins(0, 0, 0, 0)
        # self.setLayout(layout)

        _msize = self.minimumSizeHint()
        # _msize.setHeight(self.label.height()+16)
        self.resize(_msize)

    def init_position(self):
        self.vslots = None
        self.fslots = None
        self.show()
        nlines = self._text.count('<br/>') + 1
        # print("height: {}, lineheight: {}".format(self._height, self._lineheight))
        if self._position == 'fly':
            # NOTE: later offseted
            self.x = self.screenGeo.width()

            slot = None
            with Danmaku._lock:
                if nlines > 1:
                    for i, v in enumerate(self.fly_slots):
                        if v == 0:
                            for j in range(nlines):
                                try:
                                    self.fly_slots[i+j] = self
                                except IndexError:
                                    break

                            slot = i
                            break
                else:
                    m = len(self.fly_slots) // 2
                    _upper = len(self.fly_slots) // 4
                    for _ in range(m+1):
                        i = randint(0, _upper)
                        if self.fly_slots[i] == 0:
                            self.fly_slots[i] = self
                            slot = i
                            break
                        _upper *= 2
                        if _upper > len(self.fly_slots) - 1:
                            _upper = len(self.fly_slots) - 1
                    # for i in range(m+1)[::-1]:
                    #     if self.fly_slots[i] == 0:
                    #         self.fly_slots[i] = self
                    #         slot = i
                    #         break
                    #     elif self.fly_slots[-i] == 0:
                    #         self.fly_slots[-i] = self
                    #         slot = len(self.fly_slots) - i
                    #         break
            # print(len(self.fly_slots), self.fly_slots)

            if slot is None:
                self.hide()
                QtCore.QTimer.singleShot(10, self.clean_close)
                return
            else:
                self.y = min(
                    slot * self._lineheight + 20,
                    self.screenGeo.height() - self._height - 20
                )
                self.fslots = [i+j for j in range(nlines)]

                self.step = (
                    (self.screenGeo.width() + self._width)
                    / (self._lifetime / self._interval)
                    * self._speed_scale
                )

                QtCore.QTimer.singleShot(self._interval, self.fly)

        elif self._position == 'bottom':
            self.x = (self.screenGeo.width() - self._width) / 2
            got = False
            with Danmaku._lock:
                i = 0
                for i, v in enumerate(Danmaku.vertical_slots[::-1]):
                    if v == 0:
                        for j in range(nlines):
                            try:
                                Danmaku.vertical_slots[-(i+j+1)] = 1
                            except IndexError:
                                break
                        self.vslots = [-(i+j+1) for j in range(nlines)]
                        got = True
                        break

            if not got:
                self.hide()
                QtCore.QTimer.singleShot(10, self.clean_close)
                return
            else:
                self.y = (self.screenGeo.height()
                          + self._lineheight * self.vslots[-1] - 20)
                QtCore.QTimer.singleShot(self._lifetime, self.clean_close)

        elif self._position == 'top':
            self.x = (self.screenGeo.width() - self._width) / 2
            got = False
            with Danmaku._lock:
                i = 0
                for i, v in enumerate(Danmaku.vertical_slots):
                    if v == 0:
                        for j in range(nlines):
                            try:
                                Danmaku.vertical_slots[i+j] = 1
                            except IndexError:
                                break
                        self.vslots = [i+j for j in range(nlines)]
                        got = True
                        break
                # else:
                #     self.hide()
                #     QtCore.QTimer.singleShot(1000, self.init_position)
                #     return

            if not got:
                self.hide()
                QtCore.QTimer.singleShot(10, self.clean_close)
                return
            else:
                self.y = self._lineheight * self.vslots[0] + 20
                QtCore.QTimer.singleShot(self._lifetime, self.clean_close)

        # shift to the extend screen
        #if self._to_extend_screen:
        #    print(self._shift)
        #    self.x += self._shift

        # true multiscreen
        self.x += self._offset_x
        self.y += self._origin_y
        print("initial: (%d, %d)" % (self.x, self.y, ))

        self.move(self.x, self.y)
        self.position_inited = True

    def fly(self):
        _x = int(self.x)
        # TODO: reverse
        self.x -= self.step
        x_dst = int(self.x)
        self._traveled_x += _x - x_dst
        if (self.fly_slots[self.fslots[0]] == self
           and self.x + self._width < int(self.screenGeo.width() * 0.4)):
                for i in self.fslots:
                    if i >= len(self.fly_slots):
                        break
                    Danmaku.fly_slots[i] = 0

        if self._traveled_x > self._total_distance:
            self.clean_close()
        else:
            QtCore.QTimer.singleShot(self._interval, self.fly)

        if _x != x_dst:
            self.move(x_dst, self.y)

    def paintEvent(self, event):
        effect = self._effect

        if effect == '_init_lineheight':
            # don't flicker during initialization
            return

        if effect != 'outline':
            return super(Danmaku, self).paintEvent(event)

        # super(Danmaku, self).paintEvent(event)
        painter = QtGui.QPainter(self)
        pen = QtGui.QPen()
        font = self.font()
        ow = self._outline_width
        pen_width = ow * 2

        # FIXME: where did it originate?
        bottom_padding = pen_width + ow

        pen.setWidth(pen_width)
        pen.setColor(QtCore.Qt.black)
        pen.setJoinStyle(QtCore.Qt.MiterJoin)

        # FIXME: use real color mapping here
        brush = QtGui.QBrush(QtGui.QColor(self._style))

        #painter.setFont(font)
        #painter.setPen(pen)
        #painter.setBrush(brush)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        path = QtGui.QPainterPath()
        path.addText(ow, self.height() - bottom_padding, font, self._text)

        # black text with black outline would be unreadable
        if self._style != 'black':
            painter.strokePath(path, pen)

        painter.fillPath(path, brush)

    def clean_close(self):
        if self.quited is False:
            self.quited = True

            with Danmaku._lock:
                # print(Danmaku.count)
                if self.vslots is not None:
                    for i in self.vslots:
                        if i >= len(self.vertical_slots):
                            break
                        Danmaku.vertical_slots[i] = 0

            self.exited.emit(str(id(self)))
            self.destroy()


class DanmakuTestApp(QtGui.QDialog):
    def __init__(self, parent=None):
        super(DanmakuTestApp, self).__init__(parent)
        self.setWindowTitle("Danmaku")
        self.lineedit = QtGui.QLineEdit("Text")
        self.style = QtGui.QLineEdit("blue")
        self.position = QtGui.QLineEdit("top")
        self.pushbutton = QtGui.QPushButton("Send")
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.lineedit)
        layout.addWidget(self.style)
        layout.addWidget(self.position)
        layout.addWidget(self.pushbutton)
        self.setLayout(layout)
        self.pushbutton.clicked.connect(self.new_danmaku)
        self.dms = {}

    def new_danmaku(self):
        text = self.lineedit.text()
        style = self.style.text()
        position = self.position.text()
        dm = Danmaku(text, style=style, position=position, parent=self)
        dm.exited.connect(self.delete_danmaku)
        self.dms[str(id(dm))] = dm
        dm.show()

    def delete_danmaku(self, _id):
        dm = self.dms.pop(_id)
        dm.close()


def dm_test():
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    app = QtGui.QApplication(sys.argv)
    danmakuTestApp = DanmakuTestApp()
    danmakuTestApp.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    dm_test()

# vim: ts=4 sw=4 sts=4 expandtab
