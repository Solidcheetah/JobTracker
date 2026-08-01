"""Long-running background processes.

These live in the application package rather than a separate project because they
import the same models, settings and services as the API. They are not, however,
part of the API *process*: each runs standalone via `python -m`, from the same
image, with a different command.
"""
