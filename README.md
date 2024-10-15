Built this out of intense hatred for the fact that I couldn't share the videos I have with friends without being subjected to Discord's file size limit, Streamable's time limit, or YT's ToS regardless of the video's visibility,
while many other options just didn't seem to have embeds either. This applications main focus is on providing a means to upload and automatically re-encode media, while having a means to share said media.
Embeds work using twitter cards (since my initial focus was getting it to work with Discord and I had some issues with OpenGraph initially) but will hopefully move over to purely OpenGraph once I've ironed out some kinks

Built in a virtual env. The requirements file has the packages needed. I included the files I currently use for the server (sans the actual media ofc), like the migration tables and whatnot in hopes that adopting it into a new environment for myself will be easier.
after building the venv and activating, application can be run with the run_waitress.py function. Discord specific embed are a WIP
