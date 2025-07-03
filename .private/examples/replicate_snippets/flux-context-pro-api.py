import replicate

input = {
    "prompt": "Make this a 90s cartoon",
    "input_image": "https://replicate.delivery/pbxt/N55l5TWGh8mSlNzW8usReoaNhGbFwvLeZR3TX1NL4pd2Wtfv/replicate-prediction-f2d25rg6gnrma0cq257vdw2n4c.png",
    "output_format": "jpg"
}

output = replicate.run(
    "black-forest-labs/flux-kontext-pro",
    input=input
)
with open("output.jpg", "wb") as file:
    file.write(output.read())
#=> output.jpg written to disk