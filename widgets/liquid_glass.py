"""
MOON Liquid Glass
=================

PySide6 + local PyGlass integration.

Использует ScreenBackdrop для захвата реального рабочего
стола Windows за окном MOON.

Главные возможности:
- реальные обои / рабочий стол за окном
- refraction (искажение)
- Liquid Glass
- прозрачность
- светлый блик
- рамка поверх стекла
"""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QPoint,
    QRectF,
    Qt,
    QTimer,
)

from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPen,
)

from PySide6.QtWidgets import QWidget


# =========================================================
# LOCAL PYGLASS
# =========================================================

try:

    from pyglass_pyside import (
        GlassMaterial,
        GlassRenderer,
        ScreenBackdrop,
        paint_glass,
    )

    PYGLASS_AVAILABLE = True
    PYGLASS_ERROR = None

except Exception as error:

    PYGLASS_AVAILABLE = False
    PYGLASS_ERROR = error


# =========================================================
# LIQUID GLASS WIDGET
# =========================================================

class LiquidGlassWidget(QWidget):

    def __init__(
        self,
        parent: QWidget | None = None,
        radius: int = 30,
        opacity: int = 12,
        border_opacity: int = 110,
    ) -> None:

        super().__init__(parent)

        # -------------------------------------------------
        # SETTINGS
        # -------------------------------------------------

        self.radius = radius

        # Лёгкий светлый слой поверх стекла.
        self.opacity = opacity

        # Прозрачность рамки.
        self.border_opacity = border_opacity

        self._panel_opacity = 1.0
        self._matte_effect = 0.4
        self._glass_color = "default"
        self._light_theme = False


        # -------------------------------------------------
        # PYGLASS
        # -------------------------------------------------

        self._material = None

        self._renderer = None

        self._backdrop = None

        self._refracted = None

        self._initialized = False

        self._backdrop_started = False


        # -------------------------------------------------
        # QT
        # -------------------------------------------------

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        self.setAutoFillBackground(False)


    # =====================================================
    # THEME
    # =====================================================

    def set_light_theme(
        self,
        enabled: bool,
    ) -> None:

        self._light_theme = bool(enabled)

        self.update()


    # =====================================================
    # PANEL OPACITY
    # =====================================================

    def panelOpacity(self) -> float:

        return self._panel_opacity


    def setPanelOpacity(
        self,
        value: float,
    ) -> None:

        try:

            value = float(value)

        except (
            TypeError,
            ValueError,
        ):

            value = 1.0


        self._panel_opacity = max(
            0.0,
            min(
                1.0,
                value,
            ),
        )

        self.update()


    panelOpacity = Property(

        float,

        panelOpacity,

        setPanelOpacity,

    )


    # =====================================================
    # COMPATIBILITY
    # =====================================================
    def set_matte_effect(self, value: float) -> None:
        self._matte_effect = max(0.0, min(1.0, float(value)))

        if self._backdrop is None:
            return

        if self.width() <= 0 or self.height() <= 0:
            return

        try:
            self._material = GlassMaterial(
                thickness=0.40,
                frost=self._matte_effect,
                strength=65.0,
                bevel=32.0,
                chroma=0.08,
                reflect=0.18,
                f0=0.012,
            )

            self._renderer = GlassRenderer(
                self._material,
                float(self.width()),
                float(self.height()),
                float(self.radius),
            )

            self._create_refraction()
            self.update()

        except Exception as error:
            print("MOON matte effect error:", error)

    def set_glass_color(self, color: str) -> None:
        self._glass_color = color

        if color not in ("default", "green", "pink"):
            self._glass_color = "default"

        self.update()

    def set_panel_alpha(
        self,
        alpha: int,
    ) -> None:

        try:

            alpha = int(alpha)

        except (
            TypeError,
            ValueError,
        ):

            alpha = 12


        self.opacity = max(
            0,
            min(
                255,
                alpha,
            ),
        )

        self.update()


    # =====================================================
    # GET TOP LEVEL WINDOW
    # =====================================================

    def _get_window(self):

        window = self.window()

        if window is None:

            return None

        return window


    # =====================================================
    # INITIALIZE PYGLASS
    # =====================================================

    def _initialize_pyglass(self) -> None:

        if self._initialized:

            return


        if not PYGLASS_AVAILABLE:

            print(
                "PyGlass unavailable:",
                PYGLASS_ERROR,
            )

            return


        if self.width() <= 0:

            return


        if self.height() <= 0:

            return


        window = self._get_window()


        if window is None:

            return


        try:

            # =============================================
            # GLASS MATERIAL
            # =============================================

            self._material = GlassMaterial(

                # Толщина стекла.
                thickness=0.40,


                # Матирование.
                #
                # 0.0 = максимально прозрачное стекло.находится на верху смотри внимательно
                frost=self._matte_effect,


                # СИЛА ИСКАЖЕНИЯ.
                #
                # Можешь потом менять:
                #
                # 20 = слабое
                # 40 = среднее
                # 60 = сильное
                # 80 = очень сильное
                #
                strength=65.0,


                # Размер / мягкость края.
                bevel=32.0,


                # Цветовое преломление.
                chroma=0.08,


                # Отражение.
                reflect=0.18,


                # Блик стекла.
                f0=0.012,

            )


            # =============================================
            # SCREEN BACKDROP
            #
            # ВАЖНО:
            #
            # Передаём ВЕРХНЕЕ окно MOON.
            #
            # ScreenBackdrop предназначен для
            # захвата рабочего стола Windows.
            # =============================================

            self._backdrop = ScreenBackdrop(

                window,

                # Обновление.
                interval_ms=120,


                # Запас вокруг окна.
                capture_margin=180,

            )


            # =============================================
            # CONNECT SIGNAL
            # =============================================

            self._backdrop.changed.connect(

                self._on_backdrop_changed

            )


            # =============================================
            # RENDERER
            # =============================================

            self._renderer = GlassRenderer(

                self._material,

                float(
                    self.width()
                ),

                float(
                    self.height()
                ),

                float(
                    self.radius
                ),

            )


            self._initialized = True


            print(
                "MOON ScreenBackdrop initialized"
            )


        except Exception as error:

            print(
                "MOON PyGlass setup error:",
                error,
            )


            self._material = None

            self._renderer = None

            self._backdrop = None

            self._refracted = None

            self._initialized = False


    # =====================================================
    # START SCREEN BACKDROP
    # =====================================================

    def _start_backdrop(self) -> None:

        if not self._initialized:

            return


        if self._backdrop is None:

            return


        if self._backdrop_started:

            return


        try:

            # =============================================
            # CONFIGURE
            #
            # Создаёт механизм захвата рабочего стола.
            # =============================================

            live = self._backdrop.configure()


            print(
                "MOON ScreenBackdrop configured:",
                live,
            )


            # =============================================
            # START
            # =============================================

            self._backdrop.start()


            self._backdrop_started = True


            print(
                "MOON ScreenBackdrop started"
            )


        except Exception as error:

            print(
                "MOON ScreenBackdrop start error:",
                error,
            )

    def pause_backdrop(self) -> None:
        if self._backdrop is None:
            return

        try:
            self._backdrop.stop()
            self._backdrop_started = False
        except Exception as error:
            print("MOON ScreenBackdrop pause error:", error)

    def resume_backdrop(self) -> None:
        if self._backdrop is None:
            return

        try:
            if not self._backdrop_started:
                self._backdrop.start()
                self._backdrop_started = True
                self._create_refraction()
                self.update()
        except Exception as error:
            print("MOON ScreenBackdrop resume error:", error)


    # =====================================================
    # BACKDROP CHANGED
    # =====================================================

    def _on_backdrop_changed(self) -> None:

        self._create_refraction()

        self.update()


    # =====================================================
    # CREATE REFRACTION
    # =====================================================

    def _create_refraction(self) -> None:

        if self._backdrop is None:

            return


        if self._renderer is None:

            return


        try:

            background = (

                self._backdrop.array()

            )


            if background is None:

                self._refracted = None

                return


            # =============================================
            # IMPORTANT
            #
            # Позиция нашей панели
            # относительно начала захваченного
            # ScreenBackdrop.
            # =============================================

            panel_global = self.mapToGlobal(

                QPoint(
                    0,
                    0,
                )

            )


            backdrop_origin = (

                self._backdrop.global_origin()

            )


            origin = (

                panel_global
                -
                backdrop_origin

            )


            # =============================================
            # REFRACTION
            # =============================================

            self._refracted = (

                self._renderer.refract(

                    background,

                    origin,

                    self._backdrop.dpr(),

                )

            )


        except Exception as error:

            print(
                "MOON PyGlass refract error:",
                error,
            )


            self._refracted = None


    # =====================================================
    # RESIZE
    # =====================================================

    def resizeEvent(
        self,
        event,
    ) -> None:

        super().resizeEvent(event)


        # Renderer зависит от размера панели.

        self._renderer = None

        self._refracted = None


        if self._material is not None:

            try:

                self._renderer = GlassRenderer(

                    self._material,

                    float(
                        self.width()
                    ),

                    float(
                        self.height()
                    ),

                    float(
                        self.radius
                    ),

                )


            except Exception as error:

                print(
                    "MOON renderer resize error:",
                    error,
                )


        QTimer.singleShot(

            0,

            self._create_refraction,

        )


    # =====================================================
    # SHOW
    # =====================================================

    def showEvent(
        self,
        event,
    ) -> None:

        super().showEvent(event)


        # Небольшая задержка.
        #
        # В этот момент окно уже должно иметь
        # native handle.

        QTimer.singleShot(

            100,

            self._initialize_and_start,

        )


    # =====================================================
    # INITIALIZE + START
    # =====================================================

    def _initialize_and_start(self) -> None:

        self._initialize_pyglass()

        self._start_backdrop()


    # =====================================================
    # REFRESH GLASS
    # =====================================================

    def refresh_glass(self) -> None:

        if self._backdrop is None:

            return


        try:

            self._backdrop.refresh()


        except Exception as error:

            print(
                "PyGlass refresh error:",
                error,
            )


    # =====================================================
    # PAINT
    # =====================================================

    def paintEvent(
        self,
        event,
    ) -> None:

        painter = QPainter(self)


        painter.setRenderHint(

            QPainter.RenderHint.Antialiasing,

            True,

        )


        # -------------------------------------------------
        # RECT
        # -------------------------------------------------

        rect = QRectF(

            self.rect()

        )


        rect.adjust(

            1.0,
            1.0,
            -1.0,
            -1.0,

        )


        if rect.width() <= 0:

            return


        if rect.height() <= 0:

            return


        # -------------------------------------------------
        # PATH
        # -------------------------------------------------

        path = QPainterPath()


        path.addRoundedRect(

            rect,

            float(
                self.radius
            ),

            float(
                self.radius
            ),

        )


        # =================================================
        # PYGLASS
        # =================================================

        if (

            PYGLASS_AVAILABLE

            and self._refracted is not None

        ):

            try:

                # =========================================
                # CLIP
                # =========================================

                painter.save()


                painter.setClipPath(

                    path

                )


                painter.setOpacity(

                    self._panel_opacity

                )


                # =========================================
                # REAL LIQUID GLASS
                # =========================================

                paint_glass(

                    painter,

                    rect,

                    float(
                        self.radius
                    ),

                    self._refracted,


                    # 1.0 = полностью видимый эффект.
                    reveal=1.0,

                )


                painter.restore()
                
                painter.save()

                painter.setClipPath(path)

                if self._glass_color == "green":
                    tint = QColor(57, 228, 68, 28)
                elif self._glass_color == "pink":
                    tint = QColor(185, 0, 145, 28)
                else:
                    tint = None

                if tint is not None:
                    painter.fillPath(path, tint)

                painter.restore()


                # =========================================
                # LIGHT TRANSPARENT LAYER
                #
                # Очень слабый.
                #
                # Не должен превращать
                # стекло в белую панель.
                # =========================================

                painter.save()


                painter.setClipPath(

                    path

                )


                light_alpha = int(

                    self.opacity
                    *
                    self._panel_opacity

                )


                painter.fillPath(

                    path,

                    QColor(

                        255,
                        255,
                        255,
                        0,

                        light_alpha,

                    ),

                )


                painter.restore()


            except Exception as error:

                print(
                    "MOON PyGlass render error:",
                    error,
                )


        # =================================================
        # FALLBACK
        # =================================================

        else:

            painter.save()


            painter.setClipPath(

                path

            )


            alpha = int(

                self.opacity
                *
                self._panel_opacity

            )


            painter.fillPath(

                path,

                QColor(

                    255,
                    255,
                    255,

                    alpha,

                ),

            )


            painter.restore()


        # =================================================
        # TOP HIGHLIGHT
        #
        # Лёгкий блик сверху.
        # =================================================

        painter.save()


        highlight_path = QPainterPath()


        highlight_rect = QRectF(

            rect.x() + 2,

            rect.y() + 2,

            rect.width() - 4,

            max(
                1.0,
                rect.height() * 0.12,
            ),

        )


        highlight_path.addRoundedRect(

            highlight_rect,

            float(
                self.radius
            ),

            float(
                self.radius
            ),

        )


