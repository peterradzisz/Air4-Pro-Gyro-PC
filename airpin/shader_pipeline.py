"""Post-processing shader pipeline for AirPin."""
from OpenGL.GL import *
import ctypes
import os

_SHADER_DIR = os.path.dirname(__file__)


class ShaderPipeline:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self._fbo = None
        self._fbo_texture = None
        self._program = None
        self._quad_vbo = None
        self._uniforms = {}
        self.brightness = 1.0
        self.gamma = 1.0
        self.sharpness = 0.0
        self.vignette = 0.0
        self.chromatic = 0.0
        self.temperature = 6500.0
        self.enable_brightness = False
        self.enable_gamma = False
        self.enable_sharpness = False
        self.enable_vignette = False
        self.enable_chromatic = False
        self.enable_temperature = False
    def init(self):
        self._create_fbo()
        self._compile_shaders()
        self._create_quad()

    def resize(self, width, height):
        self.width = width
        self.height = height
        self._cleanup_fbo()
        self._create_fbo()

    def begin_capture(self):
        glBindFramebuffer(GL_FRAMEBUFFER, self._fbo)
        glViewport(0, 0, self.width, self.height)

    def end_capture_and_draw(self):
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glViewport(0, 0, self.width, self.height)
        glClear(GL_COLOR_BUFFER_BIT)
        any_on = (self.enable_brightness or self.enable_gamma or
                  self.enable_sharpness or self.enable_vignette or
                  self.enable_chromatic or self.enable_temperature)
        if not any_on:
            self._draw_fbo_simple()
            return
        glUseProgram(self._program)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self._fbo_texture)
        glUniform1i(self._uniforms['u_texture'], 0)
        glUniform1f(self._uniforms['u_brightness'], self.brightness)
        glUniform1f(self._uniforms['u_gamma'], self.gamma)
        glUniform1f(self._uniforms['u_sharpness'], self.sharpness)
        glUniform1f(self._uniforms['u_vignette'], self.vignette)
        glUniform1f(self._uniforms['u_chromatic'], self.chromatic)
        glUniform1f(self._uniforms['u_temperature'], self.temperature)
        glUniform1i(self._uniforms['u_enable_brightness'], GL_TRUE if self.enable_brightness else GL_FALSE)
        glUniform1i(self._uniforms['u_enable_gamma'], GL_TRUE if self.enable_gamma else GL_FALSE)
        glUniform1i(self._uniforms['u_enable_sharpness'], GL_TRUE if self.enable_sharpness else GL_FALSE)
        glUniform1i(self._uniforms['u_enable_vignette'], GL_TRUE if self.enable_vignette else GL_FALSE)
        glUniform1i(self._uniforms['u_enable_chromatic'], GL_TRUE if self.enable_chromatic else GL_FALSE)
        glUniform1i(self._uniforms['u_enable_temperature'], GL_TRUE if self.enable_temperature else GL_FALSE)
        glBindBuffer(GL_ARRAY_BUFFER, self._quad_vbo)
        pos_loc = glGetAttribLocation(self._program, 'position')
        tc_loc = glGetAttribLocation(self._program, 'texcoord')
        stride = 4 * ctypes.sizeof(ctypes.c_float)
        glEnableVertexAttribArray(pos_loc)
        glVertexAttribPointer(pos_loc, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(tc_loc)
        glVertexAttribPointer(tc_loc, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(2 * ctypes.sizeof(ctypes.c_float)))
        glDisable(GL_SCISSOR_TEST)
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        glDisableVertexAttribArray(pos_loc)
        glDisableVertexAttribArray(tc_loc)
        glUseProgram(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    def _draw_fbo_simple(self):
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self._fbo_texture)
        glColor4f(1, 1, 1, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(-1, -1)
        glTexCoord2f(1, 0); glVertex2f(1, -1)
        glTexCoord2f(1, 1); glVertex2f(1, 1)
        glTexCoord2f(0, 1); glVertex2f(-1, 1)
        glEnd()

    def _create_fbo(self):
        self._fbo_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self._fbo_texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, self.width, self.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        self._fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self._fbo)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self._fbo_texture, 0)
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if status != GL_FRAMEBUFFER_COMPLETE:
            print('WARNING: FBO incomplete, status=0x%x' % status)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def _cleanup_fbo(self):
        if self._fbo_texture is not None:
            try: glDeleteTextures([self._fbo_texture])
            except Exception: pass
            self._fbo_texture = None
        if self._fbo is not None:
            try: glDeleteFramebuffers(1, [self._fbo])
            except Exception: pass
            self._fbo = None

    def _compile_shaders(self):
        def _compile(shader_type, path):
            src = open(path, 'r').read()
            s = glCreateShader(shader_type)
            glShaderSource(s, src)
            glCompileShader(s)
            if not glGetShaderiv(s, GL_COMPILE_STATUS):
                print('Shader error (%s): %s' % (os.path.basename(path), glGetShaderInfoLog(s)))
            return s
        vs = _compile(GL_VERTEX_SHADER, os.path.join(_SHADER_DIR, 'postprocess.vert'))
        fs = _compile(GL_FRAGMENT_SHADER, os.path.join(_SHADER_DIR, 'postprocess.frag'))
        self._program = glCreateProgram()
        glAttachShader(self._program, vs)
        glAttachShader(self._program, fs)
        glLinkProgram(self._program)
        if not glGetProgramiv(self._program, GL_LINK_STATUS):
            print('Shader link error: %s' % glGetProgramInfoLog(self._program))
        glDeleteShader(vs)
        glDeleteShader(fs)
        for name in ['u_texture', 'u_brightness', 'u_gamma', 'u_sharpness',
                      'u_vignette', 'u_chromatic', 'u_temperature',
                      'u_enable_brightness', 'u_enable_gamma', 'u_enable_sharpness',
                      'u_enable_vignette', 'u_enable_chromatic', 'u_enable_temperature']:
            self._uniforms[name] = glGetUniformLocation(self._program, name)

    def _create_quad(self):
        verts = [-1,-1,0,0, 1,-1,1,0, -1,1,0,1, 1,1,1,1]
        arr = (ctypes.c_float * len(verts))(*verts)
        self._quad_vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self._quad_vbo)
        glBufferData(GL_ARRAY_BUFFER, ctypes.sizeof(arr), arr, GL_STATIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    def cleanup(self):
        self._cleanup_fbo()
        if self._program is not None:
            try: glDeleteProgram(self._program)
            except Exception: pass
            self._program = None
        if self._quad_vbo is not None:
            try: glDeleteBuffers(1, [self._quad_vbo])
            except Exception: pass
            self._quad_vbo = None

    @property
    def any_enabled(self):
        return (self.enable_brightness or self.enable_gamma or
                self.enable_sharpness or self.enable_vignette or
                self.enable_chromatic or self.enable_temperature)
