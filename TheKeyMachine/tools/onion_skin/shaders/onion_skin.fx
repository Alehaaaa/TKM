#include "Common10.fxh"

Texture2D gSourceTex < string UIWidget = "None"; > = NULL;
SamplerState gSourceSamp;
Texture2D gSourceTex2 < string UIWidget = "None"; > = NULL;
SamplerState gSourceSamp2;
Texture2D gStencilTex < string UIWidget = "None"; > = NULL;
SamplerState gStencilSamp;
float gBlendSrc = 0.5f;
float4 gUVTransform : RelativeViewportDimensions;
float4 gPixelTransform : ViewportPixelSize;
float4 gTint = {1.0, 1.0, 1.0, 1.0};
int gOutlineWidth = 3;
int gType = 1;
int gDrawBehind = 1;

float4 PS_Blend(VS_TO_PS_ScreenQuad input) : SV_TARGET
{
    float2 uv = input.UV * gUVTransform.zw + gUVTransform.xy;
    float4 scene = gSourceTex.Sample(gSourceSamp, uv);
    float4 onion = gSourceTex2.Sample(gSourceSamp2, uv);
    float4 stencil = gStencilTex.Sample(gStencilSamp, uv);
    float visible = lerp(1.0f, 1.0f - stencil.a, (float)gDrawBehind);
    float4 layer = onion * gTint;
    float alpha = onion.a;
    if (gType == 1) {
        layer = float4(gTint.rgb * 0.75f, onion.a);
    } else if (gType == 2) {
        float2 px = float2((float)gOutlineWidth, (float)gOutlineWidth) / gPixelTransform.xy;
        float around = 0.0f;
        around += gSourceTex2.Sample(gSourceSamp2, uv + float2(px.x, 0.0f)).a;
        around += gSourceTex2.Sample(gSourceSamp2, uv - float2(px.x, 0.0f)).a;
        around += gSourceTex2.Sample(gSourceSamp2, uv + float2(0.0f, px.y)).a;
        around += gSourceTex2.Sample(gSourceSamp2, uv - float2(0.0f, px.y)).a;
        alpha = (1.0f - onion.a) * clamp(around, 0.0f, 1.0f);
        layer = float4(gTint.rgb, alpha);
    }
    return lerp(scene, layer, gBlendSrc * alpha * visible);
}

technique10 Main
{
    pass p0
    {
        SetVertexShader(CompileShader(vs_4_0, VS_ScreenQuad()));
        SetGeometryShader(NULL);
        SetPixelShader(CompileShader(ps_4_0, PS_Blend()));
    }
}
