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

import logging
import sys

from PySide6.QtCore import (
    Property,
    QPoint,
    QObject,
    QRunnable,
    QRectF,
    QThreadPool,
    Signal,
    Qt,
    QTimer,
)

from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from PySide6.QtWidgets import QWidget



LOGGER = logging.getLogger("moon.liquid_glass")


# =========================================================
# LOCAL PYGLASS
# =========================================================

try:

    from pyglass_pyside import (
        GlassMaterial,
        GlassRenderer,
        GlassStyle,
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

class _RefractionSignals(QObject):
    finished = Signal(int, int, object, str)


class _RefractionTask(QRunnable):
    def __init__(self, renderer, backdrop, origin, dpr, renderer_revision,
                 backdrop_revision, fast, signals) -> None:
        super().__init__()
        self.renderer = renderer
        self.backdrop = backdrop
        self.origin = origin
        self.dpr = dpr
        self.fast = fast
        self.renderer_revision = renderer_revision
        self.backdrop_revision = backdrop_revision
        self.signals = signals

    def run(self) -> None:
        try:
            image = self.renderer.refract_image(
                self.backdrop, self.origin, self.dpr, fast=self.fast
            )
            self.signals.finished.emit(
                self.renderer_revision, self.backdrop_revision, image, ""
            )
        except Exception as error:
            self.signals.finished.emit(
                self.renderer_revision, self.backdrop_revision, None, str(error)
            )

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
        self._matte_effect = 0.2
        self._glass_thickness = 0.5
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
        self._refraction_pool = QThreadPool(self)
        self._refraction_pool.setMaxThreadCount(1)
        self._refraction_signals = _RefractionSignals(self)
        self._refraction_signals.finished.connect(self._on_refraction_finished)
        self._renderer_revision = 0
        self._backdrop_revision = 0
        self._refraction_running = False
        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        # Coalesce captures while keeping the glass responsive; pixel rendering
        # happens in a worker so scrolling and input stay on the UI thread.
        self._settle_timer.setInterval(33)
        self._settle_timer.timeout.connect(self._settle_refraction)


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
        try:
            self._material = self._make_material()
            if self._renderer is not None:
                self._replace_renderer()
                self._request_refraction(renderer_changed=True)
            self.update()

        except Exception as error:
            LOGGER.exception("Matte effect update failed")

    def set_glass_thickness(self, value: float) -> None:
        self._glass_thickness = max(0.35, min(0.65, float(value)))
        self._material = self._make_material()
        if self._renderer is not None:
            self._replace_renderer()
            self._request_refraction(renderer_changed=True)
        self.update()

    def _make_material(self) -> GlassMaterial:
        return GlassMaterial(
            thickness=self._glass_thickness,
            frost=self._matte_effect,
            strength=24.0,
            bevel=34.0,
            chroma=0.02,
            reflect=0.0,
            f0=0.045,
            disp_glow=32.0,
            disp_sat=0.28,
            disp_width=2.0,
        )

    def _replace_renderer(self) -> None:
        self._renderer = GlassRenderer(
            self._material,
            float(self.width()),
            float(self.height()),
            float(self.radius),
        )

    def set_glass_color(self, color: str) -> None:
        legacy_colors = {"green": "#39e444", "pink": "#b90091"}
        if color == "default":
            self._glass_color = "default"
        else:
            candidate = QColor(legacy_colors.get(color, color))
            self._glass_color = candidate.name() if candidate.isValid() else "default"

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
                40,
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

            LOGGER.error("PyGlass unavailable: %s", PYGLASS_ERROR)

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
                thickness=self._glass_thickness,


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
                strength=24.0,


                # Размер / мягкость края.
                bevel=34.0,


                # Цветовое преломление.
                chroma=0.02,


                # Отражение.
                reflect=0.0,


                # Блик стекла.
                f0=0.045,
                disp_glow=32.0,
                disp_sat=0.28,
                disp_width=2.0,

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
                # QScreen.grabWindow is synchronous on Windows. Keep the
                # fallback capture at 4 FPS so it doesn't monopolize the UI
                # thread while the user scrolls or moves the launchpad.
                # macOS spawns a screencapture process for each frame, so it
                # uses a still slower cadence.
                interval_ms=900 if sys.platform == "darwin" else 250 if sys.platform == "win32" else 120,


                # Запас вокруг окна.
                capture_margin=0,

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


            LOGGER.info("Screen backdrop initialized")


        except Exception as error:

            LOGGER.exception("PyGlass setup failed")


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


            LOGGER.info("Screen backdrop configured: live=%s", live)


            # =============================================
            # START
            # =============================================

            self._backdrop.start()


            self._backdrop_started = True


            LOGGER.info("Screen backdrop started")


        except Exception as error:

            LOGGER.exception("Screen backdrop start failed")

    def pause_backdrop(self) -> None:
        self._settle_timer.stop()
        if self._backdrop is None:
            return

        try:
            self._backdrop.stop()
            self._backdrop_started = False
        except Exception as error:
            LOGGER.exception("Screen backdrop pause failed")

    def resume_backdrop(self) -> None:
        if self._backdrop is None:
            return

        try:
            if not self._backdrop_started:
                self._backdrop.start()
                self._backdrop_started = True
                self.update()
        except Exception as error:
            LOGGER.exception("Screen backdrop resume failed")


    # =====================================================
    # BACKDROP CHANGED
    # =====================================================

    def _on_backdrop_changed(self) -> None:
        self._backdrop_revision += 1
        if not self._settle_timer.isActive():
            self._settle_timer.start()

    def _settle_refraction(self) -> None:
        self._create_refraction(fast=self._matte_effect <= 0.001)


    # =====================================================
    # CREATE REFRACTION
    # =====================================================

    def _create_refraction(self, fast: bool = False) -> None:
        if self._backdrop is None or self._renderer is None:
            return
        if self._refraction_running:
            return

        background = self._backdrop.array()
        if background is None:
            return

        try:
            origin = self.mapToGlobal(QPoint(0, 0)) - self._backdrop.global_origin()
            dpr = self._backdrop.dpr()
            self._refraction_running = True
            self._refraction_pool.start(
                _RefractionTask(
                    self._renderer,
                    background,
                    origin,
                    dpr,
                    self._renderer_revision,
                    self._backdrop_revision,
                    fast or self._matte_effect <= 0.001,
                    self._refraction_signals,
                )
            )
        except Exception:
            self._refraction_running = False
            LOGGER.exception("PyGlass refraction scheduling failed")

    def _request_refraction(self, *, renderer_changed: bool = False) -> None:
        if renderer_changed:
            self._renderer_revision += 1
        if not self._settle_timer.isActive():
            self._settle_timer.start()

    def _on_refraction_finished(
        self, renderer_revision: int, backdrop_revision: int, image, error: str
    ) -> None:
        self._refraction_running = False
        if error:
            LOGGER.error("PyGlass refraction failed: %s", error)
        elif renderer_revision == self._renderer_revision and image is not None:
            # QPixmap is GUI-thread-only; convert the detached QImage here.
            self._refracted = QPixmap.fromImage(image)
            self._refracted.setDevicePixelRatio(image.devicePixelRatio())
            self.update()

        frame_is_stale = backdrop_revision != self._backdrop_revision
        renderer_is_stale = renderer_revision != self._renderer_revision
        if (frame_is_stale or renderer_is_stale) and not self._settle_timer.isActive():
            self._settle_timer.start()


    # =====================================================
    # RESIZE
    # =====================================================

    def resizeEvent(
        self,
        event,
    ) -> None:

        super().resizeEvent(event)


        # Keep any in-flight task on its old renderer; the new one is built by
        # the worker when it renders the latest size.
        self._renderer = None
        self._refracted = None
        if self._material is not None:
            try:
                self._replace_renderer()
                if self._backdrop is not None:
                    self._request_refraction(renderer_changed=True)
            except Exception:
                LOGGER.exception("Glass renderer resize failed")


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

            LOGGER.exception("Screen backdrop refresh failed")


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


                painter.setOpacity(

                    self._panel_opacity

                )


                # =========================================
                # REAL LIQUID GLASS
                # =========================================

                tint = QColor(self._glass_color) if self._glass_color != "default" else None
                if tint is not None:
                    tint.setAlpha(28)

                # The slider is in percentage points (0..40). Convert that
                # value to alpha directly so it has the same meaning for any
                # captured backdrop.
                white_fill_alpha = round(self.opacity * 255 / 100)

                paint_glass(

                    painter,

                    rect,

                    float(
                        self.radius
                    ),

                    self._refracted,


                     #1.0 = полностью видимый эффект.
                    style=GlassStyle(
                        shadow_layers=0,
                        shadow_step=0.0,
                        shadow_alpha=0,
                        shadow_top=0.0,
                        shadow_bottom=0.0,
                        tint_top=white_fill_alpha,
                        tint_bottom=round(white_fill_alpha * 0.6),
                        sheen_alpha=max(5, min(16, int(self.border_opacity * 0.12))),
                        sheen_extent=0.42,
                        rim_top=int(self.border_opacity * 0.52),
                        rim_mid=int(self.border_opacity * 0.16),
                        rim_bottom=int(self.border_opacity * 0.34),
                        rim_width=1.0,
                    ),
                    reveal=1.0,
                    color_tint=tint,

                )


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
                    min(24, self.opacity * 0.18)
                    * self._panel_opacity
                )


                painter.fillPath(

                    path,

                    QColor(

                        255,
                        255,
                        255,
                        light_alpha,

                    ),

                )


                painter.restore()


            except Exception as error:

                LOGGER.exception("PyGlass painting failed")


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
                    18,
                    21,
                    32,
                    min(88, int(alpha * 0.55)),
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


