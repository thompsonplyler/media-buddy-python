import replicate
output = replicate.run(
    "thompsonplyler/thompsonplyler_flux_v3_thmpsnplylr:e45e257ecbf18f9fb4484009c86b6a759e3529eaeae3d4fb90636adbb6e00b2e",
    input={
        "model": "dev",
        "go_fast": False,
        "lora_scale": 1,
        "megapixels": "1",
        "num_outputs": 1,
        "aspect_ratio": "1:1",
        "output_format": "webp",
        "guidance_scale": 3,
        "output_quality": 80,
        "prompt_strength": 0.8,
        "extra_lora_scale": 1,
        "num_inference_steps": 28
    }
)
print(output)

# keyword for this model is thmpsnplylr. 
# To include "thompson plyler" in the output, you need to use 
# 'thmpsnplylr, a white man in his mid-40s with messy brown hair"