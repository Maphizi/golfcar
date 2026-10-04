"""GL-Engine: ein Vollbild-Dreieck, ein Fragment-Shader pro Szene, Audio als Uniforms.

Uniforms, die jede Szene bekommt:
  float iTime            Sekunden seit Start
  vec2  iResolution      Render-Auflösung in Pixeln
  float uRms uBass uMid uHigh   0..1, geglättet, auto-gain
  float uBeat            1.0 beim Beat, klingt ab
  float uSilent          1.0 wenn Stille (Visuals laufen dann nur über iTime weiter)
  sampler2D uAudioTex    512x2, Zeile y=0.25: Spektrum (64 log-Bins, 0..1), Zeile y=0.75: Waveform (0.5 = Nulllinie)
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import ctypes
import numpy as np

os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
import OpenGL
OpenGL.ERROR_CHECKING = False
OpenGL.CONTEXT_CHECKER = None
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402
from OpenGL import GL  # noqa: E402
from OpenGL.GL import shaders  # noqa: E402

log = logging.getLogger("viz.engine")
SHADER_DIR = Path(__file__).resolve().parent.parent / "shaders"
TEX_W = 512


class GLError(RuntimeError):
    pass


def create_window(settings: dict, viz_cfg: dict, title: str):
    disp = settings.get("display", {})
    eng = viz_cfg.get("engine", {})
    driver = disp.get("sdl_videodriver", "auto")
    if driver and driver != "auto":
        os.environ["SDL_VIDEODRIVER"] = driver
    pygame.init()
    size = (int(eng.get("width", 0) or disp.get("width", 0)), int(eng.get("height", 0) or disp.get("height", 0)))
    flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.FULLSCREEN
    if os.environ.get("KITT_VIZ_WINDOWED"):
        flags = pygame.OPENGL | pygame.DOUBLEBUF
        size = size if size[0] else (960, 540)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 1)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
    try:
        screen = pygame.display.set_mode(size, flags, vsync=1)
    except pygame.error as exc:
        log.warning("GL 3.1 Core nicht verfügbar (%s), versuche Standard-Kontext", exc)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, 0)
        screen = pygame.display.set_mode(size, flags)
    # PyOpenGL context-tracking patch: auf Pi5/Wayland gibt GetCurrentContext() 0 zurück.
    # contextdata.getContext patchen, damit GL-Calls ohne GLX-Context-Tracking laufen.
    from OpenGL import contextdata as _cd
    _orig_gc = _cd.getContext
    def _safe_gc(context=None):
        if context is not None:
            return context
        try:
            ctx = _orig_gc(context)
            if ctx:
                return ctx
        except Exception:
            pass
        return id(screen)  # Dummy-Context-ID
    _cd.getContext = _safe_gc
    pygame.display.set_caption(title)
    pygame.mouse.set_visible(False)
    log.info("SDL-Treiber %s, GL %s, GLSL %s, Renderer %s", pygame.display.get_driver(),
             GL.glGetString(GL.GL_VERSION).decode(), GL.glGetString(GL.GL_SHADING_LANGUAGE_VERSION).decode(),
             GL.glGetString(GL.GL_RENDERER).decode())
    return screen


class Scene:
    def __init__(self, name: str, scene_cfg: dict, hot_reload: bool, extra_uniforms: tuple[str, ...] = ()):
        self.name = name
        self.extra_uniforms = tuple(extra_uniforms)
        self.frag_path = SHADER_DIR / scene_cfg.get("shader", name) / "frag.glsl"
        self.vert_path = SHADER_DIR / "common" / "vert.glsl"
        self.render_scale = float(scene_cfg.get("render_scale", 1.0))
        self.hot_reload = hot_reload
        self.program = None
        self.uniforms: dict[str, int] = {}
        self._mtime = 0.0
        self._last_check = 0.0

    def load(self) -> None:
        vert = self.vert_path.read_text()
        frag = self.frag_path.read_text()
        try:
            prog = shaders.compileProgram(
                shaders.compileShader(vert, GL.GL_VERTEX_SHADER),
                shaders.compileShader(frag, GL.GL_FRAGMENT_SHADER),
            )
        except (shaders.ShaderCompilationError, RuntimeError) as exc:
            raise GLError(f"Shader {self.frag_path.name} ({self.name}): {str(exc)[:1500]}") from exc
        if self.program:
            GL.glDeleteProgram(self.program)
        self.program = prog
        self.uniforms = {n: GL.glGetUniformLocation(prog, n) for n in
                         ("iTime", "iResolution", "uRms", "uBass", "uMid", "uHigh", "uBeat", "uSilent", "uAudioTex")
                         + self.extra_uniforms}
        self._mtime = self.frag_path.stat().st_mtime
        log.info("Shader geladen: %s (render_scale %.2f)", self.frag_path, self.render_scale)

    def maybe_reload(self, now: float) -> None:
        if not self.hot_reload or now - self._last_check < 1.0:
            return
        self._last_check = now
        try:
            m = self.frag_path.stat().st_mtime
        except OSError:
            return
        if m != self._mtime:
            try:
                self.load()
            except GLError as exc:
                log.error("Hot-Reload fehlgeschlagen, alter Shader bleibt: %s", exc)
                self._mtime = m


class Renderer:
    def __init__(self, scene: Scene, width: int, height: int):
        self.scene = scene
        self.w, self.h = width, height
        self.rw = max(64, int(width * scene.render_scale))
        self.rh = max(64, int(height * scene.render_scale))
        # Vollbild-Dreieck
        self.vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(self.vao)
        vbo = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo)
        tri = np.array([-1, -1, 3, -1, -1, 3], dtype=np.float32)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, tri.nbytes, tri, GL.GL_STATIC_DRAW)
        GL.glEnableVertexAttribArray(0)
        GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, GL.GL_FALSE, 0, ctypes.c_void_p(0))
        # Audio-Textur 512x2 R8
        self.tex = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        self.texdata = np.zeros((2, TEX_W), dtype=np.uint8)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_R8, TEX_W, 2, 0, GL.GL_RED, GL.GL_UNSIGNED_BYTE, self.texdata)
        # Offscreen-Framebuffer bei render_scale < 1
        self.fbo = None
        if self.rw != self.w or self.rh != self.h:
            self.fbo = GL.glGenFramebuffers(1)
            ctex = GL.glGenTextures(1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, ctex)
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, self.rw, self.rh, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.fbo)
            GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, ctex, 0)
            if GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) != GL.GL_FRAMEBUFFER_COMPLETE:
                log.warning("FBO unvollständig, rendere in voller Auflösung")
                self.fbo = None
                self.rw, self.rh = self.w, self.h
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        log.info("Render %dx%d auf Display %dx%d", self.rw, self.rh, self.w, self.h)

    def upload_audio(self, spectrum: np.ndarray, wave: np.ndarray) -> None:
        # Spektrum (64 Bins) auf 512 Pixel strecken, Waveform (512) direkt
        xs = np.linspace(0, len(spectrum) - 1, TEX_W)
        spec = np.interp(xs, np.arange(len(spectrum)), spectrum)
        self.texdata[0] = np.clip(spec * 255.0, 0, 255).astype(np.uint8)
        w = wave if len(wave) == TEX_W else np.interp(np.linspace(0, len(wave) - 1, TEX_W), np.arange(len(wave)), wave)
        self.texdata[1] = np.clip((w * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glTexSubImage2D(GL.GL_TEXTURE_2D, 0, 0, 0, TEX_W, 2, GL.GL_RED, GL.GL_UNSIGNED_BYTE, self.texdata)

    def draw(self, t: float, f, extra: dict | None = None) -> None:
        sc = self.scene
        u = sc.uniforms
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.fbo or 0)
        GL.glViewport(0, 0, self.rw, self.rh)
        GL.glUseProgram(sc.program)
        GL.glUniform1f(u["iTime"], t)
        GL.glUniform2f(u["iResolution"], float(self.rw), float(self.rh))
        GL.glUniform1f(u["uRms"], f.rms)
        GL.glUniform1f(u["uBass"], f.bass)
        GL.glUniform1f(u["uMid"], f.mid)
        GL.glUniform1f(u["uHigh"], f.high)
        GL.glUniform1f(u["uBeat"], f.beat)
        GL.glUniform1f(u["uSilent"], 1.0 if f.silent else 0.0)
        for name, val in (extra or {}).items():
            loc = u.get(name, -1)
            if loc >= 0:
                GL.glUniform1f(loc, float(val))
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glUniform1i(u["uAudioTex"], 0)
        GL.glBindVertexArray(self.vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        if self.fbo:
            GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, self.fbo)
            GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, 0)
            GL.glBlitFramebuffer(0, 0, self.rw, self.rh, 0, 0, self.w, self.h, GL.GL_COLOR_BUFFER_BIT, GL.GL_LINEAR)
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)

    def screenshot(self, path: str) -> None:
        GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, 0)
        GL.glReadBuffer(GL.GL_BACK)
        data = GL.glReadPixels(0, 0, self.w, self.h, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
        surf = pygame.image.fromstring(data, (self.w, self.h), "RGB", True)
        pygame.image.save(surf, path)
        log.info("Screenshot: %s", path)


TEXT_VERT = """#version 140
in vec2 aPos;
out vec2 vUv;
uniform vec4 uRect;   // x, y, w, h in 0..1 (unten links)
void main() {
    vec2 p = aPos * 0.5 + 0.5;           // 0..1 im Dreieck
    vUv = vec2(p.x, 1.0 - p.y);
    vec2 q = uRect.xy + p * uRect.zw;
    gl_Position = vec4(q * 2.0 - 1.0, 0.0, 1.0);
}
"""
TEXT_FRAG = """#version 140
in vec2 vUv;
out vec4 fragColor;
uniform sampler2D uTex;
uniform float uAlpha;
void main() {
    vec4 c = texture(uTex, vUv);
    if (vUv.x > 1.0 || vUv.y > 1.0) discard;
    fragColor = vec4(c.rgb, c.a * uAlpha);
}
"""


class TextOverlay:
    """Textzeilen über pygame.font rendern und als Textur über die Szene blenden."""

    def __init__(self, font_px: int):
        pygame.font.init()
        path = pygame.font.match_font("dejavusansmono") or pygame.font.match_font("liberationmono")
        self.font = pygame.font.Font(path, font_px) if path else pygame.font.SysFont(None, font_px)
        self.prog = shaders.compileProgram(shaders.compileShader(TEXT_VERT, GL.GL_VERTEX_SHADER),
                                           shaders.compileShader(TEXT_FRAG, GL.GL_FRAGMENT_SHADER))
        self.u_rect = GL.glGetUniformLocation(self.prog, "uRect")
        self.u_alpha = GL.glGetUniformLocation(self.prog, "uAlpha")
        self.u_tex = GL.glGetUniformLocation(self.prog, "uTex")
        self.vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(self.vao)
        vbo = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo)
        quad = np.array([-1, -1, 1, -1, -1, 1, 1, -1, 1, 1, -1, 1], dtype=np.float32)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, quad.nbytes, quad, GL.GL_STATIC_DRAW)
        GL.glEnableVertexAttribArray(0)
        GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, GL.GL_FALSE, 0, None)
        self.tex = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        self._cache_key = None
        self._size = (1, 1)

    def set_text(self, text: str, color=(230, 230, 230)) -> None:
        key = (text, color)
        if key == self._cache_key:
            return
        self._cache_key = key
        surf = self.font.render(text or " ", True, color).convert_alpha()
        w, h = surf.get_size()
        data = pygame.image.tostring(surf, "RGBA", False)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, w, h, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, data)
        self._size = (w, h)

    def draw(self, screen_w: int, screen_h: int, x_px: float, y_px: float, alpha: float = 1.0, center: bool = False) -> None:
        """x_px/y_px: Position in Pixeln vom linken unteren Rand."""
        w, h = self._size
        if center:
            x_px -= w / 2
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glUseProgram(self.prog)
        GL.glUniform4f(self.u_rect, x_px / screen_w, y_px / screen_h, w / screen_w, h / screen_h)
        GL.glUniform1f(self.u_alpha, alpha)
        GL.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glUniform1i(self.u_tex, 1)
        GL.glBindVertexArray(self.vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)
        GL.glDisable(GL.GL_BLEND)
