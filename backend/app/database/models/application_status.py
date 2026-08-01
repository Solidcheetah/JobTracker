from enum import Enum


class ApplicationStatus(str, Enum):
    wishlist = "wishlist"
    applied = "applied"
    screen = "screen"
    onsite = "onsite"
    offer = "offer"
    rejected = "rejected"
    withdrawn = "withdrawn"
