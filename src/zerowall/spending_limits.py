"""Application-wide spending authority; independent of account billing settings."""

# User instruction, October 21, 2026: use at most $24 of the reported $25 balance.
# The separate $1 trial does not enlarge this aggregate allowance.
TOKEN_FACTORY_CAP_USD = 24
