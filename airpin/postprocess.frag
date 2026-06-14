#version 130
uniform sampler2D u_texture;
uniform float u_brightness;
uniform float u_gamma;
uniform float u_sharpness;
uniform float u_vignette;
uniform float u_chromatic;
uniform float u_temperature;
uniform bool u_enable_brightness;
uniform bool u_enable_gamma;
uniform bool u_enable_sharpness;
uniform bool u_enable_vignette;
uniform bool u_enable_chromatic;
uniform bool u_enable_temperature;
uniform float u_hdr;
uniform bool u_enable_hdr;
in vec2 TexCoord;
out vec4 FragColor;
vec3 kelvinToRGB(float k) {
    k = clamp(k, 1000.0, 40000.0) / 100.0;
    float r, g, b;
    if (k <= 66.0) { r = 255.0; }
    else { r = clamp(329.698727446 * pow(k - 60.0, -0.1332047592), 0.0, 255.0); }
    if (k <= 66.0) { g = clamp(99.4708025861 * log(k) - 161.1195681661, 0.0, 255.0); }
    else { g = clamp(288.1221695283 * pow(k - 60.0, -0.0755148492), 0.0, 255.0); }
    if (k >= 66.0) { b = 255.0; }
    else if (k <= 19.0) { b = 0.0; }
    else { b = clamp(138.5177312231 * log(k - 10.0) - 305.0447927307, 0.0, 255.0); }
    return vec3(r, g, b) / 255.0;
}
vec3 acesTonemap(vec3 x) {
    // ACES Filmic - approximates cinematic tone curve
    float a = 2.51;
    float b = 0.03;
    float c = 2.43;
    float d = 0.59;
    float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

void main() {
    vec2 uv = TexCoord;
    vec2 texelSize = 1.0 / vec2(textureSize(u_texture, 0));
    vec3 color;
    if (u_enable_chromatic && u_chromatic > 0.0) {
        vec2 center = uv - 0.5;
        float dist = length(center);
        vec2 dir = dist > 0.001 ? normalize(center) : vec2(0.0);
        float abOffset = u_chromatic * dist * dist;
        color.r = texture(u_texture, uv + dir * abOffset).r;
        color.g = texture(u_texture, uv).g;
        color.b = texture(u_texture, uv - dir * abOffset).b;
    } else { color = texture(u_texture, uv).rgb; }
    if (u_enable_sharpness && u_sharpness > 0.0) {
        vec3 blur = (
            texture(u_texture, uv + vec2(-1, 0) * texelSize).rgb +
            texture(u_texture, uv + vec2( 1, 0) * texelSize).rgb +
            texture(u_texture, uv + vec2( 0,-1) * texelSize).rgb +
            texture(u_texture, uv + vec2( 0, 1) * texelSize).rgb
        ) * 0.25;
        color = clamp(color + (color - blur) * u_sharpness, 0.0, 1.0);
    }
    if (u_enable_vignette && u_vignette > 0.0) {
        vec2 center = uv - 0.5;
        float edgeDist = length(center) / 0.7;
        color *= 1.0 + smoothstep(0.3, 1.0, edgeDist) * u_vignette;
    }
    if (u_enable_brightness && u_brightness != 1.0) { color *= u_brightness; }
    if (u_enable_gamma && u_gamma != 1.0) {
        color = pow(max(color, vec3(0.0)), vec3(1.0 / u_gamma));
    }
    if (u_enable_temperature && abs(u_temperature - 6500.0) > 10.0) {
        vec3 tempTint = kelvinToRGB(u_temperature);
        vec3 neutral = kelvinToRGB(6500.0);
        color *= tempTint / max(neutral, vec3(0.001));
    }
    if (u_enable_hdr && u_hdr != 1.0) {
        // Boost exposure beyond 1.0, then tonemap back to display range
        // This lifts shadows and compresses highlights like Windows HDR
        color = acesTonemap(color * u_hdr);
    }
    FragColor = vec4(clamp(color, 0.0, 1.0), 1.0);
}
