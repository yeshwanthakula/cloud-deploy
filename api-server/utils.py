import string
import random
from uuid import uuid4
def generate_uuid_slug(length=8):
    # Generate a random UUID and take first `length` characters
    return str(uuid4())[:length]