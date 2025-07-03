import replicate

input = {
    "prompt": "black forest gateau cake spelling out the words \"FLUX DEV\", tasty, food photography, dynamic shot",
    "guidance": 3.5
}

output = replicate.run(
    "black-forest-labs/flux-dev",
    input=input
)
for index, item in enumerate(output):
    with open(f"output_{index}.webp", "wb") as file:
        file.write(item.read())
#=> output_0.webp written to disk